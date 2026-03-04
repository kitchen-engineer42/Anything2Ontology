# Anything2Ontology - Project Context

## Overview
Anything2Ontology is a knowledge management and modelling pipeline that converts various media formats into a comprehensive ontology for coding agents. The pipeline transforms inputs (files, URLs, repos) into structured knowledge that can be used by AI coding assistants to build applications.

## Key Design Principles

### 1. Agile Schema Design
Schemas have two parts:
- **Fixed part**: Standard fields that are always present
- **JIT (Just-In-Time) part**: Flexible metadata that agents can define case-by-case

Example: `ParseResult` has fixed fields (source_path, status) and a JIT `metadata` dict.

### 2. Loose Coupling
Modules are independent and communicate through well-defined interfaces (schemas). Each module can be developed, tested, and modified independently.

### 3. Load Context As Needed
Like Claude Code's SKILL.md approach - read headers first to decide whether to load full content. Minimize context loading until necessary.

### 4. Atomic Tools
Human behavioral sequences expressed in natural language should be encapsulated into atomic, deterministic tools (parsers, extractors).

### 5. Dual-Format Logging
All operations generate both:
- JSON logs (for machine parsing)
- Plain text logs (for human reading)

## Project Structure

```
Anything2Ontology/
├── src/
│   ├── anything2markdown/     # Module 1: Universal parser
│   │   ├── parsers/           # File parsers (MarkItDown, MinerU, PaddleOCR-VL, Tabular)
│   │   ├── url_parsers/       # URL parsers (YouTube, Bilibili, FireCrawl, Repomix)
│   │   ├── utils/             # Logging, file utils, retry logic
│   │   ├── schemas/           # ParseResult schema
│   │   ├── router.py          # Routing logic
│   │   ├── pipeline.py        # Main orchestration
│   │   └── cli.py             # CLI interface (anything2md)
│   ├── markdown2chunks/       # Module 2: Smart chunking
│   │   ├── chunkers/          # HeaderChunker, LLMChunker
│   │   ├── utils/             # Token estimation, Levenshtein
│   │   ├── schemas/           # Chunk, ChunksIndex
│   │   ├── router.py          # Markdown vs JSON routing
│   │   ├── pipeline.py        # Main orchestration
│   │   └── cli.py             # CLI interface (md2chunks)
│   ├── chunks2skus/           # Module 3: Knowledge extraction
│   │   ├── extractors/        # Factual, Relational, Procedural, Meta
│   │   ├── utils/             # Logging, LLM client
│   │   ├── schemas/           # SKU, LabelTree, Glossary, Index
│   │   ├── router.py          # Load chunks, route to extractors
│   │   ├── pipeline.py        # Main orchestration
│   │   └── cli.py             # CLI interface (chunks2skus)
│   └── skus2ontology/         # Module 4: Ontology assembly
│       ├── utils/             # Logging, LLM client (with multi-turn)
│       ├── schemas/           # OntologyManifest, ChatSession
│       ├── assembler.py       # Copy SKUs, rewrite paths
│       ├── chatbot.py         # Interactive spec.md generation
│       ├── readme_generator.py # Template-based README.md
│       ├── pipeline.py        # Main orchestration
│       └── cli.py             # CLI interface (skus2ontology)
├── input/                     # User input files
├── output/                    # Module 1 output (flat structure)
│   ├── chunks/                # Module 2 output (chunked markdown)
│   ├── passthrough/           # JSON files (unchanged)
│   └── skus/                  # Module 3 output (knowledge units)
├── ontology/                  # Module 4 output (self-contained ontology)
├── logs/                      # JSON and text logs
└── module_design/             # Design docs for each module
```

## Module 1: Anything2Markdown

### Purpose
Convert various file types and URLs into Markdown or JSON for downstream processing.

### Routing Logic
| Input | Parser |
|-------|--------|
| PDF (normal) | MarkItDown |
| PDF (scanned/low quality) | PaddleOCR-VL (fallback) |
| PPT, DOC, media | MarkItDown |
| xlsx, csv | TabularParser (→ JSON) |
| YouTube URL | YouTubeParser |
| Bilibili URL | BilibiliParser (subtitles or faster-whisper) |
| GitHub repo | RepomixParser |
| Other URLs | FireCrawlParser |

### CLI Commands
```bash
anything2md init          # Create directories
anything2md run           # Run full pipeline
anything2md run -v        # Verbose mode
anything2md parse-file X  # Parse single file
anything2md parse-url X   # Parse single URL
```

## Language Configuration

