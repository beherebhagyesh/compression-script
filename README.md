# Anas Compression Script

Local browser UI for scanning a folder or zip file, finding images directly or through CSV references, and converting them into lossless WebP files inside one chosen output folder.

## Output naming

The app now asks for:

- source path
- output base path
- output folder name

All converted files are written under:

- `output base path/output folder name`

Inside that folder:

- direct image files preserve relative subfolder structure
- CSV-referenced image files are grouped by the CSV file's relative subfolder
- output filenames remain `originalname_lossless.webp`

## Run

```bat
start.bat
```

Then open:

- `http://127.0.0.1:8876`

## Notes

- Accepts a source folder or a source zip file.
- Scans source folders recursively.
- Converts direct image files found in the source tree.
- Reads CSV files in the same tree and converts image paths referenced in CSV cells.
- Writes all results into one new user-chosen output folder.
- Uses Pillow lossless WebP output.
