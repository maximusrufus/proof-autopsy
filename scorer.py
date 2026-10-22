#!/usr/bin/env python3
"""Score answers against the proof-failure benchmark ground truth.

  python scorer.py answers.jsonl
  python scorer.py answers.jsonl --allow-partial   # accept unanswered items (exit 0 even if some are missing)
  python scorer.py --example        # score the bundled toy file example_answers.jsonl (partial on purpose)

answers.jsonl: one JSON object per line: {"id": "W1", "verdict": "FLAW" | "NO-FLAW", ...}
Every rate is printed with its coverage (answered items / items in that group). Items with no valid answer are listed
as unanswered and excluded from the rates, and the exit status is 1 unless --allow-partial is given.
Exit status: 0 complete (or --allow-partial / --example), 1 unanswered items, 2 malformed input (line-numbered errors).
Input rules: UTF-8 (a BOM is accepted); each non-blank line is one JSON object with a string "id"; a repeated id, a repeated
key inside one object, or a non-object line is an error; an id that is not a benchmark item is reported as a warning.
Rates (95% Wilson intervals):
  miss rate          = NO-FLAW on FLAWED-* items
  false-alarm rate   = FLAW on CORRECT items
  artefact suscept.  = FLAW on EXTRACTION-ARTIFACT items
  flag rate on clarifications = FLAW on REVISED-clarification items (not in the miss-rate denominator)
"""

import argparse
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load_cases():
    return {
        os.path.basename(os.path.dirname(p)): json.load(open(p, encoding="utf-8"))
        for p in sorted(glob.glob(os.path.join(HERE, "items", "*", "case.json")))
    }


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def fmt(name, k, n, total=None):
    """One rate line. `total` = number of benchmark items in the group, so coverage is shown next to the rate."""
    cov = "" if total is None else f"  [answered {n}/{total} items in this group]"
    if n == 0:
        return f"{name}: n/a (no answered items){cov}"
    lo, hi = wilson(k, n)
    return f"{name}: {k}/{n} = {100 * k / n:.1f}%  (95% Wilson CI {100 * lo:.1f}-{100 * hi:.1f}%){cov}"


def _no_dup_keys(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError(
            "repeated key in one JSON object: "
            + ", ".join(sorted({k for k in keys if keys.count(k) > 1}))
        )
    return dict(pairs)


def load_answers(path, known_ids=None):
    """-> (answers {id: object}, errors [str], warnings [str]); every message carries its line number."""
    ans, errors, warnings, first = {}, [], [], {}
    with open(path, encoding="utf-8-sig") as f:
        for ln, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                o = json.loads(line, object_pairs_hook=_no_dup_keys)
            except ValueError as ex:
                errors.append(f"line {ln}: invalid JSON ({ex})")
                continue
            if not isinstance(o, dict):
                errors.append(
                    f"line {ln}: expected a JSON object, got {type(o).__name__}"
                )
                continue
            i = o.get("id")
            if not isinstance(i, str) or not i:
                errors.append(f"line {ln}: missing or non-string 'id'")
                continue
            if i in first:
                errors.append(
                    f"line {ln}: duplicate id {i!r} (first seen on line {first[i]})"
                )
                continue
            first[i] = ln
            ans[i] = o
            if known_ids is not None and i not in known_ids:
                warnings.append(
                    f"line {ln}: id {i!r} is not a benchmark item (ignored)"
                )
    return ans, errors, warnings


def score(cases, ans, out=print):
    miss = [0, 0]
    fa = [0, 0]
    art = [0, 0]
    rev = [0, 0]
    missing = []
    detail = []
    tot = dict(miss=0, fa=0, art=0, rev=0)
    for k, c in cases.items():
        g = c["ground_truth"]
        grp = (
            "miss"
            if g.startswith("FLAWED")
            else "rev"
            if g == "REVISED-clarification"
            else "fa"
            if g == "CORRECT"
            else "art"
            if g == "EXTRACTION-ARTIFACT"
            else None
        )
        if grp:
            tot[grp] += 1
        a = ans.get(k)
        if a is None:
            missing.append(k)
            continue
        v = a.get("verdict")
        if v not in ("FLAW", "NO-FLAW"):
            out(f"  bad verdict for {k}: {v!r}")
            missing.append(k)
            continue
        if g.startswith("FLAWED"):
            miss[1] += 1
            miss[0] += v == "NO-FLAW"
        elif g == "REVISED-clarification":
            rev[1] += 1
            rev[0] += v == "FLAW"
        elif g == "CORRECT":
            fa[1] += 1
            fa[0] += v == "FLAW"
        elif g == "EXTRACTION-ARTIFACT":
            art[1] += 1
            art[0] += v == "FLAW"
        detail.append((k, g, v))
    out("per item (id, ground truth, answer):")
    for d in detail:
        out("  %-14s %-20s %s" % d)
    out("")
    out(fmt("MISS RATE on flawed items", *miss, tot["miss"]))
    out(fmt("FALSE-ALARM RATE on correct items", *fa, tot["fa"]))
    out(
        fmt(
            "ARTEFACT SUSCEPTIBILITY (FLAW on extraction-artefact items)",
            *art,
            tot["art"],
        )
    )
    out(
        fmt(
            "FLAG RATE on clarifications (FLAW on REVISED-clarification items)",
            *rev,
            tot["rev"],
        )
    )
    answered = len(cases) - len(missing)
    out(f"coverage: {answered}/{len(cases)} benchmark items answered")
    if missing:
        out(
            f"INCOMPLETE: {len(missing)} of {len(cases)} items unanswered or invalid; the rates above cover only the answered items"
        )
        out("unanswered/invalid: " + ", ".join(missing))
    return dict(
        miss=miss,
        false_alarm=fa,
        artefact=art,
        clarification=rev,
        missing=missing,
        totals=dict(
            miss=tot["miss"],
            false_alarm=tot["fa"],
            artefact=tot["art"],
            clarification=tot["rev"],
        ),
        answered=answered,
        total=len(cases),
    )


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("answers", nargs="?")
    ap.add_argument("--example", action="store_true")
    ap.add_argument(
        "--allow-partial",
        action="store_true",
        help="exit 0 even when some benchmark items are unanswered",
    )
    a = ap.parse_args(argv)
    path = os.path.join(HERE, "example_answers.jsonl") if a.example else a.answers
    if not path:
        ap.error("give answers.jsonl or --example")
    cases = load_cases()
    try:
        ans, errors, warnings = load_answers(path, set(cases))
    except OSError as ex:
        print(f"error: cannot read {path}: {ex}", file=sys.stderr)
        return 2
    except UnicodeDecodeError as ex:
        print(f"error: {path} is not valid UTF-8: {ex}", file=sys.stderr)
        return 2
    for w in warnings:
        print("warning: " + w, file=sys.stderr)
    if errors:
        for e in errors:
            print(f"{path}: {e}", file=sys.stderr)
        print(
            f"error: {len(errors)} malformed line(s); nothing scored", file=sys.stderr
        )
        return 2
    r = score(cases, ans)
    if r["missing"] and not (a.allow_partial or a.example):
        print(
            "exit status 1: unanswered items (use --allow-partial to accept a partial answer file)",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
