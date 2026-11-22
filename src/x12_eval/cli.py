"""Command line: x12-eval EXPECTED ACTUAL

Works on two files or two folders. Exits with code 1 when accuracy is below
--threshold, so it can block a pipeline the same way a failing test does.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .compare import DEFAULT_IGNORE, Score, compare, compare_folders


def _report(name: str, score: Score) -> str:
    lines = [
        f"{name}: element accuracy {score.element_accuracy:.1%} "
        f"({score.elements_matched}/{score.elements_compared}), "
        f"segments {score.segments_matched}/{score.segments_expected}"
    ]
    lines += [f"  - {d.describe()}" for d in score.differences]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="x12-eval", description="Score generated X12 against expected X12.")
    parser.add_argument("expected", type=Path, help="known-good file or folder")
    parser.add_argument("actual", type=Path, help="generated file or folder")
    parser.add_argument("--threshold", type=float, default=1.0, help="minimum element accuracy to pass (0 to 1, default 1.0)")
    parser.add_argument("--ignore", default=",".join(sorted(DEFAULT_IGNORE)),
                        help="comma-separated element refs to skip (default: dates, times, control numbers)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    ignore = frozenset(x.strip().upper() for x in args.ignore.split(",") if x.strip())

    if args.expected.is_dir() and args.actual.is_dir():
        batch = compare_folders(args.expected, args.actual, ignore)
        accuracy = batch.element_accuracy
        if args.json:
            print(json.dumps({
                "element_accuracy": round(accuracy, 4),
                "exact_matches": batch.exact_matches,
                "files": {name: s.to_dict() for name, s in batch.scores.items()},
                "missing_files": batch.missing_files,
            }, indent=2))
        else:
            for name, score in batch.scores.items():
                print(_report(name, score))
            for name in batch.missing_files:
                print(f"{name}: no generated file found")
            print(f"\nOverall element accuracy {accuracy:.1%}; "
                  f"{batch.exact_matches}/{len(batch.scores)} files match exactly")
        passed = accuracy >= args.threshold and not batch.missing_files
    else:
        score = compare(args.expected.read_text(), args.actual.read_text(), ignore)
        accuracy = score.element_accuracy
        print(json.dumps(score.to_dict(), indent=2) if args.json else _report(args.actual.name, score))
        passed = accuracy >= args.threshold

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
