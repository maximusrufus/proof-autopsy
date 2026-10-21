#!/usr/bin/env python3
"""Score answers against the proof-failure benchmark ground truth.

  python scorer.py answers.jsonl
  python scorer.py --example        # score the bundled toy file example_answers.jsonl

answers.jsonl: one JSON object per line: {"id": "W1", "verdict": "FLAW" | "NO-FLAW", ...}
Items with no valid answer are listed as unanswered and excluded from rates.
Rates (95% Wilson intervals):
  miss rate          = NO-FLAW on FLAWED-* items
  false-alarm rate   = FLAW on CORRECT items
  artefact suscept.  = FLAW on EXTRACTION-ARTIFACT items
  flag rate on clarifications = FLAW on REVISED-clarification items (not in the miss-rate denominator)
"""
import json, sys, glob, os, math, argparse
HERE = os.path.dirname(os.path.abspath(__file__))

def load_cases():
    return {os.path.basename(os.path.dirname(p)): json.load(open(p, encoding="utf-8"))
            for p in sorted(glob.glob(os.path.join(HERE, "items", "*", "case.json")))}

def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)

def fmt(name, k, n):
    if n == 0: return f"{name}: n/a (no items)"
    lo, hi = wilson(k, n)
    return f"{name}: {k}/{n} = {100*k/n:.1f}%  (95% Wilson CI {100*lo:.1f}-{100*hi:.1f}%)"

def score(cases, ans, out=print):
    miss = [0, 0]; fa = [0, 0]; art = [0, 0]; rev = [0, 0]; missing = []; detail = []
    for k, c in cases.items():
        a = ans.get(k)
        if a is None: missing.append(k); continue
        v = a.get("verdict"); g = c["ground_truth"]
        if v not in ("FLAW", "NO-FLAW"):
            out(f"  bad verdict for {k}: {v!r}"); missing.append(k); continue
        if g.startswith("FLAWED"): miss[1] += 1; miss[0] += v == "NO-FLAW"
        elif g == "REVISED-clarification": rev[1] += 1; rev[0] += v == "FLAW"
        elif g == "CORRECT": fa[1] += 1; fa[0] += v == "FLAW"
        elif g == "EXTRACTION-ARTIFACT": art[1] += 1; art[0] += v == "FLAW"
        detail.append((k, g, v))
    out("per item (id, ground truth, answer):")
    for d in detail: out("  %-14s %-20s %s" % d)
    out("")
    out(fmt("MISS RATE on flawed items", *miss))
    out(fmt("FALSE-ALARM RATE on correct items", *fa))
    out(fmt("ARTEFACT SUSCEPTIBILITY (FLAW on extraction-artefact items)", *art))
    out(fmt("FLAG RATE on clarifications (FLAW on REVISED-clarification items)", *rev))
    if missing: out("unanswered/invalid: " + ", ".join(missing))
    return dict(miss=miss, false_alarm=fa, artefact=art, clarification=rev, missing=missing)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("answers", nargs="?"); ap.add_argument("--example", action="store_true")
    a = ap.parse_args()
    path = os.path.join(HERE, "example_answers.jsonl") if a.example else a.answers
    if not path: ap.error("give answers.jsonl or --example")
    ans = {}
    for ln in open(path, encoding="utf-8"):
        if ln.strip(): o = json.loads(ln); ans[o["id"]] = o
    score(load_cases(), ans)

if __name__ == "__main__":
    main()
