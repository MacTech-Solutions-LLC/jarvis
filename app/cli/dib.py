"""`jarvis dib` — defense solicitation analysis, on this machine only."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from app.dib import (
    LocalModel,
    analyze,
    assert_local_only,
    boundary_banner,
    render,
    summary_prompt,
)

dib_app = typer.Typer(help="DIB agent — analyse solicitations without sending them anywhere.")


def _read(path: Path) -> str:
    """Text from .txt/.md directly; PDFs via pypdf if present.

    A scanned PDF yields little or nothing — we say so rather than returning a
    confident empty analysis.
    """
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as e:  # pragma: no cover - environment dependent
            raise typer.BadParameter(
                "Reading PDFs needs pypdf: pip install pypdf. "
                "Or convert to text first — the analysis is identical."
            ) from e
        text = "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
        if len(text.strip()) < 200:
            typer.secho(
                "  ! Very little text extracted — this looks like a scanned PDF. "
                "Findings will be incomplete until it is OCR'd.",
                fg=typer.colors.YELLOW,
            )
        return text
    return path.read_text(errors="ignore")


def _posture(path: Path | None) -> dict:
    if not path:
        return {}
    return json.loads(path.read_text())


@dib_app.command("analyze")
def analyze_cmd(
    document: Path = typer.Argument(..., exists=True, readable=True),
    posture: Path = typer.Option(
        None, "--posture", help="JSON with your sprs_score, sprs_date, cmmc_level."
    ),
    no_summary: bool = typer.Option(
        False, "--no-summary", help="Skip the local model entirely; extraction only."
    ),
    model: str = typer.Option("llama3.1", "--model", help="Local Ollama model."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
):
    """Analyse a solicitation, SOW or contract for obligations and bid-stoppers."""
    text = _read(document)
    result = analyze(text, source=document.name, posture=_posture(posture))

    if as_json:
        from dataclasses import asdict

        typer.echo(json.dumps(asdict(result), indent=2, default=str))
        return

    summary = None
    model_ok = False
    endpoint = assert_local_only()
    if not no_summary:
        lm = LocalModel(model=model)
        model_ok = lm.available()
        if model_ok:
            try:
                summary = lm.summarize(summary_prompt(result))
            except Exception as e:  # local model is optional, never fatal
                typer.secho(f"  ! local model failed ({e}); showing extraction only",
                            fg=typer.colors.YELLOW)

    typer.echo(render(result, summary=summary, banner=boundary_banner(endpoint, model_ok)))
    raise typer.Exit(code=1 if result.blockers else 0)


@dib_app.command("clauses")
def clauses_cmd():
    """List the DFARS/FAR clauses this agent recognises."""
    from app.dib.clauses import CLAUSES

    for c in CLAUSES.values():
        flag = " ⇣" if c.flows_down else "  "
        typer.echo(f"{flag} {c.number}  {c.title}")
