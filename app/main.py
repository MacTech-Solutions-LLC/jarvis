#!/usr/bin/env python3
"""Jarvis CLI - Local-first AI operator console"""

import typer
from pathlib import Path
import subprocess
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env immediately
load_dotenv()

# retrieve version from project metadata if available
try:
    from importlib.metadata import version
    __version__ = version("jarvis-cli")
except Exception:
    __version__ = "0.1.0"

app = typer.Typer(help="Jarvis CLI - Local-first AI operator console", add_completion=True)

@app.command()
def chat():
    """Start interactive chat session"""
    from app.cli.chat import chat_command
    chat_command()

@app.command()
def ask(question: str):
    """Ask a single question"""
    from app.cli.chat import ask_command
    ask_command(question)

@app.command()
def kb(query: str):
    """Search knowledge base"""
    from app.cli.kb import kb_search_command
    kb_search_command(query)

@app.command()
def workspace(command: str, name: str = None):
    """Workspace management"""
    from app.cli.workspace import workspace_command
    workspace_command(command, name)

@app.command()
def doctor():
    """Run diagnostic checks on API keys and configurations"""
    from app.cli.doctor import doctor_command
    doctor_command()

@app.command()
def image(
    prompt: str = typer.Argument(..., help="Image description prompt"),
    model: str = typer.Option("dall-e-3", help="Model to use (dall-e-3 or replicate)") ,
    size: str = typer.Option("1024x1024", help="Image size"),
    quality: str = typer.Option("standard", help="Image quality"),
    output: Path = typer.Option(None, help="Output file path")
):
    """Generate an image from text prompt. Use --model to select provider (dall-e-3 or replicate)."""
    from app.cli.media import image
    image(prompt, model, size, quality, output)

@app.command()
def tts(
    text: str = typer.Argument(..., help="Text to convert to speech"),
    voice: str = typer.Option("nova", help="Voice to use (run 'jarvis voices' to list options)") ,
    model: str = typer.Option("tts-1", help="TTS model (OpenAI only, ignored for ElevenLabs)") ,
    output: Path = typer.Option(None, help="Output file path"),
    play: bool = typer.Option(False, help="Play the audio after generation")
):
    """Convert text to speech. Choose a voice via 'jarvis voices' or set default with 'jarvis voice <name>'."""
    from app.cli.media import tts
    tts(text, voice, model, output, play)

@app.command()
def say(
    text: str = typer.Argument(..., help="What Jarvis should say"),
    output: Path = typer.Option(None, help="Output file path"),
    speed: float = typer.Option(1.0, help="Speaking rate (0.75–1.25 sounds natural)"),
    play: bool = typer.Option(True, help="Play the audio after generation")
):
    """Speak text in the Jarvis voice (OpenAI TTS, fixed character)."""
    from app.core.config import Config
    from app.core.paths import Paths
    from app.media.voice import JarvisVoice
    from app.media.player import MediaPlayer
    from rich.console import Console

    console = Console()
    config = Config()
    paths = Paths(config)
    voice_engine = JarvisVoice(config, paths)

    if not voice_engine.configured:
        console.print("[red]OPENAI_API_KEY is not configured — Jarvis has no voice.[/red]")
        raise typer.Exit(code=1)

    path = voice_engine.speak_to_file(text, output_path=output, speed=speed)
    console.print(f"[green]Saved:[/green] {path}")

    if play:
        MediaPlayer(config, paths).play_audio(path)


@app.command()
def suite(
    refresh: bool = typer.Option(False, help="Bypass the local cache")
):
    """Print the live MacTech Suite ops briefing."""
    from app.suite.client import SuiteClient, SuiteUnavailable
    from rich.console import Console

    console = Console()
    client = SuiteClient()

    if not client.configured:
        console.print(
            "[red]SUITE_AGENT_BRIEFING_TOKEN is not set — Jarvis is not "
            "connected to the Suite.[/red]"
        )
        raise typer.Exit(code=1)

    try:
        briefing = client.fetch(force=refresh)
    except SuiteUnavailable as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    console.print(briefing.to_prompt_context())


@app.command()
def stt(
    audio_file: Path = typer.Argument(..., help="Audio file to transcribe"),
    language: str = typer.Option(None, help="Language code (e.g., 'en', 'es')"),
    translate: bool = typer.Option(False, help="Translate to English"),
    model: str = typer.Option("whisper-1", help="STT model")
):
    """Convert speech to text"""
    from app.cli.media import stt
    stt(audio_file, language, translate, model)

@app.command()
def voices():
    """List available TTS voices"""
    from app.cli.media import voices
    voices()

@app.command()
def voice(
    name: str = typer.Argument(..., help="Voice name to set as default")
):
    """Set default TTS voice"""
    from app.cli.media import set_voice
    set_voice(name)

@app.command()
def play(
    media_file: Path = typer.Argument(..., help="Media file to play"),
    blocking: bool = typer.Option(True, help="Wait for playback to finish")
):
    """Play audio or video files"""
    from app.cli.media import play
    play(media_file, blocking)

@app.command()
def web():
    """Launch web UI"""
    streamlit_path = Path(__file__).parent.parent / "web" / "app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(streamlit_path)])

def _print_env():
    # show which APIs are configured
    from app.core.config import Config
    cfg = Config()
    avail = []
    if cfg.openai_api_key:
        avail.append("OpenAI")
    if os.getenv("GROQ_API_KEY"):
        avail.append("Groq")
    if os.getenv("TAVILY_API_KEY"):
        avail.append("Tavily")
    if os.getenv("GITHUB_TOKEN"):
        avail.append("GitHub")
    if os.getenv("REPLICATE_API_KEY"):
        avail.append("Replicate")
    if os.getenv("ANTHROPIC_API_KEY"):
        avail.append("Anthropic")
    if os.getenv("ELEVENLABS_API_KEY"):
        avail.append("ElevenLabs")
    if os.getenv("HUGGINGFACE_API_KEY"):
        avail.append("HuggingFace")
    if os.getenv("KLINGAI_API_KEY"):
        avail.append("KlingAI")
    if avail:
        typer.secho("Configured providers: " + ", ".join(avail), fg="green")

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version and exit"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug output")
):
    """Entry point for the CLI. Use --help on any command for details."""
    if version:
        typer.echo(f"Jarvis CLI version {__version__}")
        raise typer.Exit()
    if debug:
        typer.echo("Debug mode enabled")
    if ctx.invoked_subcommand is None:
        _print_env()
        typer.echo(ctx.get_help())

# allow 'main' to call app()
def cli():
    """Entry point used by console script. Runs the Typer application."""
    app()

if __name__ == "__main__":
    cli()