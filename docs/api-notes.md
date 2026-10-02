# regulations.gov API v4: verified behaviour

First contact: **1 Oct 2026**, live key, docket `FDA-2020-D-2307` (plus metadata checks on `FDA-2021-D-0548`).
Each row records what the build spec assumed and what the live API actually did.

| # | Spec assumption | Verified behaviour | Consequence in code |
|---|---|---|---|
| 1 | Base URL `https://api.regulations.gov/v4` | Confirmed. The key works as the `X-Api-Key` header. | The key goes in the header only, never in a URL, so it can't leak into logs or cache keys. |
| 2 | Rate limit per key, hourly *(verify)* | `x-ratelimit-limit: 1000` per hour, with a `x-ratelimit-remaining` header on every response. | 1 s minimum spacing. Exponential backoff on 429/5xx (uses `Retry-After` when present). `ratelimit_remaining` is reported back. |
| 3 | `403` = bad/missing key | Not triggered. Handled as a hard failure (not retried). | `AuthError`. |
| 4 | List endpoint has metadata only | Confirmed. Attributes: `agencyId, documentType, highlightedContent, lastModifiedDate, objectId, postedDate, title, withdrawn`. No body. | One detail call per comment. |
| 5 | Detail needs `include=attachments` *(verify)* | Confirmed. Attachments come back in `included[]` as `type: attachments` with `docOrder`, `title`, `fileFormats[]`. | — |
| 6 | Attachment URLs in `fileFormats[].fileUrl` *(verify)* | Confirmed, e.g. `https://downloads.regulations.gov/FDA-2020-D-2307-0003/attachment_1.pdf`, each with `format` and `size`. One attachment can offer several formats. | Only the preferred format is downloaded (pdf > docx > …). The others are recorded in `other_formats`. |
| 7 | File host access | `downloads.regulations.gov` doesn't use the API key. In earlier BSCL work it returned 403 without a browser User-Agent and a regulations.gov Referer. | Downloads are sent with those headers and no key. 0 failures out of 52. |
| 8 | Detail has `organization`, `firstName`, `lastName`, `category` *(verify)* | **`organization` is null on all 60 FDA comments, and so are `firstName`/`lastName`.** `category` is filled in on 36/60 but self-reported and often wrong (Datavant and the ASA Estimands WG are "Drug Industry"; one individual is "Food Industry"). **The submitter's name only appears in `title`** ("Comment from PhRMA"). | Submitter name comes from the title. `submitter-taxonomy` must treat `category` as weak evidence and rely on the title and the attachment letterhead. |
| 9 | List `title` may be truncated | No. The full title is returned (max seen: 98 chars). | — |
| 10 | Pagination ceiling ~250 × 20 | `page[size]` 250 accepted. `meta` has `totalElements`, `hasNextPage`, `totalPages`. | `get_all` stops on `hasNextPage=false` and flags `ceiling_hit` at 20 pages. For dockets over 5,000 comments, split by `postedDate`. |
| 11 | `filter[docketId]` gets all comments | Confirmed: 60. Comments attach to **four different documents**: draft guidance `-0002` (41), NOA `-0001` (6), the extension notice `-0052` (11), and the final guidance `-0067` (2, posted 11 Jun 2026). Filtering on `commentOnId` would silently drop comments. | Always filter by docket. `commentOnDocumentId` is kept on each comment. |
| 12 | Comments posted Nov 2021 – Jan 2022 | Mostly. The range is actually 1 Oct 2021 – 28 Feb 2022, **plus two comments from 11 Jun 2026** (`-0068`, `-0069`, same individual, near-identical text) on the *final* guidance. | Pass them to the human checkpoint. They can't affect draft→final. |
| 13 | — | `duplicateComments` on the detail record = how many identical submissions the agency merged into this record (1 = itself). Here 3 records stand for 3, 5 and 15 submissions → **80 submissions behind 60 records.** | Reported as `n_submissions_represented` / `agency_collapsed_duplicates`. |
| 14 | — | `withdrawn`: 0 in this docket, so it's not yet confirmed whether withdrawn comments stay in docket-filtered lists. | `include_withdrawn` filter is in place. Re-check on a docket that has withdrawals. |
| 15 | Draft/final guidance located via `list_documents` | Both are in the docket as `documentType: Other, subtype: Guidance`, with the PDF as attachment 1: draft `-0002` (30 Sep 2021), final `-0067` (25 Jul 2024). The NOAs (`-0001`, `-0066`) carry `content.pdf` + `content.htm`. | `get_guidance_text` accepts document IDs. For notices it prefers the HTML version, because the FR PDF is 3-column. |
| 16 | Final source = FDA guidance page | The fda.gov page now serves `/media/152503/download`. It is **not identical** to the docket's Jul 2024 PDF: in §V.E.2, "age, gender, race" became "age, sex, race", so the page was edited after publication. | **Final of record = fda.gov copy (`/media/152503/download`), per JDD 1 Oct 2026.** The one-word post-publication edit vs docket `-0067` is noted in outputs. |
| 17 | Attachments are PDFs | 51 PDFs + **1 XLSX** (ISPE's comment matrix, `-0013`). One consumer comment (`-0003`) attaches 92 pages of reference documents (CFR text and similar), not commentary. | XLSX extractor added. `-0003` is passed to the checkpoint. |
| 18 | Scanned PDFs | 0 of 52 needed OCR (text layer under 100 chars/page). | `needs_ocr` flag is in place, no OCR in v1. |

## Guidance PDF conventions (FDA, 2021–2024)

* The draft has **line numbers in the left margin**. The final does not. Numbering is detected (over 40% of lines start with an integer) and stripped. A bare margin number marks a blank line, i.e. a paragraph break.
* Body text is 12 pt Times. Footnotes are 10 pt, superscripts 6.5–8 pt, running headers 10–12 pt. Text below 95% of the dominant size is dropped, so **footnotes are excluded from the diff**.
* Headings: Roman numerals in bold caps (level 1), letters in bold (level 2), numbers in bold-italic (level 3). Italic numbered lines that are *not* under a lettered heading are emphasised list items, not headings.
* The final drops the Roman numeral on `REFERENCES`. Unnumbered bold all-caps lines count as level-1 headings.
