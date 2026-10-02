---
name: draft-final-concordance
description: For each coded ask on an FDA draft guidance, judge whether the final guidance changed in the direction requested (adopted / partially adopted / not adopted / not assessable), citing the matched final-text span. Use during /docket-analysis step 4. Measures concordance, never impact.
---

# Draft → final concordance

## The caveat (it goes into every output, verbatim)

> **Concordance, not impact.** These calls record whether the final guidance text moved in the direction a commenter asked for. Changes between draft and final also reflect FDA's internal review, ICH M14, other guidances, and evolving science. A matching change does not show that a comment caused it.

Never write "FDA adopted X *because of*", "in response to", or "commenters succeeded in". Write "the final text is concordant with the ask".

## Inputs

- `output/<docket>/asks.json`: the coded asks
- `diff_guidance(draft_ref, final_ref)`: the section-aligned diff, including `paragraph_changes` and moved paragraphs. Use the refs recorded in `decisions/<docket>.json`.
- `get_guidance_text(<final NOA document id>)`: FDA's own Federal Register list of draft→final changes, used as a cross-check

## Calls

| Call | Rule |
|---|---|
| `adopted` | The final text changed **in the direction requested** and substantially covers the ask |
| `partially adopted` | A change in that direction, but narrower, weaker or covering only part of the ask |
| `not adopted` | No corresponding change, or a change in the opposite direction. That includes asks to **remove** text the final kept, and asks for **new** content the final lacks |
| `not assessable` | The ask targets something outside the guidance text: process, timelines, other guidances, FDA resourcing, meeting requests. Also use this when the target text cannot be located in the draft |

## Procedure for each ask

1. **Locate.** Start from the ask's `draft_section`. Find the draft passage the ask concerns. Then look in the aligned final section, *and* in any section the diff shows received paragraphs moved from it.
2. **Compare direction, not just change.** A modified paragraph is only `adopted` if the modification goes the way the ask points: more specific, more flexible, removed, added. An unchanged section means `not adopted`. An ask for new content means searching the whole final, not just the aligned section.
3. **Evidence.** `evidence_span` = the verbatim final text that supports the call (one to three sentences). For `not adopted` because nothing changed, quote the unchanged final passage. For a missing addition, write `evidence_span: null` and state what was searched in `rationale`. For `not assessable`, use `null`.
4. **Rationale.** One or two sentences. State the direction asked and the direction (or absence) of change.
5. **Cross-check.** If the change is one FDA listed in its FR notice, set `fr_listed_change: true`.
6. **Confidence.** high, medium or low. Low-confidence calls are over-sampled at the checkpoint.

## Output

`output/<docket>/concordance.json`:

```json
{"caveat": "<verbatim caveat>", "concordance": [{"ask_id": "...", "section_id": "IV.D.3",
  "call": "partially adopted", "evidence_span": "<verbatim final text>",
  "rationale": "...", "fr_listed_change": true, "confidence": "medium"}]}
```

Validate that every non-null `evidence_span` occurs verbatim in the final guidance text.

## Checkpoint 4 (spot check)

Draw a **seeded random sample of about 15% of calls**, stratified by call type, with every low-confidence call included on top of the sample. Show the human each sampled ask, its source span, the draft and final passages, and the call. Record agree or disagree per item. `spot_check_agreement` = agreements ÷ sampled. Corrections replace the call and are logged in `decisions/<docket>.json`.
