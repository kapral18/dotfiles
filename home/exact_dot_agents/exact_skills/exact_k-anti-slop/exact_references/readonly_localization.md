# Localization

Use when translating, changing locale-dependent formatting, or working on supported multilingual or bidirectional content.
Follow the project's supported locales, translation system, and glossary.
This reference does not authorize adding languages, a locale switcher, or a new localization framework.

## Preserve meaning and program syntax

- Translate complete messages in context.
  Keep technical identifiers, placeholders, interpolation syntax, markup, and deliberate untranslated names intact.
  Preserve negation, qualifiers, and the distinction between a label and the action it names.
- Use the existing message system for reordered variables, plural categories, and grammatical variants.
  Do not concatenate translated sentence fragments or assume every language uses English singular/plural rules.
- Reuse the project's locale-aware date, time, number, currency, and unit formatting.
  Preserve the underlying value, currency, time zone, and instant; a locale change must not silently become a conversion.
- Keep display formatting separate from machine-readable values and parsers.
  Do not translate API keys or change a stored/wire format merely because the visible label changes.

## Preserve use across locales

- Allow translated strings to expand and wrap.
  Do not force English-sized labels, truncate a necessary instruction, or reduce type until it fits.
  Use `~/.agents/skills/k-anti-slop/references/responsive.md` when layout is affected.
- Match language and direction metadata to the content. Respect bidirectional text handling for embedded numbers, paths, and identifiers.
  Do not reverse strings or mirror every icon; reading direction and an icon's meaning are separate decisions.
- Preserve Unicode names and user-entered text.
  Do not impose ASCII-only names or a single country's name/address pattern without a real product constraint.
- Retain established terminology and register; check culture-specific examples, jokes, imagery, and assumptions against the intended audience.
  Do not erase distinctive voice merely because literal translation is difficult.

Check placeholders and meaning against the source message, and inspect representative plural/formatting cases for the affected supported locales.
Use local validation when available under the SOP.
Syntax checks and pseudolocalization do not establish linguistic accuracy; report which language checks were actually performed.

Sources: [W3C internationalization guidance](https://www.w3.org/International/quicktips/) and [ICU message formatting](https://unicode-org.github.io/icu/userguide/format_parse/messages/).
