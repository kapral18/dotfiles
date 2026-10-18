# Data displays

Use for charts, quantitative tables, metrics, and benchmark presentations, including static reports.
Choose the comparison or decision first. A table or sentence can be sufficient; do not add a chart solely to decorate a report.

## Preserve the measurement

- Identify the measure, unit, population or denominator, time window, and source where they affect interpretation.
  Keep filters and comparison periods visible; do not compare unlike populations or windows without explaining the difference.
- Distinguish zero, missing, unavailable, and not applicable.
  Leave gaps in observations visible; label estimates or interpolation rather than presenting them as measurements.
- State what an aggregate represents.
  Preserve meaningful sample size, uncertainty, and variation instead of reporting only a favorable average.
  Distinguish relative percent change from percentage-point change; an undefined baseline is not an infinite improvement.
- Benchmark labels must identify the relevant version, workload, environment, and metric.
  Do not imply causation or broad superiority from a selected run, or hide a material tradeoff in a different measure.

## Preserve the visual comparison

- When bar length encodes magnitude, use a zero baseline. An interval/range bar encodes endpoints instead; label that different meaning.
  Line and scatter plots can use a restricted range when clearly labelled and appropriate to the question.
- Keep comparable panels on a common scale or make differences explicit. Label logarithmic scales and changes in units.
  Prefer separate aligned plots to dual axes that can suggest an arbitrary relationship.
- Keep category ordering and color meanings consistent across views.
  Avoid perspective, area, or volume effects that distort the encoded quantity.
  Do not smooth away an important discontinuity or hide inconvenient categories for visual balance.
- Provide an accessible text explanation or table that communicates the chart's purpose and material caveats.
  Essential values must not be available only on hover.
  Use `~/.agents/skills/k-anti-slop/references/accessibility.md` for rendered colors and interactive controls.

Trace representative displayed values, labels, and comparisons back to their inputs before calling the display accurate.
The source must support the headline as well as the plotted numbers.

Source: [Government Analysis Function chart guidance](https://analysisfunction.civilservice.gov.uk/policy-store/data-visualisation-charts/).
