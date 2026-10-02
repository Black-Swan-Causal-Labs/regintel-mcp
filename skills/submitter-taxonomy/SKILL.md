---
name: submitter-taxonomy
description: Classify every commenter on a regulations.gov docket into exactly one of seven submitter buckets (pharma/biotech, trade association, CRO/data & tech vendor, academic/independent, professional society, patient advocacy, other/anonymous), with the evidence used and a confidence level. Use during /docket-analysis step 2, or whenever someone asks who commented on an FDA docket.
---

# Submitter taxonomy

The goal is one row per **submitter**, with exactly one bucket. This step is judgment, not retrieval: the regintel-mcp server supplies the evidence and you make the call.

## Inputs

- `list_comments(docket_id)` gives the comment IDs, titles ("Comment from X") and the stub and duplicate flags.
- `get_comment(comment_id, max_chars=1500)` gives the `submitter` fields and the opening of each attachment, where the letterhead and signature block usually are.
- `decisions/<docket>.json`: earlier human decisions. Apply them and don't re-ask.

## Buckets (use these labels exactly)

| Bucket | Includes | Edge cases |
|---|---|---|
| `Pharma / biotech` | Drug and biologic sponsors, including diagnostics companies whose products are regulated as part of drug development | A sponsor's RWE subsidiary goes here only if it comments as the sponsor |
| `Trade association` | Industry membership bodies: PhRMA, BIO, ACRO, RWE Alliance, EHR Association | An association of **companies** goes here; an association of **professionals** is a professional society |
| `CRO / data & tech vendor` | CROs, RWD vendors, analytics, EHR and IT firms, cloud providers, tokenization and linkage firms, payers' data units | Payers acting **as payers** go to Other |
| `Academic / independent` | Universities, academic centres and policy institutes (e.g. Duke-Margolis), named individual researchers, independent consultants, working groups of individuals with no institutional sponsor | |
| `Professional society` | Membership bodies of individual professionals: ISPE, ISPOR, ASA working groups, AMIA, clinical specialty societies (ASCO, AUA, AHA's scientific arm) | |
| `Patient advocacy` | Disease foundations and patient organisations (e.g. LUNGevity, Crohn's & Colitis Foundation), plus nonprofits that advocate for patients and consumers (e.g. NCHR) | |
| `Other / anonymous` | Government, payers, anonymous or unidentifiable individuals, members of the public, anything else you can't classify | |

## Rules

1. **Order of evidence.** Use the `organization` field first. If it is empty (it is empty on every FDA comment checked so far), use the **title**, then the **letterhead or signature** in the attachment, then the body text. The API's `category` field is self-reported and often wrong, so treat it as weak supporting evidence only and never as the sole basis.
2. **One bucket per submitter.** If an organisation submitted more than once, record one submitter row linked to all of its comment IDs.
3. **Joint letters.** Use the lead signatory's organisation. Note the co-signers in `basis`.
4. **Individuals.** A named person writing in a professional capacity, with an affiliation stated in the letter, takes the affiliation's bucket. A named person with no affiliation goes to `Academic / independent` if the letter is substantive and technical, and to `Other / anonymous` otherwise. "Anonymous" always goes to `Other / anonymous`.
5. **Confidence.** `high` means the name alone decides the bucket. `medium` means you needed the letterhead or content. `low` means plausible alternatives remain. **Every `low` call goes to the human checkpoint** with its alternative bucket stated.
6. **Never guess from the name alone when it is ambiguous.** Read the attachment opening.

## Output

Write JSON to `output/<docket>/submitters.json`:

```json
{"submitters": [{"submitter_id": "S01", "name": "PhRMA", "bucket": "Trade association",
  "basis": "title + letterhead", "confidence": "high", "alternative": null,
  "comment_ids": ["FDA-2020-D-2307-0063"], "notes": ""}]}
```

`submitter_id` values are stable and assigned in order of first comment ID. `basis` names the evidence actually used, e.g. "title", "letterhead", "signature block", "body text" or "category field (weak)".

## Checkpoint presentation

Show the human:
- a count per bucket
- the full submitter table, sorted by bucket
- the `low`-confidence rows separately, each with its alternative bucket, for them to resolve

Record their resolutions in `decisions/<docket>.json` (`checkpoint: 2`).
