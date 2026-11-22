"""x12-eval: score generated X12 EDI against known-good files."""

from .compare import DEFAULT_IGNORE, Score, compare, compare_folders

__all__ = ["DEFAULT_IGNORE", "Score", "compare", "compare_folders"]
__version__ = "0.1.0"
