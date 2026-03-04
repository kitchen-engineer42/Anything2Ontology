# Anything2Ontology Pipeline Specification

**Version**: 1.4
**Last Updated**: 2026-02-17
**Status**: Modules 1-4 Complete, Module 5 Pending

---

## Executive Summary

Anything2Ontology is a knowledge management pipeline that transforms diverse media inputs (documents, videos, websites, code repositories) into a structured ontology optimized for AI coding agents. The end goal: a user can point Claude Code or similar agents at this ontology and say "Read this file and start building" to produce a working application.

The pipeline consists of 5 loosely-coupled modules:
1. **Anything2Markdown** - Universal parser (Complete)
2. **Markdown2Chunks** - Smart chunking (Complete)
3. **Chunks2SKUs** - Knowledge extraction (Complete)
4. **SKUs2Ontology** - Workspace assembly (Complete)
5. **Pipeline Summary** - Run reporting (Pending)

This document specifies Modules 1-4 in detail.

---

## Design Philosophy

### Core Principles

1. **Agile Schemas**: Every data structure has a fixed part (predictable fields) and a JIT (Just-In-Time) part (flexible metadata that adapts to context). We pre-define stable fields for consistency, while giving LLMs freedom to define additional fields case-by-case based on specific scenarios. This prevents over-engineering while maintaining structure.

2. **Agile Indicators**: The calculation of any metric or indicator should be adaptive. We define aspects to consider, but build mechanisms to calculate and assign different weights via sample testing with SOTA models. Conceptually, this resembles model distillation—using powerful models to calibrate lighter processes.

3. **Iterative File Updates**: Instead of generating one-time summary files after entire processes finish, update content and structure during each iteration. This ensures intermediate state is always recoverable and progress is never lost.

4. **Load Context As Needed**: Inspired by how Claude Code reads SKILL.md—scan headers first, load full content only when relevant. Minimize memory and token usage by loading context when needed, not preemptively.

5. **Atomic Tool Encapsulation**: Encapsulate human behavioral sequences expressed in natural language into atomic, deterministic tools. Complex multi-step processes become reliable, repeatable operations.

6. **Loose Coupling**: Modules communicate through well-defined interfaces (files and schemas). Each module can be developed, tested, and replaced independently.

7. **Preserve Information**: Bigger chunks > smaller chunks. Every split loses context. Only chunk when necessary, never over-chunk.

8. **Graceful Degradation**: Every operation has fallbacks. If the primary method fails, the system degrades gracefully rather than crashing.

9. **Dual-Format Logging**: All operations produce both JSON logs (machine-parseable) and text logs (human-readable). Well-structured logs are essential for debugging and pipeline observability.

---

## Module 1: Anything2Markdown

### Purpose

Convert any supported input into Markdown or JSON, creating a uniform format for downstream processing. This is the "front desk" that routes each input to the appropriate parser.

### Why Markdown?

- **Universal**: Works with any LLM without special handling
- **Structured**: Headers provide natural chunking boundaries
- **Readable**: Humans can inspect and edit intermediate outputs
- **Lightweight**: No binary formats, easy to diff and version

### Why JSON for Tabular Data?

Markdown tables are lossy for structured data. A 1000-row spreadsheet becomes unreadable as a Markdown table. JSON preserves:
- Data types (numbers stay numbers)
- Nested structures
- Array semantics
- Exact precision

---

### Input Types & Routing

#### File Inputs

| Extension | Primary Parser | Fallback | Rationale |
|-----------|---------------|----------|-----------|
| `.pdf` | MarkItDown | PaddleOCR-VL | MarkItDown is fast and free. PaddleOCR-VL (vision-language OCR) handles scanned/image-heavy PDFs via SiliconFlow API. Replaced MinerU (disabled due to network issues). |
| `.pptx`, `.ppt` | MarkItDown | - | Microsoft's own library handles these well |
| `.docx`, `.doc` | MarkItDown | - | Same as above |
| `.mp3`, `.mp4`, `.wav` | MarkItDown | - | Uses speech recognition for transcription |
| `.jpg`, `.png`, `.jpeg` | MarkItDown | - | Image description via vision models |
| `.html`, `.htm` | MarkItDown | - | Extracts text content |
| `.md`, `.txt` | MarkItDown | - | Pass-through with minimal processing |
| `.xlsx`, `.xls` | TabularParser | - | Converts to JSON, not Markdown |
| `.csv` | TabularParser | - | Same as above |

**OCR Fallback Trigger** (PaddleOCR-VL):
- MarkItDown output has < 500 valid characters (`MIN_VALID_CHARS`) → falls back to PaddleOCR-VL
- Renders each page to PNG via PyMuPDF at configurable DPI, sends to vision API
- Retries once per page on failure, inserts placeholder for unrecoverable pages
- Previous MinerU fallback disabled due to Alibaba Cloud Shanghai network issues
- **Dual backend**: SiliconFlow API (default, `PaddlePaddle/PaddleOCR-VL-1.5`) or local mlx-vlm server (`mlx-community/PaddleOCR-VL-1.5-8bit`)
- Set `OCR_BASE_URL=http://localhost:8080` for local deployment; leave empty to use SiliconFlow API
- Local server bypasses system proxy automatically; strips `<|LOC_xxx|>` bounding-box tokens from output

#### URL Inputs

URLs are listed in `input/urls.txt`, one per line.

| URL Pattern | Parser | Rationale |
|-------------|--------|-----------|
| `youtube.com/watch`, `youtu.be/` | YouTubeParser | Extracts transcript via youtube-transcript-api |
| `github.com/owner/repo` (root only) | RepomixParser | Converts entire repo to single Markdown via repomix CLI |
| All other URLs | FireCrawlParser | Crawls multi-page websites, respects robots.txt |