Set `LANGUAGE` in `.env` to control the output language of all LLM prompts:
- `LANGUAGE=en` (default) — English prompts, English output
- `LANGUAGE=zh` — Chinese prompts, Chinese output (titles, descriptions, definitions, README, mapping, eureka)

All prompt constants are `dict[str, str]` keyed by language code. At each call site, the prompt is selected via `PROMPT[settings.language]`. JSON keys, field names, enum values, and format specifications remain English in both languages.

**IMPORTANT: Dual-language rule** — When modifying any LLM prompt, always update BOTH the `"en"` and `"zh"` versions. Every prompt change must be applied to both languages to keep them in sync.

## Configuration

All settings in `.env`:
- `INPUT_DIR`, `OUTPUT_DIR`, `LOG_DIR` - Paths
- `MINERU_API_KEY`, `FIRECRAWL_API_KEY` - API keys
- `MAX_PDF_SIZE_MB=10` - Size threshold (MinerU disabled)
- `MIN_VALID_CHARS=500` - Quality threshold for OCR fallback
- `PADDLEOCR_MODEL=PaddlePaddle/PaddleOCR-VL-1.5` - OCR model (or `mlx-community/PaddleOCR-VL-1.5-8bit` for local)
- `OCR_DPI=150` - Page render resolution
- `OCR_PAGE_TIMEOUT=60` - Per-page API timeout
- `OCR_BASE_URL=` - Empty = SiliconFlow API; `http://localhost:8080` = local mlx-vlm
- `BILIBILI_COOKIES_FILE=` - Path to Netscape cookie file for Bilibili
- `BILIBILI_COOKIES_FROM_BROWSER=chrome` - Browser to extract cookies from (or empty)
- `WHISPERX_MODEL=small` - Whisper model for Bilibili transcription fallback
- `LOG_FORMAT=both` - Logging format

## Module 2: Markdown2Chunks

### Purpose
Split long markdown files into manageable chunks for LLM processing (max 100K tokens).

### Chunking Strategies
1. **Header Chunking ("Peeling Onion")**: Primary method for structured markdown. Splits by headers hierarchically (H1 → H2 → H3).
2. **LLM Chunking ("Driving Wedges")**: Fallback for plain text. Uses LLM to identify cut points with K nearest tokens, then Levenshtein matching.
3. **Rolling Context Window**: Slides through documents, processing one window at a time.

### Project Structure
```
src/markdown2chunks/
├── chunkers/           # HeaderChunker, LLMChunker
├── utils/              # Token estimation, Levenshtein, markdown parsing
├── schemas/            # Chunk, ChunkMetadata, ChunksIndex
├── router.py           # Route markdown vs JSON (pass-through)
├── pipeline.py         # Main orchestration
└── cli.py              # CLI interface
```

### CLI Commands
```bash
md2chunks run                 # Process all markdown from module 1
md2chunks chunk-file X        # Chunk single file
md2chunks estimate-tokens X   # Show token count
```

### Output Format
- Chunks saved as individual files with YAML frontmatter
- `chunks_index.json` tracks all chunks
- JSON files passed through to `output/passthrough/`

### Configuration
- `MAX_TOKEN_LENGTH=100000` - Max tokens per chunk
- `LLM_WINDOW_TOKENS=28000` - Max tokens for LLM call
- `K_NEAREST_TOKENS=50` - Tokens around cut point
- `CHUNKING_MODEL=Pro/Qwen/Qwen2.5-7B-Instruct` - SiliconFlow model

## Module 3: Chunks2SKUs

### Purpose
Extract knowledge from chunks into Standard Knowledge Units (SKUs) of 4 types.

### Knowledge Types
| Type | Description | Output |
|------|-------------|--------|
| **Factual** | Facts, data, definitions | SKU folders with content.md/json |
| **Relational** | Relations, label hierarchy, glossary | label_tree.json + glossary.json |
| **Procedural** | Workflows, skills, processes | SKILL.md (Claude Code format) |
| **Meta** | SKU routing + creative insights | mapping.md + eureka.md |

### Processing Flow
Chunks are processed sequentially. For each chunk:
1. **Factual Extractor** (isolated) → Creates new factual SKUs
2. **Relational Extractor** (read-and-update) → Updates label tree & glossary
3. **Procedural Extractor** (isolated) → Creates new skill folders
4. **Meta Extractor** (read-and-update) → Updates mapping.md, appends to eureka.md

