---
name: comment-theming
description: Break public comments on an FDA draft guidance into discrete asks, each with a verbatim source span, the draft section it targets, a theme code from a human-approved codebook, and a stance. Use during /docket-analysis step 3. Never code comments before the codebook is approved.
---

# Comment theming

## Hard gate

**Do not code any comment until the human has approved the codebook** (Checkpoint 3). Approval is recorded in `decisions/<docket>.json` as `{"checkpoint": 3, "decision": "codebook_approved", "codebook_version": "..."}`. If that entry is missing, stop and present the codebook.

## Step 1: Draft the codebook

Start from the starter themes below. Read about 10 substantive comments from different submitter buckets to check coverage. Then propose **8–12 themes**, each with an id, label, one-sentence definition, inclusion and exclusion notes, and one example span. Write the codebook to `output/<docket>/codebook.json` with `"version": "v1-draft"`.

Starter themes:

| id | label |
|---|---|
| T01 | Data provenance & traceability |
| T02 | Data relevance / fitness for purpose |
| T03 | Validation of exposures, outcomes & covariates (algorithms, PPV) |
| T04 | Missing data & data completeness |
| T05 | Linkage & tokenization |
| T06 | Data access, retention & auditability |
| T07 | Sponsor burden & feasibility of recommendations |
| T08 | Terminology / definitional clarity |
| T09 | Alignment with other FDA/international guidance (ICH, EMA) |
| T10 | Early engagement / meeting pathways with FDA |
| T11 | Privacy & data governance |
| T12 | Scope (what's in/out of the guidance) |

You may *propose* merges, splits or new themes, with a reason. Do not add them yourself: the human decides.

## Step 2: Extract asks (after approval)

An **ask** is a single request, concern or recommendation directed at FDA about the guidance.

- **One ask = one thing FDA could do or change.** Split compound sentences such as "clarify X and add an example of Y" into two asks.
- **`source_span` must be copied verbatim from the extracted text** in `corpus.jsonl` (body or `attachments[].text`): one to three sentences, exact characters, no paraphrase, no repairs. Comments laid out as tables (line number | comment | proposed change) come out with the columns interleaved, so copy a contiguous run *as extracted*, even if it reads awkwardly. Don't reconstruct the sentence as it looked in the PDF. Only whitespace differences are tolerated by validation.
- **`draft_section`.** Use the draft section the commenter names, either by line number or heading. Map line numbers to section ids using the draft's sectioning from `get_guidance_text`. If the commenter names no section, infer one only if the target is unambiguous and set `section_inferred: true`. Otherwise use `null`.
- Skip praise that contains no request, procedural boilerplate, and restatements of the same ask within one comment.
- Comments that `decisions/<docket>.json` marks `zero_asks` or `exclude_*` get no asks.

## Step 3: Code each ask

- `theme_id`: exactly one approved theme. If none fits, use `T99` and put a proposed label in `emergent_theme_proposal`. Don't create themes.
- `stance`, one of:
  - `requests more specificity`: asks FDA to define, detail, give examples, or set thresholds
  - `requests more flexibility`: asks FDA to allow alternatives, relax, soften "should", or reduce burden
  - `supports as written`: endorses a specific recommendation (record this only when it is explicit)
  - `objects`: asks FDA to remove a recommendation or reverse direction
- `confidence`: high, medium or low.

## Fan-out

Code comments in batches of about 10 per subagent. Give each subagent the approved codebook, these rules, the draft section list, and its batch of comments, read from `output/<docket>/corpus.jsonl` via `export_corpus`. Each subagent returns JSON only:

```json
{"asks": [{"ask_id": "FDA-2020-D-2307-0063-A03", "comment_id": "FDA-2020-D-2307-0063",
  "theme_id": "T03", "stance": "requests more flexibility",
  "source_span": "<verbatim>", "draft_section": "V.D.3", "section_inferred": false,
  "confidence": "high", "emergent_theme_proposal": null}]}
```

`ask_id` = `<comment_id>-A<nn>`, numbered in reading order.

## Validation before merging

For every ask, check that `source_span` occurs **verbatim** in the comment text (normalise only whitespace). Return any failures to that batch's subagent for correction. Never fix a span silently. Write the merged result to `output/<docket>/asks.json`, then report counts by theme × submitter bucket and any `T99` proposals for the human.

## Theme-coding spot check (Checkpoint 4)

Draw a seeded random 10–15% sample of asks and show the human each ask's verbatim span, its comment context, and the assigned `theme_id` and `stance`. Record agreement (with a Wilson 95% CI) and corrections in `decisions/<docket>.json` as `{"checkpoint": 4, "decision": "theme_spot_check", ...}`. This is separate from the concordance spot check: the two together cover both judgment steps.

## Method label

This is codebook-based (directed) qualitative content analysis, also called template analysis: a codebook set before coding, refined on a sample, approved by a human, then applied to every ask and counted. It is not reflexive thematic analysis. When a codebook is carried forward from an earlier docket, record that as the starting template.
