"""Step 1: Assemble ontology by copying and reorganizing SKUs."""

import json
import re
import shutil
from pathlib import Path

import structlog

from skus2ontology.schemas.ontology import OntologyManifest

logger = structlog.get_logger(__name__)

# SKU subdirectories to copy
SKU_SUBDIRS = ["factual", "procedural", "relational"]

# Regex to match any prefix before a known SKU subdirectory
# e.g. "test_data/basel_skus/factual/sku_001" → "skus/factual/sku_001"
# e.g. "output/skus/procedural/skill_003" → "skus/procedural/skill_003"
# e.g. "test_data/basel_skus/meta" → "skus/meta" (no trailing slash)
PATH_REWRITE_PATTERN = re.compile(
    r"(?:^|(?<=[\s(/\"']))[\w./\-]+?(?=(?:factual|procedural|relational|meta)(?:/|$|\s|\"|\)|,))"
)


def _rewrite_path(text: str) -> tuple[str, int]:
    """
    Rewrite SKU paths in text, replacing any prefix before
    factual/procedural/relational/meta/ with 'skus/'.

    Returns:
        Tuple of (rewritten text, number of replacements).
    """
    count = 0

    def replacer(match: re.Match) -> str:
        nonlocal count
        count += 1
        return "skus/"

    result = PATH_REWRITE_PATTERN.sub(replacer, text)
    return result, count


class OntologyAssembler:
    """Copies and reorganizes SKUs into a self-contained ontology."""

    def __init__(self, skus_dir: Path, ontology_dir: Path):
        self.skus_dir = Path(skus_dir).resolve()
        self.ontology_dir = Path(ontology_dir).resolve()

    def assemble(self) -> OntologyManifest:
        """
        Run the full assembly process.

        Returns:
            OntologyManifest with counts and status.
        """
        logger.info(
            "Starting ontology assembly",
            skus_dir=str(self.skus_dir),
            ontology_dir=str(self.ontology_dir),
        )

        manifest = OntologyManifest(
            source_skus_dir=str(self.skus_dir),
            ontology_dir=str(self.ontology_dir),
        )

        # Validate source
        if not self.skus_dir.exists():
            logger.error("SKUs directory does not exist", path=str(self.skus_dir))
            raise FileNotFoundError(f"SKUs directory not found: {self.skus_dir}")

        mapping_path = self.skus_dir / "meta" / "mapping.md"
        if not mapping_path.exists():
            logger.warning("mapping.md not found in meta/", path=str(mapping_path))

        # Create ontology
        skus_dest = self.ontology_dir / "skus"
        skus_dest.mkdir(parents=True, exist_ok=True)

        total_files = 0

        # 1. Copy SKU subdirectories
        for subdir in SKU_SUBDIRS:
            src = self.skus_dir / subdir
            dst = skus_dest / subdir
            if src.exists():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                file_count = sum(1 for _ in dst.rglob("*") if _.is_file())
                total_files += file_count
                logger.info("Copied directory", subdir=subdir, files=file_count)

        # Count SKUs
        factual_dir = skus_dest / "factual"
        procedural_dir = skus_dest / "procedural"
        if factual_dir.exists():
            manifest.factual_count = sum(1 for d in factual_dir.iterdir() if d.is_dir())
        if procedural_dir.exists():
            manifest.procedural_count = sum(1 for d in procedural_dir.iterdir() if d.is_dir())
        manifest.has_relational = (skus_dest / "relational").exists()

        # 2. Copy postprocessing/ if exists
        postproc_src = self.skus_dir / "postprocessing"
        if postproc_src.exists():
            postproc_dst = skus_dest / "postprocessing"
            if postproc_dst.exists():
                shutil.rmtree(postproc_dst)
            shutil.copytree(postproc_src, postproc_dst)
            pp_count = sum(1 for _ in postproc_dst.rglob("*") if _.is_file())
            total_files += pp_count
            logger.info("Copied postprocessing", files=pp_count)

        # 3. Copy skus_index.json → ontology/skus/skus_index.json (with path rewriting)
        index_src = self.skus_dir / "skus_index.json"
        if index_src.exists():
            index_dst = skus_dest / "skus_index.json"
            rewrite_count = self._rewrite_skus_index(index_src, index_dst)
            manifest.paths_rewritten += rewrite_count
            total_files += 1
            logger.info("Copied and rewrote skus_index.json", paths_rewritten=rewrite_count)

        # 4. Copy eureka.md → ontology/eureka.md (root)
        eureka_src = self.skus_dir / "meta" / "eureka.md"
        if eureka_src.exists():
            eureka_dst = self.ontology_dir / "eureka.md"
            shutil.copy2(eureka_src, eureka_dst)
            manifest.has_eureka = True
            total_files += 1
            logger.info("Copied eureka.md to ontology root")

        # 5. Rewrite mapping.md → ontology/mapping.md (root)
        if mapping_path.exists():
            mapping_dst = self.ontology_dir / "mapping.md"
            content = mapping_path.read_text(encoding="utf-8")
            rewritten, rewrite_count = _rewrite_path(content)
            mapping_dst.write_text(rewritten, encoding="utf-8")
            manifest.has_mapping = True
            manifest.paths_rewritten += rewrite_count
            total_files += 1
            logger.info("Rewrote mapping.md", paths_rewritten=rewrite_count)

        manifest.total_files_copied = total_files

        logger.info(
            "Assembly complete",
            total_files=total_files,
            factual=manifest.factual_count,
            procedural=manifest.procedural_count,
            paths_rewritten=manifest.paths_rewritten,
        )

        return manifest

    def _rewrite_skus_index(self, src: Path, dst: Path) -> int:
        """
        Load skus_index.json, rewrite path fields, save to dst.

        Returns:
            Number of paths rewritten.
        """
        data = json.loads(src.read_text(encoding="utf-8"))
        count = 0

        for entry in data.get("skus", []):
            old_path = entry.get("path", "")
            if old_path:
                new_path, n = _rewrite_path(old_path)
                if n > 0:
                    entry["path"] = new_path
                    count += n

        dst.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return count
