# Proof Autopsy

Can your verifier find the flaw that killed the proof? A small benchmark of mathematics manuscripts with publicly documented flaws or revisions.

Purpose: measure how a proof verifier (human or model) behaves on manuscripts whose flaw or later revision is documented in public sources. Every label comes from a public withdrawal notice or revision note. Manuscripts are not redistributed; each item links to a public commit.

## Contents
- `items/<id>/case.json` - ground truth (12 items)
- `QUESTIONS/<id>.md` - the prompt to give a verifier
- `scorer.py` - scores your `answers.jsonl`
- `example_answers.jsonl` - toy answers for `--example`
- `LICENSE` (MIT, scorer.py), `LICENSE-DATA` (CC-BY-4.0, data and questions)

## Schema (case.json)
`id`, `source{repo, commit, path}`, `step_location`, `ground_truth` (`FLAWED-documented` | `FLAWED-gap` | `REVISED-clarification` | `CORRECT` | `EXTRACTION-ARTIFACT`), `ground_truth_reference` (list of public citations), `label_confidence_notes`.

Answers: one JSON object per line, `{"id": "W1", "verdict": "FLAW" | "NO-FLAW", "location": "...", "rationale": "..."}`.

## Run
    python scorer.py answers.jsonl
    python scorer.py --example

Output: miss rate on flawed items (NO-FLAW on FLAWED-*) and flag rate on clarifications (FLAW on REVISED-clarification items, reported separately), each with a 95% Wilson interval.

## Label sources and confidence
- `FLAWED-documented` (W1-W3): withdrawal notice in openai/math (2026-10-06). W1 is also supported by J. G. George, Zenodo 10.5281/zenodo.23263564 and chokmah-me/fragile-proof-audit. High confidence that W1 is unproved; W2 and W3 inherit the W1 construction per the notice.
- `FLAWED-gap` (R3, R4): a later edition's revision note says it corrects or repairs an argument. Medium confidence: this shows a real change, not a specific false statement.
- `REVISED-clarification` (R1, R2, R6, R7, R12): a later edition adds or clarifies an argument; it does not document a false step. Excluded from the miss-rate denominator and reported separately as the flag rate on clarifications.

## Limitations
Small n (12 items), so intervals are wide. Labels come from public notices and revision notes rather than independent proofs. Item selection is not a random sample of the literature. The scorer also accepts `CORRECT` and `EXTRACTION-ARTIFACT` labels for users who add their own items.
