"""Tool implementations. Cache first; network only on a miss or refresh=True.

Everything here is retrieval and deterministic transformation. Nothing here
interprets what a comment means; that is the job of the skills.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin

from . import cache, config, guidance
from .client import ApiError, RegsGovClient
from .extract import extract, html_to_text

STUB_MAX_CHARS = 50
DUP_MIN_RATIO = 0.9
PREFERRED_FORMATS = ("pdf", "docx", "doc", "htm", "html", "txt", "rtf", "xlsx")


class Service:
    def __init__(self, client: RegsGovClient | None = None):
        self.client = client or RegsGovClient()
        self.con = cache.connect()

    # ------------------------------------------------------------ helpers
    def _cached_get(self, path: str, params: dict, refresh: bool) -> dict:
        key = cache.api_key_for(path, params)
        if not refresh:
            hit = cache.get_api(self.con, key)
            if hit is not None:
                return hit
        obj = self.client.get(path, params)
        cache.put_api(self.con, key, obj)
        return obj

    def _cached_get_all(self, path: str, params: dict, refresh: bool) -> tuple[list, dict]:
        key = cache.api_key_for(path + "#all", params)
        if not refresh:
            hit = cache.get_api(self.con, key)
            if hit is not None:
                return hit["data"], hit["meta"]
        data, meta = self.client.get_all(path, params)
        cache.put_api(self.con, key, {"data": data, "meta": meta})
        return data, meta

    @staticmethod
    def _docket_of(object_id: str) -> str:
        # FDA-2020-D-2307-0045 -> FDA-2020-D-2307
        return object_id.rsplit("-", 1)[0]

    # ------------------------------------------------------------- dockets
    def search_dockets(self, query: str, agency: str = "FDA", docket_type: str | None = None,
                       limit: int = 25, refresh: bool = False) -> dict:
        params = {"filter[searchTerm]": query, "page[size]": max(5, min(250, limit)),
                  "sort": "-lastModifiedDate"}
        if agency:
            params["filter[agencyId]"] = agency
        if docket_type:
            params["filter[docketType]"] = docket_type
        j = self._cached_get("dockets", params, refresh)
        rows = [{"docketId": d["id"], "title": d["attributes"].get("title"),
                 "docketType": d["attributes"].get("docketType"),
                 "lastModified": d["attributes"].get("lastModifiedDate")}
                for d in (j.get("data") or [])[:limit]]
        return {"query": query, "total": (j.get("meta") or {}).get("totalElements"), "dockets": rows}

    def get_docket(self, docket_id: str, refresh: bool = False) -> dict:
        row = self.con.execute("SELECT * FROM dockets WHERE docket_id=?", (docket_id,)).fetchone()
        if row and not refresh:
            d, total = json.loads(row["json"]), row["comment_total"]
        else:
            d = self.client.get(f"dockets/{docket_id}")
            c = self.client.get("comments", {"filter[docketId]": docket_id, "page[size]": 5})
            total = (c.get("meta") or {}).get("totalElements")
            self.con.execute("INSERT OR REPLACE INTO dockets VALUES (?,?,?,?)",
                             (docket_id, json.dumps(d), total, cache.now()))
            self.con.commit()
        a = d["data"]["attributes"]
        return {"docketId": docket_id, "title": _clean(a.get("title")), "agencyId": a.get("agencyId"),
                "docketType": a.get("docketType"), "abstract": _clean(a.get("dkAbstract")),
                "rin": a.get("rin"), "modifyDate": a.get("modifyDate"),
                "keywords": a.get("keywords"), "comment_count": total,
                "url": f"https://www.regulations.gov/docket/{docket_id}"}

    # ----------------------------------------------------------- documents
    def _document_detail(self, document_id: str, refresh: bool = False) -> dict:
        row = self.con.execute("SELECT detail_json FROM documents WHERE document_id=?", (document_id,)).fetchone()
        if row and row["detail_json"] and not refresh:
            return json.loads(row["detail_json"])
        det = self.client.get(f"documents/{document_id}", {"include": "attachments"})
        self.con.execute(
            "INSERT INTO documents(document_id, docket_id, detail_json, fetched_at) VALUES (?,?,?,?) "
            "ON CONFLICT(document_id) DO UPDATE SET detail_json=excluded.detail_json, fetched_at=excluded.fetched_at",
            (document_id, det["data"]["attributes"].get("docketId") or self._docket_of(document_id),
             json.dumps(det), cache.now()))
        self.con.commit()
        return det

    @staticmethod
    def _file_urls(detail: dict) -> list[dict]:
        out = []
        for f in detail["data"]["attributes"].get("fileFormats") or []:
            out.append({"source": "content", "title": None, "format": f.get("format"), "url": f.get("fileUrl")})
        for inc in detail.get("included") or []:
            a = inc.get("attributes", {})
            for f in a.get("fileFormats") or []:
                out.append({"source": f"attachment {a.get('docOrder')}", "title": a.get("title"),
                            "format": f.get("format"), "url": f.get("fileUrl")})
        return out

    def list_documents(self, docket_id: str, refresh: bool = False) -> dict:
        data, _ = self._cached_get_all("documents", {"filter[docketId]": docket_id, "sort": "postedDate"}, refresh)
        out = []
        for d in data:
            a = d["attributes"]
            self.con.execute(
                "INSERT INTO documents(document_id, docket_id, list_json, fetched_at) VALUES (?,?,?,?) "
                "ON CONFLICT(document_id) DO UPDATE SET list_json=excluded.list_json",
                (d["id"], docket_id, json.dumps(d), cache.now()))
            det = self._document_detail(d["id"], refresh)
            da = det["data"]["attributes"]
            out.append({"documentId": d["id"], "title": _clean(a.get("title")),
                        "documentType": a.get("documentType"), "subtype": da.get("subtype"),
                        "postedDate": a.get("postedDate"), "commentStartDate": da.get("commentStartDate"),
                        "commentEndDate": da.get("commentEndDate"), "frDocNum": da.get("frDocNum"),
                        "fileUrls": self._file_urls(det),
                        "url": f"https://www.regulations.gov/document/{d['id']}"})
        self.con.commit()
        return {"docketId": docket_id, "n_documents": len(out), "documents": out}

    # ------------------------------------------------------------ comments
    def _comment_index(self, docket_id: str, refresh: bool) -> list[dict]:
        data, meta = self._cached_get_all("comments", {"filter[docketId]": docket_id, "sort": "postedDate"}, refresh)
        for c in data:
            self.con.execute(
                "INSERT INTO comments(comment_id, docket_id, list_json, listed_at) VALUES (?,?,?,?) "
                "ON CONFLICT(comment_id) DO UPDATE SET list_json=excluded.list_json, listed_at=excluded.listed_at",
                (c["id"], docket_id, json.dumps(c), cache.now()))
        self.con.commit()
        if meta.get("ceiling_hit"):
            data.append({"_warning": "page ceiling hit (~5,000 records); split the query by postedDate"})
        return data

    def _comment_detail(self, comment_id: str, refresh: bool = False) -> dict:
        row = self.con.execute("SELECT detail_json FROM comments WHERE comment_id=?", (comment_id,)).fetchone()
        if row and row["detail_json"] and not refresh:
            return json.loads(row["detail_json"])
        det = self.client.get(f"comments/{comment_id}", {"include": "attachments"})
        self.con.execute(
            "INSERT INTO comments(comment_id, docket_id, detail_json, detail_fetched_at) VALUES (?,?,?,?) "
            "ON CONFLICT(comment_id) DO UPDATE SET detail_json=excluded.detail_json, "
            "detail_fetched_at=excluded.detail_fetched_at",
            (comment_id, det["data"]["attributes"].get("docketId") or self._docket_of(comment_id),
             json.dumps(det), cache.now()))
        self.con.commit()
        return det

    def _attachments_for(self, parent_id: str, detail: dict, docket_id: str, download: bool,
                         refresh: bool = False) -> list[dict]:
        """Download + extract each attachment once (preferred format only). Cached by parent#docOrder."""
        out = []
        for inc in detail.get("included") or []:
            a = inc.get("attributes", {})
            fmts = a.get("fileFormats") or []
            order = a.get("docOrder")
            key = f"{parent_id}#{order}"
            row = self.con.execute("SELECT * FROM attachments WHERE attachment_key=?", (key,)).fetchone()
            if row and (row["extraction_ok"] is not None or row["error"]) and not refresh:
                out.append(dict(row))
                continue
            if not fmts:
                rec = {"attachment_key": key, "parent_id": parent_id, "docket_id": docket_id,
                       "attachment_id": inc.get("id"), "doc_order": order, "title": a.get("title"),
                       "url": None, "format": None, "other_formats": "[]", "error":
                       f"no downloadable file ({a.get('restrictReasonType') or 'not published'})",
                       "extraction_ok": 0, "needs_ocr": 0, "fetched_at": cache.now()}
                self._put_attachment(rec)
                out.append(rec)
                continue
            fmts = sorted(fmts, key=lambda f: PREFERRED_FORMATS.index(f.get("format"))
                          if f.get("format") in PREFERRED_FORMATS else 99)
            chosen = fmts[0]
            rec = {"attachment_key": key, "parent_id": parent_id, "docket_id": docket_id,
                   "attachment_id": inc.get("id"), "doc_order": order, "title": a.get("title"),
                   "url": chosen.get("fileUrl"), "format": chosen.get("format"),
                   "other_formats": json.dumps([f.get("format") for f in fmts[1:]]),
                   "fetched_at": cache.now()}
            if not download:
                out.append(rec)
                continue
            try:
                path = config.RAW / docket_id / f"{parent_id}_att{order}.{chosen.get('format') or 'bin'}"
                if path.exists() and path.stat().st_size and not refresh:
                    data = path.read_bytes()
                else:
                    data, _ = self.client.download(rec["url"])
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                ex, kind = extract(data, chosen.get("format") or "")
                rec.update(local_path=str(path.relative_to(config.ROOT)), bytes=len(data), sniffed_type=kind,
                           page_count=ex.page_count, extracted_text=ex.text, extraction_method=ex.method,
                           extraction_ok=int(ex.ok), needs_ocr=int(ex.needs_ocr), error=ex.error)
            except ApiError as e:
                rec.update(extraction_ok=0, needs_ocr=0, error=str(e))
            self._put_attachment(rec)
            out.append(rec)
        return out

    def _put_attachment(self, rec: dict) -> None:
        cols = ["attachment_key", "parent_id", "docket_id", "attachment_id", "doc_order", "title", "url",
                "format", "other_formats", "local_path", "bytes", "sniffed_type", "page_count",
                "extracted_text", "extraction_method", "extraction_ok", "needs_ocr", "error", "fetched_at"]
        self.con.execute(f"INSERT OR REPLACE INTO attachments({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                         [rec.get(c) for c in cols])
        self.con.commit()

    @staticmethod
    def _submitter(attrs: dict, list_title: str | None) -> dict:
        org = (attrs.get("organization") or "").strip()
        person = " ".join(x for x in [(attrs.get("firstName") or "").strip(),
                                      (attrs.get("lastName") or "").strip()] if x)
        from_title = re.sub(r"^Comment (submitted by|from)\s+", "", (attrs.get("title") or list_title or "")).strip()
        name = org or person or from_title or "Anonymous"
        return {"submitterName": name, "organization": org or None, "firstName": attrs.get("firstName"),
                "lastName": attrs.get("lastName"), "category": attrs.get("category"),
                "govAgency": attrs.get("govAgency"), "govAgencyType": attrs.get("govAgencyType"),
                "submitterRep": attrs.get("submitterRep"), "city": attrs.get("city"),
                "stateProvinceRegion": attrs.get("stateProvinceRegion"), "country": attrs.get("country"),
                "title": attrs.get("title") or list_title}

    def get_comment(self, comment_id: str, refresh: bool = False, max_chars: int | None = None) -> dict:
        det = self._comment_detail(comment_id, refresh)
        a = det["data"]["attributes"]
        docket_id = a.get("docketId") or self._docket_of(comment_id)
        atts = self._attachments_for(comment_id, det, docket_id, download=True, refresh=refresh)
        body = html_to_text(a.get("comment") or "")
        trunc = (lambda s: s if (s is None or max_chars is None or len(s) <= max_chars)
                 else s[:max_chars] + f"\n[... truncated; {len(s)} chars total]")
        return {
            "commentId": comment_id, "docketId": docket_id, "commentOnDocumentId": a.get("commentOnDocumentId"),
            "postedDate": a.get("postedDate"), "receiveDate": a.get("receiveDate"),
            "withdrawn": a.get("withdrawn"), "reasonWithdrawn": a.get("reasonWithdrawn"),
            "duplicateComments": a.get("duplicateComments"),
            "submitter": self._submitter(a, None),
            "body": trunc(body), "body_chars": len(body),
            "attachments": [{"docOrder": x.get("doc_order"), "title": x.get("title"), "url": x.get("url"),
                             "format": x.get("format"), "page_count": x.get("page_count"),
                             "extraction_method": x.get("extraction_method"),
                             "extraction_ok": bool(x.get("extraction_ok")), "needs_ocr": bool(x.get("needs_ocr")),
                             "error": x.get("error"), "text": trunc(x.get("extracted_text"))} for x in atts],
            "url": f"https://www.regulations.gov/comment/{comment_id}",
        }

    def _flags(self, docket_id: str) -> tuple[dict, list]:
        """Stub and duplicate flags for comments whose detail is cached. Flag, never drop."""
        rows = self.con.execute(
            "SELECT comment_id, list_json, detail_json FROM comments WHERE docket_id=? AND detail_json IS NOT NULL",
            (docket_id,)).fetchall()
        info = {}
        for r in rows:
            a = json.loads(r["detail_json"])["data"]["attributes"]
            lt = json.loads(r["list_json"])["attributes"].get("title") if r["list_json"] else None
            atts = self.con.execute("SELECT extracted_text, url FROM attachments WHERE parent_id=? ORDER BY doc_order",
                                    (r["comment_id"],)).fetchall()
            body = html_to_text(a.get("comment") or "")
            n_files = sum(1 for x in atts if x["url"])
            n_inc = len(json.loads(r["detail_json"]).get("included") or [])
            full = (body + "\n" + "\n".join(x["extracted_text"] or "" for x in atts)).strip()
            info[r["comment_id"]] = {"name": self._submitter(a, lt)["submitterName"], "body": body,
                                     "full": full, "has_attachment": bool(n_files or n_inc),
                                     "agency_duplicate_count": a.get("duplicateComments"),
                                     "is_stub": len(body) < STUB_MAX_CHARS and not (n_files or n_inc)}
        # Duplicates: same normalised submitter AND near-identical full text.
        groups, by_name = [], {}
        for cid, x in sorted(info.items()):
            by_name.setdefault(re.sub(r"[^a-z0-9]", "", x["name"].lower()), []).append(cid)
        for name, cids in by_name.items():
            if len(cids) < 2:
                continue
            seen = set()
            for i, c1 in enumerate(cids):
                grp = [c1]
                for c2 in cids[i + 1:]:
                    if c2 in seen:
                        continue
                    t1, t2 = info[c1]["full"][:6000], info[c2]["full"][:6000]
                    if t1 and t2 and difflib.SequenceMatcher(None, t1, t2, autojunk=False).ratio() >= DUP_MIN_RATIO:
                        grp.append(c2)
                if len(grp) > 1 and c1 not in seen:
                    seen.update(grp)
                    groups.append({"submitter": info[c1]["name"], "comment_ids": grp})
        for g in groups:
            for k, cid in enumerate(g["comment_ids"]):
                info[cid]["duplicate_of"] = g["comment_ids"][0] if k else None
                info[cid]["duplicate_group"] = g["comment_ids"]
        return info, groups

    def list_comments(self, docket_id: str, include_withdrawn: bool = False, refresh: bool = False) -> dict:
        idx = self._comment_index(docket_id, refresh)
        flags, groups = self._flags(docket_id)
        out, n_withdrawn = [], 0
        for c in idx:
            if "_warning" in c:
                continue
            a = c["attributes"]
            if a.get("withdrawn"):
                n_withdrawn += 1
                if not include_withdrawn:
                    continue
            f = flags.get(c["id"])
            out.append({"commentId": c["id"], "title": a.get("title"), "postedDate": a.get("postedDate"),
                        "withdrawn": a.get("withdrawn"),
                        "submitterName": f["name"] if f else re.sub(r"^Comment (submitted by|from)\s+", "", a.get("title") or ""),
                        "has_attachment": f["has_attachment"] if f else None,
                        "is_stub": f["is_stub"] if f else None,
                        "duplicate_of": f.get("duplicate_of") if f else None,
                        "agency_duplicate_count": f["agency_duplicate_count"] if f else None,
                        "url": f"https://www.regulations.gov/comment/{c['id']}"})
        return {"docketId": docket_id, "n_listed": len(idx), "n_withdrawn": n_withdrawn, "n_returned": len(out),
                "flags_available_for": len(flags), "duplicate_groups": groups,
                "note": None if len(flags) >= len(out) else
                "is_stub/duplicate flags need comment detail: run build_corpus first.",
                "comments": out}

    def build_corpus(self, docket_id: str, with_attachments: bool = True, refresh: bool = False,
                     max_comments: int | None = None) -> dict:
        """Pull every comment (+ attachments) into the cache. Resumable: cached items are skipped."""
        before = dict(self.client.stats)
        idx = [c for c in self._comment_index(docket_id, refresh) if "_warning" not in c]
        failures, fetched_now = [], 0
        for c in idx:
            cid = c["id"]
            have = self.con.execute("SELECT detail_json FROM comments WHERE comment_id=?", (cid,)).fetchone()
            if max_comments is not None and fetched_now >= max_comments and not (have and have["detail_json"]):
                continue
            try:
                if not (have and have["detail_json"]) or refresh:
                    fetched_now += 1
                det = self._comment_detail(cid, refresh)
                atts = self._attachments_for(cid, det, docket_id, download=with_attachments, refresh=refresh)
                for x in atts:
                    if x.get("error") or (with_attachments and not x.get("extraction_ok")):
                        failures.append({"commentId": cid, "attachment": x.get("doc_order"),
                                         "title": x.get("title"), "needs_ocr": bool(x.get("needs_ocr")),
                                         "error": x.get("error") or "no text extracted"})
            except ApiError as e:
                failures.append({"commentId": cid, "attachment": None, "error": str(e)})
        flags, groups = self._flags(docket_id)
        att = self.con.execute(
            "SELECT COUNT(*) n, SUM(extraction_ok) ok, SUM(needs_ocr) ocr, COUNT(DISTINCT parent_id) parents "
            "FROM attachments a JOIN comments c ON c.comment_id=a.parent_id WHERE c.docket_id=?", (docket_id,)).fetchone()
        methods = dict(self.con.execute(
            "SELECT COALESCE(extraction_method,'none'), COUNT(*) FROM attachments a JOIN comments c "
            "ON c.comment_id=a.parent_id WHERE c.docket_id=? GROUP BY 1", (docket_id,)).fetchall())
        n_withdrawn = sum(1 for c in idx if c["attributes"].get("withdrawn"))
        missing = [c["id"] for c in idx if c["id"] not in flags]
        return {
            "docketId": docket_id, "n_comments": len(idx), "n_withdrawn": n_withdrawn,
            "n_detail_cached": len(flags), "complete": not missing, "pending": missing[:50],
            "n_with_attachments": sum(1 for f in flags.values() if f["has_attachment"]),
            "n_attachment_files": att["n"] or 0, "n_attachments_extracted": att["ok"] or 0,
            "n_needs_ocr": att["ocr"] or 0, "extraction_methods": methods,
            # duplicateComments = identical submissions the agency collapsed into this record (1 = itself).
            "n_submissions_represented": sum((f["agency_duplicate_count"] or 1) for f in flags.values()),
            "agency_collapsed_duplicates": {cid: f["agency_duplicate_count"] for cid, f in flags.items()
                                            if (f["agency_duplicate_count"] or 1) > 1},
            "n_stubs": sum(1 for f in flags.values() if f["is_stub"]),
            "stubs": sorted(cid for cid, f in flags.items() if f["is_stub"]),
            "duplicate_groups": groups,
            "n_failed": len(failures), "failures": failures,
            "requests_this_call": {k: self.client.stats[k] - before.get(k, 0) for k in self.client.stats},
            "ratelimit_remaining": self.client.ratelimit_remaining,
        }

    # ------------------------------------------------------------ guidance
    def _resolve_guidance_file(self, ref: str) -> tuple[bytes, str, str]:
        """ref = document id or URL -> (bytes, source_url, local filename)."""
        if re.match(r"^[A-Z]+-\d{4}-[A-Z]+-\d+-\d+$", ref):
            det = self._document_detail(ref)
            files = self._file_urls(det)
            if not files:
                raise ValueError(f"{ref} has no downloadable file")
            notice = det["data"]["attributes"].get("documentType") in ("Notice", "Rule", "Proposed Rule")
            htm = [f for f in files if f["source"] == "content" and f["format"] in ("htm", "html")]
            if notice and htm:
                # Federal Register PDFs are 3-column; the HTML rendition sections cleanly.
                pick = htm[0]
            else:
                pdfs = [f for f in files if f["format"] == "pdf"] or files
                # Prefer an attachment titled like a guidance over cover/notice content.
                pick = next((f for f in pdfs if re.search(r"guidance", f.get("title") or "", re.I)), pdfs[0])
            url, docket = pick["url"], self._docket_of(ref)
            name = f"{ref}_{pick['source'].replace(' ', '')}.{pick['format']}"
        else:
            url, docket = ref, "_external"
            name = re.sub(r"[^A-Za-z0-9._-]+", "_", ref.split("://", 1)[-1])[:150]
        path = config.RAW / docket / name
        for cand in (path, path.with_name(path.name + ".pdf"), path.with_name(path.name + ".html")):
            if cand.exists() and cand.stat().st_size:
                return cand.read_bytes(), url, str(cand)
        data, ctype = self.client.download(url)
        if "html" in ctype and not data.startswith(b"%PDF"):
            # An FDA guidance landing page: follow its /media/<id>/download link.
            m = re.search(rb'href="([^"]*/media/\d+/download[^"]*)"', data)
            if m:
                url = urljoin(url, m.group(1).decode())
                data, ctype = self.client.download(url)
        if docket == "_external":
            path = path.with_name(path.name + (".pdf" if data.startswith(b"%PDF") else ".html"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return data, url, str(path)

    def _guidance(self, ref: str, refresh: bool = False) -> dict:
        row = self.con.execute("SELECT * FROM guidance_text WHERE ref=?", (ref,)).fetchone()
        if row and not refresh and row["parser_version"] == guidance.PARSER_VERSION:
            return {**dict(row), "sections": json.loads(row["sections_json"])}
        data, url, local = self._resolve_guidance_file(ref)
        ex, kind = extract(data, keep_lines=True)
        if kind == "pdf":
            sections = guidance.sectionize(guidance.clean_lines(ex.lines, ex.page_count or 1))
        else:
            sections = guidance.sectionize_plain_text(ex.text)
        rec = {"ref": ref, "source_url": url, "local_path": str(Path(local).relative_to(config.ROOT)),
               "page_count": ex.page_count, "extraction_method": ex.method, "text": ex.text,
               "sections_json": json.dumps(sections), "parser_version": guidance.PARSER_VERSION,
               "fetched_at": cache.now()}
        self.con.execute(f"INSERT OR REPLACE INTO guidance_text({','.join(rec)}) VALUES ({','.join('?' * len(rec))})",
                         list(rec.values()))
        self.con.commit()
        return {**rec, "sections": sections}

    def get_guidance_text(self, ref: str, refresh: bool = False, include_full_text: bool = False) -> dict:
        g = self._guidance(ref, refresh)
        return {"ref": ref, "source_url": g["source_url"], "local_path": g["local_path"],
                "page_count": g["page_count"], "extraction_method": g["extraction_method"],
                "n_sections": len(g["sections"]),
                "sections": [{k: s[k] for k in ("section_id", "level", "heading", "parent_heading", "text")}
                             for s in g["sections"]],
                **({"full_text": g["text"]} if include_full_text else {})}

    def diff_guidance(self, draft_ref: str, final_ref: str, include_text: bool = True,
                      write_to: str | None = None) -> dict:
        d, f = self._guidance(draft_ref), self._guidance(final_ref)
        rows = guidance.diff_sections(d["sections"], f["sections"], include_text=include_text)
        counts = {}
        for r in rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        out = {"draft": {"ref": draft_ref, "source_url": d["source_url"], "n_sections": len(d["sections"])},
               "final": {"ref": final_ref, "source_url": f["source_url"], "n_sections": len(f["sections"])},
               "method": "Sections split on Roman/lettered/numbered bold headings; aligned by parent-qualified "
                         "heading match, then heading+text similarity; paragraph diff within aligned sections; "
                         "paragraphs found in another section are labelled moved_in/moved_out. Footnotes are "
                         "excluded (font-size filter). Deterministic; no model calls.",
               "status_counts": counts, "sections": rows}
        if write_to:
            p = Path(write_to)
            p = p if p.is_absolute() else config.ROOT / p
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(out, indent=2))
            out = {k: v for k, v in out.items() if k != "sections"} | {
                "written_to": str(p), "sections": [{k: r[k] for k in ("section_id", "heading", "status")} for r in rows]}
        return out

    # ------------------------------------------------------------- export
    def export_corpus(self, docket_id: str, path: str | None = None) -> dict:
        """Write one JSONL row per comment (body + attachment text + flags) for the skills to read."""
        flags, _ = self._flags(docket_id)
        p = Path(path) if path else config.OUTPUT / docket_id / "corpus.jsonl"
        p = p if p.is_absolute() else config.ROOT / p
        p.parent.mkdir(parents=True, exist_ok=True)
        n = 0
        with open(p, "w") as fh:
            for cid in sorted(flags):
                c = self.get_comment(cid)
                c["is_stub"] = flags[cid]["is_stub"]
                c["duplicate_of"] = flags[cid].get("duplicate_of")
                c["text_hash"] = hashlib.sha1(flags[cid]["full"].encode()).hexdigest()[:12]
                fh.write(json.dumps(c) + "\n")
                n += 1
        return {"docketId": docket_id, "n_comments": n, "path": str(p)}


def _clean(s):
    return re.sub(r"\s+", " ", s).strip() if isinstance(s, str) else s
