from pathlib import Path

from x12_eval.cli import main
from x12_eval.compare import compare, compare_folders

EXAMPLES = Path(__file__).parent.parent / "examples"
EXPECTED = (EXAMPLES / "expected" / "load_tender.edi").read_text()
GENERATED = (EXAMPLES / "generated" / "load_tender.edi").read_text()


def kinds(score):
    return [d.kind for d in score.differences]


def test_identical_files_score_100_percent():
    score = compare(EXPECTED, EXPECTED)
    assert score.exact_match
    assert score.element_accuracy == 1.0 and score.segment_accuracy == 1.0


def test_dates_and_control_numbers_are_ignored():
    rerun = (EXAMPLES / "generated" / "shipment_status.edi").read_text()
    original = (EXAMPLES / "expected" / "shipment_status.edi").read_text()
    assert compare(original, rerun).exact_match


def test_ignored_fields_can_be_turned_back_on():
    rerun = (EXAMPLES / "generated" / "shipment_status.edi").read_text()
    original = (EXAMPLES / "expected" / "shipment_status.edi").read_text()
    assert not compare(original, rerun, ignore=frozenset()).exact_match


def test_finds_each_real_difference():
    score = compare(EXPECTED, GENERATED)
    found = {d.describe() for d in score.differences}
    assert "L1101: expected 'PO12345', got 'PO12354'" in found
    assert "G6202: expected '20261123', got '20261124'" in found
    assert "missing segment N1 (expected at position 12)" in found
    assert "SE01: expected '11', got '10'" in found


def test_missing_segment_does_not_shift_alignment():
    # Dropping one N1 must not make every later segment look wrong.
    score = compare(EXPECTED, GENERATED)
    assert kinds(score).count("missing_segment") == 1
    assert "extra_segment" not in kinds(score)
    assert score.segments_matched == score.segments_expected - 1


def test_extra_segment_is_reported():
    with_extra = EXPECTED.replace("B2A*00~", "B2A*00~\nNTE*GEN*Fragile~").replace("SE*11", "SE*12")
    score = compare(EXPECTED, with_extra)
    assert "extra segment NTE not in the expected file" in {d.describe() for d in score.differences}


def test_accuracy_counts():
    score = compare(EXPECTED, GENERATED)
    # 5 wrong: L1101, G6202 and SE01, plus the missing N1's two values.
    assert score.elements_compared - score.elements_matched == 5
    assert 0.8 < score.element_accuracy < 0.95


def test_folder_mode_micro_average():
    batch = compare_folders(EXAMPLES / "expected", EXAMPLES / "generated")
    assert set(batch.scores) == {"load_tender.edi", "shipment_status.edi"}
    assert batch.exact_matches == 1
    assert batch.missing_files == []


def test_cli_exit_codes(capsys):
    expected, generated = str(EXAMPLES / "expected"), str(EXAMPLES / "generated")
    assert main([expected, generated]) == 1  # below the default 100% threshold
    assert main([expected, generated, "--threshold", "0.8"]) == 0
    out = capsys.readouterr().out
    assert "Overall element accuracy" in out
