# Anas Compression Script

Local browser UI for scanning a folder, finding images directly or through CSV references, and converting them into sibling lossless WebP files.

## Output naming

Directly discovered image files are written next to the original as:

- `originalname_lossless.webp`

CSV-referenced image files are written into the CSV file's subfolder using the same output name:

- `originalname_lossless.webp`

## Run

```bat
start.bat
```

Then open:

- `http://127.0.0.1:8876`

## Notes

- Scans folders recursively.
- Converts direct image files found in the folder tree.
- Reads CSV files in the same tree and converts image paths referenced in CSV cells.
- Groups CSV-driven outputs into the CSV subfolder.
- Uses Pillow lossless WebP output.
