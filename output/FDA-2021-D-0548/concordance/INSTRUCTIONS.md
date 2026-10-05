# Concordance coding: FDA-2021-D-0548 (Data Standards for Drug and Biological Product Submissions Containing Real-World Data)

Read `skills/draft-final-concordance/SKILL.md` first and follow it. These notes are run-specific and match the first docket's run (FDA-2020-D-2307) except where marked NEW.

## Inputs (all under output/FDA-2021-D-0548/)
- `concordance/batch_N.asks.json`: YOUR asks (ask_id, comment_id, theme, stance, verbatim source_span, draft_section).
- `concordance/draft_text.md`: the draft guidance (Oct 2021), split into `### [section_id] heading` blocks.
- `concordance/final_text.md`: the final guidance of record (fda.gov copy, Dec 2023, with one later edit: "gender identity" became "sex identity" in III.D). Same format. The Glossary (IV) was removed.
- NEW `concordance/final_footnotes.md`: the final's footnotes, which the section text omits. FDA's notice says it moved glossary concepts "from glossary entries to footnotes to the main document text", so for any ask about a definition or glossary entry, check the footnotes as well as the text. Evidence quoted from a footnote uses `section_id: "footnote"`.
- `guidance_diff.json`: the deterministic section diff. Per section: status, paragraph_changes (modified/added/removed, plus moved_in/moved_out). Use it to find WHERE text changed. Your judgment decides WHETHER that change matches the ask.
- `concordance/fr_listed_changes.txt`: FDA's own list of draft→final changes (Federal Register). It names one substantive change: clarifying the challenges of using currently supported data standards for RWD, and elaborating FDA resources for consultation about data standards. Set `fr_listed_change: true` when the matching change is that one.
- `corpus.jsonl`: full comment texts, if a span alone is too terse to tell what was asked.

## Calls
- **adopted**: the final text changed in the direction the ask requests and substantially satisfies it.
- **partially adopted**: a change in that direction, but narrower, softer, or covering only part of the ask.
- **not adopted**: the relevant text is unchanged, or the change goes the other way, or requested new content is absent from the final.
- **not assessable**: the ask concerns process, resourcing, other guidances, FDA behaviour, or things outside the text (meetings, workshops, Catalog updates FDA would make elsewhere, publishing case examples...), OR you cannot locate what it targets.

Direction rules:
- "requests more specificity": the final must add the detail, definition, example or threshold asked for. Generic rewording ≠ adopted.
- "requests more flexibility": the final must soften ("should" → "may"/"consider"), add "e.g."/alternatives, or make a requirement conditional or risk-based.
- "objects" (remove or reverse): adopted only if the text is removed or reversed.
- "supports as written": adopted if the endorsed text survives substantively; not adopted if it was cut.
- Glossary asks: the final removed the Glossary and moved definitions into footnotes or the text. Judge whether the requested definition or change now appears anywhere (text or footnotes). A definition that moved unchanged is not adopted for an ask that requested a change to it.
- GENERAL asks (no draft_section): search the whole final.
- An ask asking FDA to add a standard to the Data Standards Catalog is a request about a separate FDA resource: not assessable, unless it asks the guidance text itself to say something (then judge the text).

## Output: `concordance/batch_N.json`
```json
{"concordance": [{"ask_id": "...", "section_id": "<FINAL section id, \"footnote\", or null>", "call": "adopted|partially adopted|not adopted|not assessable",
  "evidence_span": "<verbatim final text or footnote, 1-3 sentences, or null>", "rationale": "<1-2 sentences: direction asked vs what the final does>",
  "fr_listed_change": true/false, "confidence": "high|medium|low"}]}
```
- Exactly one entry per ask in your batch.
- `evidence_span` must be copied exactly from final_text.md or final_footnotes.md (whitespace may differ). Required for adopted/partial. For not adopted where the text is unchanged, quote the unchanged final passage. Use null when there's nothing to quote.
- Never say a comment caused a change. Write "the final is concordant with / does not reflect the ask".

Check your work with `.venv/bin/python scripts/check_concordance.py output/FDA-2021-D-0548/concordance/batch_N.json` until it prints OK. Write only your batch file.
