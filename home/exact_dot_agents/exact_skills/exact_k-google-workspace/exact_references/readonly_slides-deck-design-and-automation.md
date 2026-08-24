# Google Slides: Deck Design And Automation

Use this reference for portable Google Slides mechanics: target resolution, canvas math, layout templates, `gws` batchUpdate patterns, and visual verification.
Keep product-specific palette, ownership, content sourcing, and release policy in the domain skill that loaded this reference.

## Target Resolution

Extract identifiers before any mutation:

- Presentation URL: `https://docs.google.com/presentation/d/<presentationId>/edit#slide=id.<slideId>`
- `presentationId`: the `/d/<id>/` segment.
- `slideId`: the optional `#slide=id.<id>` fragment.
- Existing objects: read them from `gws slides presentations get`; use live object IDs for updates.

Object IDs created through the Slides API need stable, unique names of at least 5 characters.
Use prefixes that make the role visible, such as `slide_overview_01`, `card_01_title`, or `badge_status_01`.

## Canvas And Units

Google Slides uses EMUs for positions and transforms:

- `1 inch = 914400 EMU`
- `1 pt = 12700 EMU`
- Standard 16:9 widescreen canvas: `10.00" x 5.625"` (`9144000 x 5143500 EMU`)

Use helper constants in scripts instead of repeating raw numbers:

```python
EMU_PER_INCH = 914400
EMU_PER_PT = 12700

def inches(value: float) -> int:
    return int(round(value * EMU_PER_INCH))
```

## Layout Templates

Use these templates as starting geometry, then adjust to the deck's current theme and content density.

### 3-Card Architecture Grid

For overviews, concepts, process maps, and package groups:

- Title: `x = 0.52"`, `y = 0.46"`, `w = 9.19"`, `h = 0.50"`
- Card 1: `x = 0.68"`, `y = 1.45"`, `w = 2.76"`, `h = 3.68"`
- Card 2: `x = 3.62"`, `y = 1.45"`, `w = 2.76"`, `h = 3.68"`
- Card 3: `x = 6.56"`, `y = 1.45"`, `w = 2.76"`, `h = 3.68"`
- Text inset inside each card: `0.14"` on each side.

### 2-Column Showcase

For feature walkthroughs, screenshots, demos, or gallery slides:

- Title: `x = 0.52"`, `y = 0.46"`, `w = 9.19"`, `h = 0.50"`
- Badge row: `y = 1.01"–1.05"`, `h = 0.24"`
- Left narrative column: `x = 0.57"`, `y = 1.45"`, `w = 3.15"`, `h = 3.65"`
- Gutter: keep `0.28"–0.33"` between text and media.
- Right media box: `x = 4.00"`, `y = 1.45"`, `w = 5.43"`, `h = 3.70"`

## Typography And Spacing

Fit text by budgeting lines before writing them:

- Slide title: `22–26pt`, bold.
- Card header: `13–14pt`, bold.
- Card subheader: `9.5–10pt`, italic when it represents metadata.
- Body and bullets: `9.0–9.5pt`, `115–125%` line spacing, `3–4pt` space above.
- Badge text: `8.5pt`, bold, centered.

A `3.65"` tall card comfortably holds 1 header, 1 short subheader, and about 5 short bullets at `9pt` with `115%` line spacing.
Use paragraph spacing instead of inserting `\n\n` between every bullet.
Keep at least `0.20"` bottom clearance inside rounded card containers.

## Badge Sizing

Badges provide compact categorization when the slide needs it:

```python
def badge_width_inches(text: str) -> float:
    return max(1.40, len(text) * 0.085 + 0.35)
```

Use `0.24"` height and `0.12"` horizontal gaps between badges.
When a badge would exceed its row, shorten the label or move the category into the body text.

## Image Scaling

Fit screenshots and diagrams inside a dedicated box while preserving aspect ratio:

```python
BOX_X = inches(4.00)
BOX_Y = inches(1.45)
BOX_W = inches(5.43)
BOX_H = inches(3.70)

iw = image["size"]["width"]["magnitude"]
ih = image["size"]["height"]["magnitude"]

scale = min(BOX_W / iw, BOX_H / ih)
rendered_w = iw * scale
rendered_h = ih * scale

img_x = BOX_X + (BOX_W - rendered_w) / 2.0
img_y = BOX_Y + (BOX_H - rendered_h) / 2.0

transform_request = {
    "updatePageElementTransform": {
        "objectId": image["objectId"],
        "transform": {
            "scaleX": scale,
            "scaleY": scale,
            "translateX": img_x,
            "translateY": img_y,
            "unit": "EMU",
        },
        "applyMode": "ABSOLUTE",
    }
}
```

## `gws` Automation Lifecycle

1. Inspect the method: `gws schema slides.presentations.get` or `gws schema slides.presentations.batchUpdate`.
2. Read current state: `gws slides presentations get --params '{"presentationId":"<id>"}'`.
3. Build the batch request from live object IDs and explicit geometry.
4. For text replacement, use `deleteText`, `insertText`, `updateTextStyle`, then `updateParagraphStyle`.
5. Submit with `gws slides presentations batchUpdate`.
6. Re-read the presentation and verify the expected objects, text, links, and transforms.
7. Open the slide in a browser only for visual QA that the API response cannot prove.

For speaker notes, read `slideProperties.notesPage.pageElements` and target the page element with a `BODY` placeholder.
Use `insertText` against that notes page element object ID.

## Visual QA Checklist

Use browser verification for rendered layout after API checks pass:

- Images keep their aspect ratio.
- Text stays inside its intended container.
- The text/media gutter is visible.
- Badges do not wrap.
- Links point to the intended sources.
- The slide matches the deck's current visual language unless a domain skill supplied a deliberate redesign.
