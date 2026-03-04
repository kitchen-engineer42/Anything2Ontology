"""Main orchestration pipeline for ontology assembly."""

import json
from datetime import datetime
from pathlib import Path

import structlog

from skus2ontology.assembler import OntologyAssembler
from skus2ontology.chatbot import SpecChatbot
from skus2ontology.config import settings
from skus2ontology.readme_generator import ReadmeGenerator
from skus2ontology.schemas.ontology import OntologyManifest

logger = structlog.get_logger(__name__)


class OntologyPipeline:
    """
    Main pipeline for assembling an ontology from SKUs.

    Steps:
    1. Assemble: copy/organize SKUs, rewrite paths
    2. Chatbot: interactive spec.md generation (optional)
    3. README: generate README.md
    """

    def __init__(
        self,
        skus_dir: Path | None = None,
        ontology_dir: Path | None = None,
    ):
        self.skus_dir = Path(skus_dir) if skus_dir else settings.skus_output_dir
        self.ontology_dir = Path(ontology_dir) if ontology_dir else settings.ontology_dir

    def run(self, skip_chatbot: bool = False) -> OntologyManifest:
        """
        Run the full ontology pipeline.

        Args:
            skip_chatbot: If True, skip the interactive chatbot step.

        Returns:
            OntologyManifest with assembly metadata.
        """
        start_time = datetime.now()
        logger.info(
            "Starting ontology pipeline",
            skus_dir=str(self.skus_dir),
            ontology_dir=str(self.ontology_dir),
            skip_chatbot=skip_chatbot,
        )

        # Step 1: Assemble
        manifest = self.assemble_only()

        # Step 2: Chatbot (optional)
        if not skip_chatbot:
            spec = self.chatbot_only()
            if spec:
                manifest.has_spec = True

        # Step 3: README
        readme_gen = ReadmeGenerator(self.ontology_dir)
        readme_gen.write(manifest)

        # Save manifest
        self._save_manifest(manifest)

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(
            "Ontology pipeline complete",
            total_files=manifest.total_files_copied,
            has_spec=manifest.has_spec,
            has_readme=manifest.has_readme,
            duration_seconds=f"{duration:.1f}",
        )

        return manifest

    def assemble_only(self) -> OntologyManifest:
        """Run only the assembly step."""
        assembler = OntologyAssembler(self.skus_dir, self.ontology_dir)
        return assembler.assemble()

    def chatbot_only(self) -> str:
        """
        Run only the chatbot step.
        Ontology must already exist with mapping.md.

        Returns:
            Spec content string.
        """
        chatbot = SpecChatbot(self.ontology_dir)
        spec = chatbot.run()

        # Save chat log
        session = chatbot.get_session()
        chat_log_path = self.ontology_dir / "chat_log.json"
        chat_log_path.write_text(
            session.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info(
            "Saved chat log",
            path=str(chat_log_path),
            rounds=session.rounds_used,
            confirmed=session.confirmed,
        )

        return spec

    def _save_manifest(self, manifest: OntologyManifest) -> None:
        """Save ontology manifest to disk."""
        manifest_path = self.ontology_dir / "ontology_manifest.json"
        manifest_path.write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info("Saved ontology manifest", path=str(manifest_path))
