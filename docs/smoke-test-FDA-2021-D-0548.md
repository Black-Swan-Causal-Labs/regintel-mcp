# Smoke test: second docket, FDA-2021-D-0548

*Data Standards for Drug and Biological Product Submissions Containing Real-World Data* · run 3 Oct 2026

Acceptance criterion: "Works on a second docket without code changes."

## Retrieval layer (MCP server): passed, no code changes

| Step | Result |
|---|---|
| `get_docket` | 30 comments, Nonrulemaking |
| `build_corpus` | 30/30 comments; 22 attachments (21 PDF, 1 DOCX); 22/22 extracted; 0 need OCR; 0 failures; 53 network calls, about 1 minute |
| Flags | 1 stub (`-0004`); 1 likely duplicate pair (CDISC `-0025`/`-0026`); no FDA-merged duplicates |
| `list_documents` | Draft `-0002` (22 Oct 2021), final `-0037` (22 Dec 2023), NOAs `-0001`/`-0036`, extension notice `-0011` |
| `diff_guidance` | 11 sections aligned: 9 modified, 1 unchanged, Glossary removed (the same pattern as FDA-2020-D-2307) |

## Found and fixed (outside the server's core tools)

1. **Unnumbered heading IDs.** "APPENDIX: EXAMPLES OF MAPPING…" became a very long section ID. IDs for unnumbered headings now use the first word (`APPENDIX`, `REFERENCES`, `GLOSSARY`). Parser version bumped to 2. FDA-2020-D-2307 IDs are unchanged.
2. **Overview extraction** (`scripts/build_analysis.py`) had been written around phrases from the first docket's notices. It now uses standard Federal Register sections:
   - **Summary:** the SUMMARY paragraph (its first, title-repeating sentence dropped).
   - **Timeline:** every notice in the docket, including comment-period extensions.
   - **Changes:** numbered and unnumbered change lists are both handled.
   - **Scope:** the topic list is optional, and Docket Lens hides it when absent.

## Not yet run

The judgment steps (submitter taxonomy, codebook, coding, concordance) need the four human checkpoints. The corpus is exported to `output/FDA-2021-D-0548/corpus.jsonl` and ready for `/docket-analysis`.
