"""CLI entry point for skus2ontology module."""

from pathlib import Path

import click

from skus2ontology.config import settings
from skus2ontology.pipeline import OntologyPipeline
from skus2ontology.utils.logging_setup import setup_logging


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
def main(verbose: bool):
    """SKUs2Ontology - Assemble SKUs into a self-contained ontology."""
    if verbose:
        settings.log_level = "DEBUG"
    setup_logging()


@main.command()
@click.option(
    "--skus-dir",
    "-s",
    type=click.Path(exists=True, path_type=Path),
    help="Source SKUs directory (default: output/skus/)",
)
@click.option(
    "--ontology-dir",
    "-w",
    type=click.Path(path_type=Path),
    help="Target ontology directory (default: ./ontology/)",
)
@click.option(
    "--skip-chatbot",
    is_flag=True,
    help="Skip the interactive chatbot step",
)
def run(skus_dir: Path | None, ontology_dir: Path | None, skip_chatbot: bool):
    """Run the full ontology pipeline."""
    pipeline = OntologyPipeline(
        skus_dir=skus_dir,
        ontology_dir=ontology_dir,
    )

    manifest = pipeline.run(skip_chatbot=skip_chatbot)

    zh = settings.language == "zh"
    click.echo(f"\n{'本体就绪！' if zh else 'Ontology ready!'}")
    click.echo(f"  {'位置' if zh else 'Location'}: {pipeline.ontology_dir}")
    click.echo(f"  {'事实型SKU' if zh else 'Factual SKUs'}: {manifest.factual_count}")
    click.echo(f"  {'程序型SKU' if zh else 'Procedural SKUs'}: {manifest.procedural_count}")
    rel_val = ('是' if zh else 'Yes') if manifest.has_relational else ('否' if zh else 'No')
    click.echo(f"  {'关系型' if zh else 'Relational'}: {rel_val}")
    spec_val = ('是' if zh else 'Yes') if manifest.has_spec else ('否' if zh else 'No')
    click.echo(f"  spec.md: {spec_val}")
    readme_val = ('是' if zh else 'Yes') if manifest.has_readme else ('否' if zh else 'No')
    click.echo(f"  README.md: {readme_val}")
    click.echo(f"  {'文件总数' if zh else 'Total files'}: {manifest.total_files_copied}")
    click.echo(f"  {'路径重写数' if zh else 'Paths rewritten'}: {manifest.paths_rewritten}")


@main.command()
@click.option(
    "--skus-dir",
    "-s",
    type=click.Path(exists=True, path_type=Path),
    help="Source SKUs directory",
)
@click.option(
    "--ontology-dir",
    "-w",
    type=click.Path(path_type=Path),
    help="Target ontology directory",
)
def assemble(skus_dir: Path | None, ontology_dir: Path | None):
    """Copy and organize SKUs into ontology (no chatbot)."""
    pipeline = OntologyPipeline(
        skus_dir=skus_dir,
        ontology_dir=ontology_dir,
    )

    manifest = pipeline.assemble_only()

    zh = settings.language == "zh"
    click.echo(f"\n{'组装完成！' if zh else 'Assembly complete!'}")
    click.echo(f"  {'位置' if zh else 'Location'}: {pipeline.ontology_dir}")
    click.echo(f"  {'事实型SKU' if zh else 'Factual SKUs'}: {manifest.factual_count}")
    click.echo(f"  {'程序型SKU' if zh else 'Procedural SKUs'}: {manifest.procedural_count}")
    click.echo(f"  {'文件总数' if zh else 'Total files'}: {manifest.total_files_copied}")
    click.echo(f"  {'路径重写数' if zh else 'Paths rewritten'}: {manifest.paths_rewritten}")


@main.command()
@click.option(
    "--ontology-dir",
    "-w",
    type=click.Path(exists=True, path_type=Path),
    help="Ontology directory (must already exist with mapping.md)",
)
def chatbot(ontology_dir: Path | None):
    """Run the spec chatbot on an existing ontology."""
    pipeline = OntologyPipeline(ontology_dir=ontology_dir)
    spec = pipeline.chatbot_only()

    if spec:
        click.echo(f"\nspec.md generated ({len(spec)} chars)")
        click.echo(f"  Saved to: {pipeline.ontology_dir / 'spec.md'}")
    else:
        click.echo("\nNo spec generated.")


@main.command()
def init():
    """Create the ontology directory."""
    settings.ontology_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"Created ontology directory: {settings.ontology_dir}")


if __name__ == "__main__":
    main()
