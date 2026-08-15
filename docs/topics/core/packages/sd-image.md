---
sidebar_position: 20
---

# Image generation and editing

`,image-local` runs [FLUX.2 klein 9B](https://huggingface.co/leejet/FLUX.2-klein-9B-GGUF) for text-to-image and instruction edit, through `sd-cli` from [leejet/stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp).

These are not llama.cpp chat GGUFs. There is no agent skill; run the CLI yourself. Cloud choices are `,image-openrouter`, `,image-codex`, `,image-openai`, and the existing Gemini `,nano-banana` command.

Default is generate: a plain English prompt, no `-i`. Edit runs only when you pass `-i`. Klein rewrites the canvas. It has no mask, so it cannot pixel-lock an unmentioned region.

Ideogram 4 is not this CLI. It needs a full JSON caption and draws a gray "Image blocked by safety filter" screen on thin prompts.

## Cloud commands

All 3 `,image-*` cloud commands auto-orient and strip metadata from temporary input copies through the managed ImageMagick binary. They never modify the source and fail before upload if sanitization fails.

`,image-codex` uses the active Codex ChatGPT login and its built-in GPT Image 2 tool. It does not use `OPENAI_API_KEY`. Codex fixes quality, size, and background to `auto`, emits PNG, and exposes no mask:

```bash
,image-codex "a cat astronaut"
,image-codex -i photo.jpg "add shorts to the kid" -o edited.png
```

`,image-openai` calls the native GPT Image 2 Images API with `OPENAI_API_KEY`, falling back to `pass show openai/api/token`. GPT Image 2 always uses high input fidelity. The command exposes quality, arbitrary valid size, PNG/JPEG/WebP, JPEG/WebP compression, background, repeated inputs, and a mask applied to the first input:

```bash
,image-openai "a cat astronaut" --quality high --size 2048x2048
,image-openai -i photo.jpg --mask mask.png "add shorts to the kid" --quality high -o edited.png
,image-openai "a poster" --format webp --compression 85 --background opaque
```

Input and mask are converted to matching PNGs. A grayscale mask becomes its alpha channel, so black becomes transparent and white opaque. Masks guide GPT Image 2 but do not pixel-lock their exact boundary.

## Preconditions

- macOS Darwin (the pinned `sd-cli` zip is the Darwin Metal build).
- `gh` and `hf` are on PATH (Homebrew; `hf` is already in the AI Brewfile slice).
- You want on-device generate/edit because the image cannot leave the machine.

## Pieces

| Piece                                  | Source                              | When it installs                                                              |
| -------------------------------------- | ----------------------------------- | ----------------------------------------------------------------------------- |
| `sd-cli` + `libstable-diffusion.dylib` | custom `zip_opt`                    | `chezmoi apply` → `~/.local/opt/sd-cli/` + wrapper `~/.local/bin/sd-cli`      |
| `,image-local`                         | `home/exact_bin` + `home/exact_lib` | `chezmoi apply`                                                               |
| Weights (~15 GB)                       | `~/.config/sd-image/models.txt`     | **command-only**: `,image-local sync`. Not gated on `downloadLlamaCppModels`. |

Do not add these files to `models.ini` or the Pi/Codex/OpenCode llama.cpp catalogs.

## Manifest

[`home/dot_config/sd-image/readonly_models.txt`](../../../../home/dot_config/sd-image/readonly_models.txt)

```text
role|hf-repo|hf-file
role|hf-repo|hf-file|dest-basename
```

Roles: `klein`, `klein_llm`, `vae`.

Default quality pick (64 GB unified memory): FLUX.2 klein 9B `Q8_0` + Qwen3-8B `Q4_K_M` + the Comfy-Org FLUX.2 VAE (`flux2-vae.safetensors`, stored as `flux2_ae.safetensors`). `black-forest-labs/FLUX.2-dev` `ae.safetensors` is gated.

## Steps

1. Apply so `sd-cli` and `,image-local` exist:

```bash
chezmoi apply --no-tty ~/.local/bin/sd-cli ~/bin/,image-local ~/.config/sd-image/models.txt
```

1. Download weights:

```bash
,image-local sync
,image-local status
```

1. Generate (default; klein 9B, 4 steps, CFG 1.0). Prompt is a plain sentence. Canvas is sd-cli's 512×512 unless you pass both `--width` and `--height`:

```bash
,image-local "a cat sitting on a windowsill"
,image-local "a cat sitting on a windowsill" --width 1024 --height 1024
```

Personal (64 GB) omits `--offload-to-cpu`. Work (36 GB) keeps it so the M3 Pro does not run out of memory. Same model and steps either way.

1. Edit (only with `-i`; klein 9B, 4 steps, CFG 1.0, euler). Canvas always follows the input image. Do not pass `--width` / `--height`. A large photo stays that large, so the edit is slower:

```bash
,image-local -i photo.png -p "make the smaller kid wear shorts"
```

Stdout is the output path.

## Verification

```bash
command -v sd-cli
sd-cli --version
,image-local --version
,image-local status
```

Loading is architecturally matched to the sd.cpp FLUX.2 klein 9B generate and edit examples. A first live run still depends on the synced weights and Metal memory.

## Rollback

1. Leave the `zip_opt|sd-cli|...` row in place if `,image-local` still needs the runner.
2. Delete `~/bin/,image-local`, `~/lib/,image-local/`, `~/.config/sd-image/`, and `~/.local/share/sd-image/models/` if you want this command and its weights gone.
