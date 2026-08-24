# Elastic Slides BatchUpdate Templates

Use these Python snippets as starting points for Elastic-themed Google Slides mutations through `gws`.
They assume the generic Google Slides reference is already loaded for target resolution, layout math, and verification.

## Shared Helpers

```python
import json
import subprocess

EMU_PER_INCH = 914400

ELASTIC_BLUE = {"red": 0.0, "green": 0.37, "blue": 0.72}
SLATE_GREY = {"red": 0.29, "green": 0.33, "blue": 0.41}
CHARCOAL = {"red": 0.14, "green": 0.16, "blue": 0.18}
CARD_BACKGROUND = {"red": 0.97, "green": 0.98, "blue": 0.99}
CARD_BORDER = {"red": 0.82, "green": 0.84, "blue": 0.87}


def inches(value: float) -> int:
    return int(round(value * EMU_PER_INCH))


def rgb(color: dict[str, float]) -> dict:
    return {"opaqueColor": {"rgbColor": color}}


def run_batch(presentation_id: str, requests: list[dict]) -> None:
    subprocess.run(
        [
            "gws",
            "slides",
            "presentations",
            "batchUpdate",
            "--params",
            json.dumps({"presentationId": presentation_id}),
            "--json",
            json.dumps({"requests": requests}),
        ],
        check=True,
    )
```

## Create A 2-Column Showcase Slide

```python
presentation_id = "<presentationId>"
slide_id = "slide_showcase_01"

run_batch(
    presentation_id,
    [
        {
            "createSlide": {
                "objectId": slide_id,
                "slideLayoutReference": {"predefinedLayout": "BLANK"},
            }
        }
    ],
)

requests = [
    {
        "createShape": {
            "objectId": f"{slide_id}_title",
            "shapeType": "TEXT_BOX",
            "elementProperties": {
                "pageObjectId": slide_id,
                "size": {
                    "width": {"magnitude": inches(9.19), "unit": "EMU"},
                    "height": {"magnitude": inches(0.50), "unit": "EMU"},
                },
                "transform": {
                    "scaleX": 1,
                    "scaleY": 1,
                    "translateX": inches(0.52),
                    "translateY": inches(0.46),
                    "unit": "EMU",
                },
            },
        }
    },
    {
        "createShape": {
            "objectId": f"{slide_id}_body",
            "shapeType": "TEXT_BOX",
            "elementProperties": {
                "pageObjectId": slide_id,
                "size": {
                    "width": {"magnitude": inches(3.15), "unit": "EMU"},
                    "height": {"magnitude": inches(3.65), "unit": "EMU"},
                },
                "transform": {
                    "scaleX": 1,
                    "scaleY": 1,
                    "translateX": inches(0.57),
                    "translateY": inches(1.45),
                    "unit": "EMU",
                },
            },
        }
    },
    {
        "createShape": {
            "objectId": f"{slide_id}_media_frame",
            "shapeType": "ROUND_RECTANGLE",
            "elementProperties": {
                "pageObjectId": slide_id,
                "size": {
                    "width": {"magnitude": inches(5.43), "unit": "EMU"},
                    "height": {"magnitude": inches(3.70), "unit": "EMU"},
                },
                "transform": {
                    "scaleX": 1,
                    "scaleY": 1,
                    "translateX": inches(4.00),
                    "translateY": inches(1.45),
                    "unit": "EMU",
                },
            },
        }
    },
]

run_batch(presentation_id, requests)
```

## Replace And Style A Linked Title

```python
title_object_id = f"{slide_id}_title"
title_text = "Stack Management: Ingest Pipelines"
source_url = "https://github.com/elastic/kibana/blob/main/x-pack/platform/plugins/shared/ingest_pipelines/kibana.jsonc"

requests = [
    {"deleteText": {"objectId": title_object_id, "textRange": {"type": "ALL"}}},
    {"insertText": {"objectId": title_object_id, "text": title_text, "insertionIndex": 0}},
    {
        "updateTextStyle": {
            "objectId": title_object_id,
            "textRange": {"type": "ALL"},
            "style": {
                "bold": True,
                "fontFamily": "Arial",
                "fontSize": {"magnitude": 24, "unit": "PT"},
                "foregroundColor": rgb(ELASTIC_BLUE),
                "link": {"url": source_url},
            },
            "fields": "bold,fontFamily,fontSize,foregroundColor,link",
        }
    },
]

run_batch(presentation_id, requests)
```

## Create A Status Badge

```python
badge_id = f"{slide_id}_badge_status"
badge_text = "Co-owned w/ Core"
badge_x = inches(0.57)
badge_y = inches(1.05)
badge_w = inches(max(1.40, len(badge_text) * 0.085 + 0.35))
badge_h = inches(0.24)

requests = [
    {
        "createShape": {
            "objectId": badge_id,
            "shapeType": "ROUND_RECTANGLE",
            "elementProperties": {
                "pageObjectId": slide_id,
                "size": {
                    "width": {"magnitude": badge_w, "unit": "EMU"},
                    "height": {"magnitude": badge_h, "unit": "EMU"},
                },
                "transform": {
                    "scaleX": 1,
                    "scaleY": 1,
                    "translateX": badge_x,
                    "translateY": badge_y,
                    "unit": "EMU",
                },
            },
        }
    },
    {
        "insertText": {
            "objectId": badge_id,
            "text": badge_text,
            "insertionIndex": 0,
        }
    },
    {
        "updateTextStyle": {
            "objectId": badge_id,
            "textRange": {"type": "ALL"},
            "style": {
                "bold": True,
                "fontFamily": "Arial",
                "fontSize": {"magnitude": 8.5, "unit": "PT"},
                "foregroundColor": rgb(CHARCOAL),
            },
            "fields": "bold,fontFamily,fontSize,foregroundColor",
        }
    },
]

run_batch(presentation_id, requests)
```

## Aspect-Ratio Fit An Existing Image

```python
image = next(element for element in page_elements if element["objectId"] == "<imageObjectId>")

box_x = inches(4.00)
box_y = inches(1.45)
box_w = inches(5.43)
box_h = inches(3.70)

iw = image["size"]["width"]["magnitude"]
ih = image["size"]["height"]["magnitude"]
scale = min(box_w / iw, box_h / ih)
rendered_w = iw * scale
rendered_h = ih * scale

requests = [
    {
        "updatePageElementTransform": {
            "objectId": image["objectId"],
            "transform": {
                "scaleX": scale,
                "scaleY": scale,
                "translateX": box_x + (box_w - rendered_w) / 2.0,
                "translateY": box_y + (box_h - rendered_h) / 2.0,
                "unit": "EMU",
            },
            "applyMode": "ABSOLUTE",
        }
    }
]

run_batch(presentation_id, requests)
```

## Visual QA Probe

Use this only after `gws` re-read checks pass:

```javascript
await page.goto(
  `https://docs.google.com/presentation/d/${presentationId}/edit#slide=id.${slideId}`,
  {
    waitUntil: "domcontentloaded",
  },
);
await page.waitForTimeout(2500);
await page.screenshot({ path: `/tmp/elastic-slide-${slideId}.png` });
```