**Why not GitHub API for repos?**
Repomix produces a single, well-structured Markdown file with proper code fencing and file organization. Raw API calls would require us to build this structure ourselves.

**Why FireCrawl for websites?**
FireCrawl handles JavaScript-rendered content, pagination, and multi-page crawling. Simple HTTP requests miss dynamic content and require manual link following.

---

### Output Format

#### Directory Structure
```
output/
├── document_name.md           # Parsed markdown
├── spreadsheet_name.json      # Tabular data as JSON
├── folder1_folder2_file.md    # Nested paths flattened
└── youtube_VIDEO_ID.md        # URL-based outputs
```

#### Path Flattening

**Why flatten?**
- Downstream modules don't need to traverse directories
- Filenames encode full provenance
- Simpler glob patterns for batch processing

**Example**:
```
input/reports/2024/Q1/sales.pdf
→ output/reports_2024_Q1_sales.md
```

#### ParseResult Schema

```python
class ParseResult(BaseModel):
    source_path: Path           # Original file location
    output_path: Path           # Where output was written
    source_type: str            # "file" or "url"
    parser_used: str            # "markitdown", "mineru", "youtube", etc.
    status: str                 # "success" or "failed"
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    output_format: str          # "markdown" or "json"
    character_count: int | None
    error_message: str | None
    metadata: dict              # JIT fields (page count, video duration, etc.)
```

---

### CLI Interface

```bash
anything2md init              # Create input/, output/, logs/ directories
anything2md run               # Process all files and URLs
anything2md run -v            # Verbose mode
anything2md parse-file X      # Parse single file
anything2md parse-url X       # Parse single URL
```

---

### Configuration

All settings in `.env`:

```bash
# Paths
INPUT_DIR=./input
OUTPUT_DIR=./output
LOG_DIR=./logs

# API Keys
SILICONFLOW_API_KEY=sk-xxx    # For LLM features
MINERU_API_KEY=xxx            # For VLM PDF parsing
FIRECRAWL_API_KEY=xxx         # For website crawling

# Thresholds
MAX_PDF_SIZE_MB=10            # Size threshold (unused, MinerU disabled)
MIN_VALID_CHARS=500           # Quality threshold for OCR fallback

# PaddleOCR-VL (scanned PDF OCR)
PADDLEOCR_MODEL=PaddlePaddle/PaddleOCR-VL-1.5  # SiliconFlow model ID
OCR_DPI=150                   # Page render resolution
OCR_PAGE_TIMEOUT=60           # Per-page API timeout (seconds)
OCR_BASE_URL=                 # Empty = SiliconFlow API; http://localhost:8080 = local mlx-vlm

# Retry
RETRY_COUNT=1
RETRY_DELAY_SECONDS=2

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=both               # json, text, or both
```

---

### Error Handling

1. **Retry Once**: Failed operations retry once after delay, then skip
2. **Never Block**: One failed file doesn't stop the pipeline
3. **Log Everything**: Failures are logged with full context for debugging
4. **Return Status**: ParseResult includes error_message for failed items

---

## Module 2: Markdown2Chunks

### Purpose

Split markdown files that exceed LLM context limits into smaller, semantically coherent chunks while preserving as much context as possible.

### Why 100K Token Limit?

- Most modern LLMs support 100K-200K context windows
- Larger chunks = less information loss at boundaries
- Single chunk = no splitting overhead
- Configurable via `MAX_TOKEN_LENGTH` for different models

### Why Not Just Split by Character Count?

- Characters ≠ tokens (ratio varies 1:1 to 1:5 depending on language/content)
- Splitting mid-sentence destroys meaning
- Splitting mid-section loses context
- We need semantic boundaries, not arbitrary cuts

---

### Chunking Strategies

#### Strategy 1: Header Chunking ("Peeling Onion")

**When**: Markdown has headers (H1, H2, H3, etc.)

**How**:
1. Parse markdown into section tree by headers
2. Calculate token count for each section (including children)
3. If section fits in limit → output as single chunk
4. If section too large → recurse into children
5. If leaf section still too large → fall back to LLM chunking

**Why "Peeling Onion"?**
Like peeling an onion layer by layer, we only split at natural boundaries (headers) and only go deeper when necessary.

**Example**:
```markdown
# Chapter 1 (50K tokens total)
  ## Section 1.1 (20K tokens) → Chunk 1
  ## Section 1.2 (30K tokens) → Chunk 2
# Chapter 2 (80K tokens total) → Chunk 3
```

#### Strategy 2: LLM Chunking ("Driving Wedges")

**When**:
- No headers in content (plain text)
- Header section still exceeds limit after recursion

**How**:
1. Load first 100K tokens into LLM (Rolling Context Window)
2. Ask LLM: "Where should this text be split?"
3. LLM returns K tokens before and after each suggested cut point
4. Use Levenshtein distance to locate exact positions in original text
5. Cut at first valid position
6. Slide window to start from last cut point
7. Repeat until document is fully processed

**Why K Nearest Tokens Instead of Full Content?**

If we asked LLM to output the full chunks:
- Token cost: O(n) output tokens per chunk
- Error rate: LLM might modify/hallucinate content
- Verification: Hard to verify output matches input

With K nearest tokens:
- Token cost: O(k) output tokens per chunk (k=50 by default)
- Error tolerance: Levenshtein handles minor differences
- Verification: We cut the original text, not LLM output

**Why Levenshtein Distance?**

