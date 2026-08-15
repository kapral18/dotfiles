---
name: k-nano-banana
description: "Use when the user names Nano Banana, ,nano-banana, Gemini/Google image, or gemini-*-image. Not for unnamed image requests."
tool_version: ",nano-banana 1.2.0"
---

# Nano Banana (cloud generate and edit)

Wraps the `,nano-banana` CLI (`~/bin/,nano-banana` → `~/lib/,nano-banana/main.py`).
One prompt in, one raster file out, via Gemini Nano Banana 2 (`gemini-3.1-flash-image`).
Every prompt and `-i`/`--url` input is uploaded to Google. That is the point of this tool.

This is one named image lane, not the default for raster work.
Load it only when this turn names Nano Banana, `,nano-banana`, Gemini image, Google image gen/edit, or a `gemini-*-image` model.

Do not use:

- unnamed image, icon, sticker, illustration, or edit requests: do not load this skill.
- SVG / vector output: the model returns raster bitmaps only.
- photos that must not leave the machine: this CLI is cloud-only; stop and use the on-device editor instead.

## First actions

1. Confirm this turn named Nano Banana, `,nano-banana`, Gemini image, Google image gen/edit, or a `gemini-*-image` model.
   If it did not, stop without calling the CLI.
2. Classify the request: generate, edit, compose, inpaint, style, or video-to-image.
3. Pick flags from the table below. Quote the prompt. Set `-o` or `cd` first.
4. Done when the CLI printed a path and that file exists.

## Command

```bash
,nano-banana "PROMPT"                                      # generate
,nano-banana "PROMPT" -o path/out.jpg
,nano-banana "PROMPT" -a 16:9 -s 2K
,nano-banana "make the sky sunset" -i photo.png            # edit
,nano-banana "change only the blue sofa to brown leather" -i room.png   # semantic inpaint
,nano-banana "put the logo on the shirt" -i person.png -i logo.png
,nano-banana "poster of this video" --url 'https://www.youtube.com/watch?v=VIDEO'
,nano-banana "PROMPT" -m gemini-3-pro-image                 # Nano Banana Pro
```

Flags: `-o/--output`, `-i/--input` (repeatable local image, max 14), `--url` (one YouTube URL, flash-only), `-a/--aspect-ratio`, `-s/--size`, `-m/--model` (default `gemini-3.1-flash-image`), `--version`, `-h/--help`.

## Request classes

There is no extra flag per class. The prompt plus `-i`/`--url` is the whole interface.

| Class            | How                                                                                      |
| ---------------- | ---------------------------------------------------------------------------------------- |
| Generate         | prompt only. CLI prefixes `Generate an image of:` for the API.                           |
| Edit             | `-i` the photo plus an instruction ("make the sky sunset").                              |
| Semantic inpaint | `-i` plus "change only X to Y; keep the rest unchanged". No mask file.                   |
| Compose / try-on | repeat `-i` (subject, garment, logo, …) and name each image in the prompt.               |
| Style transfer   | `-i` plus the target medium ("watercolor", "Starry Night").                              |
| Video-to-image   | `--url` YouTube on the default Flash model. Pro (`-m gemini-3-pro-image`) rejects video. |
| Iterate          | pass the previous output as `-i` and describe the delta.                                 |

## Controlling output

These map to `generationConfig.imageConfig`. When neither is set, the model picks defaults.

- **`-a/--aspect-ratio`** — `1:1`, `1:4`, `1:8`, `2:3`, `3:2`, `3:4`, `4:1`, `4:3`, `4:5`, `5:4`, `8:1`, `9:16`, `16:9`, `21:9`.
- **`-s/--size`** — `512`, `1K`, `2K`, `4K`. **Case-sensitive**. `512` is Flash-only. `2K` ≈ 4MP, `4K` ≈ 16MP.
- **Style is not a flag.** Put medium/lighting/mood in the prompt.

Invalid `-a`/`-s` returns `ERROR: API call failed (400)` and writes no file.

## Behavior (verified)

- **Output location:** no `-o` → current directory, prompt slug, max 50 chars. Not `/tmp`.
- **Stdout = the path.** Nothing else, so `img=$(,nano-banana "a red fox")`. Shrink notes go to stderr.
- **Format is the model's.** API currently returns `image/jpeg`. `-o foo.png` still writes JPEG bytes into that name.
  Convert with `magick` for a real PNG.
- **Inline limit is 7MB per image** (Gemini inline/console cap). Larger locals are auto-shrunk with `sips` to JPEG.
  GIF is rejected (not an accepted MIME).
- **API key:** `NANOBANANA_API_KEY`, then `GEMINI_API_KEY`, then `GOOGLE_API_KEY` (fish/`pass`).
  Non-fish: `export NANOBANANA_API_KEY=$(pass google/gemini/api/token)`.
- **Models:** default Nano Banana 2 (`gemini-3.1-flash-image`). Pro: `-m gemini-3-pro-image`.

## Limitations

- Raster only. For vectors: generate then trace (`vtracer`/`potrace`), or emit SVG from a text model.
- One output image per invocation. No local video on `-i`. One YouTube `--url`. No Files API.
- Cloud: every prompt and input leaves the machine.

## Troubleshooting `ERROR: no image in response`

HTTP 200 with no image bytes. The message includes `blockReason` / `finishReason` when present.

Generate (no media) prefixes `Generate an image of:` so bare prompts are not answered as text.
The prefix is omitted when `-i`/`--url` is present and never changes the filename slug.

```bash
NANOBANANA_DEBUG=1 ,nano-banana "PROMPT" 2>/tmp/nb-debug.json
```

Inspect `promptFeedback.blockReason`, `candidates[].finishReason`, `candidates[].safetyRatings`.
Common 200-no-image: `SAFETY`, `IMAGE_SAFETY`, `PROHIBITED_CONTENT`, `RECITATION`, or a text-only decline.

## Notes

- Stdlib Python over REST. No extra packages.
- Errors exit non-zero with `ERROR:` and write no file.