### Project Structure
```
src/chunks2skus/
├── extractors/         # FactualExtractor, RelationalExtractor, ProceduralExtractor, MetaExtractor
├── utils/              # Logging, LLM client
├── schemas/            # SKUHeader, LabelTree, Glossary, SKUsIndex
├── router.py           # Load chunks, route to extractors
├── pipeline.py         # Main orchestration
└── cli.py              # CLI interface (chunks2skus)
```

### Output Structure
```
output/skus/
├── factual/            # SKU folders with header.md + content
├── relational/         # label_tree.json, glossary.json
├── procedural/         # Skill folders with SKILL.md
├── meta/               # mapping.md, eureka.md
└── skus_index.json     # Master index
```

### CLI Commands
```bash
chunks2skus run                    # Process all chunks
chunks2skus run -v                 # Verbose mode
chunks2skus extract-chunk <file>   # Extract from single chunk
chunks2skus show-index             # Display SKUs summary
chunks2skus init                   # Create output directories
```

### Configuration
- `EXTRACTION_MODEL=Pro/zai-org/GLM-5` - Model for extraction
- `SKUS_OUTPUT_DIR=./output/skus` - Output directory

## Module 4: SKUs2Ontology

### Purpose
Assemble extracted SKUs into a self-contained ontology where a coding agent can "read spec.md and start building." Three steps: copy/organize SKUs, interactive chatbot to generate spec.md, generate README.md.

### Pipeline Steps
1. **Assembly** (`assembler.py`): Copy factual/, procedural/, relational/, postprocessing/ into ontology/skus/. Copy eureka.md and mapping.md to ontology root. Rewrite all SKU paths (e.g. `output/skus/factual/sku_001` → `skus/factual/sku_001`) in mapping.md and skus_index.json.
2. **Chatbot** (`chatbot.py`): Interactive multi-turn conversation with LLM. Compresses mapping.md into a summary for the system prompt. User describes their app → LLM drafts spec.md → user iterates → `/confirm` to finalize. Max rounds configurable.
3. **README** (`readme_generator.py`): Template-based README.md with quick start, structure overview, SKU type table, and stats from OntologyManifest.

### Project Structure
```
src/skus2ontology/
├── utils/              # Logging, LLM client (call_llm + call_llm_chat)
├── schemas/            # OntologyManifest, ChatMessage, ChatSession
├── assembler.py        # Copy SKUs, rewrite paths
├── chatbot.py          # Interactive spec.md generation
├── readme_generator.py # Template-based README.md
├── pipeline.py         # Main orchestration
└── cli.py              # CLI interface (skus2ontology)
```

### Output Structure
```
ontology/
├── README.md                    # Entry point for agents
├── spec.md                      # App specification (from chatbot)
├── mapping.md                   # SKU router (paths rewritten to skus/...)
├── eureka.md                    # Creative insights
├── ontology_manifest.json       # Assembly metadata
├── chat_log.json                # Chatbot conversation log
└── skus/
    ├── factual/                 # header.md + content.md/json per SKU
    ├── procedural/              # header.md + SKILL.md per skill
    ├── relational/              # label_tree.json, glossary.json
    ├── postprocessing/          # bucketing, dedup, confidence reports
    └── skus_index.json          # Master index (paths rewritten)
```

### CLI Commands
```bash
skus2ontology run                                      # Full pipeline
skus2ontology run -v                                   # Verbose
skus2ontology run --skip-chatbot                       # No interactive chatbot
skus2ontology run -s <skus_dir> -w <ontology_dir>      # Custom paths
skus2ontology assemble -s <skus_dir> -w <ontology_dir> # Copy only
skus2ontology chatbot -w <ontology_dir>                # Chatbot only
skus2ontology init                                     # Create ontology dir
```

### Configuration
- `ONTOLOGY_DIR=./ontology` - Output ontology directory
- `CHATBOT_MODEL=Pro/zai-org/GLM-5` - Model for spec chatbot
- `MAX_CHAT_ROUNDS=5` - Max conversation rounds
- `CHATBOT_TEMPERATURE=0.4` - LLM temperature
- `CHATBOT_MAX_TOKENS=8000` - Max tokens per response

## Modules

1. **Anything2Markdown** ✓ - Universal parser
2. **Markdown2Chunks** ✓ - Smart chunking
3. **Chunks2SKUs** ✓ - Knowledge extraction (Factual, Relational, Procedural, Meta)
4. **SKUs2Ontology** ✓ - Ontology assembly with spec.md chatbot

## Development Notes

- Python 3.10+ required
- Install: `pip install -e ".[dev]"`
- External tool: `npm install -g repomix`
- Run tests: `pytest`