LLM output is approximate. "The quick brown fox" might come back as "The quick brown fox." (with period) or "the quick brown fox" (lowercase). Levenshtein finds the best match within a search window, tolerating small differences.

#### Rolling Context Window

**Problem**: Document has 500K tokens but LLM can only process 100K at a time.

**Solution**:
1. Load tokens 0-100K, find cut points, cut
2. Load tokens from last_cut to last_cut+100K, find cut points, cut
3. Repeat until end of document

**Why not parallel processing?**
Each window needs to start from the previous cut point to maintain continuity. Parallel would create gaps or overlaps.

---

### LLM Response Parsing

#### The Problem

LLMs frequently return malformed JSON:
```json
{
  cut_points: [                    // Missing quotes on key
    {
      'tokens_before': "text",     // Single quotes
      "tokens_after": "more text"
    }
  ]
}
```

#### The Solution

Two-stage parsing:
1. **Try `json.loads()`** - Standard JSON parsing
2. **Regex fallback** - Extract values using patterns:
   ```
   ["\']?tokens_before["\']?\s*:\s*["\'](.+?)["\']
   ```

This handles:
- Unquoted keys
- Single quotes
- Mixed quote styles
- Extra text around JSON

---

### Output Format

#### Chunk Files

Each chunk is a markdown file with YAML frontmatter:

```markdown
---
title: "Section 1.2: Data Processing"
source: "original_document.md"
chunk: 2
total: 5
tokens: 45000
method: "header"
---

[Actual content here...]
```

**Frontmatter Fields**:
- `title`: Section header or LLM-generated title
- `source`: Original filename
- `chunk`: Position in sequence (1-indexed for humans)
- `total`: Total chunks from this source
- `tokens`: Estimated token count
- `method`: "single", "header", or "llm"

#### Chunks Index

`chunks_index.json` provides a master manifest:

```json
{
  "created_at": "2026-02-14T21:58:17",
  "total_chunks": 145,
  "total_tokens": 544936,
  "source_files": ["doc1.md", "doc2.md"],
  "chunks": [
    {
      "chunk_id": "doc1_chunk_001",
      "file_path": "output/chunks/doc1_chunk_001.md",
      "title": "Introduction",
      "estimated_tokens": 15000,
      "source_file": "doc1.md",
      "chunking_method": "header"
    }
  ]
}
```

#### JSON Pass-through

JSON files from Module 1 (tabular data) skip chunking entirely and are copied to `output/passthrough/`. Rationale: JSON data should be queried, not split.

---

### Token Estimation

#### Why tiktoken?

- **Local**: No API calls, runs instantly
- **Accurate**: Same tokenizer used by GPT-4/Claude
- **Fast**: Millions of tokens per second
- **Encoding**: `cl100k_base` (100K vocabulary, modern standard)

#### Character-to-Token Ratios

Observed in testing:
- English prose: ~4.5 chars/token
- Chinese text: ~1.3 chars/token
- Code: ~3.5 chars/token
- Mixed content: ~3-4 chars/token

This is why character-based splitting doesn't work—a 100K character Chinese document is ~77K tokens, while a 100K character English document is only ~22K tokens.

---

### CLI Interface

```bash
md2chunks run                 # Process all files from Module 1 output
md2chunks run -v              # Verbose mode
md2chunks chunk-file X        # Chunk single file
md2chunks estimate-tokens X   # Show token count without chunking
```

---

### Configuration

```bash
# Chunking
MAX_TOKEN_LENGTH=100000       # Target chunk size
K_NEAREST_TOKENS=50           # Tokens around cut point

# LLM (SiliconFlow)
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
CHUNKING_MODEL=Pro/zai-org/GLM-4.7    # Fast model for chunking
COMPLEX_MODEL=Pro/zai-org/GLM-5        # Reserved for complex tasks
```

---

### Performance Characteristics

#### Stress Test: Basel Framework (2000 pages)

| Metric | Value |
|--------|-------|
| Input | 9.8MB PDF |
| Parsed text | 3.45M characters |
| Token count | 781,290 |
| Output chunks | 21 |
| Processing time | ~47 minutes |
| LLM calls | ~10 (100K tokens each) |

#### Bottlenecks

1. **LLM API latency**: ~7 minutes per 100K token call to GLM-4.7
2. **Sequential processing**: Rolling window requires sequential calls
3. **PDF parsing**: Large PDFs take 20-30 seconds

#### Optimizations Applied

1. **Header chunking first**: Most documents split without LLM calls
2. **Regex fallback**: Avoids re-calling LLM on JSON parse failures
3. **Local tokenization**: No API calls for token counting

---

## Module 3: Chunks2SKUs

### Purpose

Extract structured knowledge from chunks into four types of Standard Knowledge Units (SKUs): Factual, Relational, Procedural, and Meta. This transforms raw text into actionable knowledge that AI coding agents can use to build applications.

### Why Four Knowledge Types?

Different knowledge serves different purposes in application building:

| Type | What It Captures | Example | Use Case |
|------|------------------|---------|----------|
| **Factual** | Data, facts, definitions, statistics | "CET1 ratio must be ≥4.5%" | Reference data, validation rules |
| **Relational** | Hierarchies, taxonomies, term definitions | Risk → Credit Risk → IRB Approach | Navigation, disambiguation |
| **Procedural** | Workflows, step-by-step processes | "Calculate G-SIB score in 6 steps" | Executable procedures, automations |
| **Meta** | SKU routing, creative insights | "Use skill_003 for CVA calculations" | System organization, feature ideas |

### Processing Model

#### Sequential Extraction
Each chunk passes through all four extractors in order:
```
Factual → Relational → Procedural → Meta
```

