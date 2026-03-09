# Compression Script

A local browser-based image compression and conversion tool. Run it from the terminal, open it in your browser, and process entire folders of images without uploading anything anywhere.

This is the **web prototype**. The packaged desktop app is [Squish](https://github.com/beherebhagyesh/squish).

---

## What it does

- Scan a source folder or zip file for images
- Choose a conversion mode and preset
- Convert images to JPG, PNG, or WebP
- See per-file results with original size, output size, and reduction percentage

## Modes

| Mode | Behavior |
|---|---|
| Keep Format & Compress | JPG stays JPG, PNG stays PNG — just smaller |
| Convert to WebP | Any format → WebP for web publishing |
| Convert & Compress | Change format and reduce size aggressively |

## Presets

| Preset | Quality | Max Width |
|---|---|---|
| Lossless | 100, lossless | No limit |
| Balanced | 82 | 2000px |
| Small File | 68 | 1600px |

Advanced controls: quality slider, max width/height, target KB, strip metadata.

---

## Requirements

- Python 3.10+
- Pillow

## Setup

```bash
git clone https://github.com/beherebhagyesh/compression-script
cd compression-script
start.bat
```

`start.bat` creates a virtual environment, installs Pillow, and starts the server at `http://127.0.0.1:8876`. Open that URL in your browser.

Or run manually:

```bash
pip install -r requirements.txt
python backend/server.py
```

---

## Supported formats

**Input:** JPG, PNG, WebP, BMP, TIFF, GIF

**Output:** JPG, PNG, WebP

---

## Project structure

```
compression-script/
├── backend/
│   └── server.py        # Python HTTP server and conversion engine
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── docs/
│   ├── ROADMAP.md
│   ├── SPEC.md
│   └── TAURI_PLAN.md
├── requirements.txt
└── start.bat
```

---

## Relationship to Squish

This repo is the development prototype where the conversion logic and UI were built and stabilised. The pipeline was then ported to Rust and packaged as [Squish](https://github.com/beherebhagyesh/squish) — a standalone Windows desktop app that requires no Python, no terminal, and no setup.

Use this repo to run from source, contribute, or work on the conversion pipeline.
