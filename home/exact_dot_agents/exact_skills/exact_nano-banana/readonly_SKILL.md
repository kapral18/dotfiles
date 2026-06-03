---
name: nano-banana
description: Generate raster images from a text prompt with the local `,nano-banana` CLI (Gemini "Nano Banana" image model). Use when the user asks to generate, create, or produce an image / picture / icon / illustration from a text description.
---

# Nano Banana (image generation)

Wraps the `,nano-banana` CLI (`~/bin/,nano-banana`): one text prompt in, one raster image file out. Backed by the Gemini `gemini-3.1-flash-image-preview` model via the Generative Language API.

Use when:

- the user asks to generate / create / make an image, picture, icon, sticker, or illustration from a text description.

Do not use:

- editing an existing image, or image-to-image: the CLI is text-to-image only (no input-image flag).
- SVG / vector output: the model returns raster bitmaps only (see Limitations).

## Command

```bash
,nano-banana "PROMPT"                  # writes <prompt-slug>.<ext> in the CURRENT directory
,nano-banana "PROMPT" -o path/out.png  # write to an explicit path
,nano-banana "PROMPT" -a 16:9 -s 2K    # control aspect ratio + resolution
,nano-banana "PROMPT" -m MODEL         # override the model id
```

Flags: `-o/--output` (path), `-a/--aspect-ratio`, `-s/--size`, `-m/--model` (default `gemini-3.1-flash-image-preview`), `-h/--help`. The prompt is a single positional argument — quote it.

## Controlling output

These map to the API's `generationConfig.imageConfig`. When neither is set, the model picks defaults (≈1408×768).

- **`-a/--aspect-ratio`** — `1:1`, `3:2`, `2:3`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9`.
- **`-s/--size`** — `512`, `1K`, `2K`, `4K`. **Case-sensitive**: lowercase `1k` is rejected (HTTP 400). `2K` ≈ 4MP, `4K` ≈ 16MP.
- **Style is NOT a flag.** The API has no style parameter — put style/medium/lighting/mood in the prompt text ("watercolor", "flat vector icon", "cinematic, golden hour").

Invalid `-a`/`-s` values return a clean `ERROR: API call failed (400)` and write no file.

## Behavior (verified)

- **Output location:** with no `-o`, the file is written to the **current working directory** (a prompt-derived slug, max 50 chars). It is NOT written to `/tmp`. `cd` first, or pass `-o`, to control placement.
- **Stdout = the path.** The CLI prints the final file path on success and nothing else, so it composes: `img=$(,nano-banana "a red fox")`.
- **Format is decided by the model, not the extension.** The API currently returns `image/jpeg`. With no `-o`, the slug gets the true extension (`.jpg`). With `-o foo.png`, JPEG bytes are written into `foo.png` (the name is honored verbatim; the bytes are whatever the API returned). To guarantee a real PNG, convert afterward (e.g. `magick foo.jpg foo.png`).
- **API key:** read from `NANOBANANA_API_KEY`, falling back to `GEMINI_API_KEY`, then `GOOGLE_API_KEY` — all exported via `pass` in `config.fish`. In a non-login/non-fish shell, export it first: `export NANOBANANA_API_KEY=$(pass google/gemini/api/token)`.

## Workflow

1. Decide where the image should land; `cd` there or set `-o`.
2. Run `,nano-banana "<detailed prompt>"`. Richer prompts (subject, style, background, composition) yield better results. Add `-a`/`-s` for a specific aspect ratio or resolution.
3. Read the printed path; report it (and open/preview if the user wants).
4. Need a different raster format? Convert the output with ImageMagick (`magick`).

## Limitations

- **Raster only — no SVG/vector.** `gemini-3.1-flash-image-preview` emits bitmap data; there is no API option for SVG. For vectors: generate a PNG then trace it (`vtracer`/`potrace`), or ask a text model to emit SVG markup directly (a different tool, not this one).
- Text-to-image only: no input image, no editing/inpainting.
- One image per invocation.

## Notes

- No external dependencies (stdlib Python over the REST API).
- On error (missing key, HTTP failure, no image in response) the CLI exits non-zero with an `ERROR:` message and writes no file.