**Why this order?**
- Meta extractor needs all SKU paths to build the routing map
- Relational builds context that could inform other extractions
- No dependency between Factual and Procedural (both isolated)

#### Two Processing Modes

| Mode | Extractors | Behavior |
|------|------------|----------|
| **Isolated** | Factual, Procedural | Each chunk processed independently, outputs new SKUs |
| **Read-and-Update** | Relational, Meta | Read existing files, merge new knowledge, write back |

**Why Read-and-Update for Relational/Meta?**
- Relational knowledge accumulates (glossary grows, label tree expands)
- Meta knowledge needs full picture (mapping references all SKUs)
- Avoids duplicate entries and maintains consistency

---

### Output Structure

```
output/skus/
├── factual/
│   ├── sku_001/
│   │   ├── header.md          # Metadata (+ confidence after proofread)
│   │   └── content.md         # or content.json for structured data
│   └── ...
├── relational/
│   ├── header.md              # Describes the knowledge base
│   ├── label_tree.json        # Multi-level category hierarchy
│   └── glossary.json          # Term definitions with labels
├── procedural/
│   ├── skill_001/
│   │   └── SKILL.md           # Claude Code skill format
│   └── ...
├── meta/
│   ├── header.md
│   ├── mapping.md             # SKU router (when to use what)
│   └── eureka.md              # Creative insights (append-only)
├── postprocessing/
│   ├── bucketing_result.json  # Bucket assignments
│   ├── dedup_report.json      # Dedup actions
│   └── confidence_report.json # Per-SKU confidence scores
└── skus_index.json            # Master index (with confidence field)
```

---

### Extractors

#### Factual Extractor

**Input**: Chunk content (isolated)
**Output**: 0-N new SKU folders in `factual/`

Each SKU contains:
- `header.md`: Name, classification, char count, source, description
- `content.md`: The factual knowledge (or `content.json` for tabular data)

**Extraction Focus**:
- Definitions and terminology
- Statistics and metrics
- Rules and requirements
- Reference data

#### Relational Extractor

**Input**: Chunk content + existing `label_tree.json` + `glossary.json`
**Output**: Updated `label_tree.json` and `glossary.json`

**label_tree.json** - Hierarchical categories:
```json
{
  "roots": [
    {
      "name": "Capital Requirements",
      "children": [
        {"name": "Credit Risk", "children": [...]},
        {"name": "Market Risk", "children": [...]}
      ]
    }
  ]
}
```

**glossary.json** - Term definitions:
```json
{
  "entries": [
    {
      "term": "CET1",
      "definition": "Common Equity Tier 1 - highest quality capital",
      "labels": ["Capital Requirements", "Regulatory Ratios"],
      "source_chunk": "BaselFramework_chunk_003",
      "related_terms": ["Tier 1", "Capital Ratio"]
    }
  ]
}
```

#### Procedural Extractor

**Input**: Chunk content (isolated)
**Output**: 0-N new skill folders in `procedural/`

Each skill uses Claude Code format with YAML frontmatter:

```markdown
---
name: g-sib-score-calculation
description: Calculate systemic importance score using indicator-based approach
---

# G-SIB Score Calculation

## Overview
This procedure calculates a bank's systemic importance score...

## Steps

### 1. Collect Indicator Data
Gather data for all 13 indicators across five categories...

### 2. Convert Currency
Convert all data from reporting currency to euros...

## Decision Points
- Score ≥ 130 basis points: Bank is classified as G-SIB
- Score < 130 basis points: May still be designated via supervisory judgment
```

#### Meta Extractor

**Input**: Chunk content + all current SKUs + existing `mapping.md` + `eureka.md`
**Output**: Updated `mapping.md`, appended `eureka.md`

**Dual-Prompt Design** (different temperatures for different tasks):

| File | Temperature | System Prompt Focus |
|------|-------------|---------------------|
| `mapping.md` | 0.2 (low) | Accuracy, precision, no hallucination |
| `eureka.md` | 0.7 (high) | Creativity, unexpected connections |

**mapping.md** - SKU router:
```markdown
# SKU Mapping

## Capital Requirements
- `factual/sku_012`: CET1 ratio requirements - use for capital adequacy checks
- `procedural/skill_003`: G-SIB score calculation - use when classifying banks

## Risk Measurement
- `factual/sku_045`: SA-CCR formulas - use for counterparty credit risk
```

**eureka.md** - Creative insights (append-only):
```markdown
### From BaselFramework_chunk_005

- [Feature] The margin period of risk formula could inspire a "complexity penalty"
  calculator showing how operational factors increase risk horizons
- [Design] The "waterfall allocation" pattern for default fund contributions
  could be visualized showing how losses flow through CCP structure
```

---

### LLM Configuration

```bash
EXTRACTION_MODEL=Pro/zai-org/GLM-5
SKUS_OUTPUT_DIR=./output/skus
```

**Temperature Settings**:
- Factual: 0.3 (balanced accuracy)
- Relational: 0.3 (structured output)
- Procedural: 0.3 (clear steps)
- Meta/Mapping: 0.2 (high accuracy)
- Meta/Eureka: 0.7 (creative exploration)

---

### CLI Interface

```bash
# Extraction
chunks2skus run                    # Process all chunks from Module 2
chunks2skus run -v                 # Verbose mode (use: chunks2skus -v run)
chunks2skus extract-chunk <path>   # Process single chunk through all extractors
chunks2skus show-index             # Display SKUs index summary
chunks2skus init                   # Create output directories

# Postprocessing
chunks2skus postprocess all -s <skus_dir> -c <chunks_dir>   # All 3 steps
chunks2skus postprocess bucket -s <skus_dir>                 # Bucketing only
chunks2skus postprocess dedup -s <skus_dir>                  # Dedup only
chunks2skus postprocess proof -s <skus_dir> -c <chunks_dir>  # Proofreading only
```

