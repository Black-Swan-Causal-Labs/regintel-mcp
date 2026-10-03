# FDA-2020-D-2307: who commented, what they asked, what changed

*Real-World Data: Assessing EHR and Medical Claims Data* · draft 30 Sep 2021 → final Jul 2024 · run 2026-10-03 · codebook v1

> **Concordance, not impact. These calls record whether the final guidance text moved in the direction a commenter asked for. Changes between draft and final also reflect FDA's internal review, ICH M14, other guidances, and evolving science. A matching change does not show that a comment caused it.**

## Who commented

60 comments (80 submissions counting FDA-merged duplicates) from 59 submitters.

| Submitter type | Submitters | Requests coded |
|---|---|---|
| CRO / data & tech vendor | 16 | 201 |
| Other / anonymous | 12 | 16 |
| Pharma / biotech | 7 | 151 |
| Professional society | 7 | 239 |
| Academic / independent | 6 | 150 |
| Trade association | 6 | 434 |
| Patient advocacy | 5 | 20 |

## What they asked for

1211 discrete requests, each quoted verbatim. Stance: requests more specificity 921, requests more flexibility 220, supports as written 39, objects 31.

| Theme | Requests | Submitters raising it | Adopted or partial (of assessable) |
|---|---|---|---|
| Data provenance, traceability & quality assurance | 85 | 28 | 16% |
| Data relevance, fit for purpose & representativeness | 172 | 37 | 49% |
| Methodology: validation, study design & analytic methods | 320 | 35 | 41% |
| Missing data & data completeness | 55 | 26 | 26% |
| Linkage & tokenization | 42 | 27 | 26% |
| Data access, roles of data holders, retention & auditability | 70 | 22 | 9% |
| Proportionality, sponsor burden & feasibility | 87 | 24 | 44% |
| Terminology & definitional clarity | 98 | 21 | 35% |
| Alignment with other guidance & data standards | 73 | 25 | 0% |
| FDA engagement & implementation support | 110 | 29 | 28% |
| Privacy & data governance | 20 | 13 | 12% |
| Scope & data types | 79 | 29 | 18% |

## What changed, and whether it matched the requests

Section-aligned diff: 37 sections modified, 3 added (validation split into IV.D.1–3), 1 removed (Glossary), 2 unchanged.

Of 1211 requests, 180 concern process or things outside the text (not assessable). Of the 1031 assessable: **143 adopted (14%), 198 partially adopted (19%), 690 not adopted (67%).**

112 adopted/partial calls fall on one of the four changes FDA itself listed in the Federal Register.

| Submitter type | Adopted or partial (of assessable) |
|---|---|
| CRO / data & tech vendor | 35% (n=163) |
| Other / anonymous | 38% (n=13) |
| Pharma / biotech | 30% (n=118) |
| Professional society | 33% (n=217) |
| Academic / independent | 38% (n=130) |
| Trade association | 32% (n=378) |
| Patient advocacy | 8% (n=12) |

**Reading:** FDA moved most on how much validation is needed and on data relevance; least on data access/vendor roles, data standards and harmonisation with ICH E9(R1). Requests for estimands, target trial emulation, immortal-time bias and DAGs do not appear in the final. Adoption rates vary little by submitter type.

## Method and checks

- **Retrieval (deterministic):** regintel-mcp pulled the docket via the regulations.gov API, extracted the attachment text (one decoded-glyph PDF, one XLSX, no OCR needed), and diffed draft vs final section by section.
- **Judgment (Claude + skills, human-gated):** submitter classification → codebook (approved before any coding) → requests coded by 6 parallel subagents → repeats merged under JDD's rule (1,265 → 1,211) → concordance by 6 parallel subagents.
- **Verification:** every request quote is verbatim in the comment text, and every evidence quote is verbatim in the final guidance (scripted checks). Table-layout comments also carry a reading-order quote recovered from the PDF table cells.
- **Human spot check:** JDD reviewed 55 calls from a seeded random sample. Agreement **91%** (Wilson 95% CI 80–96%). Disagreements ran in both directions; corrections applied.
- **Exclusions:** 2 comments posted in 2026 against the final (excluded from draft→final). One comment attaching only third-party reference documents (counted, zero requests).
- **Final of record:** Current fda.gov copy (JDD decision). Identical to the Jul 2024 docket copy (FDA-2020-D-2307-0067) except a later edit in V.E.2: 'age, gender, race' -> 'age, sex, race'.
- **Limitations:** footnotes and figure contents are not in the compared text (5 requests not assessable for this reason). Request counts reflect letter length: BIO alone accounts for 232 requests.

Full decision log: `decisions/FDA-2020-D-2307.json`. Data: `analysis.json`.
