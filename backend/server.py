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


def is_image_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def find_direct_images(target: Path) -> list[Path]:
    return [p for p in target.rglob("*") if is_image_file(p)]


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

    all_images = sorted(find_direct_images(target), key=lambda p: str(p))

    def relative_from_target(path: Path) -> Path:
        try:
            return path.relative_to(target)
        except ValueError:
            return Path(path.name)

    return {
        "source_path": str(source_path),
        "source_kind": source_kind,
        "working_folder": str(target),
        "source_label": source_label,
        "output_root": str(output_root),
        "counts": {
            "total_images": len(all_images),
        },
        "images": [
            {
                "source": str(path),
                "relative": str(relative_from_target(path)),
                "source_ext": path.suffix.lower(),
            }
            for path in all_images
        ],
    }


# ---------------------------------------------------------------------------
# Preset resolution
# ---------------------------------------------------------------------------

PRESETS = {
    "lossless": {
        "lossless": True,
        "quality": 100,
        "max_width": None,
        "max_height": None,
    },
    "balanced": {
        "lossless": False,
        "quality": 82,
        "max_width": 2000,
        "max_height": None,
    },
    "small_file": {
        "lossless": False,
        "quality": 68,
        "max_width": 1600,
        "max_height": None,
    },
}


def resolve_options(body: dict) -> dict:
    """Merge preset defaults with any explicit overrides from the request body."""
    preset_key = (body.get("preset") or "balanced").lower().replace(" ", "_").replace("-", "_")
    base = dict(PRESETS.get(preset_key, PRESETS["balanced"]))

    # Explicit overrides win over preset defaults
    for key in ("quality", "lossless", "max_width", "max_height", "target_kb", "strip_metadata", "overwrite"):
        if body.get(key) is not None:
            base[key] = body[key]

    # Fill keys that might not exist in preset
    base.setdefault("target_kb", None)
    base.setdefault("strip_metadata", False)
    base.setdefault("overwrite", False)

    return base


# ---------------------------------------------------------------------------
# Output path helpers
# ---------------------------------------------------------------------------

MODE_SUFFIX = {
    "keep_format": "_compressed",
    "to_webp_lossless": "_lossless",
    "to_webp_lossy": "_webp",
    "convert_compress": "_optimized",
}


def resolve_output_ext(mode: str, source_ext: str, output_format: str | None) -> str:
    if mode == "keep_format":
        # Stay with source extension (normalise jpeg → jpg for output)
        return ".jpg" if source_ext in {".jpeg", ".jpg"} else source_ext
    if mode in {"to_webp_lossless", "to_webp_lossy"}:
        return ".webp"
    # convert_compress: user-chosen format, default webp
    fmt = (output_format or "webp").lower().strip(".")
    return {"jpg": ".jpg", "jpeg": ".jpg", "png": ".png", "webp": ".webp"}.get(fmt, ".webp")


def resolve_suffix(mode: str) -> str:
    return MODE_SUFFIX.get(mode, "_optimized")


def make_output_path(output_root: Path, relative: str, source_ext: str, mode: str, output_format: str | None) -> Path:
    rel = Path(relative)
    ext = resolve_output_ext(mode, source_ext, output_format)
    suffix = resolve_suffix(mode)
    return output_root / rel.parent / f"{rel.stem}{suffix}{ext}"


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------

def _open_and_prepare(source: Path, lossless: bool, strip_metadata: bool) -> Image.Image:
    img = Image.open(source)
    if lossless or img.mode in {"RGBA", "LA", "P"}:
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")
    return img


def _apply_resize(img: Image.Image, max_width: int | None, max_height: int | None, scale: float = 1.0) -> Image.Image:
    w, h = img.size
    target_w = int((max_width or w) * scale)
    target_h = int((max_height or h) * scale)
    # Only downscale, never upscale
    ratio = min(target_w / w, target_h / h, 1.0)
    if ratio < 1.0:
        new_w, new_h = int(w * ratio), int(h * ratio)
        return img.resize((new_w, new_h), Image.LANCZOS)
    return img