---

### Section 3.4: Postprocessing

Three postprocessing steps run after extraction to refine SKU quality.

#### Step 1: Bucketing

Group factual and procedural SKUs by similarity into buckets (≤100K tokens each) for efficient downstream processing.

**Similarity Matrix** (N×N, weighted sum):

| Aspect | Weight | Method |
|--------|--------|--------|
| Literal | 0.2 | TF-IDF on descriptions → cosine similarity (sklearn) |
| Label | 0.3 | Jaccard similarity on label paths from `label_tree.json` |
| Vector | 0.5 | bge-m3 embeddings → cosine similarity (SiliconFlow API) |

**Splitting**: Agglomerative clustering (scipy, average linkage). Recursive: if a bucket exceeds `MAX_BUCKET_TOKENS`, split into 2 and recurse.

**Fallbacks**: Embedding API down → reweight literal+label. Label tree missing → reweight literal+vector. Both down → literal only.

#### Step 2: Dedup/Contradiction (Two-Tier)

**Tier 1 — Quick Scan** (cheap model, headers only):
- Scan each bucket's SKU headers (name + description) for potential duplicates
- Model: `DEDUP_SCAN_MODEL` (default: Qwen3-VL-235B), temp 0.2
- Large buckets sub-batched at 80 headers per call
- Over-flagging is cheap; Tier 2 filters false positives

**Tier 2 — Deep Read** (GLM-5, flagged pairs only):
- Load full content of both SKUs
- Conservative: "when in doubt, KEEP both"
- Actions: `keep` / `delete` / `rewrite` / `merge`
- Applies on disk: removes folders, updates `skus_index.json`, cleans `mapping.md`

**Safety**: All LLM-returned SKU IDs validated against bucket. Single-SKU buckets skipped.

#### Step 3: Proofreading/Confidence (Bipolar Design)

**Key insight**: Source chunk alignment proves extraction faithfulness, NOT knowledge reliability. High alignment should not inflate confidence. Only external verification matters.

**Bipolar scoring**:

1. **Source Integrity Check (penalty only)**:
   - Faithful extraction → no penalty (neutral)
   - Distortion/hallucination vs source → hard penalty (0.2-0.5)
   - Source unavailable → skip

2. **External Verification (the real signal)**:
   - Web search via Jina `s.jina.ai` (5 results per SKU)
   - Score 0.0-1.0 based on independent corroboration

3. **Final**: `confidence = web_confidence - source_penalty` (clamped 0.0-1.0)

**Scoring Guide**:
| Range | Meaning |
|-------|---------|
| 0.8-1.0 | Multiple web sources corroborate |
| 0.6-0.8 | Some corroboration, minor gaps |
| 0.4-0.6 | Ambiguous — neither confirmed nor denied |
| 0.2-0.4 | Weak external support |
| 0.0-0.2 | Contradicted by external sources |

**Resilience**: Jina down → score on ambiguity (0.5); source missing → no penalty; resumable (skips scored SKUs).

#### Postprocessing Output

```
output/skus/postprocessing/
├── bucketing_result.json       # Bucket assignments + similarity metadata
├── dedup_report.json           # Actions taken per pair
└── confidence_report.json      # Per-SKU confidence + web references
```

#### Postprocessing Configuration

```bash
MAX_BUCKET_TOKENS=100000
EMBEDDING_MODEL=Pro/BAAI/bge-m3
SIMILARITY_WEIGHT_LITERAL=0.2
SIMILARITY_WEIGHT_LABEL=0.3
SIMILARITY_WEIGHT_VECTOR=0.5
DEDUP_SCAN_MODEL=Qwen/Qwen3-VL-235B-A22B-Instruct
JINA_API_KEY=...
```

#### Postprocessing Dependencies

```
scikit-learn>=1.3.0    # TF-IDF + cosine similarity
scipy>=1.11.0          # Agglomerative clustering
```

---

### Performance Characteristics

#### Stress Test: Basel Framework (21 chunks, ~863K tokens)

| Metric | Value |
|--------|-------|
| Input chunks | 21 |
| Total tokens | 863,325 |
| Factual SKUs | 84 |
| Procedural skills | 21 |
| Relational entries | 200+ glossary terms |
| Eureka insights | 63 bullets |
| Processing time | ~2 hours |
| LLM calls | ~84 (4 per chunk) |

#### Error Handling

- **Timeout**: One relational extraction timed out - system continued gracefully
- **JSON Parse Failures**: Regex fallback extracts structured data from malformed responses
- **Empty Responses**: Logged and skipped, no data corruption

---

## Module 4: SKUs2Ontology

### Purpose

Assemble extracted SKUs into a self-contained ontology where a coding agent can "read spec.md and start building." This is the final module that produces the deliverable ontology directory.

### Why a Separate Assembly Step?

Module 3 outputs SKUs into `output/skus/` with paths referencing the extraction directory (e.g., `test_data/basel_skus/factual/sku_001`). A ontology needs:
- **Self-contained paths**: All references use ontology-relative paths (`skus/factual/sku_001`)
- **Flat entry points**: `mapping.md` and `eureka.md` at ontology root, not buried in `meta/`
- **Agent-friendly entry**: `spec.md` + `README.md` that tell the agent what to build and where to find knowledge

### Why an Interactive Chatbot?

A spec cannot be auto-generated—it requires user intent. The chatbot:
- **Interviews** the user about goals, target users, and features
- **Suggests** relevant SKUs from the knowledge base
- **Iterates** on the spec based on feedback
- **References** SKUs by ontology-relative paths so the coding agent can find them

