# Coding instructions: FDA-2021-D-0548 (Data Standards for Drug and Biological Product Submissions Containing Real-World Data)

The working directory is the repo root (`regulations-gov-fda/`). The codebook is APPROVED (v1, checkpoint 3). Follow `skills/comment-theming/SKILL.md` steps 2 and 3 exactly; the essentials are repeated here.

## Inputs
- Your comment IDs: `output/FDA-2021-D-0548/asks/batch_<N>.ids.json`
- Comment text: `output/FDA-2021-D-0548/corpus.jsonl`, one JSON per line. The text of a comment = `body` + every `attachments[].text`.
- Codebook (14 themes, read every definition and include/exclude note): `output/FDA-2021-D-0548/codebook.json`
- Draft section map (line numbers → section ids): `output/FDA-2021-D-0548/draft_sections.txt`
- Draft guidance text, if you need to see what a line refers to: `.venv/bin/python -c "from regintel_mcp.service import Service; import json; print(json.dumps(Service().get_guidance_text('FDA-2021-D-0548-0002'), indent=1))"`

## What an ask is
A single request, concern or recommendation directed at FDA about the guidance. **One ask = one thing FDA could do or change.** Split "clarify X and add an example of Y" into two asks. Skip praise with no request, procedural boilerplate, and background/self-description (e.g. an organisation listing its own projects).

## Repeat rule (JDD decision, same as the first docket)
Within ONE comment, a point that is reiterated counts ONCE, unless a later instance makes a genuinely section-specific point (a different recommendation or a different target). The same request restated in the cover letter, the summary and the line table counts once — keep the most specific instance (stated section, clearest wording). Different asks that merely share boilerplate wording are NOT repeats.

## Fields
- `ask_id`: `<comment_id>-A<nn>` (two digits, A01, A02…), numbered in reading order.
- `source_span`: copied **verbatim** from the extracted text — one to three sentences, exact characters, no paraphrase, no repairs. Only whitespace differences are tolerated. Comments laid out as tables (line | comment | proposed change) come out with columns interleaved: copy a contiguous run *as extracted*, even if it reads awkwardly. The span must on its own convey the request where possible (aim for ≥12 words).
- `draft_section`: the section the commenter names (by line number via `draft_sections.txt`, or by heading): one of `I, II, III, III.A, III.B, III.C, III.D, III.E, IV, APPENDIX`. If none is named, infer only if unambiguous and set `section_inferred: true`; otherwise `null` (= general comment on the guidance).
- `theme_id`: exactly one of T01–T14. If none fits, `T99` with a proposed label in `emergent_theme_proposal`. Don't invent themes. Key boundaries: which standard / Catalog / SDTM vs FHIR, OMOP, waivers → **T13**; how to map, Define-XML, controlled terminology (MedDRA, WHODrug, LOINC) → **T14**; documenting what was done and where it goes in the submission → **T01**; glossary/definition wording → **T08**; consistency with other FDA guidance or other agencies → **T09**; workshops, meetings, templates, process to propose Catalog additions → **T10**.
- `stance`: `requests more specificity` (define, detail, examples, thresholds) | `requests more flexibility` (allow alternatives, relax, reduce burden) | `supports as written` (explicit endorsement of a specific recommendation only) | `objects` (remove or reverse a recommendation).
- `confidence`: high | medium | low.

## Output
Write ONLY `output/FDA-2021-D-0548/asks/batch_<N>.json`:

```json
{"asks": [{"ask_id": "FDA-2021-D-0548-0032-A01", "comment_id": "FDA-2021-D-0548-0032",
  "theme_id": "T13", "stance": "requests more flexibility", "source_span": "<verbatim>",
  "draft_section": "III.C", "section_inferred": false, "confidence": "high", "emergent_theme_proposal": null}]}
```

Every comment in your batch must be read in full. A comment with no asks simply contributes none (say so in your final message).

## Validate before finishing
Run `.venv/bin/python scripts/check_asks.py output/FDA-2021-D-0548/asks/batch_<N>.json` and fix every listed ask until it prints `OK`. Do not modify any other file.

Final message: the OK line, number of asks per comment, any T99 proposals, and anything a human reviewer should know (ambiguous calls, comments with zero asks).
