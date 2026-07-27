"""DFARS / FAR clause knowledge for defense solicitations.

Deliberately a hand-curated table rather than something the model infers.
Clause obligations are the part of an analysis a contractor will act on and
an assessor will check, so they must be exact and identical every run. The
local model is used to summarise narrative, never to decide what 252.204-7012
requires.

Each entry states the obligation in the contractor's terms and the trigger
that makes it apply, because "this clause is present" is far less useful than
"this clause means you must do X within Y days".
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Clause:
    number: str
    title: str
    obligation: str
    triggers: tuple[str, ...] = ()
    flows_down: bool = False
    cmmc_level: int | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)


# Ordered roughly by how often they decide bid/no-bid for a small contractor.
CLAUSES: dict[str, Clause] = {
    c.number: c
    for c in (
        Clause(
            "252.204-7012",
            "Safeguarding Covered Defense Information and Cyber Incident Reporting",
            "Implement all 110 controls of NIST SP 800-171 on any system that "
            "processes, stores or transmits CDI. Report cyber incidents to DC3 "
            "within 72 hours, preserve images for 90 days, and flow this clause "
            "down to subcontractors handling CDI. Cloud services used to store CDI "
            "must meet FedRAMP Moderate equivalency.",
            triggers=("covered defense information", "CDI", "controlled unclassified information", "CUI"),
            flows_down=True,
            tags=("cui", "incident-reporting", "800-171"),
        ),
        Clause(
            "252.204-7019",
            "Notice of NIST SP 800-171 DoD Assessment Requirements",
            "You must have a current (within 3 years) Basic Assessment score "
            "posted in SPRS to be eligible for award. No score, no award.",
            triggers=("SPRS", "basic assessment"),
            tags=("sprs", "pre-award"),
        ),
        Clause(
            "252.204-7020",
            "NIST SP 800-171 DoD Assessment Requirements",
            "Post and maintain your SPRS score, grant DoD access to conduct "
            "Medium/High assessments on request, and flow the requirement down to "
            "subcontractors — you must verify their scores before award.",
            triggers=("SPRS", "assessment"),
            flows_down=True,
            tags=("sprs", "subcontractor"),
        ),
        Clause(
            "252.204-7021",
            "Cybersecurity Maturity Model Certification Requirements",
            "Hold the specified CMMC level for the information systems used on "
            "this contract, maintain it for the contract's duration, and flow the "
            "requirement down to subcontractors at the level appropriate to what "
            "they handle.",
            triggers=("CMMC",),
            flows_down=True,
            tags=("cmmc",),
        ),
        Clause(
            "252.204-7008",
            "Compliance with Safeguarding Covered Defense Information Controls",
            "By submitting the offer you represent that you will implement "
            "800-171 by the time of award. Any control not implemented must be "
            "submitted in writing to the DoD CIO for adjudication within 30 days.",
            triggers=("covered defense information",),
            tags=("representation", "pre-award"),
        ),
        Clause(
            "252.204-7000",
            "Disclosure of Information",
            "No release of contract-related information to the public without "
            "written approval from the Contracting Officer.",
            tags=("disclosure",),
        ),
        Clause(
            "52.204-21",
            "Basic Safeguarding of Covered Contractor Information Systems",
            "Fifteen basic safeguarding requirements on any system holding "
            "Federal Contract Information. This is the floor — it applies even "
            "when there is no CUI in scope.",
            triggers=("federal contract information", "FCI"),
            flows_down=True,
            cmmc_level=1,
            tags=("fci",),
        ),
        Clause(
            "252.239-7010",
            "Cloud Computing Services",
            "Cloud services holding DoD data must be FedRAMP Moderate equivalent "
            "or better, data stays within the United States or its outlying areas, "
            "and incident reporting obligations apply to the cloud provider too.",
            triggers=("cloud",),
            tags=("cloud", "fedramp"),
        ),
        Clause(
            "252.225-7048",
            "Export-Controlled Items",
            "Comply with export control law (ITAR/EAR). Access by foreign persons "
            "— including employees — may require licensing.",
            triggers=("export", "ITAR", "EAR"),
            flows_down=True,
            tags=("export",),
        ),
        Clause(
            "252.211-7003",
            "Item Unique Identification and Valuation",
            "Mark deliverable items with IUID and register them in the DoD IUID "
            "registry.",
            tags=("delivery",),
        ),
        Clause(
            "252.246-7007",
            "Contractor Counterfeit Electronic Part Detection and Avoidance System",
            "Maintain an acceptable counterfeit-part detection and avoidance "
            "system; purchase from original or authorized sources where possible.",
            flows_down=True,
            tags=("supply-chain",),
        ),
        Clause(
            "252.239-7018",
            "Supply Chain Risk",
            "The Government may exclude sources for supply chain risk. Applies to "
            "national security systems.",
            tags=("supply-chain",),
        ),
    )
}

# CMMC level implied by what the solicitation says is in scope. FCI alone is
# Level 1; CUI pulls Level 2; the 7021 clause naming a level always wins.
CMMC_BY_SCOPE = {
    "fci_only": 1,
    "cui": 2,
}


def lookup(number: str) -> Clause | None:
    """Exact-match a clause number, tolerating the DFARS 'DFARS ' prefix."""
    return CLAUSES.get(number.strip().upper().replace("DFARS ", "").replace("FAR ", ""))


def flowdown_clauses(numbers: list[str]) -> list[Clause]:
    """Clauses among `numbers` a prime must push to its subs — the set a small
    contractor most often misses when it in turn subcontracts."""
    found = [lookup(n) for n in numbers]
    return [c for c in found if c and c.flows_down]
