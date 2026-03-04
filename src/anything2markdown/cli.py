"""CLI entry point for Anything2Markdown."""

import sys
from pathlib import Path

import click

from .config import settings
from .pipeline import Anything2MarkdownPipeline
from .router import Router
from .utils.file_utils import ensure_directory
from .utils.logging_setup import get_logger, setup_logging


@click.group()
@click.version_option(version="0.1.0", prog_name="anything2md")
def cli():
    """Anything2Markdown - Universal file and URL parser for LLM pipelines."""
    pass


@cli.command()
@click.option(
    "--input",
    "-i",
    "input_dir",
    type=click.Path(exists=True, path_type=Path),
    help="Input directory (overrides .env setting)",
)
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(path_type=Path),
    help="Output directory (overrides .env setting)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose (DEBUG) logging",
)
def run(input_dir: Path | None, output_dir: Path | None, verbose: bool):
    """
    Run the Anything2Markdown pipeline.

    Processes all files in the input directory and URLs from urls.txt,
    converting them to Markdown or JSON format.
    """
    # Override settings if provided
    if input_dir:
        settings.input_dir = input_dir
    if output_dir:
        settings.output_dir = output_dir
    if verbose:
        settings.log_level = "DEBUG"

    # Setup logging
    setup_logging()
    logger = get_logger(__name__)

    logger.info("Starting Anything2Markdown pipeline")
    logger.info("Input directory", path=str(settings.input_dir))
    logger.info("Output directory", path=str(settings.output_dir))

    try:
        # Run pipeline
        pipeline = Anything2MarkdownPipeline()
        results = pipeline.run()

        # Get summary
        summary = pipeline.get_summary()

        # Print summary to console
        zh = settings.language == "zh"
        click.echo("")
        click.echo("=" * 50)
        click.echo("流水线完成" if zh else "Pipeline Complete")
        click.echo("=" * 50)
        click.echo(f"{'总处理数' if zh else 'Total processed'}: {summary['total']}")
        click.echo(f"  {'成功' if zh else 'Success'}: {summary['success']}")
        click.echo(f"  {'失败' if zh else 'Failed'}: {summary['failed']}")
        click.echo(f"  {'跳过' if zh else 'Skipped'}: {summary['skipped']}")
        click.echo(f"{'输出目录' if zh else 'Output directory'}: {settings.output_dir}")

        # Exit with error code if any failures
        if summary["failed"] > 0:
            sys.exit(1)

    except Exception as e:
        logger.exception("Pipeline failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command("parse-file")
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(path_type=Path),
    help="Output directory",
)
def parse_file(file_path: Path, output_dir: Path | None):
    """Parse a single file."""
    # Setup
    setup_logging()

    output = output_dir or settings.output_dir
    ensure_directory(output)

    # Route and parse
    router = Router()
    try:
        parser = router.route_file(file_path)
        result = parser.parse(file_path, output)

        # OCR fallback for scanned PDFs with low-quality MarkItDown output
        if (
            file_path.suffix.lower() == ".pdf"
            and result.status == "success"
            and parser.parser_name == "markitdown"
            and result.output_path
            and result.output_path.exists()
        ):
            output_content = result.output_path.read_text(encoding="utf-8")
            if router.should_fallback_to_ocr(output_content):
                click.echo("MarkItDown extracted too few characters, falling back to PaddleOCR-VL...")
                result.output_path.unlink(missing_ok=True)
                ocr_parser = router.get_ocr_fallback_parser()
                result = ocr_parser.parse(file_path, output)

        click.echo(f"Status: {result.status}")
        click.echo(f"Parser: {result.parser_used}")
        if result.status == "success":
            click.echo(f"Output: {result.output_path}")
            click.echo(f"Characters: {result.character_count}")
        else:
            click.echo(f"Error: {result.error_message}")

        if result.status == "failed":
            sys.exit(1)

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command("parse-url")
@click.argument("url")
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(path_type=Path),
    help="Output directory",
)
def parse_url(url: str, output_dir: Path | None):
    """Parse a single URL."""
    # Setup
    setup_logging()

    output = output_dir or settings.output_dir
    ensure_directory(output)

    # Route and parse
    router = Router()
    parser = router.route_url(url)
    result = parser.parse(url, output)

    click.echo(f"Status: {result.status}")
    click.echo(f"Parser: {result.parser_used}")
    if result.status == "success":
        click.echo(f"Output: {result.output_path}")
        click.echo(f"Characters: {result.character_count}")
    else:
        click.echo(f"Error: {result.error_message}")

    if result.status == "failed":
        sys.exit(1)


@cli.command()
def init():
    """Initialize project directories and create example files."""
    # Create directories
    ensure_directory(settings.input_dir)
    ensure_directory(settings.output_dir)
    ensure_directory(settings.log_dir)
    ensure_directory(settings.log_dir / "json")
    ensure_directory(settings.log_dir / "text")

    # Create urls.txt if it doesn't exist
    urls_file = settings.input_dir / "urls.txt"
    if not urls_file.exists():
        urls_file.write_text(
            "# Add URLs to parse, one per line\n"
            "# Examples:\n"
            "# https://example.com\n"
            "# https://www.youtube.com/watch?v=dQw4w9WgXcQ\n"
            "# https://github.com/microsoft/markitdown\n",
            encoding="utf-8",
        )

    # Create .gitkeep in output
    gitkeep = settings.output_dir / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()

    click.echo("Initialized Anything2Ontology directories:")
    click.echo(f"  Input:  {settings.input_dir}")
    click.echo(f"  Output: {settings.output_dir}")
    click.echo(f"  Logs:   {settings.log_dir}")
    click.echo("")
    click.echo(f"Add files to {settings.input_dir} and URLs to {urls_file}")


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