### Why Compressed Context?

`mapping.md` can be 127KB (~35K tokens). Sending it verbatim would consume most of the context window. The chatbot compresses it by keeping only section headers, SKU paths, and description lines—stripping verbose "When to use" text. This preserves navigability while reducing token cost by ~60%.

---

### Pipeline Steps

#### Step 1: Assembly (`assembler.py`)

**Class**: `OntologyAssembler(skus_dir, ontology_dir)`

Operations:
1. Validate `skus_dir` exists with `meta/mapping.md`
2. Create `ontology_dir/skus/`
3. `shutil.copytree` for `factual/`, `procedural/`, `relational/` → `ontology/skus/`
4. Copy `postprocessing/` if exists → `ontology/skus/postprocessing/`
5. Copy `skus_index.json` → `ontology/skus/skus_index.json` (with path rewriting)
6. Copy `eureka.md` → `ontology/eureka.md` (root)
7. Rewrite `mapping.md` paths → `ontology/mapping.md` (root)

**Path Rewriting**: Regex replaces any prefix before `factual/`/`procedural/`/`relational/`/`meta/` with `skus/`.

| Before | After |
|--------|-------|
| `test_data/basel_skus/factual/sku_001` | `skus/factual/sku_001` |
| `output/skus/procedural/skill_003` | `skus/procedural/skill_003` |
| `test_data/basel_skus/meta` | `skus/meta` |

Applied to both `mapping.md` (text replacement) and `skus_index.json` (per-entry `path` field).

#### Step 2: Chatbot (`chatbot.py`)

**Class**: `SpecChatbot(ontology_dir)`

**Context Management**:
- Compress `mapping.md`: keep `##` headers + `###` SKU paths + `**Description:**` lines (cap at 30K chars)
- Include first ~5K chars of `eureka.md` for creative inspiration
- System prompt sent once, carried through conversation

**Chat Loop**:
1. LLM sends initial greeting (asks about app goals) — does NOT count as a round
2. User types input → LLM responds → repeat (each user message = 1 round)
3. User types `/confirm` → finalize prompt → extract spec → save
4. Max rounds reached → auto-finalize with current draft

**Spec Extraction**: Look for ` ```markdown ``` ` code block first, then largest ` ``` ``` ` block, then treat full response as spec if it starts with `#`.

**LLM Function**: `call_llm_chat(messages)` — takes full message history list, same OpenAI SDK pattern as `call_llm()` but passes `messages` directly for multi-turn.

#### Step 3: README (`readme_generator.py`)

**Class**: `ReadmeGenerator(ontology_dir)`

Template-based, includes:
- Quick start (read spec.md → use mapping.md → check eureka.md)
- Directory structure diagram
- SKU type table (factual, procedural, relational)
- Stats from `OntologyManifest` (counts, file totals)

---

### Output Structure

```
ontology/
├── README.md                    # Entry point for agents
├── spec.md                      # App specification (from chatbot)
├── mapping.md                   # SKU router (paths rewritten to skus/...)
├── eureka.md                    # Creative insights
├── ontology_manifest.json      # Assembly metadata
├── chat_log.json                # Chatbot conversation log
└── skus/
    ├── factual/sku_001..N/      # header.md + content.md/json
    ├── procedural/skill_001..N/ # header.md + SKILL.md
    ├── relational/              # label_tree.json, glossary.json
    ├── postprocessing/          # bucketing, dedup, confidence reports
    └── skus_index.json          # Master index (paths rewritten)
```

---

### Schemas

#### OntologyManifest
```python
class OntologyManifest(BaseModel):
    created_at: datetime
    source_skus_dir: str           # Original SKUs directory
    ontology_dir: str             # Target ontology directory
    factual_count: int             # Number of factual SKU folders
    procedural_count: int          # Number of procedural skill folders
    has_relational: bool           # Whether relational/ was copied
    has_mapping: bool              # Whether mapping.md was created
    has_eureka: bool               # Whether eureka.md was copied
    has_spec: bool                 # Whether spec.md was generated
    has_readme: bool               # Whether README.md was generated
    total_files_copied: int        # Total files in ontology
    paths_rewritten: int           # Number of path rewrites applied
```

#### ChatSession
```python
class ChatMessage(BaseModel):
    role: str                      # system, assistant, user
    content: str

class ChatSession(BaseModel):
    started_at: datetime
    messages: list[ChatMessage]    # Full conversation history
    rounds_used: int               # User messages sent
    max_rounds: int                # Configurable limit (default 5)
    confirmed: bool                # Whether user typed /confirm
    spec_content: Optional[str]    # Extracted spec text
```

---

### CLI Interface

```bash
# Full pipeline
skus2ontology run                                    # Assemble + chatbot + README
skus2ontology run -v                                 # Verbose mode
skus2ontology run --skip-chatbot                     # No interactive chatbot
skus2ontology run -s <skus_dir> -w <ontology_dir>   # Custom paths

# Individual steps
skus2ontology assemble -s <skus_dir> -w <ontology_dir>  # Copy only
skus2ontology chatbot -w <ontology_dir>                  # Chatbot only
skus2ontology init                                        # Create ontology dir
```

---

### Configuration

```bash
# Module 4: Workspace Assembly
ONTOLOGY_DIR=./ontology
CHATBOT_MODEL=Pro/zai-org/GLM-5
MAX_CHAT_ROUNDS=5
CHATBOT_TEMPERATURE=0.4
CHATBOT_MAX_TOKENS=8000
```

---

### Performance Characteristics

