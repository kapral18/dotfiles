# Accessibility

## Contrast

Measure actual foreground/background pairs; visual confidence is not a measurement.
Resolve tokens, opacity, overlays, supported themes, and reachable states before choosing the pair.
For text over an image or gradient, the weakest background beneath the text matters.
Use a stable backing surface when the contrast cannot be bounded.

- WCAG AA text: at least 4.5:1 for normal text; 3:1 for large text.
- Large text means at least 18pt regular (24 CSS px) or 14pt bold (about 18.67 CSS px), not 18px regular.
- Necessary component boundaries, state indicators, and graphical information need 3:1 against adjacent colors under the non-text criterion.
  Pure decoration and inactive controls have exceptions; do not fail every decorative border as if it were a control.
- Compare the unrounded ratio to the threshold. A displayed 4.50 can still be below 4.5.
- Text, labels, and icons must remain legible in each supported theme and relevant state.
  A grey-on-grey pairing needs the same calculation as other colors.

Use the bundled, standard-library Python calculator for opaque RGB hex pairs:

```sh
timeout 5 python3 ~/.agents/skills/k-anti-slop/scripts/contrast.py '#777777' '#ffffff'
timeout 5 python3 ~/.agents/skills/k-anti-slop/scripts/contrast.py '#777777' '#ffffff' --minimum 3
```

It accepts three or six hex digits with an optional `#`. Quote shell arguments containing `#`.
JSON reports the unrounded ratio, AA/AAA text results, non-text result, chosen minimum, and pass/fail.
Exit codes: 0 meets the chosen minimum, 1 is below it, 2 is invalid input. The default minimum is 4.5; 3 and 7 are also supported.
Choose 3 only for applicable large text or non-text checks, not to make normal text pass.
The calculator does not resolve CSS, composite transparency, inspect screenshots, or certify a page's accessibility.

## Keyboard, focus, and state

- Prefer native links, buttons, inputs, and established accessible components.
  Preserve names, roles, labels, DOM reading order, and keyboard reachability.
- Use activation and dismissal keys appropriate to the control: links and buttons have different native semantics.
  Menus, dialogs, and composite widgets need their established keyboard model, focus entry, and focus return.
- Never remove an outline without an effective replacement.
  Focus must remain visible against the actual surface and unobscured by sticky content; check each supported theme.
- Keep sequential focus in a logical order. Avoid positive `tabindex` to repair a bad DOM order.
  Negative `tabindex` is valid for managed focus and roving-tabindex widgets; do not remove it blindly.
- Provide a way to bypass repeated navigation where needed.
  Do not trap focus outside an intentional modal interaction; closing a modal returns focus to a sensible place.
- Do not communicate error, success, selection, or status through color alone.
  Use text, shape, icons with accessible meaning, or an appropriate announcement as well.
- For reachable empty, loading, error, disabled, and success states, provide a clear meaning and useful next action.
  Connect form errors to their inputs and preserve entered data when recovery permits.

## Zoom and viewport

Allow text resize to 200% without losing content or controls. Do not disable browser zoom.
Avoid fixed heights and clipping that hide enlarged content; keep the focused input, its error, and the submit action reachable when the mobile keyboard appears.
For reflow, touch, and fixed navigation, use `~/.agents/skills/k-anti-slop/references/responsive.md`.

Threshold sources: [WCAG contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) and [non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html).
Report source-based coverage separately from any rendered checks actually performed under the SOP. Never present a pair calculation as a complete audit.
