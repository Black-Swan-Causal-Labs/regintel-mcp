# Repeat review (JDD rule, 1 Oct 2026)

Within ONE comment, a point that is reiterated counts ONCE, unless a later instance makes a genuinely
section-specific point (a different recommendation or a different target in the guidance). Same
request restated in the cover letter, the summary and the line table counts once. The same request
applied to several sections purely as reiteration counts once. Different asks that merely share
boilerplate wording ("X recommends that the Agency clarify…") are NOT repeats.

For each comment in your list:
1. Read its asks in output/FDA-2020-D-2307/asks.json and the full comment text in
   output/FDA-2020-D-2307/corpus.jsonl (body + attachments[].text). Use the surrounding text, not just
   the span, to see what each ask actually requests.
2. Group true repeats. Keep the most specific instance (the one with a stated draft_section and the
   clearest wording); the rest are dropped.
3. Spans under ~12 words that don't convey the request on their own: propose `span_extended`, a
   LONGER contiguous run copied exactly from the extracted text (must contain the original span or
   sit right next to it in the same row/paragraph; whitespace-only differences allowed). Never repair or
   reconstruct text.

Write ONLY your output file (named in your prompt):
{"duplicates": [{"keep": "<ask_id>", "drop": ["<ask_id>", ...], "reason": "<one line>"}],
 "span_extensions": [{"ask_id": "<ask_id>", "span_extended": "<verbatim>"}]}

Before finishing, verify every span_extended is verbatim with:
.venv/bin/python -c "import json,re,sys;ws=lambda s:re.sub(r'\s+',' ',s or '').strip();T={(c:=json.loads(l))['commentId']:ws(' '.join([c['body']]+[a['text'] or '' for a in c['attachments']])) for l in open('output/FDA-2020-D-2307/corpus.jsonl')};o=json.load(open(sys.argv[1]));b=[e['ask_id'] for e in o['span_extensions'] if ws(e['span_extended']) not in T[e['ask_id'].rsplit('-',1)[0]]];print(b or 'OK')" <your output file>
Fix any listed ask_id. Do not modify any other file.
