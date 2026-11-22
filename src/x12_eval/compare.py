"""Score a generated X12 file against a known-good (expected) one.

How it works:
1. Parse both files with x12-mcp's parser (so delimiters come from each ISA).
2. Align the two segment lists by segment ID with difflib, the same algorithm
   behind `diff`. This keeps one missing segment from shifting every later
   segment out of line.
3. Compare aligned segments element by element, skipping fields that are
   expected to differ between runs (dates, times, control numbers).

The result is deterministic, so it can gate a build: same inputs, same score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from x12_mcp.parser import Segment, parse

# Fields that legitimately change every time a file is generated.
DEFAULT_IGNORE: frozenset[str] = frozenset({
    "ISA09", "ISA10", "ISA13",  # interchange date, time, control number
    "GS04", "GS05", "GS06",  # group date, time, control number
    "ST02", "SE02",  # transaction control number
    "GE02", "IEA02",  # trailer control numbers
})


@dataclass
class Difference:
    kind: str  # "missing_segment", "extra_segment" or "element_mismatch"
    segment: str  # segment ID, e.g. "L11"
    ref: str = ""  # element reference, e.g. "L1101"
    expected: str = ""
    actual: str = ""
    position: int | None = None  # position in the expected file when known

    def describe(self) -> str:
        if self.kind == "missing_segment":
            return f"missing segment {self.segment} (expected at position {self.position})"
        if self.kind == "extra_segment":
            return f"extra segment {self.segment} not in the expected file"
        return f"{self.ref}: expected '{self.expected}', got '{self.actual}'"


@dataclass
class Score:
    segments_expected: int = 0
    segments_matched: int = 0
    elements_compared: int = 0
    elements_matched: int = 0
    differences: list[Difference] = field(default_factory=list)

    @property
    def element_accuracy(self) -> float:
        return self.elements_matched / self.elements_compared if self.elements_compared else 1.0

    @property
    def segment_accuracy(self) -> float:
        return self.segments_matched / self.segments_expected if self.segments_expected else 1.0

    @property
    def exact_match(self) -> bool:
        return not self.differences

    def to_dict(self) -> dict:
        return {
            "element_accuracy": round(self.element_accuracy, 4),
            "segment_accuracy": round(self.segment_accuracy, 4),
            "elements_matched": self.elements_matched,
            "elements_compared": self.elements_compared,
            "segments_matched": self.segments_matched,
            "segments_expected": self.segments_expected,
            "differences": [vars(d) for d in self.differences],
        }


def _values(seg: Segment, ignore: frozenset[str]) -> dict[str, str]:
    """Non-empty, non-ignored element values keyed by reference (e.g. 'B204')."""
    out = {}
    for n, value in enumerate(seg.elements, start=1):
        ref = f"{seg.id}{n:02d}"
        value = value.strip()  # ISA pads fields with spaces
        if value and ref not in ignore:
            out[ref] = value
    return out


def _count_unmatched(seg: Segment, ignore: frozenset[str], score: Score) -> None:
    """A missing or extra segment counts all of its elements as wrong."""
    score.elements_compared += len(_values(seg, ignore))


def compare_segments(expected: list[Segment], actual: list[Segment], ignore: frozenset[str] = DEFAULT_IGNORE) -> Score:
    score = Score(segments_expected=len(expected))
    matcher = SequenceMatcher(None, [s.id for s in expected], [s.id for s in actual], autojunk=False)

    for tag, e_start, e_end, a_start, a_end in matcher.get_opcodes():
        if tag == "equal":
            for exp_seg, act_seg in zip(expected[e_start:e_end], actual[a_start:a_end]):
                score.segments_matched += 1
                exp_vals, act_vals = _values(exp_seg, ignore), _values(act_seg, ignore)
                for ref in sorted(exp_vals.keys() | act_vals.keys()):
                    score.elements_compared += 1
                    if exp_vals.get(ref) == act_vals.get(ref):
                        score.elements_matched += 1
                    else:
                        score.differences.append(Difference(
                            "element_mismatch", exp_seg.id, ref,
                            exp_vals.get(ref, ""), act_vals.get(ref, ""), exp_seg.position,
                        ))
            continue
        # "delete", "insert" and "replace" all mean the segment IDs disagree.
        for seg in expected[e_start:e_end]:
            _count_unmatched(seg, ignore, score)
            score.differences.append(Difference("missing_segment", seg.id, position=seg.position))
        for seg in actual[a_start:a_end]:
            _count_unmatched(seg, ignore, score)
            score.differences.append(Difference("extra_segment", seg.id))
    return score


def compare(expected_text: str, actual_text: str, ignore: frozenset[str] = DEFAULT_IGNORE) -> Score:
    """Compare two X12 files given as text."""
    return compare_segments(parse(expected_text).segments, parse(actual_text).segments, ignore)


@dataclass
class BatchResult:
    scores: dict[str, Score]
    missing_files: list[str]  # expected files with no generated counterpart

    @property
    def element_accuracy(self) -> float:
        """Micro-average: every compared element across all files counts once."""
        compared = sum(s.elements_compared for s in self.scores.values())
        matched = sum(s.elements_matched for s in self.scores.values())
        return matched / compared if compared else 1.0

    @property
    def exact_matches(self) -> int:
        return sum(s.exact_match for s in self.scores.values())


def compare_folders(expected_dir: Path, actual_dir: Path, ignore: frozenset[str] = DEFAULT_IGNORE) -> BatchResult:
    """Pair files by name and score each pair."""
    scores: dict[str, Score] = {}
    missing: list[str] = []
    for exp_file in sorted(p for p in expected_dir.iterdir() if p.is_file()):
        act_file = actual_dir / exp_file.name
        if not act_file.exists():
            missing.append(exp_file.name)
            continue
        scores[exp_file.name] = compare(exp_file.read_text(), act_file.read_text(), ignore)
    return BatchResult(scores, missing)
