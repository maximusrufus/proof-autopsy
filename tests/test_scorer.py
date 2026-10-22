"""Regression tests for the adversarial review of scorer.py (findings 21 and 22)."""
import json
import os
import sys

import pytest

REL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REL)
import scorer as S

CASES = S.load_cases()
IDS = sorted(CASES)


def write(tmp_path, lines, bom=False):
    p = tmp_path / "answers.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8-sig" if bom else "utf-8")
    return str(p)


def full(verdict="NO-FLAW"):
    return [json.dumps({"id": i, "verdict": verdict}) for i in IDS]


def run(path, *flags):
    return S.main([path, *flags])


# ---- 21: duplicate ids, coverage next to every rate, non-zero exit when items are unanswered ----
def test_f21_duplicate_id_is_an_error(tmp_path, capsys):
    lines = full() + [json.dumps({"id": IDS[0], "verdict": "FLAW"})]  # the attack: a later answer silently overwrote the first
    assert run(write(tmp_path, lines)) == 2
    err = capsys.readouterr().err
    assert f"line {len(IDS) + 1}: duplicate id '{IDS[0]}' (first seen on line 1)" in err and "nothing scored" in err


def test_f21_unanswered_items_exit_nonzero_unless_allow_partial(tmp_path, capsys):
    p = write(tmp_path, full()[:3])
    assert run(p) == 1
    out = capsys.readouterr()
    assert "INCOMPLETE" in out.out and "unanswered/invalid" in out.out and "exit status 1" in out.err
    assert run(p, "--allow-partial") == 0


def test_f21_complete_answer_file_exits_zero_without_flag(tmp_path, capsys):
    assert run(write(tmp_path, full())) == 0
    assert "INCOMPLETE" not in capsys.readouterr().out


def test_f21_coverage_is_printed_next_to_every_rate(tmp_path, capsys):
    run(write(tmp_path, full()[:4]), "--allow-partial")
    out = capsys.readouterr().out
    rate_lines = [l for l in out.splitlines() if l.startswith(("MISS RATE", "FALSE-ALARM", "ARTEFACT", "FLAG RATE"))]
    assert len(rate_lines) == 4 and all("items in this group]" in l and "[answered " in l for l in rate_lines)
    assert f"coverage: 4/{len(IDS)} benchmark items answered" in out


def test_f21_invalid_verdict_counts_as_unanswered_and_fails(tmp_path, capsys):
    lines = full()
    lines[0] = json.dumps({"id": IDS[0], "verdict": "maybe"})
    assert run(write(tmp_path, lines)) == 1
    assert IDS[0] in capsys.readouterr().out


def test_f21_example_is_partial_on_purpose_and_exits_zero(capsys):
    assert S.main(["--example"]) == 0
    assert "coverage:" in capsys.readouterr().out


# ---- 22: line-numbered errors, utf-8-sig, unknown ids warn ----
def test_f22_bom_file_is_read(tmp_path):
    p = write(tmp_path, [json.dumps({"id": IDS[0], "verdict": "FLAW"})], bom=True)
    ans, errors, warnings = S.load_answers(p, set(IDS))
    assert errors == [] and IDS[0] in ans


@pytest.mark.parametrize("bad,needle", [
    ("{not json", "invalid JSON"), ("[1,2]", "expected a JSON object"), ('"s"', "expected a JSON object"),
    ('{"verdict": "FLAW"}', "missing or non-string 'id'"), ('{"id": 5, "verdict": "FLAW"}', "missing or non-string 'id'"),
    ('{"id": "W1", "verdict": "FLAW", "verdict": "NO-FLAW"}', "repeated key"),
])
def test_f22_malformed_lines_report_line_numbers_and_exit_2(tmp_path, capsys, bad, needle):
    p = write(tmp_path, [full()[0], bad])
    assert run(p) == 2
    err = capsys.readouterr().err
    assert "line 2:" in err and needle in err


def test_f22_unknown_ids_warn_and_are_ignored(tmp_path, capsys):
    lines = full() + [json.dumps({"id": "ZZZ-not-an-item", "verdict": "FLAW"})]
    assert run(write(tmp_path, lines)) == 0
    err = capsys.readouterr().err
    assert f"warning: line {len(IDS) + 1}: id 'ZZZ-not-an-item' is not a benchmark item (ignored)" in err


def test_unreadable_file_exits_2(tmp_path):
    assert S.main([str(tmp_path / "missing.jsonl")]) == 2
    bad = tmp_path / "latin.jsonl"
    bad.write_bytes(b'{"id": "W1", "verdict": "FLAW", "x": "\xe9"}\n')
    assert S.main([str(bad)]) == 2
