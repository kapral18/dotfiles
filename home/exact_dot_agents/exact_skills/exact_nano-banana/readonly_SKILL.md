---
name: nano-banana
description: Generate raster images from text prompts with local ,nano-banana.
---

# Nano Banana (image generation)

Wraps the `,nano-banana` CLI (`~/bin/,nano-banana`): one text prompt in, one raster image file out.
Backed by the Gemini `gemini-3.1-flash-image` model via the Generative Language API.

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

Flags: `-o/--output` (path), `-a/--aspect-ratio`, `-s/--size`, `-m/--model` (default `gemini-3.1-flash-image`), `-h/--help`.
The prompt is a single positional argument — quote it.

## Controlling output

These map to the API's `generationConfig.imageConfig`. When neither is set, the model picks defaults (≈1408×768).

- **`-a/--aspect-ratio`** — `1:1`, `3:2`, `2:3`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9`.
- **`-s/--size`** — `512`, `1K`, `2K`, `4K`. **Case-sensitive**: lowercase `1k` is rejected (HTTP 400). `2K` ≈ 4MP, `4K` ≈ 16MP.
- **Style is NOT a flag.** The API has no style parameter — put style/medium/lighting/mood in the prompt text ("watercolor",
  "flat vector icon", "cinematic, golden hour").

Invalid `-a`/`-s` values return a clean `ERROR: API call failed (400)` and write no file.

## Behavior (verified)

- **Output location:** with no `-o`, the file is written to the **current working directory** (a prompt-derived slug, max 50 chars).
  It is NOT written to `/tmp`.
  `cd` first, or pass `-o`, to control placement.
- **Stdout = the path.** The CLI prints the final file path on success and nothing else, so it composes: `img=$(,nano-banana "a red fox")`.
- **Format is decided by the model, not the extension.** The API currently returns `image/jpeg`.
  With no `-o`, the slug gets the true extension (`.jpg`).
  With `-o foo.png`, JPEG bytes are written into `foo.png` (the name is honored verbatim; the bytes are whatever the API returned).
  To guarantee a real PNG, convert afterward (e.g.
  `magick foo.jpg foo.png`).
- **API key:** read from `NANOBANANA_API_KEY`, falling back to `GEMINI_API_KEY`, then `GOOGLE_API_KEY` —
  all exported via `pass` in `config.fish`.
  In a non-login/non-fish shell, export it first: `export NANOBANANA_API_KEY=$(pass google/gemini/api/token)`.

## Workflow

1. Decide where the image should land; `cd` there or set `-o`.
2. Run `,nano-banana "<detailed prompt>"`.
   Richer prompts (subject, style, background, composition) yield better results.
   Add `-a`/`-s` for a specific aspect ratio or resolution.
3. Read the printed path; report it (and open/preview if the user wants).
4. Need a different raster format? Convert the output with ImageMagick (`magick`).

## Limitations

- **Raster only — no SVG/vector.** `gemini-3.1-flash-image` emits bitmap data; there is no API option for SVG.
  For vectors: generate a PNG then trace it (`vtracer`/`potrace`), or ask a text model to emit SVG markup directly (a different tool,
  not this one).
- Text-to-image only: no input image, no editing/inpainting.
- One image per invocation.

## Troubleshooting `ERROR: no image in response`

This fires only when the API returns HTTP 200
but no candidate part carries image bytes (HTTP/network errors hit different `ERROR:` branches).
The message includes the API's own reason when present, e.g.
`(blockReason=PROHIBITED_CONTENT)`, `(finishReason=IMAGE_SAFETY)`, or a truncated text reply —
that is the signal for whether it was a content/safety block vs. a text-only reply.

**Text-only replies are mitigated automatically.** The CLI prefixes every request to the API with `Generate an image of:`
because the image model otherwise treats bare/ambiguous prompts (e.g.
`elastic`) as questions and answers in text (`finishReason=STOP`, no image).
This prefix only affects the API request — the output filename slug is still derived from your raw prompt.
The model is still nondeterministic, so a `finishReason=STOP` text reply remains possible; re-running usually succeeds.

For the full picture, set `NANOBANANA_DEBUG=1` to dump the raw JSON response to **stderr** (stdout still prints only the file path,
so composability is preserved):

```bash
NANOBANANA_DEBUG=1 ,nano-banana "PROMPT" 2>/tmp/nb-debug.json
```

Then inspect `promptFeedback.blockReason`, `candidates[].finishReason`, and `candidates[].safetyRatings`.
Common 200-no-image causes: safety/policy block (`SAFETY`, `IMAGE_SAFETY`, `PROHIBITED_CONTENT`, `RECITATION`),
a text-only reply (the model declined in words), or empty `candidates` with a `promptFeedback.blockReason`.

## Notes

- No external dependencies (stdlib Python over the REST API).
- On error (missing key, HTTP failure, no image in response) the CLI exits non-zero with an `ERROR:` message and writes no file.
