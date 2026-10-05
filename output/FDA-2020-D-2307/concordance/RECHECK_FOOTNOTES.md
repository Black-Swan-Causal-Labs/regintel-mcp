# Footnote re-check: FDA-2020-D-2307 (JDD decision 4 Oct 2026)

Purpose: apply the SAME footnote rule used in the FDA-2021-D-0548 run, so both runs treat footnotes alike.
The original calls in this docket were made without footnote text. Re-judge ONLY the asks in
`concordance/recheck.asks.json` (each shows `previous_call` and `previous_rationale` for reference — do not anchor on them).

Read first: `skills/draft-final-concordance/SKILL.md` and `concordance/INSTRUCTIONS.md` (the original run rules). Then apply this addition:

- NEW evidence sources: `concordance/final_footnotes.md` (the final's footnotes) and `concordance/draft_footnotes.md` (the draft's footnotes).
  Use the draft footnotes to tell whether a footnote CHANGED between draft and final. A footnote present and unchanged in both is "unchanged text" (not adopted for an ask requesting a change; adopted only for a "supports as written" ask).
- Glossary asks: the final removed the Glossary (VII) and moved some definitions into the text or footnotes. Judge whether the requested definition or change now appears anywhere (text or footnotes). A definition that moved unchanged is not adopted for an ask that requested a change to it.
- Evidence quoted from a footnote uses `section_id: "footnote"` and must be copied exactly from final_footnotes.md.
- "not assessable" is no longer correct merely because the target sat in a footnote: if the target footnote can now be located (draft or final), judge it.

Output: `concordance/recheck.json` in the usual format, one entry per ask, plus a field `"changed_from_previous": true|false`.
Check with `.venv/bin/python scripts/check_concordance.py output/FDA-2020-D-2307/concordance/recheck.json` until OK. Write only that file.
