"""DIB Agent — solicitation and contract analysis for defense contractors.

Local-only by construction: see boundary.py. The extraction path makes no
network call of any kind, so it is safe to run against CUI-marked documents.
"""

from .analyzer import Analysis, Finding, analyze
from .boundary import BoundaryViolation, LocalModel, assert_local_only, boundary_banner
from .report import render, summary_prompt

__all__ = [
    "Analysis", "Finding", "analyze",
    "BoundaryViolation", "LocalModel", "assert_local_only", "boundary_banner",
    "render", "summary_prompt",
]
