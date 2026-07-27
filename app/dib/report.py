"""Render an Analysis for a human deciding whether to bid.

Ordering is the design: blockers first, because the only question that matters
in the first ten seconds is "can we even bid this". Everything is traceable to
a verbatim snippet so the contractor can check the tool rather than trust it.
"""

from __future__ import annotations

from .analyzer import Analysis

SEV = {"blocker": "BLOCKER ", "obligation": "must-do  ", "note": "note     "}


def render(a: Analysis, *, summary: str | None = None, banner: str | None = None) -> str:
    L: list[str] = []
    ident = a.solicitation_number or a.source
    L.append("")
    L.append(f"  {ident}")
    L.append("  " + "─" * max(20, len(ident)))

    facts = []
    if a.cmmc_level:
        facts.append(f"CMMC Level {a.cmmc_level}")
    scope = "CUI" if a.handles_cui else ("FCI" if a.handles_fci else "no CUI/FCI language found")
    facts.append(f"scope: {scope}")
    if a.naics:
        facts.append(f"NAICS {a.naics}")
    if a.set_asides:
        facts.append("set-aside: " + ", ".join(a.set_asides))
    L.append("  " + " · ".join(facts))
    if a.cmmc_basis:
        L.append(f"    basis: {a.cmmc_basis}")
    L.append("")

    if a.blockers:
        L.append("  BID-STOPPERS")
        for f in a.blockers:
            L.append(f"    ✖ {f.title}")
            L.append(f"      {f.detail}")
        L.append("")

    others = [f for f in a.findings if f.severity != "blocker"]
    if others:
        L.append("  OBLIGATIONS")
        for f in others:
            L.append(f"    {SEV[f.severity]}{f.title}")
            L.append(f"      {f.detail}")
            if f.evidence:
                L.append(f'      ↳ "{f.evidence[:150]}"')
        L.append("")

    if a.clauses:
        L.append("  CLAUSES FOUND")
        for c in a.clauses:
            flag = " ⇣ flows down" if c.flows_down else ""
            L.append(f"    {c.number}  {c.title}{flag}")
            L.append(f"      {c.obligation}")
        L.append("")

    if a.unknown_clause_numbers:
        L.append(
            "  UNRECOGNISED CLAUSES (not in the local table — read them yourself)\n    "
            + ", ".join(a.unknown_clause_numbers[:20])
        )
        L.append("")

    if a.cdrls or a.data_items or a.response_due or a.delivery_windows:
        L.append("  DELIVERY")
        if a.response_due:
            L.append(f"    response due: {a.response_due}")
        if a.delivery_windows:
            L.append(f"    windows: {', '.join(a.delivery_windows)}")
        if a.cdrls:
            L.append(f"    CDRLs ({len(a.cdrls)}): {', '.join(a.cdrls[:15])}")
        if a.data_items:
            L.append(f"    data items: {', '.join(a.data_items[:10])}")
        L.append("")

    if summary:
        L.append("  SUMMARY (local model — narrative only; the findings above are")
        L.append("  extracted deterministically and do not depend on it)")
        for line in summary.splitlines():
            L.append(f"    {line}")
        L.append("")

    if banner:
        L.append(banner)
    L.append("")
    return "\n".join(L)


def summary_prompt(a: Analysis) -> str:
    """Ground the model in what we already extracted, and forbid invention."""
    return (
        "You are advising a small US defense contractor deciding whether to bid.\n"
        "Below are facts extracted from a solicitation by a deterministic parser.\n"
        "Write 3-5 short sentences: what this contract would require of them "
        "operationally, and the single biggest risk. Do not invent clause numbers, "
        "dates or requirements that are not listed. Do not repeat the list back.\n\n"
        f"CMMC level required: {a.cmmc_level or 'not stated'}\n"
        f"CUI in scope: {a.handles_cui}\nFCI in scope: {a.handles_fci}\n"
        f"Clauses: {', '.join(c.number for c in a.clauses) or 'none found'}\n"
        f"Flow-downs: {', '.join(c.number for c in a.flowdowns) or 'none'}\n"
        f"CDRL count: {len(a.cdrls)}\n"
        f"Blockers: {'; '.join(f.title for f in a.blockers) or 'none'}\n"
    )