#### Test: Basel Framework (420 SKUs)

| Metric | Value |
|--------|-------|
| Factual SKUs | 300 |
| Procedural skills | 82 |
| Total files copied | 775 |
| Paths rewritten | 803 |
| Assembly time | <1 second |

#### Bottlenecks

1. **Chatbot latency**: Each LLM response takes 5-15 seconds depending on context size
2. **Large mapping.md**: 127KB requires compression to fit in system prompt
3. **File I/O**: `shutil.copytree` for 775 files is fast (<1s) but scales linearly

---

## Integration: Module 2 → Module 3

### Data Flow

```
output/chunks/              Module 3              output/skus/
├── doc_chunk_001.md  ────► Chunks2SKUs ────────► ├── factual/
├── doc_chunk_002.md  ────►   │                   │   ├── sku_001/
├── ...               ────►   │                   │   └── ...
└── chunks_index.json ────►   ├─► Factual ────────► ├── relational/
                              ├─► Relational ─────► │   ├── label_tree.json
                              ├─► Procedural ─────► │   └── glossary.json
                              └─► Meta ───────────► ├── procedural/
                                                    │   ├── skill_001/
                                                    │   └── ...
                                                    └── meta/
                                                        ├── mapping.md
                                                        └── eureka.md
```

### Interface Contract

Module 3 expects:
- Chunk files (`.md`) in `output/chunks/`
- Index file `chunks_index.json` with chunk metadata
- UTF-8 encoding

Module 3 produces:
- SKU folders organized by type in `output/skus/`
- Index file `output/skus/skus_index.json` (with optional `confidence` per entry)
- `mapping.md` for SKU routing
- `eureka.md` for creative insights
- `postprocessing/` with bucketing, dedup, and confidence reports

---

## Integration: Module 3 → Module 4

### Data Flow

```
output/skus/                    Module 4               ontology/
├── factual/sku_001..300/ ────► SKUs2Ontology ──────► ├── README.md
├── procedural/skill_001..82/─►   │                   ├── spec.md (chatbot)
├── relational/            ────►   ├─► Assembler ─────► ├── mapping.md (rewritten)
├── meta/                  ────►   │   (copy+rewrite)  ├── eureka.md
│   ├── mapping.md         ────►   │                   ├── ontology_manifest.json
│   └── eureka.md          ────►   ├─► Chatbot ───────► ├── chat_log.json
├── postprocessing/        ────►   │   (spec.md)       └── skus/
└── skus_index.json        ────►   └─► README Gen ──────    ├── factual/
                                                            ├── procedural/
                                                            ├── relational/
                                                            ├── postprocessing/
                                                            └── skus_index.json
```

### Interface Contract

Module 4 expects:
- `output/skus/` (or custom path) with `meta/mapping.md` for validation
- `factual/`, `procedural/`, `relational/` subdirectories with SKU content
- `skus_index.json` with per-entry `path` fields
- `meta/eureka.md` (optional but recommended)
- `postprocessing/` (optional, copied if present)

Module 4 produces:
- Self-contained `ontology/` directory
- `mapping.md` with paths rewritten to `skus/...`
- `skus_index.json` with paths rewritten to `skus/...`
- `spec.md` from interactive chatbot (or skipped)
- `README.md` with quick start instructions
- `ontology_manifest.json` with assembly metadata
- `chat_log.json` with conversation history

---

## Integration: Module 1 → Module 2

### Data Flow

```
input/                    Module 1              output/                Module 2           output/chunks/
├── doc.pdf      ──────►  Anything2Markdown ──► ├── doc.md    ──────► Markdown2Chunks ──► ├── doc_chunk_001.md
├── data.xlsx    ──────►                   ──► ├── data.json ──────►  (pass-through) ──► │   ...
├── urls.txt     ──────►                   ──► ├── youtube_X.md ───►                ──► ├── chunks_index.json
└── folder/      ──────►                   ──► └── folder_Y.md ────►                ──► └── passthrough/
    └── file.pdf                                                                             └── data.json
```

### Interface Contract

Module 2 expects:
- Markdown files (`.md`) in `output/`
- JSON files (`.json`) in `output/` (passed through)
- UTF-8 encoding
- No binary files

Module 2 produces:
- Chunk files in `output/chunks/`
- Index file `output/chunks/chunks_index.json`
- Pass-through files in `output/passthrough/`

---

## Appendix A: Dependencies

```
# Module 1
markitdown[all]>=0.1.0       # Microsoft's document parser
firecrawl-py>=1.0.0          # Website crawler
youtube-transcript-api>=0.6.0 # YouTube transcripts
pandas>=2.0.0                 # Tabular data
openpyxl>=3.1.0              # Excel support
xlrd>=2.0.1                  # Legacy Excel
PyPDF2>=3.0.0                # PDF utilities
PyMuPDF>=1.24.0              # PDF page rendering (OCR pipeline)
httpx>=0.27.0                # HTTP client
# Optional: mlx-vlm           # Local PaddleOCR-VL deployment on Apple Silicon

# Module 2
tiktoken>=0.7.0              # Token estimation
python-Levenshtein>=0.25.0   # Fuzzy matching
openai>=1.0.0                # SiliconFlow API client

# Module 3 (Postprocessing)
scikit-learn>=1.3.0             # TF-IDF + cosine similarity
scipy>=1.11.0                   # Agglomerative clustering

# Module 4 (no new dependencies — uses openai, click, pydantic, structlog from above)

# Shared
click>=8.1.0                 # CLI framework
pydantic>=2.0.0              # Data validation
pydantic-settings>=2.0.0     # Config management
structlog>=24.0.0            # Structured logging

# External (npm)
repomix                      # Git repo → Markdown
```

