"""regintel-mcp: regulations.gov docket retrieval as MCP tools (stdio).

Retrieval lives here. Judgment lives in the skills. Every tool reads the
local cache first and touches the network only on a miss or refresh=True.
"""
from __future__ import annotations

import functools
import json
import sys

from mcp.server.fastmcp import FastMCP

from .client import ApiError
from .config import MissingKeyError
from .service import Service

mcp = FastMCP("regintel")
_svc: Service | None = None


def svc() -> Service:
    global _svc
    if _svc is None:
        _svc = Service()
    return _svc


def _safe(fn):
    """Turn expected failures into JSON errors instead of protocol errors."""
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except (ApiError, MissingKeyError, ValueError) as e:
            return {"error": type(e).__name__, "message": str(e)}
    return wrapper


@mcp.tool()
@_safe
def search_dockets(query: str, agency: str = "FDA", docket_type: str | None = None,
                   limit: int = 25, refresh: bool = False) -> dict:
    """Search regulations.gov dockets by keyword. docket_type: 'Rulemaking' or 'Nonrulemaking'
    (FDA guidance dockets are Nonrulemaking). Returns docketId, title, docketType, lastModified."""
    return svc().search_dockets(query, agency, docket_type, limit, refresh)


@mcp.tool()
@_safe
def get_docket(docket_id: str, refresh: bool = False) -> dict:
    """Docket metadata plus the total number of public comments (e.g. 'FDA-2020-D-2307')."""
    return svc().get_docket(docket_id, refresh)


@mcp.tool()
@_safe
def list_documents(docket_id: str, refresh: bool = False) -> dict:
    """Documents in a docket (Federal Register notices, draft/final guidance, meeting material) with
    documentType, subtype, postedDate and every downloadable file URL. Use it to locate the draft
    guidance, the final guidance, and the notices of availability."""
    return svc().list_documents(docket_id, refresh)


@mcp.tool()
@_safe
def list_comments(docket_id: str, include_withdrawn: bool = False, refresh: bool = False) -> dict:
    """All public comments in a docket (pagination handled). Each row: commentId, title, postedDate,
    submitterName, and — once build_corpus has run — has_attachment, is_stub (body < 50 chars and no
    attachment) and duplicate_of (same submitter, near-identical text). Flags never drop rows."""
    return svc().list_comments(docket_id, include_withdrawn, refresh)


@mcp.tool()
@_safe
def get_comment(comment_id: str, refresh: bool = False, max_chars: int | None = None) -> dict:
    """One comment in full: body text, submitter fields (organization, name, category, location),
    attachment metadata and extracted attachment text. max_chars truncates long texts."""
    return svc().get_comment(comment_id, refresh, max_chars)


@mcp.tool()
@_safe
def build_corpus(docket_id: str, with_attachments: bool = True, refresh: bool = False,
                 max_comments: int | None = None) -> dict:
    """Pull every comment and attachment of a docket into the local cache and extract attachment text.
    Resumable: anything already cached is skipped, so re-running finishes an interrupted pull.
    max_comments caps new detail fetches per call. Returns counts of comments, attachments,
    extraction outcomes, OCR needs, stubs, duplicate groups and itemised failures."""
    return svc().build_corpus(docket_id, with_attachments, refresh, max_comments)


@mcp.tool()
@_safe
def get_guidance_text(ref: str, refresh: bool = False, include_full_text: bool = False) -> dict:
    """Plain text of a guidance document, split into sections by its numbered headings
    (I./A./1.). ref is a regulations.gov document id (e.g. 'FDA-2020-D-2307-0002') or a URL
    (an fda.gov guidance page or a /media/<id>/download PDF)."""
    return svc().get_guidance_text(ref, refresh, include_full_text)


@mcp.tool()
@_safe
def diff_guidance(draft_ref: str, final_ref: str, include_text: bool = True,
                  write_to: str | None = None) -> dict:
    """Section-aligned draft-vs-final diff. For each section: section_id, heading, status
    (added/removed/modified/unchanged), draft_text, final_text, paragraph_changes (incl. paragraphs
    moved between sections) and change_summary_stats. Refs as in get_guidance_text. write_to
    saves the full diff as JSON (relative paths resolve to the repo) and returns a summary."""
    return svc().diff_guidance(draft_ref, final_ref, include_text, write_to)


@mcp.tool()
@_safe
def export_corpus(docket_id: str, path: str | None = None) -> dict:
    """Write the cached corpus as JSONL (one full comment per line, with stub/duplicate flags) to
    output/<docket>/corpus.jsonl, for skills and subagents to read in batches."""
    return svc().export_corpus(docket_id, path)


def main() -> None:
    # CLI convenience for long pulls outside a chat:  python -m regintel_mcp build-corpus FDA-2020-D-2307
    if len(sys.argv) > 2 and sys.argv[1] == "build-corpus":
        print(json.dumps(svc().build_corpus(sys.argv[2]), indent=2))
        return
    mcp.run()


if __name__ == "__main__":
    main()
