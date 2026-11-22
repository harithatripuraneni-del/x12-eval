# x12-eval

**Score generated X12 EDI against known-good files.**

When an AI model, a new map or a platform migration produces EDI, "it looks right" isn't good enough. `x12-eval` compares a generated file with a known-good one and reports element-level accuracy, so you can measure quality, track it over time and block a release when it drops.

```
$ x12-eval examples/expected examples/generated
load_tender.edi: element accuracy 86.8% (33/38), segments 14/15
  - L1101: expected 'PO12345', got 'PO12354'
  - G6202: expected '20261123', got '20261124'
  - missing segment N1 (expected at position 12)
  - SE01: expected '11', got '10'
shipment_status.edi: element accuracy 100.0% (51/51), segments 18/18

Overall element accuracy 94.4%; 1/2 files match exactly
```

## Why it's built this way

- **Ignores what should change.** Dates, times and control numbers (ISA09, ISA13, GS06, ST02 and so on) differ on every run, so they're skipped by default. Use `--ignore` to change the list.
- **Aligns before it compares.** Segments are matched by ID with `difflib`, the algorithm behind `diff`, so one missing segment doesn't make everything after it look wrong.
- **Deterministic, so it can gate.** The same inputs always give the same score. The CLI exits with code 1 below `--threshold`, just like a failing test.
- **Reuses a real parser.** Delimiters come from each file's ISA header via [x12-mcp](https://github.com/harithatripuraneni-del/x12-mcp).

## Quick start

Requires Python 3.10+.

```bash
git clone https://github.com/harithatripuraneni-del/x12-eval.git
cd x12-eval
pip install -e ".[dev]"
pytest
```

Compare two files or two folders (files are paired by name):

```bash
x12-eval expected.edi generated.edi
x12-eval expected_dir/ generated_dir/ --threshold 0.95
x12-eval expected_dir/ generated_dir/ --json
```

Use it from Python:

```python
from x12_eval import compare

score = compare(expected_text, generated_text)
print(f"{score.element_accuracy:.1%}")
for diff in score.differences:
    print(diff.describe())
```

## How the score works

- **Element accuracy** = matching elements / compared elements. Empty and ignored elements aren't counted. A missing or extra segment counts all of its elements as wrong.
- **Segment accuracy** = expected segments that were found in the right order.
- **Folder accuracy** is a micro-average: every element in every file counts once, so large files aren't drowned out by small ones.

## Ideas for what's next

- Per-partner ignore lists loaded from a config file
- An HTML report for sharing results
- A GitHub Action wrapper so map changes are scored on every pull request

## License

MIT. Example files are synthetic and contain no real company data.
