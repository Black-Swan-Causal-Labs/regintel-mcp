#!/usr/bin/env python3
"""Agreement between Claude's codes (asks.json) and the blind second coder (jev_codes.jsonl).

    python scripts/coder_agreement.py FDA-2020-D-2307 [FDA-2021-D-0548 ...]

Per docket: percent agreement and Cohen's kappa (with a bootstrap 95% CI) for theme and stance, per-theme
agreement, the most frequent theme confusions, and every disagreement ranked by Jev's confidence.
Writes output/<docket>/coder_agreement.json. Asks Claude coded T99 have no Jev counterpart and are reported apart.
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def kappa(pairs):
    n = len(pairs)
    if not n:
        return None
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def boot_ci(pairs, reps=2000, seed=20261004):
    rng = random.Random(seed)
    ks = sorted(kappa([rng.choice(pairs) for _ in pairs]) for _ in range(reps))
    return ks[int(0.025 * reps)], ks[int(0.975 * reps) - 1]


def summarize(pairs):
    k = kappa(pairs)
    lo, hi = boot_ci(pairs)
    return {"n": len(pairs), "agree": sum(a == b for a, b in pairs),
            "pct_agree": round(sum(a == b for a, b in pairs) / len(pairs), 3),
            "kappa": round(k, 3), "kappa_ci95": [round(lo, 3), round(hi, 3)]}


def main(docket):
    out = ROOT / "output" / docket
    asks = {a["ask_id"]: a for a in json.loads((out / "asks.json").read_text())["asks"]}
    jev = {j["ask_id"]: j for j in map(json.loads, (out / "jev_codes.jsonl").read_text().splitlines())}
    labels = {t["theme_id"]: t["label"] for t in json.loads((out / "codebook.json").read_text())["themes"]}
    t99 = [a for a in asks if asks[a]["theme_id"] == "T99"]
    ids = [a for a in asks if a in jev and a not in t99]
    th = [(asks[a]["theme_id"], jev[a]["jev_theme"]) for a in ids]
    st = [(asks[a]["stance"], jev[a]["jev_stance"]) for a in ids]

    per_theme = {}
    for t in sorted(labels):
        rows = [(c, j) for c, j in th if c == t]
        if rows:
            per_theme[t] = {"label": labels[t], "n_claude": len(rows), "agree": sum(c == j for c, j in rows),
                            "n_jev": sum(j == t for _, j in th)}
    confusions = Counter((c, j) for c, j in th if c != j).most_common(12)
    dis = []
    for a in ids:
        A, J = asks[a], jev[a]
        if A["theme_id"] != J["jev_theme"] or A["stance"] != J["jev_stance"]:
            dis.append({"ask_id": a, "claude_theme": A["theme_id"], "jev_theme": J["jev_theme"],
                        "jev_theme_confidence": J["jev_theme_confidence"],
                        "jev_prob_of_claude_theme": J["jev_theme_probabilities"].get(A["theme_id"]),
                        "claude_stance": A["stance"], "jev_stance": J["jev_stance"],
                        "jev_stance_confidence": J["jev_stance_confidence"],
                        "claude_confidence": A.get("confidence"), "span": A["source_span"][:300]})
    dis.sort(key=lambda d: -max(d["jev_theme_confidence"] if d["claude_theme"] != d["jev_theme"] else 0,
                                d["jev_stance_confidence"] if d["claude_stance"] != d["jev_stance"] else 0))
    tok = [j["usage"]["input_tokens"] for j in jev.values() if j.get("usage") and j["usage"]["input_tokens"]]
    res = {"docket_id": docket, "second_coder": sorted({j["model"] for j in jev.values()}),
           "n_asks": len(asks), "n_compared": len(ids), "n_t99_excluded": len(t99),
           "theme": summarize(th), "stance": summarize(st),
           "theme_and_stance_both_agree": sum(asks[a]["theme_id"] == jev[a]["jev_theme"] and asks[a]["stance"] == jev[a]["jev_stance"] for a in ids),
           "theme_agreement_by_claude_confidence": {c: summarize([(asks[a]["theme_id"], jev[a]["jev_theme"]) for a in ids if asks[a].get("confidence") == c])
                                                    for c in ("high", "medium", "low") if sum(asks[a].get("confidence") == c for a in ids) > 5},
           "per_theme": per_theme,
           "top_theme_confusions": [{"claude": c, "jev": j, "n": n} for (c, j), n in confusions],
           "stance_confusions": [{"claude": c, "jev": j, "n": n} for (c, j), n in Counter((c, j) for c, j in st if c != j).most_common()],
           "jev_input_tokens_total": sum(tok),
           "disagreements": dis}
    (out / "coder_agreement.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(f"\n== {docket}  (Claude vs {', '.join(res['second_coder'])}; n={len(ids)}, T99 excluded {len(t99)})")
    for k in ("theme", "stance"):
        s = res[k]
        print(f"  {k:6} agree {s['agree']}/{s['n']} = {100 * s['pct_agree']:.1f}%   kappa {s['kappa']:.2f} (95% CI {s['kappa_ci95'][0]:.2f}–{s['kappa_ci95'][1]:.2f})")
    print("  theme agreement by Claude confidence:", {c: f"{100 * v['pct_agree']:.0f}% (n={v['n']})" for c, v in res["theme_agreement_by_claude_confidence"].items()})
    print("  per theme (Claude n → % Jev agrees; Jev total n):")
    for t, v in per_theme.items():
        print(f"    {t} {v['label'][:48]:48} {v['n_claude']:4} → {100 * v['agree'] / v['n_claude']:3.0f}%   (Jev {v['n_jev']})")
    print("  top theme confusions (Claude→Jev):", ", ".join(f"{d['claude']}→{d['jev']} {d['n']}" for d in res["top_theme_confusions"][:8]))
    print("  stance confusions:", "; ".join(f"{d['claude']}→{d['jev']} {d['n']}" for d in res["stance_confusions"][:5]))
    print(f"  disagreements (theme or stance): {len(dis)};  Jev input tokens {sum(tok):,}")


if __name__ == "__main__":
    for d in sys.argv[1:]:
        main(d)
