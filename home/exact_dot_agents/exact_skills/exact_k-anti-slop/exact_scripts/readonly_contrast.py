#!/usr/bin/env python3
"""Calculate WCAG contrast for two opaque sRGB hex colors, without I/O beyond CLI output.

Adapted from antislop's contrast checker; see ../LICENSE.
Formula: https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
"""

import argparse
import json
import re


def hex_color(value: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"#?(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", value):
        raise argparse.ArgumentTypeError("expected 3 or 6 RGB hex digits, optionally prefixed by #")
    digits = value.removeprefix("#")
    if len(digits) == 3:
        digits = "".join(char * 2 for char in digits)
    return tuple(int(digits[index : index + 2], 16) for index in (0, 2, 4))


def luminance(rgb: tuple[int, int, int]) -> float:
    def linear(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("foreground", type=hex_color)
    parser.add_argument("background", type=hex_color)
    parser.add_argument("--minimum", type=float, choices=(3, 4.5, 7), default=4.5)
    args = parser.parse_args()
    light, dark = sorted((luminance(args.foreground), luminance(args.background)), reverse=True)
    ratio = (light + 0.05) / (dark + 0.05)
    passes = ratio >= args.minimum
    print(
        json.dumps(
            {
                "ratio": ratio,
                "minimum": args.minimum,
                "passes": passes,
                "aa_normal": ratio >= 4.5,
                "aa_large": ratio >= 3,
                "aaa_normal": ratio >= 7,
                "aaa_large": ratio >= 4.5,
                "non_text": ratio >= 3,
            },
            indent=2,
        )
    )
    return 0 if passes else 1


if __name__ == "__main__":
    raise SystemExit(main())
