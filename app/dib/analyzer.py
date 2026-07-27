"""Solicitation analysis for a defense contractor.

Design rule: anything an assessor or contracting officer could hold you to is
extracted deterministically — clause numbers, CMMC level, CUI scope, CDRLs,
dates. The local model is only ever asked to summarise prose that is already
grounded in those findings. An LLM that hallucinates "252.204-7012 applies"
is worse than no tool at all, so it is never the one deciding.

Everything here runs on the contractor's machine. No network call is made from
this module, which is what makes it safe to point at a CUI-marked solicitation.
See boundary.py for the guarantee.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .clauses import CLAUSES, Clause, lookup

# ── patterns ────────────────────────────────────────────────────────────────

# DFARS 252.x / FAR 52.x, tolerating the alternate-roman suffixes real
# solicitations carry (e.g. 252.204-7012 (DEVIATION 2016-O0001)).
CLAUSE_RE = re.compile(r"\b((?:252|52)\.\d{3}-\d{1,4})\b")

CMMC_RE = re.compile(r"CMMC\s*(?:2\.0\s*)?(?:Level|LVL|L)\s*([123])\b", re.I)

CUI_MARKING_RE = re.compile(
    r"\b(CUI//SP-[A-Z]{2,6}|CUI//[A-Z/-]{2,20}|CONTROLLED UNCLASSIFIED INFORMATION|"
    r"COVERED DEFENSE INFORMATION|\bCDI\b|\bCTI\b)",
    re.I,
)

FCI_RE = re.compile(r"\bfederal contract information\b|\bFCI\b", re.I)

# CDRL / deliverable lines: "CDRL A001", "Data Item A002", "DI-MGMT-81334".
CDRL_RE = re.compile(r"\b(?:CDRL\s*)?\b([A-Z]{1}\d{3})\b(?!\d)")
DID_RE = re.compile(r"\b(DI-[A-Z]{3,5}-\d{5}[A-Z]?)\b")

# Dates the contractor is actually bound by.
ARO_RE = re.compile(r"\b(?:ARO|after receipt of order)\s*\+?\s*(\d{1,3})\s*(day|calendar day|week|month)s?\b", re.I)
DUE_RE = re.compile(
    r"\b(?:proposals?|offers?|quotes?|responses?)\s+(?:are\s+)?due\b[^.\n]{0,80}?"
    r"(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})",
    re.I,
)

SET_ASIDE_RE = re.compile(
    r"\b(8\(a\)|HUBZone|SDVOSB|service-disabled veteran|WOSB|women-owned|"
    r"small business set-aside|total small business)\b",
    re.I,
)

NAICS_RE = re.compile(r"\bNAICS\s*(?:code)?\s*:?\s*(\d{6})\b", re.I)
SOL_NUM_RE = re.compile(r"\b([A-Z0-9]{6}-?\d{2}-?[A-Z]-?\d{4}|[A-Z]\d{5}[A-Z]\d{2}[A-Z]\d{4})\b")


# ── result ──────────────────────────────────────────────────────────────────


@dataclass
class Finding:
    """One thing the contractor has to do something about."""

    severity: str  # "blocker" | "obligation" | "note"
    title: str
    detail: str
    evidence: str = ""  # verbatim snippet, so the human can check us


@dataclass
class Analysis:
    source: str
    solicitation_number: str | None = None
    naics: str | None = None
    set_asides: list[str] = field(default_factory=list)
    cmmc_level: int | None = None
    cmmc_basis: str = ""
    handles_cui: bool = False
    handles_fci: bool = False
    cui_evidence: list[str] = field(default_factory=list)
    clauses: list[Clause] = field(default_factory=list)
    unknown_clause_numbers: list[str] = field(default_factory=list)
    flowdowns: list[Clause] = field(default_factory=list)
    cdrls: list[str] = field(default_factory=list)
    data_items: list[str] = field(default_factory=list)
    response_due: str | None = None
    delivery_windows: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def blockers(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "blocker"]


def _snippet(text: str, match: re.Match, width: int = 90) -> str:
    """Verbatim context around a match, trimmed to whole words so the operator
    can read it — a snippet starting mid-word reads like a bug and undermines
    trust in the finding it supports."""
    start = max(0, match.start() - width // 2)
    end = min(len(text), match.end() + width // 2)
    chunk = text[start:end]
    if start > 0 and not text[start - 1].isspace():
        chunk = chunk.partition(" ")[2]
    if end < len(text) and not text[end].isspace():
        chunk = chunk.rpartition(" ")[0]
    return " ".join(chunk.split())


def analyze(text: str, *, source: str = "solicitation", posture: dict | None = None) -> Analysis:
    """Extract obligations from solicitation text.

    `posture` is the contractor's own state — {"sprs_score": int|None,
    "sprs_date": "YYYY-MM-DD", "cmmc_level": int|None}. When supplied, findings
    become specific to this company ("you have no SPRS score on file") instead
    of generic advice.
    """
    a = Analysis(source=source)
    posture = posture or {}

    if m := SOL_NUM_RE.search(text):
        a.solicitation_number = m.group(1)
    if m := NAICS_RE.search(text):
        a.naics = m.group(1)
    a.set_asides = sorted({m.group(1) for m in SET_ASIDE_RE.finditer(text)}, key=str.lower)

    # ── clauses ────────────────────────────────────────────────────────────
    seen: list[str] = []
    for m in CLAUSE_RE.finditer(text):
        num = m.group(1)
        if num not in seen:
            seen.append(num)
    for num in seen:
        if c := lookup(num):
            a.clauses.append(c)
        else:
            a.unknown_clause_numbers.append(num)
    a.flowdowns = [c for c in a.clauses if c.flows_down]

    # ── information scope ──────────────────────────────────────────────────
    for m in CUI_MARKING_RE.finditer(text):
        a.handles_cui = True
        snip = _snippet(text, m)
        if snip not in a.cui_evidence:
            a.cui_evidence.append(snip)
        if len(a.cui_evidence) >= 4:
            break
    a.handles_fci = bool(FCI_RE.search(text))

    # ── CMMC level: explicit statement wins, else infer from scope ──────────
    if m := CMMC_RE.search(text):
        a.cmmc_level = int(m.group(1))
        a.cmmc_basis = f"stated in the solicitation ({_snippet(text, m)})"
    elif any(c.number == "252.204-7021" for c in a.clauses):
        a.cmmc_level = 2 if a.handles_cui else 1
        a.cmmc_basis = "252.204-7021 present; level inferred from information scope"
    elif a.handles_cui:
        a.cmmc_level = 2
        a.cmmc_basis = "CUI/CDI in scope implies Level 2 even where CMMC is not named"
    elif a.handles_fci:
        a.cmmc_level = 1
        a.cmmc_basis = "FCI only"

    # ── deliverables and dates ─────────────────────────────────────────────
    a.cdrls = sorted({m.group(1) for m in CDRL_RE.finditer(text)})
    a.data_items = sorted({m.group(1) for m in DID_RE.finditer(text)})
    if m := DUE_RE.search(text):
        a.response_due = m.group(1)
    a.delivery_windows = sorted(
        {f"ARO+{m.group(1)} {m.group(2).lower()}s" for m in ARO_RE.finditer(text)}
    )

    _derive_findings(a, posture)
    return a


def _derive_findings(a: Analysis, posture: dict) -> None:
    """Turn extracted facts into things to do, against this company's posture."""
    has = {c.number for c in a.clauses}

    if a.handles_cui and "252.204-7012" not in has:
        a.findings.append(
            Finding(
                "note",
                "CUI language without 252.204-7012",
                "The document refers to CUI/CDI but 252.204-7012 was not found. "
                "Either the clause is incorporated by reference elsewhere, or the "
                "scope is looser than the language suggests. Confirm with the CO "
                "before assuming 800-171 does not apply.",
                a.cui_evidence[0] if a.cui_evidence else "",
            )
        )

    if "252.204-7019" in has or "252.204-7020" in has:
        score = posture.get("sprs_score")
        if score is None:
            a.findings.append(
                Finding(
                    "blocker",
                    "SPRS score required and none on file",
                    "252.204-7019 makes a current Basic Assessment score in SPRS a "
                    "condition of award. Nothing is recorded in your posture, so this "
                    "is a bid-stopper until a score is posted.",
                )
            )
        else:
            a.findings.append(
                Finding(
                    "obligation",
                    f"SPRS score must be current (yours: {score})",
                    "The score must be less than three years old at award. Confirm "
                    "the assessment date and refresh it if it is close.",
                )
            )

    if a.cmmc_level:
        held = posture.get("cmmc_level")
        if held is None:
            a.findings.append(
                Finding(
                    "blocker" if a.cmmc_level >= 2 else "obligation",
                    f"CMMC Level {a.cmmc_level} required; your level is unrecorded",
                    f"{a.cmmc_basis}. Level {a.cmmc_level} must be held for the systems "
                    "used on this contract — and for Level 2 that means a C3PAO "
                    "assessment, which takes months. Start now or team with someone "
                    "who holds it.",
                )
            )
        elif held < a.cmmc_level:
            a.findings.append(
                Finding(
                    "blocker",
                    f"CMMC Level {a.cmmc_level} required; you hold Level {held}",
                    "This is a gating requirement, not a post-award fix.",
                )
            )

    if a.flowdowns:
        nums = ", ".join(c.number for c in a.flowdowns)
        a.findings.append(
            Finding(
                "obligation",
                f"{len(a.flowdowns)} clause(s) flow down to subcontractors",
                f"{nums} must appear in your subcontracts, and 252.204-7020 requires "
                "you to verify a sub's SPRS score before award. This is the step "
                "small primes most often miss.",
            )
        )

    if a.handles_cui:
        a.findings.append(
            Finding(
                "obligation",
                "CUI handling obligations are in play",
                "Marking, storage, transmission and disposal all have requirements, "
                "and 72-hour incident reporting to DC3 applies. Confirm where CUI "
                "will actually live before you bid — email and general-purpose file "
                "sharing are the usual failure points.",
                a.cui_evidence[0] if a.cui_evidence else "",
            )
        )

    if a.cdrls:
        a.findings.append(
            Finding(
                "obligation",
                f"{len(a.cdrls)} deliverable line item(s) identified",
                "Each CDRL carries its own format, frequency and acceptance criteria. "
                f"Items: {', '.join(a.cdrls[:12])}"
                + (" …" if len(a.cdrls) > 12 else ""),
            )
        )

    if not a.clauses and not a.handles_cui and not a.handles_fci:
        a.findings.append(
            Finding(
                "note",
                "No DFARS/FAR clauses or information-scope language found",
                "Either this is not a solicitation, the text layer did not extract "
                "(a scanned PDF needs OCR), or clauses are incorporated by reference "
                "only. Do not read this as 'no obligations'.",
            )
        )
