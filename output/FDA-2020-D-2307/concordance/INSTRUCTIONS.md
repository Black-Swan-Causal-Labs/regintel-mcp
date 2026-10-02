# Concordance coding: FDA-2020-D-2307

Read `skills/draft-final-concordance/SKILL.md` first and follow it. These notes are run-specific.

## Inputs (all under output/FDA-2020-D-2307/)
- `concordance/batch_N.asks.json`: YOUR asks (ask_id, comment_id, theme, stance, verbatim source_span, draft_section).
- `concordance/draft_text.md`: the draft guidance (Sep 2021), split into `### [section_id] heading` blocks.
- `concordance/final_text.md`: the final guidance of record (fda.gov copy, Jul 2024, with one later edit: "gender" became "sex" in V.E.2). Same format. Final section ids: the validation section was split into IV.D.1–IV.D.3, the Glossary (VII) was removed, and REFERENCES lost its numeral.
- `guidance_diff.json`: the deterministic section diff. Per section: status, paragraph_changes (modified/added/removed, plus moved_in/moved_out with the target section). Use it to find WHERE text changed. Your judgment decides WHETHER that change matches the ask.
- `concordance/fr_listed_changes.txt`: FDA's own list of draft→final changes (Federal Register).
- `corpus.jsonl`: full comment texts, if a span alone is too terse to tell what was asked.

## Calls
- **adopted**: the final text changed in the direction the ask requests and substantially satisfies it.
- **partially adopted**: a change in that direction, but narrower, softer, or covering only part of the ask.
- **not adopted**: the relevant text is unchanged, or the change goes the other way, or requested new content is absent from the final.
- **not assessable**: the ask concerns process, resourcing, other guidances, FDA behaviour, or things outside the text (meetings, workshops, registries of studies, publishing case examples...), OR you cannot locate what it targets.

Direction rules:
- "requests more specificity": the final must add the detail, definition, example or threshold asked for. Generic rewording ≠ adopted.
- "requests more flexibility": the final must soften ("should" → "may"/"consider"), add "e.g."/alternatives, or make a requirement conditional or risk-based.
- "objects" (remove or reverse): adopted only if the text is removed or reversed.
- "supports as written": adopted if the endorsed text survives substantively; not adopted if it was cut.
- Asks about the Glossary: the final removed it and moved some definitions into the text (FR change 4). Judge whether the requested definition or change now appears anywhere.
- GENERAL asks (no draft_section): search the whole final.

## Output: `concordance/batch_N.json`
```json
{"concordance": [{"ask_id": "...", "section_id": "<FINAL section id or null>", "call": "adopted|partially adopted|not adopted|not assessable",
  "evidence_span": "<verbatim final text, 1-3 sentences, or null>", "rationale": "<1-2 sentences: direction asked vs what the final does>",
  "fr_listed_change": true/false, "confidence": "high|medium|low"}]}
```
- Exactly one entry per ask in your batch.
- `evidence_span` must be copied exactly from final_text.md (whitespace may differ). Required for adopted/partial. For not adopted where the text is unchanged, quote the unchanged final passage. Use null when there's nothing to quote.
- Never say a comment caused a change. Write "the final is concordant with / does not reflect the ask".

Check your work with `.venv/bin/python scripts/check_concordance.py output/FDA-2020-D-2307/concordance/batch_N.json` until it prints OK. Write only your batch file.