---

## Appendix B: Known Limitations

1. **MinerU disabled**: Network issues to Alibaba Cloud Shanghai. Replaced with PaddleOCR-VL as OCR fallback for scanned PDFs. Supports dual backend: SiliconFlow API or local mlx-vlm on Apple Silicon.

2. **Nested folder testing**: Walk function implemented but not stress-tested with deep nesting.

3. **LLM chunking is slow**: ~7 min per 100K window. Consider batch APIs or parallel calls with overlapping windows.

4. **No incremental processing**: Re-running processes all files. Consider file hashing for change detection.

5. **Memory usage**: Large files loaded entirely into memory. Consider streaming for 1GB+ files.

6. ~~**No postprocessing**~~: Postprocessing implemented (bucketing, dedup, proofreading with bipolar confidence). See Section 3.4.

7. **Sequential LLM calls**: Each chunk requires 4 LLM calls (one per extractor). Consider batching or parallel extraction for non-dependent extractors.

8. **Eureka accumulation**: eureka.md grows indefinitely with append-only bullets. May need summarization for very large corpora.

9. **Chatbot context window**: Compressed mapping.md (~30K chars) + eureka (~5K chars) + conversation history may approach model limits on long conversations. The max rounds default (5) mitigates this.

10. **No incremental assembly**: Re-running `skus2ontology assemble` overwrites the entire ontology. Consider diffing for large ontologys.

---

## Appendix C: Future Modules (Preview)

### Module 5: Pipeline Summary
Generate run report with:
- Processing statistics (files, chunks, SKUs)
- Timing breakdowns by module
- Quality metrics and confidence scores
- Error summary and recommendations

---

## Appendix D: Module 3 Schemas

### SKUHeader
```python
class SKUHeader(BaseModel):
    name: str                      # SKU identifier
    classification: SKUType        # factual/relational/procedural/meta
    character_count: int           # Content size
    source_chunk: str              # e.g., "document_chunk_003"
    description: str               # One-line summary
    confidence: Optional[float]    # 0.0-1.0, set by proofreading step
```

### LabelTree
```python
class LabelNode(BaseModel):
    name: str
    children: list["LabelNode"] = []

class LabelTree(BaseModel):
    roots: list[LabelNode] = []

    def add_path(self, path: list[str]) -> None:
        """Add label path like ["Finance", "Risk", "Credit Risk"]"""
```

### Glossary
```python
class GlossaryEntry(BaseModel):
    term: str
    definition: str
    labels: list[str] = []         # Links to label_tree nodes
    source_chunk: str
    related_terms: list[str] = []

class Glossary(BaseModel):
    entries: list[GlossaryEntry] = []

    def add_or_update(self, entry: GlossaryEntry) -> None:
        """Add new entry or update existing by term"""
```

### SKUsIndex
```python
class SKUEntry(BaseModel):
    sku_id: str
    name: str
    classification: SKUType
    path: str
    source_chunk: str
    character_count: int
    description: str
    confidence: Optional[float]    # Set by proofreading

class SKUsIndex(BaseModel):
    created_at: datetime
    updated_at: datetime
    total_skus: int
    total_characters: int
    chunks_processed: list[str]
    skus: list[SKUEntry]
    factual_count: int
    relational_count: int
    procedural_count: int
    meta_count: int

    def add_sku(self, entry: SKUEntry) -> None: ...
    def remove_sku(self, sku_id: str) -> bool: ...  # For dedup deletion
```

### Postprocessing Schemas
```python
class BucketEntry(BaseModel):
    sku_id: str
    name: str
    description: str
    classification: str
    token_count: int
    label_path: list[str] = []

class Bucket(BaseModel):
    bucket_id: str
    total_tokens: int
    sku_count: int
    entries: list[BucketEntry]

class BucketingResult(BaseModel):
    total_skus: int
    total_buckets: int
    similarity_weights: dict[str, float]
    factual_buckets: list[Bucket]
    procedural_buckets: list[Bucket]

class DedupAction(BaseModel):
    sku_a: str
    sku_b: str
    action: str                    # "keep" / "delete" / "rewrite" / "merge"
    detail: str
    deleted_skus: list[str]

class DedupReport(BaseModel):
    buckets_scanned: int
    pairs_flagged: int
    total_deleted: int
    total_kept: int
    actions: list[DedupAction]

class ConfidenceEntry(BaseModel):
    sku_id: str
    confidence: float              # 0.0-1.0
    reasoning: str
    web_references: list[str]
    source_chunk_available: bool
    web_search_available: bool

class ConfidenceReport(BaseModel):
    total_scored: int
    average_confidence: float
    entries: list[ConfidenceEntry]
```

---

## Appendix E: Module 4 Schemas

### OntologyManifest
```python
class OntologyManifest(BaseModel):
    created_at: datetime
    source_skus_dir: str
    ontology_dir: str
    factual_count: int = 0
    procedural_count: int = 0
    has_relational: bool = False
    has_mapping: bool = False
    has_eureka: bool = False
    has_spec: bool = False
    has_readme: bool = False
    total_files_copied: int = 0
    paths_rewritten: int = 0
```

### ChatSession
```python
class ChatMessage(BaseModel):
    role: str                      # system, assistant, user
    content: str

class ChatSession(BaseModel):
    started_at: datetime
    messages: list[ChatMessage]
    rounds_used: int = 0
    max_rounds: int = 5
    confirmed: bool = False
    spec_content: Optional[str] = None
```

---

*Document authored for Anything2Ontology product team. For implementation details, see source code in `src/` and design docs in `module_design/`.*
