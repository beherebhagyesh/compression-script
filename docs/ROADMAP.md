# Roadmap

## Goal

Turn the current single-purpose local converter into a real multi-mode conversion engine first, then package it as a Tauri desktop app.

## Product Direction

The app should support common user intents, not codec jargon.

Primary user intents:

- make these files smaller
- convert these to WebP
- keep the same format but compress
- get these under a max size
- make these web-friendly

That means the product should be built around:

- conversion modes
- presets
- advanced controls only when needed

## Phase 1: Conversion Engine Refactor

Refactor the current backend from one fixed function into an option-driven pipeline.

Current:

- one path
- lossless WebP output only

Target:

- one conversion request schema
- one processing pipeline
- multiple output strategies

Core backend model:

- `source_path`
- `output_base_path`
- `output_folder_name`
- `mode`
- `preset`
- `output_format`
- `lossless`
- `quality`
- `max_width`
- `max_height`
- `target_kb`
- `strip_metadata`
- `overwrite`
- `keep_structure`

Processing pipeline stages:

1. Discover input files.
2. Resolve CSV-linked files.
3. Normalize image.
4. Optional resize.
5. Optional metadata stripping.
6. Encode according to mode and preset.
7. If target size mode, iterate until threshold or fail-safe stop.
8. Write output.
9. Report stats:
   - original bytes
   - output bytes
   - percent reduction
   - output path
   - warnings

## Phase 2: Modes

Implement these three first because they cover most value.

### 1. Keep format, compress

Behavior:

- JPG -> JPG
- PNG -> PNG
- WebP -> WebP

Use cases:

- users want smaller files without changing type

Technical notes:

- JPG: reduce quality progressively
- PNG: optimize, maybe palette reduction later
- WebP: re-encode with quality or lossless options

### 2. Convert to WebP

Behavior:

- any supported input -> WebP

Options:

- lossless
- lossy
- quality

Use cases:

- web publishing
- standardization
- strong compression gains

### 3. Convert and compress

Behavior:

- input -> chosen target format
- with optional resizing and quality compression

Likely outputs first:

- WebP
- JPG

Use cases:

- reduce size aggressively
- normalize mixed inputs

## Phase 3: Presets

Use presets as the main interface.

Recommended first set:

- `Lossless`
- `Balanced`
- `Small file`
- `Under 200 KB`
- `Under 50 KB`

Preset behavior should auto-fill advanced values.

Example mapping:

### Lossless

- `lossless=true`
- no target KB
- no resize unless user sets it

### Balanced

- `quality=82`
- `lossless=false`
- optional max width around `2000px`

### Small file

- `quality=68`
- optional max width around `1600px`

### Under 200 KB

- `target_kb=200`

### Under 50 KB

- `target_kb=50`

## Phase 4: Advanced Controls

Expose only after the core modes work.

Advanced settings:

- output format:
  - keep original
  - WebP
  - JPG
  - PNG
- compression type:
  - lossless
  - lossy
- quality:
  - 1 to 100
- resize:
  - max width
  - max height
- target size:
  - max KB
- metadata:
  - keep
  - strip
- overwrite:
  - yes or no
- filename suffix:
  - `_lossless`
  - `_compressed`
  - `_webp`
  - custom

## Phase 5: File Format Policy

Input support first:

- JPG and JPEG
- PNG
- WebP
- BMP
- TIFF
- GIF

Output support first:

- JPG
- PNG
- WebP

Recommended rules:

### Keep format, compress

- JPG, PNG, WebP only for v1

### Convert to WebP

- all supported inputs

### Convert and compress

- WebP or JPG output first

Avoid AVIF in first iteration because packaging and support complexity are not worth it yet.

## Phase 6: Target Size Logic

This needs explicit design because it is expensive and approximate.

For `target_kb` mode:

1. Load image.
2. Optional downscale if dimensions are huge.
3. Start at a quality baseline.
4. Encode.
5. Check bytes.
6. If above target:
   - reduce quality stepwise
   - if still too large, reduce dimensions
   - retry
7. Stop when:
   - under target, or
   - min quality reached, or
   - min dimensions reached, or
   - max attempts reached

Suggested fail-safe bounds:

- min quality: `35`
- min scale: `40%`
- max iterations: `8 to 12`

Output should report:

- success under target
- or closest possible result

This matters because exact `50 KB` may be impossible without unacceptable quality loss.

## Phase 7: Frontend UX

Keep it simple.

Main fields:

- source path
- output base path
- output folder name

New controls:

- mode
- preset

Advanced drawer:

- output format
- lossless toggle
- quality slider
- max width
- max height
- target KB
- strip metadata

Results table should add:

- original format
- output format
- original size
- output size
- reduction percent
- status
- warnings

## Phase 8: Output Naming

Need consistent naming rules per mode.

Recommended default suffixes:

- keep format compress -> `_compressed`
- WebP conversion lossless -> `_lossless`
- WebP conversion lossy -> `_webp`
- target-size mode -> `_target`
- convert and compress -> `_optimized`

Later:

- allow custom suffix

## Phase 9: Backend Refactor Tasks

Concrete tasks:

1. Replace `convert_to_lossless_webp()` with generalized `convert_image(options)`.
2. Add request schema for conversion options.
3. Add preset resolution function:
   - `resolve_preset(mode, preset, overrides)`
4. Add encoder helpers:
   - `encode_jpg`
   - `encode_png`
   - `encode_webp`
5. Add resize helper.
6. Add target-size iterative loop.
7. Add stats calculator.
8. Return structured per-file results.

## Phase 10: Tauri Readiness

Do not start Tauri until Phase 1 to Phase 4 are stable.

When ready for Tauri:

- frontend can remain mostly the same conceptually
- Python backend should ideally be replaced or embedded carefully

Better long-term architecture:

- Tauri UI
- Rust or bundled local worker for conversion

If keeping Python temporarily:

- Tauri launches local Python service

But that adds packaging complexity.

Best long-term:

- port conversion logic to Rust or an equivalent local binary strategy

## Recommended MVP Scope Before Tauri

Do only this first:

1. Modes:
   - keep format compress
   - convert to WebP
   - convert and compress
2. Presets:
   - Lossless
   - Balanced
   - Small file
3. Advanced:
   - target max KB
   - quality
   - max width
4. Outputs:
   - JPG
   - PNG
   - WebP

This is the smallest useful product slice.

## Priority Order

1. General conversion pipeline
2. Mode selector
3. Presets
4. Keep-format compression
5. WebP lossy and lossless
6. Convert-and-compress path
7. Target KB loop
8. UI result metrics
9. Output naming rules
10. Tauri packaging

## Risks

- PNG compression expectations can be unrealistic without color reduction or format change
- exact size targeting may disappoint unless clearly labeled approximate
- GIF and TIFF support can introduce edge cases
- Tauri packaging gets harder if Python stays as a dependency

## Recommendation

With low credits and need for momentum, do not overbuild.

Lock the next iteration to:

- 3 modes
- 3 presets
- 1 advanced target-size control
- JPG, PNG, WebP outputs only

That gives the highest user value with controlled complexity.

## Next Documentation

This roadmap should later become:

- `docs/SPEC.md`
- `docs/TAURI_PLAN.md`
- implementation tasks from top priority downward
