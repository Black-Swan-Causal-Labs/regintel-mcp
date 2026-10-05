---
description: Analyse a regulations.gov docket end to end (who commented, what they asked for, what changed draft to final) with four human checkpoints
argument-hint: <docketId>
---

Run the regulatory-intelligence pipeline on docket **$ARGUMENTS** using the `regintel-mcp` tools and the `submitter-taxonomy`, `comment-theming` and `draft-final-concordance` skills.

At the start, read `decisions/$ARGUMENTS.json` if it exists. Apply every recorded decision and never re-ask a decided question. Append each new checkpoint outcome there (`date`, `by`, `checkpoint`, `decision`, `notes`).

**At each ⏸ checkpoint: present the material, then STOP and wait for the human's explicit go-ahead. Do not continue in the same turn.**

1. **Retrieve.** Call `get_docket`, `list_documents` and `build_corpus`. Identify the draft guidance, the final guidance, and the Federal Register notices of availability.
   ⏸ **Checkpoint 1:** show the draft and final refs (with dates and URLs), the corpus summary (comments, submissions represented, attachments, extraction, OCR needs, stubs, duplicates, failures), and anything odd. Proposed exclusions need the human's decision.

2. **Classify submitters** with `submitter-taxonomy`. Write `output/$ARGUMENTS/submitters.json`.
   ⏸ **Checkpoint 2:** show counts per bucket, the full table, and the low-confidence calls with alternatives.

3. **Theme.** Draft the codebook with `comment-theming` step 1.
   ⏸ **Checkpoint 3:** show the codebook. **No comment is coded until the human approves it.** Then run `export_corpus` and code all comments with subagents in batches of about 10, each returning JSON. Validate the source spans and write `output/$ARGUMENTS/asks.json`.

4. **Concordance.** Run `diff_guidance` (with the refs from decisions), then `draft-final-concordance`.
   ⏸ **Checkpoint 4:** two seeded random spot checks, each about 10–15%: one of theme coding (theme and stance per ask) and one of concordance calls. Log both agreements.

5. **Emit.**
   - Write `output/$ARGUMENTS/analysis.json` following the schema in `docs/analysis-schema.json`, and validate it with `python scripts/validate_analysis.py output/$ARGUMENTS/analysis.json`.
   - Write a short `summary.md`: who spoke, the top themes by bucket, the concordance tallies, and the caveat. Note any known differences between the final-of-record and other copies of the final.
   - Build the local Docket Lens: `python scripts/build_explorer.py $ARGUMENTS`, then serve `explorer/$ARGUMENTS/` with any static server. Do not publish or deploy it (`scripts/build_site.sh`) unless the human asks.

The concordance caveat appears in every output: concordance, not impact.
