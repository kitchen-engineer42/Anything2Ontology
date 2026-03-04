# Anything2Ontology Algorithm Description

## Table of Contents

- [1. System Overview](#1-system-overview)
- [2. Module 1: Anything2Markdown — Universal Parser](#2-module-1-anything2markdown--universal-parser)
- [3. Module 2: Markdown2Chunks — Smart Chunking](#3-module-2-markdown2chunks--smart-chunking)
- [4. Module 3: Chunks2SKUs — Knowledge Extraction](#4-module-3-chunks2skus--knowledge-extraction)
- [5. Module 4: SKUs2Ontology — Ontology Assembly](#5-module-4-skus2ontology--ontology-assembly)
- [6. Global Design Patterns](#6-global-design-patterns)

---

## 1. System Overview

### 1.1 System Purpose

Anything2Ontology is a **knowledge management and modelling pipeline** that converts various media formats (files, URLs, code repositories) into a structured ontology for AI coding assistants (e.g., Claude Code) to use directly. The final output is a self-contained `ontology/` directory where a coding agent can simply "read spec.md and start building."

**Why "Ontology"**: The word "ontology" encompasses multiple forms of knowledge — facts, skills, schemas (conceptual models), and lore (accumulated domain knowledge). The pipeline's core intermediate product is the **Standard Knowledge Unit (SKU)**, classified into four types along these dimensions: Factual, Relational, Procedural, and Meta. Together, these four types of SKUs are assembled into a complete ontology.

### 1.2 Four-Stage Pipeline Architecture

```
Input (Files/URLs)
    |
    v
+-------------------------+
| Module 1: Anything2Markdown |  Everything -> Markdown/JSON
+------------+------------+
             |
             v
+-------------------------+
| Module 2: Markdown2Chunks   |  Long docs -> Chunks (<=100K tokens)
+------------+------------+
             |
             v
+-------------------------+
| Module 3: Chunks2SKUs       |  Chunks -> Standard Knowledge Units (SKUs)
|   +- Postprocessing         |  Bucketing/Dedup/Confidence scoring
+------------+------------+
             |
             v
+-------------------------+
| Module 4: SKUs2Ontology     |  SKUs -> Self-contained ontology
+-------------------------+
```

Each module is an independent CLI tool, loosely coupled through index files on the filesystem (`parse_results_index.json`, `chunks_index.json`, `skus_index.json`). There is no unified main script — users run them sequentially:

```bash
anything2md run       # Module 1
md2chunks run         # Module 2
chunks2skus run       # Module 3
chunks2skus postprocess all  # Optional: Postprocessing
skus2ontology run    # Module 4
```

### 1.3 Core Data Flow

```
input/
├── files (PDF, PPT, DOCX, XLSX, ...)
└── urls.txt (YouTube, Bilibili, GitHub, websites)
        |
        v  [Module 1]
output/
├── *.md (Markdown files, flat or grouped by directory)
├── *.json (tabular data)
└── parse_results_index.json
        |
        v  [Module 2]
output/chunks/
├── *_chunk_001.md ... *_chunk_NNN.md (with YAML frontmatter)
├── chunks_index.json
└── output/passthrough/ (JSON pass-through)
        |
        v  [Module 3]
output/skus/
├── factual/sku_000/ ... sku_NNN/ (factual knowledge)
├── relational/ (label tree + glossary + relationships)
├── procedural/skill_000/ ... skill_NNN/ (skills/workflows)
├── meta/ (mapping.md + eureka.md)
├── postprocessing/ (bucketing/dedup/confidence reports)
└── skus_index.json
        |
        v  [Module 4]
ontology/
├── README.md (agent entry point)
├── spec.md (application specification)
├── mapping.md (SKU routing table, paths rewritten)
├── eureka.md (cross-domain insights)
├── ontology_manifest.json
├── chat_log.json
└── skus/ (copies of all SKUs, paths rewritten)
```

---

## 2. Module 1: Anything2Markdown — Universal Parser

### 2.1 Purpose

Convert various file types and URLs into a unified Markdown or JSON format, providing standardized input for downstream processing.

### 2.2 Routing Algorithm

The router (`router.py`) acts as a front desk receptionist, dispatching inputs to the appropriate parser based on type.

#### 2.2.1 File Routing `route_file(path)`

| File Extension | Routing Target | Output Format |
|---------------|---------------|---------------|
| `.pdf` | MarkItDownParser | Markdown |
| `.ppt`, `.pptx`, `.doc`, `.docx`, `.html`, `.epub`, `.md`, `.txt` | MarkItDownParser | Markdown |
| `.xlsx`, `.xls`, `.csv` | TabularParser | JSON |
| `.png`, `.jpg`, `.mp3`, `.mp4`, `.css`, `.js` | Skip (non-text) | — |

**OCR Fallback Decision** `should_fallback_to_ocr(output_path)`:

```
If MarkItDown parsing succeeds but output quality is poor:
    valid_char_count = regex_count(letters + digits + common punctuation)
    If valid_char_count < MIN_VALID_CHARS (default 500):
        Classified as scanned/low-quality PDF
        -> Fall back to PaddleOCR-VL for re-parsing
```

#### 2.2.2 URL Routing `route_url(url)`

| URL Pattern | Routing Target |
|------------|---------------|
| `youtube.com/watch`, `youtu.be/`, `youtube.com/embed` | YouTubeParser |
| `bilibili.com/video/`, `b23.tv/`, `bilibili.com/bangumi` | BilibiliParser |
| `github.com/{owner}/{repo}` (excluding /issues, /pull, etc.) | RepomixParser |
| Other HTTP(S) URLs | FireCrawlParser |

### 2.3 File Parsers

#### 2.3.1 MarkItDownParser

**Algorithm**:
1. Call the `MarkItDown()` library for format conversion
2. Extract `.text_content` text content
3. Generate flattened output filename (`flatten_path` strategy: direct child files keep original name, nested files join path with underscores)
4. Write to `.md` file

**Supported formats**: PDF, PPT(X), DOC(X), HTML, EPUB, MD, TXT

#### 2.3.2 PaddleOCR-VL Parser (OCR Fallback Parser)

**Algorithm** (with resume support):

```
1. Initialize OpenAI-compatible client (SiliconFlow cloud or local mlx-vlm)
2. Open PDF with PyMuPDF (fitz)
3. Check progress file (.progress.jsonl) for resume support
4. Process page by page:
   a. Render to PNG (DPI=150)
   b. Convert to Base64 encoding
   c. Call vision API:
      Prompt = "Convert this document page to markdown..."
      Model = PaddleOCR-VL (via OpenAI-compatible API)
      Params = max_tokens=4000, temperature=0.1
   d. Clean <|LOC_xxx|> location markers
   e. Retry up to 2 times on failure
   f. Append to progress file after each page (incremental save, crash-recoverable)
5. Assemble all pages with "---" separators
6. Clean up progress file on success
```

**Key features**:
- Local server bypass: `trust_env=False` to avoid proxy interference
- Incremental save: one JSON line per page, resume from last completed page after crash
- Failed page markers: `<!-- OCR failed -->` comments

#### 2.3.3 TabularParser

**Algorithm**:
1. Detect file type (CSV / Excel)
2. CSV -> `pd.read_csv()` -> records format
3. Excel -> `pd.ExcelFile()` -> iterate worksheets:
   - Single worksheet: flatten to records array
   - Multiple worksheets: maintain as nested dict `{sheet_name: [records]}`
4. Output JSON (`ensure_ascii=False`, supports CJK characters)

#### 2.3.4 MinerU Parser (Cloud Parsing for Large PDFs)

**Algorithm** (with chunked upload support):

```
1. Get PDF page count (PyPDF2)
2. If pages > 400 or file > 2MB: process in chunks
3. For each chunk:
   a. Request pre-signed upload URL: POST /file-urls/batch -> batch_id + upload_url
   b. Stream upload file: PUT upload_url
   c. Poll batch status: GET /extract-results/batch/{batch_id}
      (5-second interval, 30-minute timeout)
   d. Download ZIP when status becomes "done"
   e. Extract full.md or first .md file from ZIP
4. Concatenate all chunks with "---" and "# Part N" headers
```

> Note: MinerU routing is currently disabled due to Alibaba Cloud network connectivity issues.

### 2.4 URL Parsers

#### 2.4.1 YouTubeParser

**Algorithm**:
1. Extract video ID from URL (regex matching multiple formats)
2. Call `YouTubeTranscriptApi` to get subtitles:
   - Priority language list: [en, zh, zh-Hans, zh-Hant, zh-CN, zh-TW]
   - Fallback strategy: manually created -> auto-generated -> any available subtitles
3. Format as Markdown:
   - Detect sentence-ending punctuation (.!?... and CJK punctuation) for paragraph grouping
   - Join segments within the same paragraph with spaces

#### 2.4.2 BilibiliParser

**Dual-strategy algorithm**:

```
Strategy 1: CC subtitles first (via yt-dlp)
  1. Extract video info (title, BV number)
  2. Try subtitle sources by priority:
     requested_subtitles -> subtitles -> automatic_captions
  3. Parse by format priority: json3 -> srv3 -> vtt -> srt
  4. Parse different subtitle structures:
     - json3: {"events": [{"segs": [{"utf8": "..."}], "tStartMs": ...}]}
     - srv1-3: XML <p t="...">text</p>
     - vtt: WebVTT timestamp format
     - Bilibili JSON: {"from": ..., "to": ..., "content": "..."}
  5. Convert to unified structure {"text": "...", "start": seconds}

Strategy 2: WhisperX fallback (when no subtitles available)
  1. Download audio-only with yt-dlp -> WAV
  2. Load faster-whisper model (configurable size)
  3. Detect GPU: cuda -> float16, cpu -> int8
  4. Speech-to-text (language=zh)
  5. Extract timestamped segments
```

**Cookie support**:
- Prefer Netscape-format cookie file
- Fall back to browser cookie extraction (chrome/firefox/safari/edge)
- Bilibili requires cookies to avoid HTTP 412 errors

#### 2.4.3 FireCrawlParser

**Algorithm**:
1. Call FireCrawl API to crawl web pages (limit=50 pages)
2. Extract URL and Markdown content from each page
3. Combine all pages with `# {page_url}` headers and `---` separators

#### 2.4.4 RepomixParser

**Algorithm**:
1. Check if `repomix` CLI is installed
2. Extract repository name from URL: `github.com/{owner}/{repo}`
3. Run subprocess: `repomix --remote {url} --style markdown --output {path}`
4. Timeout limit: 10 minutes

### 2.5 Pipeline Orchestration

```
run()
+- Traverse all files in input/ directory
|  +- For each file: _process_file_with_retry()
|     +- Check for existing output (resume support) -> skip
|     +- Route to parser
|     +- Execute parsing
|     +- If PDF + MarkItDown + poor output quality -> OCR fallback
|        (delete low-quality output, re-parse with PaddleOCR-VL)
|
+- Read all URLs from urls.txt
|  +- For each URL: _process_url_with_retry()
|     +- Route to parser
|     +- Execute parsing
|
+- Save parse_results_index.json (summary + per-item details)
+- Output statistics log (success/failed/skipped)
```

**Retry strategy**: 1 global retry (2 total attempts), 2-second delay. Distinguishes `RetryableError` (retryable) from `NonRetryableError` (skip immediately).

**Resume support**: Skips files with existing non-empty output, returns ParseResult marked with `resumed=True`.

### 2.6 Data Model: ParseResult

Uses **agile schema** design (fixed part + JIT part):

| Field | Type | Description |
|-------|------|-------------|
| `source_path` | str | Input path (file or URL) |
| `source_type` | "file" / "url" | Input type |
| `output_path` | str | Output file path |
| `output_format` | "markdown" / "json" | Output format |
| `parser_used` | str | Parser name used |
| `status` | "success" / "failed" / "skipped" | Processing status |
| `started_at` / `completed_at` | datetime | Timestamps |
| `duration_seconds` | float | Processing duration |
| `character_count` | int | Output character count |
| `error_message` | str? | Error message |
| `retry_count` | int | Retry count |
| **`metadata`** | **dict[str, Any]** | **JIT metadata** (parser-specific custom fields) |

`metadata` examples:
- MarkItDown: `{"original_extension": ".pdf"}`
- PaddleOCR-VL: `{"page_count": 50, "pages_failed": 2, "ocr_model": "...", "dpi": 150}`
- YouTube: `{"video_id": "...", "transcript_segments": 120}`
- Bilibili: `{"video_id": "BV...", "title": "...", "transcript_segments": 80}`

---

## 3. Module 2: Markdown2Chunks — Smart Chunking

### 3.1 Purpose

Split long Markdown files into chunks suitable for LLM processing (each chunk <= 100K tokens). JSON files are passed through without processing.

### 3.2 Routing Algorithm

```
should_chunk(file_path):
    .md file  -> needs chunking
    .json file -> pass through to passthrough/
    other      -> skip with warning

get_chunker(content):
    If Markdown contains headers (# ## ### ...)
        -> HeaderChunker (deterministic, fast)
    Else
        -> LLMChunker (semantic splitting, fallback)
```

### 3.3 HeaderChunker — "Peeling Onion" Algorithm

**Core idea**: Split along header hierarchy layer by layer, only splitting when a section exceeds the token limit. Prioritize maintaining the document's logical structure.

#### 3.3.1 Algorithm Flow

```
Input: Markdown document with header hierarchy

Phase 1: Header Detection
  parse_headers(content) -> list[MarkdownSection]
  Use regex ^(#{1,6})\s+(.+)$ to match all headers
  Create MarkdownSection for each header:
    { level, title, content, start_pos, end_pos, token_count }

Phase 2: Build Hierarchy Tree
  build_section_tree(sections) -> tree
  Use stack algorithm to build parent-child relationships:
    For each section:
      node = {section, children: []}
      while stack top level >= current level: pop stack
      if stack non-empty: add as child of stack top node
      else: add to root list
      push to stack

Phase 3: Recursive Tree Processing (core)
  _process_tree(tree):
    For each node:
      subtree_total_tokens = _calculate_subtree_tokens(node)  // recursive sum

      if subtree_total_tokens <= MAX_TOKEN_LENGTH:
          -> Merge entire subtree into a single chunk
          (call _extract_subtree_content to recursively concatenate content)
      else:
          -> Extract introduction (content between section header and first sub-header)
          -> If introduction is non-empty, create standalone chunk
          -> Recursively process each child node
          -> If no children and still over limit, mark for LLM re-chunking
```

#### 3.3.2 Walkthrough Example

```
Document structure:
# Main Title (100 tokens)
  ## Section A (30,000 tokens)
    ### Subsection A1 (10,000 tokens)
    ### Subsection A2 (20,000 tokens)
  ## Section B (15,000 tokens)

MAX_TOKEN_LENGTH = 100,000

Processing:
1. Root node "Main Title": subtree = 145,100 tokens > limit -> split
   -> Extract introduction (100 tokens), create chunk 0
2. Child node "Section A": subtree = 60,000 tokens <= limit
   -> Merge into chunk 1 (includes A + A1 + A2 complete content)
3. Child node "Section B": subtree = 15,000 tokens <= limit
   -> Merge into chunk 2

Output: 3 chunks
```

### 3.4 LLMChunker — "Driving Wedges" Algorithm

**Core idea**: Use LLM to identify semantic split points, then use Levenshtein fuzzy matching to locate exact positions. Suitable for plain text or long paragraphs without headers.

#### 3.4.1 Algorithm Flow

```
Input: Very long Markdown or plain text

Phase 1: Rolling Context Window Loop
  remaining_text = content
  chunks = []

  while remaining_text is non-empty:
    remaining_tokens = estimate_tokens(remaining_text)

    if remaining_tokens <= MAX_TOKEN_LENGTH:
        -> Create final chunk, exit loop

    // 1. Extract window
    window_text = truncate_to_tokens(remaining_text, MAX_TOKEN_LENGTH)

    // 2. Call LLM to find split points
    cut_points = _get_cut_points(window_text)
    // LLM returns for each split point:
    //   tokens_before: exact text of ~K tokens before the split point
    //   tokens_after:  exact text of ~K tokens after the split point
    //   chunk_title:   short title for the chunk

    // 3. Levenshtein fuzzy match to locate position
    if cut_points is non-empty:
        cut_pos = find_cut_position(
            cut_points[0].tokens_before,
            cut_points[0].tokens_after,
            remaining_text
        )
    else:
        cut_pos = _find_paragraph_boundary(remaining_text)

    // 4. Create chunk and advance
    chunk_content = remaining_text[:cut_pos]
    remaining_text = remaining_text[cut_pos:].lstrip()
    chunks.append(chunk_content)
```

#### 3.4.2 LLM Split Point Query

**Prompt structure**:

```
Input to LLM:
  CONTENT: ~100K tokens of text window
  TASK: Find 1-3 natural split points in the text

For each split point, output:
  1. tokens_before: exact ~K tokens before the split point (default K=50)
  2. tokens_after: exact ~K tokens after the split point
  3. chunk_title: 5-10 word title for the chunk before the split point

Output format (JSON):
{
  "cut_points": [
    {
      "tokens_before": "...exact text...",
      "tokens_after": "...exact text...",
      "chunk_title": "Section Title"
    }
  ]
}
```

#### 3.4.3 Levenshtein Fuzzy Matching Algorithm

**Why fuzzy matching is needed**: LLM output text may have minor differences from the original (whitespace, encoding differences), making exact string matching unreliable.

```
find_best_match(needle, haystack, search_window=500):
  Sliding window search over first search_window characters of haystack:
    For each position i:
      candidate = haystack[i : i + len(needle)]
      distance = Levenshtein.distance(needle, candidate)
      similarity = 1 - distance / max(len(needle), len(candidate))

      if distance < historical minimum and similarity > 0.7:
          update best position

  Return best match position (or None)

find_cut_position(tokens_before, tokens_after, text):
  Phase 1: Locate matching position of tokens_before
    before_pos = find_best_match(tokens_before, text)
    cut_pos = before_pos + len(tokens_before)

  Phase 2: Verify tokens_after appears nearby
    after_search = text[cut_pos : cut_pos + len(tokens_after) + 100]
    after_pos = find_best_match(tokens_after, after_search)
    // Allow 50-character gap

  Phase 3: Skip leading whitespace
    while text[cut_pos] is whitespace: cut_pos += 1

  Return cut_pos
```

#### 3.4.4 Paragraph Boundary Fallback

Fallback strategy when LLM split fails:

```
_find_paragraph_boundary(text, max_tokens):
  Truncate text to first max_tokens worth of text
  Search for best break point by priority:
    1. Last double newline "\n\n" (paragraph boundary) -> best
    2. Last single newline "\n" (line boundary)
    3. Last sentence-ending punctuation (". " "! " "? ")
    4. Hard fallback: cut directly at token limit
```

### 3.5 Token Estimation

Uses `tiktoken`'s `cl100k_base` encoder (compatible with GPT-4 and Claude):

| Function | Purpose |
|----------|---------|
| `estimate_tokens(text)` | Returns token count |
| `truncate_to_tokens(text, max)` | Precisely truncate to specified token count |
| `get_token_limit()` | Returns configured limit (default 100,000) |

### 3.6 Pipeline Orchestration

```
ChunkingPipeline.run():
  Discovery phase:
    Recursively find all .md and .json files under output/
    Exclude chunks/, passthrough/, skus/ directories

  Processing phase (sequential):
    For each .md file:
      tokens = estimate_tokens(content)
      if tokens <= MAX_TOKEN_LENGTH:
          -> Create single chunk (method="single")
      else:
          -> Route to HeaderChunker or LLMChunker
          -> Execute chunking
          -> _rechunk_if_needed: check if each chunk exceeds limit
             Over-limit chunks are re-split with LLMChunker
      -> Write chunk files with YAML frontmatter
      -> Update ChunksIndex

    For each .json file:
      -> Copy to output/passthrough/ (collision-safe naming)

  Output phase:
    Write chunks_index.json
    Output statistics log
```

### 3.7 Output Format

Each chunk file includes YAML frontmatter:

```yaml
---
title: "Section Title"
source: "original_filename.md"
chunk: 1
total: 3
tokens: 25000
method: "header"
---

[actual content]
```

File naming convention: `{original_filename_without_extension}_chunk_{sequence:03d}.md`

---

## 4. Module 3: Chunks2SKUs — Knowledge Extraction

### 4.1 Purpose

Extract four types of Standard Knowledge Units (SKUs) from chunks while maintaining cumulative updates to the global knowledge structure.

### 4.2 Four Knowledge Types

| Type | Name | Description | Processing Mode | Output |
|------|------|-------------|----------------|--------|
| Factual | Factual | Data, definitions, facts | Isolated | Independent SKU folders |
| Relational | Relational | Concept hierarchies, terminology, semantic relations | Read-and-update | Global JSON files |
| Procedural | Procedural | Workflows, skills, best practices | Isolated | Independent SKILL folders |
| Meta | Meta | Knowledge routing, cross-domain insights | Read-and-update | mapping.md + eureka.md |

### 4.3 Core Processing Flow: Sequential Processing with Cumulative Context

This is the most critical design pattern in Module 3. Chunks are processed sequentially, each chunk passes through all four extractors, and knowledge accumulates throughout the process:

```
all_skus = []  // global SKU accumulation list

for chunk in chunks:  // strictly sequential processing
    if already_processed(chunk): continue  // resume support

    // Step 1: Factual extraction (isolated, no context dependency)
    factual_skus = FactualExtractor.extract(chunk.content, chunk.id, {})

    // Step 2: Relational extraction (reads existing label_tree.json and glossary.json, updates them)
    relational_ctx = RelationalExtractor.get_context_for_next()
    RelationalExtractor.extract(chunk.content, chunk.id, relational_ctx)
    // -> Updates global: label_tree.json, glossary.json, relationships.json

    // Step 3: Procedural extraction (isolated, no context dependency)
    procedural_skus = ProceduralExtractor.extract(chunk.content, chunk.id, {})

    // Step 4: Meta extraction (receives list of all created SKUs)
    new_skus = factual_skus + procedural_skus
    meta_ctx = {"all_skus": all_skus + new_skus}
    MetaExtractor.extract(chunk.content, chunk.id, meta_ctx)
    // -> Updates global: mapping.md, eureka.md

    all_skus.extend(new_skus)
    save_index()  // save after each chunk for recovery support
```

### 4.4 Factual Extractor

**Goal**: Extract "what is X" type knowledge — data points, definitions, statistics, tables.

**Algorithm**:

```
1. Call LLM (temperature=0.3):
   - Send chunk content
   - Request JSON array output, each item is an independent fact
   - Special rule: tables/JSON arrays/CSV must be preserved as a whole, no row splitting
   - Follow MECE principle (Mutually Exclusive, Collectively Exhaustive)

2. For each extracted fact:
   - Generate unique ID: sku_000, sku_001, ... (global incrementing counter)
   - Determine content type: markdown or json
   - Create SKU folder:
     output/factual/sku_NNN/
     +-- header.md    (metadata: name, classification, character count, source chunk, description)
     +-- content.md   (Markdown content) or content.json (JSON content)

3. Return SKU info list (ID, name, path, description, etc.)
```

### 4.5 Relational Extractor

**Goal**: Extract relationships between concepts, maintain a global label hierarchy tree and glossary.

**Algorithm** (read-and-update mode):

```
1. Load persisted state:
   - label_tree.json -> LabelTree instance
   - glossary.json -> Glossary instance
   - relationships.json -> Relationships collection

2. Call LLM (temperature=0.3, max_tokens=8000):
   - Send current state as context (label tree + glossary summary, capped at 6000 chars)
   - Send new chunk content
   - Request JSON output:
     {
       "label_tree": updated hierarchy tree,
       "glossary": new/updated glossary entries,
       "relationships": typed semantic relationships
     }

3. Merge updates:
   _merge_label_tree(new_tree):
     Recursively merge new nodes into existing tree
     Case-insensitive matching
     Preserve existing nodes, only add new ones

   _merge_glossary(new_glossary):
     For each entry, call Glossary.add_or_update():
       - Keep longer definitions (richer content)
       - Accumulate source chunks
       - Merge labels, aliases, related_terms (deduplicated)

   Update relationships collection (deduplicate by subject+predicate+object)

4. Save updated JSON files
```

**Relationship types** (13): is-a, has-a, part-of, causes, caused-by, requires, enables, contradicts, related-to, depends-on, regulates, implements, example-of

**Data structures**:

```
LabelTree (label hierarchy tree):
  add_path(["Finance", "Risk", "Credit Risk"]) -> create nested path
  get_all_paths() -> flatten to path list

Glossary:
  get_entry(term) -> case-insensitive + alias support
  add_or_update(entry) -> merge strategy
  get_terms_by_label(label) -> query by category

GlossaryEntry:
  { term, definition, labels[], source_chunks[], aliases[], related_terms[] }
```

### 4.6 Procedural Extractor

**Goal**: Extract actionable workflows, skills, and best practices, outputting in Claude Code-compatible SKILL.md format.

**Algorithm**:

```
1. Call LLM (temperature=0.3, max_tokens=6000):
   - Send chunk content
   - Request JSON array, each item is a procedure/skill:
     {
       "name": "hyphen-case identifier (<=64 chars)",
       "description": "when to use (<=200 chars, no angle brackets)",
       "body": "Markdown instructions (overview+steps+decision points+expected results)",
       "has_scripts": boolean,
       "scripts": [{"name": "script name", "content": "script content"}],
       "has_references": boolean,
       "references": [{"name": "reference name", "content": "reference content"}]
     }

2. For each procedure:
   - Generate unique ID: skill_000, skill_001, ...
   - Convert name to hyphen-case
   - Remove angle brackets from description, truncate to 200 chars
   - Create skill folder:
     output/procedural/skill_NNN/
     +-- header.md
     +-- SKILL.md      (YAML frontmatter + Markdown body)
     +-- scripts/       (if scripts exist)
     |   +-- script_0.py
     |   +-- script_1.py
     +-- references/    (if references exist)
         +-- reference_0.md

SKILL.md format (Claude Code compatible):
  ---
  name: skill-name
  description: When to use this skill
  ---

  [Complete Markdown instructions]
```

### 4.7 Meta Extractor

**Goal**: Generate "knowledge about knowledge" for the knowledge base — an SKU routing table (mapping.md) and cross-domain creative insights (eureka.md).

**Algorithm** (dual-track processing):

```
Track A: Update mapping.md (precision-oriented, temperature=0.2)
  1. Call LLM:
     - Input: current list of all SKUs + existing mapping.md + current chunk_id
     - Output: updated mapping.md (Markdown-format SKU routing directory)
     - System prompt emphasizes: accuracy, no hallucination, only include actually existing SKUs
  2. Shrinkage protection: if new content shrinks >50% from old (unless first time), reject update
  3. Write mapping.md

Track B: Update eureka.md (creativity-oriented, temperature=0.7)
  1. Call LLM:
     - Input: existing eureka.md + new chunk content (first 8000 chars)
     - Output: { "updated": bool, "eureka_content": "updated content" }
  2. Quality gate (enforced by prompt):
     - Insights must span multiple domains (cross-domain patterns)
     - Must reveal surprising connections or design principles
     - Not simple feature suggestions or intra-domain details
     - Maximum 20 bullet points total
     - Organized by topic (## headers), not by chunk
     - Include source chunk references: [chunk_001, chunk_005]
  3. Merge strategy:
     - New insight reinforces existing bullet -> merge and update references
     - Existing bullet superseded by better formulation -> delete old one
  4. Shrinkage protection: same as mapping.md
```

### 4.8 Postprocessing Sub-pipeline

After main extraction completes, an optional three-step postprocessing pipeline can be run for quality control.

#### 4.8.1 Step 1: Bucketing

**Goal**: Group factual and procedural SKUs by similarity, with each group not exceeding `max_bucket_tokens` (default 100K).

**Multi-dimensional similarity scoring algorithm**:

```
Total similarity = w1 x literal_similarity + w2 x label_similarity + w3 x vector_similarity

Where:
  Literal similarity (w1=0.2): TF-IDF vectorization + cosine similarity
  Label similarity (w2=0.3): Jaccard distance of label tree paths
  Vector similarity (w3=0.5): Embeddings via SiliconFlow bge-m3 API + cosine similarity

Adaptive weights: if embedding API is unavailable, weights are automatically redistributed to remaining dimensions
```

**Recursive bisection algorithm**:

```
Uses Hierarchical Agglomerative Clustering
Recursively bisect the SKU set until each bucket's total tokens <= max_bucket_tokens

Output: bucketing_result.json
  - Factual bucket list
  - Procedural bucket list
  - Each bucket: bucket_id, total_tokens, sku_count, entries[]
```

#### 4.8.2 Step 2: Deduplication (Dedup)

**Goal**: Detect and handle duplicate and contradictory SKUs.

**Two-tier LLM judgment algorithm**:

```
Tier 1: Header scan (quick screening)
  For SKUs within each bucket:
    Batch-send header.md (max 80 SKUs per batch to avoid token overflow)
    LLM quickly identifies which pairs might be duplicates
    Output: suspected duplicate pairs list [(sku_a, sku_b, reason)]

Tier 2: Deep comparison (precise judgment)
  For each suspected duplicate pair:
    Read full content of both SKUs (first 8000 chars)
    LLM makes judgment, returns action:
      "keep"          -> Different, keep both
      "delete"        -> Clear duplicate, delete one
      "rewrite"       -> Need to modify one's content
      "merge"         -> Merge into one SKU
      "contradiction" -> Keep but mark contradiction (record only, no action)

Safety mechanisms:
  - Validate LLM-returned SKU IDs actually exist in current bucket (prevent hallucinated IDs)
  - Update mapping.md to remove references to deleted SKUs
  - Save detailed dedup_report.json
```

#### 4.8.3 Step 3: Confidence Scoring (Proofreading)

**Goal**: Compute confidence scores for each SKU through RAG-based verification.

**Two-step confidence calculation**:

```
Step 1: Source integrity check (penalty term, 0.0-0.5)
  Compare extracted SKU against original source chunk
  Can only lower confidence (detect hallucination/distortion)
  No penalty if source unavailable

Step 2: External verification (primary signal, 0.0-1.0)
  Web search via Jina API (https://s.jina.ai/)
  Rate limited: ~100 RPM (0.6-second interval)
  Extract title, URL, summary from top 5 results
  LLM evaluates whether web information corroborates SKU claims

Final score = max(0.0, min(1.0, external_verification_score - source_penalty_score))
```

**Resumable**: Skips already-scored SKUs (checks `sku_entry.confidence` field).

**Output**:
- Updates each SKU's `header.md` (adds confidence line)
- Updates `skus_index.json`
- Saves `confidence_report.json`

### 4.9 Data Model

#### SKUsIndex (Master Index)

```
{
  created_at, updated_at,
  total_skus,
  total_characters,
  chunks_processed: [chunk_id, ...],  // processed chunks, supports resume
  skus: [
    { sku_id, name, classification, path, source_chunk,
      character_count, description, confidence }
  ],
  factual_count, relational_count, procedural_count, meta_count
}
```

### 4.10 LLM Call Utility

```
call_llm_json(prompt, ..., max_retries=2):
  First call: request structured JSON format
  If parsing fails: retry (up to max_retries times)
    - Append error message to prompt
    - Slightly lower temperature (temp - 0.1)
    - LLM self-corrects based on error feedback

  parse_json_response(text):
    - Strip Markdown code block markers
    - Attempt JSON parsing
    - Fallback: convert single quotes to double quotes and retry
```

---

## 5. Module 4: SKUs2Ontology — Ontology Assembly

### 5.1 Purpose

Assemble extracted SKUs into a self-contained ontology that a coding agent can use directly. Three-step process: copy and organize -> interactive spec.md generation -> generate README.md.

### 5.2 Step 1: Assembly (Assembler)

**Algorithm**:

```
OntologyAssembler.assemble():
  1. Verify source directory exists
  2. Create ontology/skus/ directory

  3. Copy subdirectories:
     factual/ -> ontology/skus/factual/
     procedural/ -> ontology/skus/procedural/
     relational/ -> ontology/skus/relational/
     postprocessing/ -> ontology/skus/postprocessing/ (if exists)
     (delete target directory first then copy entirely, ensuring clean state)

  4. Path rewriting for skus_index.json:
     Iterate each SKU entry's "path" field
     Rewrite any prefix (e.g., "output/skus/", "test_data/...")
     to unified "skus/"

  5. Copy eureka.md -> ontology/eureka.md (root directory)

  6. Path rewriting for mapping.md -> ontology/mapping.md:
     Full-text search-and-replace all SKU path prefixes to "skus/"

  7. Return OntologyManifest (statistics)
```

**Path rewriting regex**:

```regex
(?:^|(?<=[\s(/\"']))[\w./\-]+?(?=(?:factual|procedural|relational|meta)(?:/|$|\s|\"|\)|,))
```

Matches any path prefix before `factual`, `procedural`, `relational`, `meta`, and replaces with `skus/`.

Examples:
- `output/skus/factual/sku_001` -> `skus/factual/sku_001`
- `test_data/basel_skus/procedural/skill_003` -> `skus/procedural/skill_003`

### 5.3 Step 2: Interactive Chatbot (Generate spec.md)

**Algorithm**:

```
SpecChatbot.run():
  1. Build system prompt:
     a. Load mapping.md and compress (cap at 30,000 chars):
        - Keep header lines (#, ##, ###)
        - Keep SKU path lines
        - Keep description lines (**Description:**)
        - Remove verbose "when to use" text
     b. Load eureka.md summary (cap at 5,000 chars)
     c. Format system prompt template

  2. Get initial greeting:
     Call call_llm_chat([system_message])
     Display AI response

  3. Multi-turn conversation loop:
     while rounds < MAX_CHAT_ROUNDS:
       User input
       If input = "/confirm":
         -> Finalize spec.md
         -> Save to ontology/spec.md
         -> Exit loop

       Append user message to conversation history
       Call call_llm_chat(full conversation history)
       Display AI response

       If remaining rounds <= 1: show warning

  4. Auto-finalize when max rounds exhausted

  5. Save chat_log.json (complete conversation record)
```

**Spec extraction algorithm** (extract spec content from LLM response):

```
_extract_spec(response):
  Priority:
  1. Look for ```markdown code block -> extract content
  2. Look for largest ``` code block -> extract content
  3. If response starts with # (valid Markdown header) -> use full response
  4. Otherwise -> use whitespace-stripped full response
```

**Mapping compression algorithm** (token saving):

```
_compress_mapping(content):
  Keep: header lines, SKU path lines, description lines, separator lines
  Remove: verbose usage instruction text
  Truncate to MAPPING_SUMMARY_MAX_CHARS (30,000)
```

### 5.4 Step 3: README Generation

**Algorithm**:

```
ReadmeGenerator.write(manifest):
  1. Extract statistics from manifest:
     - Factual SKU count
     - Procedural SKU count
     - Whether relational knowledge exists
     - Total files copied

  2. Fill bilingual template (en/zh):
     - Quick start (3 steps)
     - Directory structure (ASCII tree diagram)
     - SKU type description table
     - Statistics
     - Usage guide (4 steps)

  3. Write to ontology/README.md
```

### 5.5 Data Model

```
OntologyManifest:
  created_at, source_skus_dir, ontology_dir
  factual_count, procedural_count
  has_relational, has_mapping, has_eureka
  has_spec, has_readme
  total_files_copied, paths_rewritten

ChatSession:
  started_at
  messages: [ChatMessage(role, content), ...]
  rounds_used, max_rounds
  confirmed: bool
  spec_content: str?
```

---

## 6. Global Design Patterns

### 6.1 Agile Schema Design

All data models use a **fixed part + JIT part** design:

```
Fixed part: standard fields that are always present (source_path, status, sku_id, etc.)
JIT part: flexible metadata dictionary, customized by each component as needed

Advantage: parsers/extractors can store custom metadata without modifying the schema
```

### 6.2 Loose Coupling

Modules communicate through index files on the filesystem:

```
Module 1 -> parse_results_index.json -> Module 2
Module 2 -> chunks_index.json -> Module 3
Module 3 -> skus_index.json -> Module 4
```

Each module can be developed, tested, and run independently.

### 6.3 Resume Support

System-wide support for interrupt recovery:

| Component | Recovery Mechanism |
|-----------|-------------------|
| Module 1 Pipeline | Detects existing non-empty output files, skips already-processed items |
| PaddleOCR-VL | `.progress.jsonl` incremental per-page saving |
| Module 3 Pipeline | `chunks_processed` list + save index after each chunk |
| Confidence Scoring | Skips SKUs that already have a `confidence` field |

### 6.4 Dual-Format Logging

All modules use `structlog` for simultaneous output:

```
Console: colored text (real-time feedback)
JSON file: logs/json/module_name_timestamp.json (machine parsing)
Text file: logs/text/module_name_timestamp.log (human reading)
```

### 6.5 Bilingual Support

All LLM prompts and CLI output are stored as bilingual versions in `dict[str, str]`:

```python
PROMPT = {
    "en": "English prompt text...",
    "zh": "Chinese prompt text..."
}

# At call site:
prompt = PROMPT[settings.language]
```

**Important rule**: JSON field names, enum values, and format specifications remain in English in both languages.

### 6.6 Retry and Fallback Strategy

```
File processing fallback chain:
  File input
  +- Route to parser by extension
  +- If PDF + MarkItDown -> parse
  |  +- Output quality poor (< MIN_VALID_CHARS)?
  |     -> Fallback: PaddleOCR-VL per-page OCR
  +- Other formats -> parse directly

LLM call retry:
  call_llm_json: up to max_retries times
  Each time feed error message back to LLM for self-correction
  temperature slightly decreased

Global retry:
  1 retry per file/URL (2 total attempts)
  Per-page OCR 2 attempts (initial + 1 retry)
```

### 6.7 Configuration System

All configuration loaded via `.env` file, each module's independent `config.py` uses Pydantic BaseSettings:

| Config Item | Default | Description |
|------------|---------|-------------|
| `INPUT_DIR` | `./input` | Input directory |
| `OUTPUT_DIR` | `./output` | Output directory |
| `MAX_PDF_SIZE_MB` | 10 | PDF size threshold |
| `MIN_VALID_CHARS` | 500 | OCR fallback threshold |
| `OCR_DPI` | 150 | Page render resolution |
| `MAX_TOKEN_LENGTH` | 100,000 | Chunk size limit |
| `K_NEAREST_TOKENS` | 50 | LLM split point context |
| `EXTRACTION_MODEL` | `Pro/zai-org/GLM-5` | Knowledge extraction model |
| `EMBEDDING_MODEL` | `Pro/BAAI/bge-m3` | Embedding model |
| `MAX_BUCKET_TOKENS` | 100,000 | Bucket size limit |
| `CHATBOT_MODEL` | `Pro/zai-org/GLM-5` | Chatbot model |
| `MAX_CHAT_ROUNDS` | 5 | Max conversation rounds |
| `LANGUAGE` | `en` | Language (en/zh) |
| `LOG_FORMAT` | `both` | Log format |

### 6.8 CLI Entry Points

Four independent CLI tools defined via `pyproject.toml`:

```ini
[project.scripts]
anything2md = "anything2markdown.cli:main"
md2chunks = "markdown2chunks.cli:main"
chunks2skus = "chunks2skus.cli:main"
skus2ontology = "skus2ontology.cli:main"
```

Each tool supports `run`, `init`, and other subcommands with `-v` (verbose) option.
