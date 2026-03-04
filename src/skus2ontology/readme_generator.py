"""Step 3: Generate README.md for the ontology."""

from pathlib import Path

import structlog

from skus2ontology.config import settings
from skus2ontology.schemas.ontology import OntologyManifest

logger = structlog.get_logger(__name__)

README_TEMPLATE = {
    "en": """# Ontology

## Quick Start

1. **Read `spec.md`** — what to build
2. **Use `mapping.md`** — navigate SKUs by feature
3. **Check `eureka.md`** — creative ideas and cross-cutting insights

## Structure

```
ontology/
├── spec.md                      # App specification
├── mapping.md                   # SKU router — find the right knowledge
├── eureka.md                    # Creative insights and feature ideas
├── ontology_manifest.json       # Assembly metadata
├── chat_log.json                # Chatbot conversation log
└── skus/
    ├── factual/                 # Facts, definitions, data (header.md + content)
    ├── procedural/              # Skills and workflows (header.md + SKILL.md)
    ├── relational/              # Label tree + glossary
    ├── postprocessing/          # Bucketing, dedup, confidence reports
    └── skus_index.json          # Master index of all SKUs
```

## SKU Types

| Type | Description | Files |
|------|-------------|-------|
| **Factual** | Facts, definitions, data points, statistics | `header.md` + `content.md` or `content.json` |
| **Procedural** | Workflows, skills, step-by-step processes | `header.md` + `SKILL.md` |
| **Relational** | Category hierarchy and glossary | `label_tree.json` + `glossary.json` |

## Stats

{stats_section}

## How to Use

1. Start with `spec.md` to understand what the app should do
2. Use `mapping.md` to find relevant SKUs for each feature
3. Read SKU `header.md` files for quick summaries before loading full content
4. Reference `eureka.md` for creative ideas that connect multiple knowledge areas
""",

    "zh": """# 本体

## 快速开始

1. **阅读 `spec.md`** — 了解要构建什么
2. **使用 `mapping.md`** — 按功能导航SKU
3. **查看 `eureka.md`** — 创意和跨领域洞察

## 目录结构

```
ontology/
├── spec.md                      # 应用规格说明
├── mapping.md                   # SKU路由 — 找到正确的知识
├── eureka.md                    # 创意洞察和功能构想
├── ontology_manifest.json       # 组装元数据
├── chat_log.json                # 对话记录
└── skus/
    ├── factual/                 # 事实、定义、数据（header.md + content）
    ├── procedural/              # 技能和工作流（header.md + SKILL.md）
    ├── relational/              # 标签树 + 术语表
    ├── postprocessing/          # 分桶、去重、置信度报告
    └── skus_index.json          # 所有SKU的主索引
```

## SKU 类型

| 类型 | 描述 | 文件 |
|------|------|------|
| **事实型** | 事实、定义、数据点、统计 | `header.md` + `content.md` 或 `content.json` |
| **程序型** | 工作流、技能、分步流程 | `header.md` + `SKILL.md` |
| **关系型** | 分类层级和术语表 | `label_tree.json` + `glossary.json` |

## 统计

{stats_section}

## 使用方法

1. 从 `spec.md` 开始，了解应用的功能目标
2. 使用 `mapping.md` 为每个功能找到相关SKU
3. 阅读SKU的 `header.md` 了解摘要，再按需加载完整内容
4. 参考 `eureka.md` 获取连接多个知识领域的创意
""",
}

STATS_LABELS = {
    "en": {
        "factual": "Factual SKUs",
        "procedural": "Procedural SKUs",
        "relational": "Relational knowledge",
        "total_files": "Total files copied",
        "yes": "Yes",
        "no": "No",
    },
    "zh": {
        "factual": "事实型SKU",
        "procedural": "程序型SKU",
        "relational": "关系型知识",
        "total_files": "复制文件总数",
        "yes": "是",
        "no": "否",
    },
}


class ReadmeGenerator:
    """Generates README.md for the assembled ontology."""

    def __init__(self, ontology_dir: Path):
        self.ontology_dir = Path(ontology_dir).resolve()

    def write(self, manifest: OntologyManifest) -> None:
        """
        Generate and write README.md.

        Args:
            manifest: OntologyManifest with counts and status.
        """
        lang = settings.language
        labels = STATS_LABELS[lang]

        stats_lines = []
        stats_lines.append(f"- **{labels['factual']}**: {manifest.factual_count}")
        stats_lines.append(f"- **{labels['procedural']}**: {manifest.procedural_count}")
        rel_val = labels["yes"] if manifest.has_relational else labels["no"]
        stats_lines.append(f"- **{labels['relational']}**: {rel_val}")
        stats_lines.append(f"- **{labels['total_files']}**: {manifest.total_files_copied}")

        stats_section = "\n".join(stats_lines)
        content = README_TEMPLATE[lang].format(stats_section=stats_section)

        readme_path = self.ontology_dir / "README.md"
        readme_path.write_text(content, encoding="utf-8")

        manifest.has_readme = True
        logger.info("Generated README.md", path=str(readme_path))