def _encode_to_bytes(img: Image.Image, ext: str, quality: int, lossless: bool) -> bytes:
    import io
    buf = io.BytesIO()
    if ext == ".webp":
        if lossless and img.mode == "RGBA":
            img.save(buf, format="WEBP", lossless=True, method=6)
        elif lossless:
            img.save(buf, format="WEBP", lossless=True, method=6)
        else:
            img.save(buf, format="WEBP", quality=quality, method=6)
    elif ext == ".jpg":
        img = img.convert("RGB") if img.mode != "RGB" else img
        img.save(buf, format="JPEG", quality=quality, optimize=True)
    elif ext == ".png":
        img.save(buf, format="PNG", optimize=True)
    else:
        img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def encode_image(source: Path, output: Path, options: dict) -> dict:
    """
    Core encode function. Handles:
    - resize
    - quality
    - lossless
    - target_kb iterative loop
    Returns a stats dict with bytes_in, bytes_out, warnings.
    """
    ext = output.suffix.lower()
    quality = int(options.get("quality") or 82)
    lossless = bool(options.get("lossless", False))
    max_width = options.get("max_width")
    max_height = options.get("max_height")
    target_kb = options.get("target_kb")
    strip_metadata = bool(options.get("strip_metadata", False))

    bytes_in = source.stat().st_size
    warnings = []

    # Warn if source is already WebP and mode is keep_format
    if source.suffix.lower() == ".webp" and ext == ".webp":
        warnings.append("Source is already WebP. Re-encoded with current settings.")

    img = _open_and_prepare(source, lossless, strip_metadata)

    if target_kb:
        # Iterative size targeting
        target_bytes = target_kb * 1024
        MIN_QUALITY = 35
        MIN_SCALE = 0.40
        MAX_ITERATIONS = 10
        scale = 1.0
        result_bytes = None

        for attempt in range(MAX_ITERATIONS):
            resized = _apply_resize(img, max_width, max_height, scale)
            data = _encode_to_bytes(resized, ext, quality, lossless)
            if len(data) <= target_bytes:
                result_bytes = data
                break
            # Reduce quality first, then scale
            if quality > MIN_QUALITY:
                quality = max(MIN_QUALITY, quality - 8)
            elif scale > MIN_SCALE:
                scale = max(MIN_SCALE, scale - 0.12)
            else:
                # Exhausted options — use best effort
                result_bytes = data
                warnings.append(f"Could not reach {target_kb} KB. Best result: {len(data) // 1024} KB.")
                break

        if result_bytes is None:
            result_bytes = data

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(result_bytes)
        bytes_out = len(result_bytes)
    else:
        resized = _apply_resize(img, max_width, max_height)
        data = _encode_to_bytes(resized, ext, quality, lossless)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        bytes_out = len(data)

    reduction = round((1 - bytes_out / bytes_in) * 100, 1) if bytes_in else 0

    return {
        "source": str(source),
        "output": str(output),
        "source_ext": source.suffix.lower(),
        "output_ext": ext,
        "bytes_in": bytes_in,
        "bytes_out": bytes_out,
        "reduction_pct": reduction,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # silence access log
        pass

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
                return self._send_json({
                    "ok": True,
                    **discover_images(source_path, output_base_path, output_folder_name),
                })

            if route == "/api/convert":
                images = body.get("images", [])
                if not images:
                    raise ValueError("No images provided for conversion.")

                mode = (body.get("mode") or "to_webp_lossy").strip()
                output_format = body.get("outputFormat") or None
                output_root = Path(body.get("outputRoot", "")).expanduser().resolve()
                options = resolve_options(body)

                # Lossless mode: override to lossless webp
                if mode == "to_webp_lossless":
                    options["lossless"] = True

                results = []
                for item in images:
                    source = Path(item["source"])
                    relative = item["relative"]
                    source_ext = item.get("source_ext", source.suffix.lower())
                    output_path = make_output_path(output_root, relative, source_ext, mode, output_format)

                    try:
                        stats = encode_image(source, output_path, options)
                        stats["status"] = "ok"
                    except Exception as exc:
                        stats = {
                            "source": str(source),
                            "output": str(output_path),
                            "source_ext": source_ext,
                            "output_ext": output_path.suffix.lower(),
                            "bytes_in": source.stat().st_size if source.exists() else 0,
                            "bytes_out": 0,
                            "reduction_pct": 0,
                            "warnings": [],
                            "status": "error",
                            "error": str(exc),
                        }
                    results.append(stats)

                return self._send_json({"ok": True, "results": results, "count": len(results)})

            self.send_error(404, "Not found")
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=400)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"Compression Script running on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
