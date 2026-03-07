import csv
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"
HOST = "127.0.0.1"
PORT = 8876
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".gif", ".webp"}
CSV_EXTENSIONS = {".csv"}


def is_image_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def find_direct_images(target: Path) -> list[Path]:
    return [p for p in target.rglob("*") if is_image_file(p)]


def candidate_paths_from_cell(cell: str, csv_path: Path, root: Path) -> list[Path]:
    value = (cell or "").strip().strip('"').strip("'")
    if not value:
        return []

    candidates = []
    raw = Path(value)
    if raw.suffix.lower() in IMAGE_EXTENSIONS:
        candidates.append(raw)
    else:
        return []

    resolved = []
    for candidate in candidates:
        if candidate.is_absolute():
            resolved.append(candidate)
        else:
            resolved.append((csv_path.parent / candidate).resolve())
            resolved.append((root / candidate).resolve())
            resolved.append((root / candidate.name).resolve())
    return resolved


def prepare_source(source_path: str) -> tuple[Path, str, str]:
    source = Path(source_path).expanduser().resolve()
    if not source.exists():
        raise ValueError("Source path does not exist.")
    if source.is_dir():
        return source, "directory", source.name
    if source.is_file() and source.suffix.lower() == ".zip":
        extract_root = source.parent / f"{source.stem}__extracted"
        extract_root.mkdir(parents=True, exist_ok=True)
        with ZipFile(source, "r") as archive:
            archive.extractall(extract_root)
        return extract_root, "zip", source.stem
    raise ValueError("Source path must be a folder or a .zip file.")


def build_output_root(output_base_path: str, output_folder_name: str) -> Path:
    output_base = Path(output_base_path).expanduser().resolve()
    if not output_base.exists() or not output_base.is_dir():
        raise ValueError("Output base path does not exist or is not a directory.")
    folder_name = output_folder_name.strip()
    if not folder_name:
        raise ValueError("Output folder name is required.")
    return output_base / folder_name


def discover_images(source_path: str, output_base_path: str, output_folder_name: str) -> dict:
    target, source_kind, source_label = prepare_source(source_path)
    output_root = build_output_root(output_base_path, output_folder_name)

    direct_images = {p.resolve() for p in find_direct_images(target)}
    csv_image_refs = []
    for csv_file in target.rglob("*.csv"):
        try:
            readers = []
            try:
                readers.append(csv_file.open("r", encoding="utf-8-sig", newline=""))
            except UnicodeDecodeError:
                readers.append(csv_file.open("r", encoding="latin-1", newline=""))
            for handle in readers:
                with handle:
                    reader = csv.reader(handle)
                    for row in reader:
                        for cell in row:
                            for candidate in candidate_paths_from_cell(cell, csv_file, target):
                                if candidate.exists() and is_image_file(candidate):
                                    csv_image_refs.append((candidate.resolve(), csv_file.resolve()))
        except Exception:
            continue

    csv_images = {path for path, _ in csv_image_refs}
    all_images = sorted(direct_images | csv_images)
    csv_group_map: dict[Path, list[Path]] = {}
    for image_path, csv_path in csv_image_refs:
        csv_group_map.setdefault(image_path, []).append(csv_path)

    def relative_from_target(path: Path) -> Path:
        try:
            return path.relative_to(target)
        except ValueError:
            return Path(path.name)

    def mapped_output(path: Path) -> Path:
        if path in csv_group_map:
            csv_parent = min(csv_group_map[path], key=lambda p: len(p.relative_to(target).parts)).parent
            relative_parent = csv_parent.relative_to(target)
            return output_root / relative_parent / f"{path.stem}_lossless.webp"
        relative = relative_from_target(path)
        return output_root / relative.parent / f"{path.stem}_lossless.webp"

    return {
        "source_path": str(source_path),
        "source_kind": source_kind,
        "working_folder": str(target),
        "source_label": source_label,
        "output_root": str(output_root),
        "counts": {
            "direct_images": len(direct_images),
            "csv_referenced_images": len(csv_images),
            "total_unique_images": len(all_images),
        },
        "images": [
            {
                "source": str(path),
                "relative": str(relative_from_target(path)),
                "output": str(mapped_output(path)),
                "csv_groups": [str(p.parent) for p in csv_group_map.get(path, [])],
            }
            for path in all_images
        ],
    }


def convert_to_lossless_webp(source_path: str, output_path: str | None = None) -> dict:
    source = Path(source_path).expanduser().resolve()
    if not source.exists() or not is_image_file(source):
        raise ValueError(f"Unsupported or missing image: {source}")

    output = (
        Path(output_path).expanduser().resolve()
        if output_path
        else source.with_name(f"{source.stem}_lossless.webp")
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as img:
        normalized = img.convert("RGBA") if img.mode in {"RGBA", "LA", "P"} else img.convert("RGB")
        normalized.save(output, format="WEBP", lossless=True, method=6)

    return {
        "source": str(source),
        "output": str(output),
        "bytes": output.stat().st_size,
    }


class AppHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, file_path: Path) -> None:
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "Not found")
            return
        content = file_path.read_bytes()
        mime_type, _ = mimetypes.guess_type(str(file_path))
        self.send_response(200)
        self.send_header("Content-Type", mime_type or "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        if route == "/":
            return self._send_file(FRONTEND_DIR / "index.html")
        if route.startswith("/frontend/"):
            relative = route.removeprefix("/frontend/")
            return self._send_file(FRONTEND_DIR / relative)
        self.send_error(404, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        try:
            body = self._read_json()
            if route == "/api/scan":
                source_path = body.get("sourcePath", "")
                output_base_path = body.get("outputBasePath", "")
                output_folder_name = body.get("outputFolderName", "")
                return self._send_json({"ok": True, **discover_images(source_path, output_base_path, output_folder_name)})
            if route == "/api/convert":
                items = body.get("images", [])
                if not items:
                    raise ValueError("No images were provided for conversion.")
                converted = [
                    convert_to_lossless_webp(
                        item["source"] if isinstance(item, dict) else item,
                        item.get("output") if isinstance(item, dict) else None,
                    )
                    for item in items
                ]
                return self._send_json({"ok": True, "converted": converted, "count": len(converted)})
            self.send_error(404, "Not found")
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=400)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"Compression Script running on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
