# Responsive layout

## Reflow and scale

- Choose breakpoints where the content stops working, using the project's tokens where appropriate.
  Account for narrow, intermediate, and wide widths; phone and desktop samples alone do not establish the range between them.
- Let columns stack or regroup, navigation change form, and spacing and type scale as needed.
  Do not force three layout states or a separate mobile composition when a fluid layout already works throughout the target range.
- Design the narrow layout as deliberately as the wide one. A trailing override is not itself a defect; incomplete reflow is.
  Preserve reading and focus order when rearranging content.
- Use flexible tracks and children (`minmax`, wrapping, sensible minima, `min-width: 0` where needed).
  A fixed width or 12-column grid must not force unreadable columns or overflow.
- Adjust heading sizes, gaps, padding, and hero height to the available space.
  Fluid type or breakpoint steps can work; keep body text readable and touch targets usable rather than shrinking everything.
- Prefer content-driven heights.
  Where a full-height region is intentional, account for browser chrome with appropriate viewport units such as `dvh`;
  avoid accidental `100vh` clipping or empty slabs.

## Overflow

- Trace horizontal overflow to its element: long strings, code, tables, images, fixed children, and flex/grid minimum sizes are common causes.
  Wrap, resize, or contain it according to the content.
- Keep intentional two-dimensional content, such as a wide data table, in an accessible local scroll region when reflow would lose meaning.
  Do not hide page overflow globally to conceal the offender.
- Allow content and containers to grow.
  Crop an image when intended; never clip text, focus indicators, or controls to make a narrow layout look tidy.

## Touch and navigation

- Aim for 44 by 44 CSS px touch areas with enough separation for reliable targeting.
  This is a usability target, not the WCAG 2.2 AA minimum: that criterion uses 24 by 24 CSS px with defined spacing and other exceptions.
- Give hover interactions a touch and keyboard equivalent. Keep the state understandable without hover; provide visible activation feedback.
- Adapt navigation when its links no longer fit.
  Keep primary destinations discoverable; label a menu control accessibly and use a visible “Menu” label when the icon alone is unclear.
- Reserve space for fixed headers and bottom bars, including safe-area insets and scroll padding where needed.
  The last item, focused field, and submit action must remain reachable above navigation and the onscreen keyboard.
- Keep sticky navigation compact enough that content remains useful on a short viewport.
  Do not add scroll animations or a new navigation system when a sizing fix suffices.

Check the affected layout and states against the source, including long content, intermediate widths, zoom, and keyboard assumptions.
Follow the SOP for any rendered verification; do not claim a drag-through or touch check that was not performed.

Target-size source: [WCAG 2.2 AA minimum and exceptions](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html).
