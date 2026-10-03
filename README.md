# regintel-mcp

**Regulatory intelligence from FDA regulations.gov dockets:** who commented, what they asked for, and what changed between the draft and final guidance.

Black Swan Causal Labs · [blackswancausallabs.com](https://blackswancausallabs.com)

> **Retrieval lives in the MCP server. Judgment lives in skills. Humans sit at the checkpoints.**

| Layer | Component | Status |
|---|---|---|
| Data | `regintel-mcp` server (this repo, MIT) | **Phase 1 built.** Fetch, cache, extract, diff. No interpretation. |
| Method | skills: `submitter-taxonomy`, `comment-theming`, `draft-final-concordance` | Built |
| Orchestration | `/docket-analysis <docketId>` with 4 human checkpoints | Built; first run on FDA-2020-D-2307 |
| Output | Docket Lens explorer (reads one `analysis.json`; PolyForm Noncommercial) | **Built** for FDA-2020-D-2307 |

## Install

Python 3.11 or later.

```bash
git clone https://github.com/Black-Swan-Causal-Labs/regintel-mcp.git
cd regintel-mcp
python3 -m venv .venv && .venv/bin/pip install -e .
cp .env.example .env    # then paste your key into .env
```

**API key:** get a free key at <https://open.gsa.gov/api/regulationsgov/> and put it in `.env` as `REGULATIONS_GOV_API_KEY=...`. `.env` is gitignored. The key is sent only as the `X-Api-Key` header and never appears in logs, the cache or any output. `DEMO_KEY` is fine for single lookups but too rate-limited for a full corpus pull. Personal keys allow 1,000 requests/hour.

**Register with an MCP client.** MCP is an open standard, so the server works with any compatible assistant (Claude, OpenAI Codex, others). For Claude Code, from the repo directory:

```bash
claude mcp add regintel-mcp -- "$(pwd)/.venv/bin/python" -m regintel_mcp
```

When installed as a Claude plugin, `.mcp.json` starts the server from the plugin root.

## Tools

Every tool reads the local SQLite cache (`data/cache.sqlite`) first. It only touches the network on a cache miss or when called with `refresh=true`.

| Tool | Does |
|---|---|
| `search_dockets(query, agency="FDA", docket_type?, limit=25)` | Keyword search over dockets |
| `get_docket(docket_id)` | Docket metadata and total comment count |
| `list_documents(docket_id)` | Notices, draft and final guidance, meeting material, with every file URL |
| `list_comments(docket_id, include_withdrawn=false)` | All comments, paginated internally. Flags `is_stub`, `duplicate_of` and `agency_duplicate_count` (flags only; nothing is dropped) |
| `get_comment(comment_id)` | Body, submitter fields, attachments and **extracted attachment text** |
| `build_corpus(docket_id, with_attachments=true)` | Pulls every comment and attachment into the cache. Resumable. Reports stubs, duplicates, OCR needs and failures |
| `get_guidance_text(ref)` | A guidance document (doc ID or URL) split into numbered sections |
| `diff_guidance(draft_ref, final_ref)` | Section-aligned draft-vs-final diff with paragraph changes and moved-paragraph detection |
| `export_corpus(docket_id)` | Writes `output/<docket>/corpus.jsonl` for skills and subagents |

For long pulls outside a chat: `.venv/bin/python -m regintel_mcp build-corpus FDA-2020-D-2307`.

**How the diff works:** the text layer is extracted with pdfplumber. Running headers, draft line numbers, footnotes and the table of contents are removed. Sections are split on the guidance's own Roman, letter and number headings, then matched draft→final by heading (parent-qualified first) and then by heading plus text similarity. Paragraphs are diffed within each matched section, and paragraphs that moved to a different section are labelled. Everything is deterministic: there are no model calls in the server.

API behaviour verified against the live service is recorded in [`docs/api-notes.md`](docs/api-notes.md).

## Docket Lens (the explorer)

**Docket Lens** (`explorer/template.html`) is a single page that reads one `analysis.json` and shows three linked views: who spoke, what they asked for (a themes × submitter-type heatmap that opens the verbatim requests), and what changed (draft vs final by section, with each request's call). Build a docket's copy with:

```bash
.venv/bin/python scripts/build_analysis.py FDA-2020-D-2307
.venv/bin/python scripts/build_explorer.py FDA-2020-D-2307
```

Then open `explorer/FDA-2020-D-2307/index.html` through any static server, e.g. `python3 -m http.server --directory explorer/FDA-2020-D-2307`. The explorer is licensed separately under PolyForm Noncommercial 1.0.0 (`explorer/LICENSE`, `explorer/NOTICE`).

## The concordance caveat

This tool measures **concordance, not impact.** Changes between draft and final guidance also come from FDA's internal review, ICH M14, other guidances and the evolving science. When the final text moves in the direction a commenter asked for, that does **not** show the comment caused the change. Every output from this project carries that caveat.

## License

Server: MIT (see `LICENSE`). The Explorer template is licensed separately under PolyForm Noncommercial 1.0.0.

© 2026 Black Swan Causal Labs · <https://blackswancausallabs.com>
