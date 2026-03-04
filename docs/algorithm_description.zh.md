# Anything2Ontology 算法详细说明

## 目录

- [一、系统总览](#一系统总览)
- [二、模块一：Anything2Markdown — 万物转 Markdown](#二模块一anything2markdown--万物转-markdown)
- [三、模块二：Markdown2Chunks — 智能分块](#三模块二markdown2chunks--智能分块)
- [四、模块三：Chunks2SKUs — 知识萃取](#四模块三chunks2skus--知识萃取)
- [五、模块四：SKUs2Ontology — 本体组装](#五模块四skus2ontology--本体组装)
- [六、全局设计模式](#六全局设计模式)

---

## 一、系统总览

### 1.1 系统定位

Anything2Ontology 是一条**知识管理与建模流水线**，将各种媒体格式（文件、URL、代码仓库）转换为结构化的本体（Ontology），供 AI 编程助手（如 Claude Code）直接使用。最终产物是一个自包含的 `ontology/` 目录，编程 Agent 只需"读 spec.md，立即开始构建"。

**为什么叫 "Ontology"**：Ontology（本体）一词涵盖了事实（facts）、技能（skills）、概念模型（schema）与知识体系（lore）等多种知识形态。流水线的核心中间产物是**标准知识单元（SKU, Standard Knowledge Unit）**，按知识维度分为四类：事实知识（Factual）、关系知识（Relational）、程序知识（Procedural）和元知识（Meta）。这四类 SKU 组装在一起，构成完整的本体。

### 1.2 四级流水线架构

```
输入 (文件/URL)
    │
    ▼
┌─────────────────────┐
│ 模块一：Anything2Markdown │  万物 → Markdown/JSON
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 模块二：Markdown2Chunks  │  长文档 → 分块（≤100K tokens）
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 模块三：Chunks2SKUs     │  分块 → 标准知识单元（SKU）
│   └─ 后处理子流水线      │  聚类/去重/置信度评分
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 模块四：SKUs2Ontology  │  SKU → 自包含本体
└─────────────────────┘
```

每个模块是独立的 CLI 工具，通过文件系统上的索引文件（`parse_results_index.json`、`chunks_index.json`、`skus_index.json`）松散耦合。没有统一的主脚本，用户依次运行：

```bash
anything2md run       # 模块一
md2chunks run         # 模块二
chunks2skus run       # 模块三
chunks2skus postprocess all  # 可选：后处理
skus2ontology run    # 模块四
```

### 1.3 核心数据流

```
input/
├── files (PDF, PPT, DOCX, XLSX, …)
└── urls.txt (YouTube, Bilibili, GitHub, 网页)
        │
        ▼  [模块一]
output/
├── *.md (Markdown 文件，扁平或按目录分组)
├── *.json (表格数据)
└── parse_results_index.json
        │
        ▼  [模块二]
output/chunks/
├── *_chunk_001.md … *_chunk_NNN.md (带 YAML 前言)
├── chunks_index.json
└── output/passthrough/ (JSON 透传)
        │
        ▼  [模块三]
output/skus/
├── factual/sku_000/ … sku_NNN/ (事实知识)
├── relational/ (标签树 + 术语表 + 关系图)
├── procedural/skill_000/ … skill_NNN/ (技能/流程)
├── meta/ (mapping.md + eureka.md)
├── postprocessing/ (聚类/去重/置信度报告)
└── skus_index.json
        │
        ▼  [模块四]
ontology/
├── README.md (Agent 入口)
├── spec.md (应用规格说明)
├── mapping.md (SKU 路由表，路径已重写)
├── eureka.md (跨领域洞察)
├── ontology_manifest.json
├── chat_log.json
└── skus/ (所有 SKU 的副本，路径已重写)
```

---

## 二、模块一：Anything2Markdown — 万物转 Markdown

### 2.1 职责

将各种文件类型和 URL 统一转换为 Markdown 或 JSON，为下游处理提供标准化输入。

### 2.2 路由算法

路由器（`router.py`）是前台接待员，根据输入类型分派到对应解析器。

#### 2.2.1 文件路由 `route_file(path)`

| 文件扩展名 | 路由目标 | 输出格式 |
|-----------|---------|---------|
| `.pdf` | MarkItDownParser | Markdown |
| `.ppt`, `.pptx`, `.doc`, `.docx`, `.html`, `.epub`, `.md`, `.txt` | MarkItDownParser | Markdown |
| `.xlsx`, `.xls`, `.csv` | TabularParser | JSON |
| `.png`, `.jpg`, `.mp3`, `.mp4`, `.css`, `.js` | 跳过（非文本） | — |

**OCR 降级判定** `should_fallback_to_ocr(output_path)`：

```
若 MarkItDown 解析成功但输出质量差：
    有效字符数 = 正则统计(字母 + 数字 + 常见标点)
    若 有效字符数 < MIN_VALID_CHARS (默认 500)：
        判定为扫描件/低质量 PDF
        → 降级到 PaddleOCR-VL 重新解析
```

#### 2.2.2 URL 路由 `route_url(url)`

| URL 模式 | 路由目标 |
|----------|---------|
| `youtube.com/watch`, `youtu.be/`, `youtube.com/embed` | YouTubeParser |
| `bilibili.com/video/`, `b23.tv/`, `bilibili.com/bangumi` | BilibiliParser |
| `github.com/{owner}/{repo}`（排除 /issues, /pull 等子路径） | RepomixParser |
| 其他 HTTP(S) URL | FireCrawlParser |

### 2.3 文件解析器

#### 2.3.1 MarkItDownParser

**算法**：
1. 调用 `MarkItDown()` 库进行格式转换
2. 提取 `.text_content` 文本内容
3. 生成扁平化输出文件名（`flatten_path` 策略：直接子文件保持原名，嵌套文件用下划线连接路径）
4. 写入 `.md` 文件

**支持格式**：PDF、PPT(X)、DOC(X)、HTML、EPUB、MD、TXT

#### 2.3.2 PaddleOCR-VL Parser（OCR 降级解析器）

**算法**（支持断点续传）：

```
1. 初始化 OpenAI 兼容客户端（SiliconFlow 云端 或 本地 mlx-vlm）
2. 用 PyMuPDF (fitz) 打开 PDF
3. 检查进度文件 (.progress.jsonl) 以支持续传
4. 逐页处理：
   a. 渲染为 PNG（DPI=150）
   b. 转 Base64 编码
   c. 调用视觉 API：
      提示词 = "Convert this document page to markdown..."
      模型 = PaddleOCR-VL（通过 OpenAI 兼容 API）
      参数 = max_tokens=4000, temperature=0.1
   d. 清理 <|LOC_xxx|> 定位标记
   e. 失败时重试最多 2 次
   f. 每页完成后追加写入进度文件（增量保存，崩溃可恢复）
5. 用 "---" 分隔符组装所有页面
6. 成功后清理进度文件
```

**核心特性**：
- 本地服务器旁路：`trust_env=False` 避免代理干扰
- 增量保存：每页写一行 JSON，崩溃后可从最后完成页续传
- 失败页标记：`<!-- OCR failed -->` 注释

#### 2.3.3 TabularParser（表格解析器）

**算法**：
1. 检测文件类型（CSV / Excel）
2. CSV → `pd.read_csv()` → records 格式
3. Excel → `pd.ExcelFile()` → 遍历工作表：
   - 单工作表：展平为 records 数组
   - 多工作表：保持为嵌套字典 `{sheet_name: [records]}`
4. 输出 JSON（`ensure_ascii=False`，支持中文）

#### 2.3.4 MinerU Parser（大型 PDF 的云端解析）

**算法**（支持分片上传）：

```
1. 获取 PDF 页数（PyPDF2）
2. 若 页数 > 400 或 文件 > 2MB：分片处理
3. 对每个分片：
   a. 请求预签名上传 URL：POST /file-urls/batch → batch_id + upload_url
   b. 流式上传文件：PUT upload_url
   c. 轮询批次状态：GET /extract-results/batch/{batch_id}
      （5 秒间隔，30 分钟超时）
   d. 状态变为 "done" 后下载 ZIP
   e. 从 ZIP 中提取 full.md 或第一个 .md 文件
4. 用 "---" 和 "# Part N" 标题拼接所有分片
```

> 注：因阿里云网络连通性问题，MinerU 路由当前已禁用。

### 2.4 URL 解析器

#### 2.4.1 YouTubeParser

**算法**：
1. 从 URL 提取视频 ID（正则匹配多种格式）
2. 调用 `YouTubeTranscriptApi` 获取字幕：
   - 优先语言列表：[en, zh, zh-Hans, zh-Hant, zh-CN, zh-TW]
   - 回退策略：手动创建 → 自动生成 → 任何可用字幕
3. 格式化为 Markdown：
   - 检测句末标点（.!?…，中文标点）进行段落分组
   - 同一段落内用空格连接片段

#### 2.4.2 BilibiliParser

**双策略算法**：

```
策略一：CC 字幕优先（通过 yt-dlp）
  1. 提取视频信息（标题、BV 号）
  2. 按优先级尝试字幕源：
     requested_subtitles → subtitles → automatic_captions
  3. 按格式优先级解析：json3 → srv3 → vtt → srt
  4. 解析不同格式的字幕结构：
     - json3: {"events": [{"segs": [{"utf8": "..."}], "tStartMs": ...}]}
     - srv1-3: XML <p t="...">text</p>
     - vtt: WebVTT 时间戳格式
     - Bilibili JSON: {"from": ..., "to": ..., "content": "..."}
  5. 转换为统一结构 {"text": "...", "start": seconds}

策略二：WhisperX 降级（无字幕时）
  1. 用 yt-dlp 下载纯音频 → WAV
  2. 加载 faster-whisper 模型（可配置大小）
  3. 检测 GPU：cuda → float16，cpu → int8
  4. 语音转文字（language=zh）
  5. 提取带时间码的片段
```

**Cookie 支持**：
- 优先使用 Netscape 格式 cookie 文件
- 回退到浏览器 cookie 提取（chrome/firefox/safari/edge）
- B站 需要 cookie 避免 HTTP 412 错误

#### 2.4.3 FireCrawlParser

**算法**：
1. 调用 FireCrawl API 爬取网页（limit=50 页）
2. 每页提取 URL 和 Markdown 内容
3. 用 `# {page_url}` 标题和 `---` 分隔符组合所有页面

#### 2.4.4 RepomixParser

**算法**：
1. 检查 `repomix` CLI 是否已安装
2. 从 URL 提取仓库名：`github.com/{owner}/{repo}`
3. 运行子进程：`repomix --remote {url} --style markdown --output {path}`
4. 超时限制：10 分钟

### 2.5 流水线编排

```
run()
├─ 遍历 input/ 目录的所有文件
│  └─ 对每个文件：_process_file_with_retry()
│     ├─ 检查是否已有输出（断点续传）→ 跳过
│     ├─ 路由到解析器
│     ├─ 执行解析
│     └─ 若 PDF + MarkItDown + 输出质量差 → OCR 降级
│        （删除低质量输出，用 PaddleOCR-VL 重新解析）
│
├─ 从 urls.txt 读取所有 URL
│  └─ 对每个 URL：_process_url_with_retry()
│     ├─ 路由到解析器
│     └─ 执行解析
│
├─ 保存 parse_results_index.json（摘要 + 逐项详情）
└─ 输出统计日志（成功/失败/跳过）
```

**重试策略**：全局 1 次重试（共 2 次尝试），2 秒延迟。区分 `RetryableError`（可重试）和 `NonRetryableError`（直接跳过）。

**断点续传**：跳过已有非空输出的文件，返回标记 `resumed=True` 的 ParseResult。

### 2.6 数据模型：ParseResult

采用**敏捷 Schema** 设计（固定部分 + JIT 部分）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_path` | str | 输入路径（文件或 URL） |
| `source_type` | "file" / "url" | 输入类型 |
| `output_path` | str | 输出文件路径 |
| `output_format` | "markdown" / "json" | 输出格式 |
| `parser_used` | str | 使用的解析器名称 |
| `status` | "success" / "failed" / "skipped" | 处理状态 |
| `started_at` / `completed_at` | datetime | 时间戳 |
| `duration_seconds` | float | 处理耗时 |
| `character_count` | int | 输出字符数 |
| `error_message` | str? | 错误信息 |
| `retry_count` | int | 重试次数 |
| **`metadata`** | **dict[str, Any]** | **JIT 元数据**（各解析器自定义） |

`metadata` 示例：
- MarkItDown: `{"original_extension": ".pdf"}`
- PaddleOCR-VL: `{"page_count": 50, "pages_failed": 2, "ocr_model": "...", "dpi": 150}`
- YouTube: `{"video_id": "...", "transcript_segments": 120}`
- Bilibili: `{"video_id": "BV...", "title": "...", "transcript_segments": 80}`

---

## 三、模块二：Markdown2Chunks — 智能分块

### 3.1 职责

将长 Markdown 文件切分为适合 LLM 处理的分块（每块 ≤ 100K tokens），JSON 文件透传不处理。

### 3.2 路由算法

```
should_chunk(file_path):
    .md 文件  → 需要分块
    .json 文件 → 透传到 passthrough/
    其他       → 跳过并警告

get_chunker(content):
    若 Markdown 中存在标题（# ## ### …）
        → HeaderChunker（确定性，速度快）
    否则
        → LLMChunker（语义切分，回退方案）
```

### 3.3 HeaderChunker —— "剥洋葱"算法

**核心思想**：沿标题层级逐层剥离，只有在某节超过 token 上限时才进行切分。优先保持文档的逻辑结构完整。

#### 3.3.1 算法流程

```
输入：带标题层级的 Markdown 文档

阶段一：标题检测
  parse_headers(content) → list[MarkdownSection]
  用正则 ^(#{1,6})\s+(.+)$ 匹配所有标题
  为每个标题创建 MarkdownSection:
    { level, title, content, start_pos, end_pos, token_count }

阶段二：构建层次树
  build_section_tree(sections) → tree
  使用栈（stack）算法构建父子关系：
    对每个 section:
      node = {section, children: []}
      while 栈顶层级 ≥ 当前层级: 弹出栈
      if 栈非空: 添加为栈顶节点的子节点
      else: 添加到根列表
      压入栈

阶段三：递归处理树（核心）
  _process_tree(tree):
    对每个节点：
      子树总 token = _calculate_subtree_tokens(node)  // 递归求和

      if 子树总 token ≤ MAX_TOKEN_LENGTH:
          → 将整个子树合并为一个 chunk
          （调用 _extract_subtree_content 递归拼接内容）
      else:
          → 提取引言（该节标题到第一个子标题之间的内容）
          → 若引言非空，创建独立 chunk
          → 递归处理每个子节点
          → 若无子节点且仍超限，标记待 LLM 二次切分
```

#### 3.3.2 示例演示

```
文档结构：
# 主标题 (100 tokens)
  ## 章节 A (30,000 tokens)
    ### 小节 A1 (10,000 tokens)
    ### 小节 A2 (20,000 tokens)
  ## 章节 B (15,000 tokens)

MAX_TOKEN_LENGTH = 100,000

处理过程：
1. 根节点 "主标题"：子树 = 145,100 tokens > 上限 → 拆分
   → 提取引言（100 tokens），创建 chunk 0
2. 子节点 "章节 A"：子树 = 60,000 tokens ≤ 上限
   → 合并为 chunk 1（包含 A + A1 + A2 完整内容）
3. 子节点 "章节 B"：子树 = 15,000 tokens ≤ 上限
   → 合并为 chunk 2

输出：3 个 chunks
```

### 3.4 LLMChunker —— "楔入法"算法

**核心思想**：利用 LLM 识别语义切分点，再通过 Levenshtein 模糊匹配定位精确位置。适用于纯文本或无标题的长段落。

#### 3.4.1 算法流程

```
输入：超长 Markdown 或纯文本

阶段一：滚动上下文窗口循环
  remaining_text = content
  chunks = []

  while remaining_text 非空:
    remaining_tokens = estimate_tokens(remaining_text)

    if remaining_tokens ≤ MAX_TOKEN_LENGTH:
        → 创建最后一个 chunk，退出循环

    // ① 截取窗口
    window_text = truncate_to_tokens(remaining_text, MAX_TOKEN_LENGTH)

    // ② 调用 LLM 寻找切分点
    cut_points = _get_cut_points(window_text)
    // LLM 返回每个切分点的：
    //   tokens_before: 切分点前 ~K tokens 的精确文本
    //   tokens_after:  切分点后 ~K tokens 的精确文本
    //   chunk_title:   该 chunk 的简短标题

    // ③ Levenshtein 模糊匹配定位
    if cut_points 非空:
        cut_pos = find_cut_position(
            cut_points[0].tokens_before,
            cut_points[0].tokens_after,
            remaining_text
        )
    else:
        cut_pos = _find_paragraph_boundary(remaining_text)

    // ④ 创建 chunk 并推进
    chunk_content = remaining_text[:cut_pos]
    remaining_text = remaining_text[cut_pos:].lstrip()
    chunks.append(chunk_content)
```

#### 3.4.2 LLM 切分点查询

**提示词结构**：

```
输入给 LLM：
  CONTENT: ~100K tokens 的文本窗口
  TASK: 在文本中找到 1-3 个自然切分点

对每个切分点，输出：
  1. tokens_before: 切分点前精确 ~K tokens（默认 K=50）
  2. tokens_after: 切分点后精确 ~K tokens
  3. chunk_title: 切分点之前 chunk 的 5-10 字标题

输出格式（JSON）：
{
  "cut_points": [
    {
      "tokens_before": "...精确文本...",
      "tokens_after": "...精确文本...",
      "chunk_title": "该段标题"
    }
  ]
}
```

#### 3.4.3 Levenshtein 模糊匹配算法

**为什么需要模糊匹配**：LLM 输出的文本可能与原文存在微小差异（空白符、编码差异），不能用精确字符串匹配。

```
find_best_match(needle, haystack, search_window=500):
  对 haystack 前 search_window 字符进行滑窗搜索：
    对每个位置 i:
      candidate = haystack[i : i + len(needle)]
      distance = Levenshtein.distance(needle, candidate)
      similarity = 1 - distance / max(len(needle), len(candidate))

      if distance < 历史最小 且 similarity > 0.7:
          更新最佳位置

  返回最佳匹配位置（或 None）

find_cut_position(tokens_before, tokens_after, text):
  阶段一：定位 tokens_before 的匹配位置
    before_pos = find_best_match(tokens_before, text)
    cut_pos = before_pos + len(tokens_before)

  阶段二：验证 tokens_after 是否在附近出现
    after_search = text[cut_pos : cut_pos + len(tokens_after) + 100]
    after_pos = find_best_match(tokens_after, after_search)
    // 允许 50 字符间隙

  阶段三：跳过前导空白
    while text[cut_pos] 是空白字符: cut_pos += 1

  返回 cut_pos
```

#### 3.4.4 段落边界回退

当 LLM 切分失败时的回退策略：

```
_find_paragraph_boundary(text, max_tokens):
  截取 text 前 max_tokens 对应的文本
  按优先级搜索最佳断点：
    1. 最后一个双换行 "\n\n"（段落边界）→ 最优
    2. 最后一个单换行 "\n"（行边界）
    3. 最后一个句末标点（". " "! " "? "）
    4. 硬回退：直接在 token 上限处截断
```

### 3.5 Token 估算

使用 `tiktoken` 的 `cl100k_base` 编码器（兼容 GPT-4 和 Claude）：

| 函数 | 用途 |
|------|------|
| `estimate_tokens(text)` | 返回 token 数量 |
| `truncate_to_tokens(text, max)` | 精确截断到指定 token 数 |
| `get_token_limit()` | 返回配置的上限（默认 100,000） |

### 3.6 流水线编排

```
ChunkingPipeline.run():
  发现阶段：
    递归查找 output/ 下所有 .md 和 .json 文件
    排除 chunks/, passthrough/, skus/ 目录

  处理阶段（顺序处理）：
    对每个 .md 文件：
      tokens = estimate_tokens(content)
      if tokens ≤ MAX_TOKEN_LENGTH:
          → 创建单一 chunk（method="single"）
      else:
          → 路由到 HeaderChunker 或 LLMChunker
          → 执行分块
          → _rechunk_if_needed：检查每个 chunk 是否超限
             超限的用 LLMChunker 二次切分
      → 写入带 YAML 前言的分块文件
      → 更新 ChunksIndex

    对每个 .json 文件：
      → 复制到 output/passthrough/（防碰撞命名）

  输出阶段：
    写入 chunks_index.json
    输出统计日志
```

### 3.7 输出格式

每个 chunk 文件带 YAML 前言：

```yaml
---
title: "章节标题"
source: "原始文件名.md"
chunk: 1
total: 3
tokens: 25000
method: "header"
---

[实际内容]
```

文件命名规则：`{原始文件名去后缀}_chunk_{序号:03d}.md`

---

## 四、模块三：Chunks2SKUs — 知识萃取

### 4.1 职责

从分块中萃取四种标准知识单元（SKU），同时维护全局知识结构的累积更新。

### 4.2 四种知识类型

| 类型 | 英文名 | 描述 | 处理模式 | 输出 |
|------|--------|------|---------|------|
| 事实知识 | Factual | 数据、定义、事实 | 隔离 | 独立 SKU 文件夹 |
| 关系知识 | Relational | 概念层级、术语、语义关系 | 读取-更新 | 全局 JSON 文件 |
| 程序知识 | Procedural | 流程、技能、最佳实践 | 隔离 | 独立 SKILL 文件夹 |
| 元知识 | Meta | 知识路由、跨域洞察 | 读取-更新 | mapping.md + eureka.md |

### 4.3 核心处理流程：累积上下文的顺序处理

这是模块三最关键的设计模式。Chunks 按顺序处理，每个 chunk 经过全部四个提取器，知识在处理过程中不断累积：

```
all_skus = []  // 全局 SKU 累积列表

for chunk in chunks:  // 严格顺序处理
    if 已处理过(chunk): continue  // 断点续传

    // 步骤 1：事实提取（隔离，不依赖上下文）
    factual_skus = FactualExtractor.extract(chunk.content, chunk.id, {})

    // 步骤 2：关系提取（读取已有 label_tree.json 和 glossary.json，更新它们）
    relational_ctx = RelationalExtractor.get_context_for_next()
    RelationalExtractor.extract(chunk.content, chunk.id, relational_ctx)
    // → 更新全局：label_tree.json, glossary.json, relationships.json

    // 步骤 3：程序提取（隔离，不依赖上下文）
    procedural_skus = ProceduralExtractor.extract(chunk.content, chunk.id, {})

    // 步骤 4：元提取（接收所有已创建的 SKU 列表）
    new_skus = factual_skus + procedural_skus
    meta_ctx = {"all_skus": all_skus + new_skus}
    MetaExtractor.extract(chunk.content, chunk.id, meta_ctx)
    // → 更新全局：mapping.md, eureka.md

    all_skus.extend(new_skus)
    save_index()  // 每处理完一个 chunk 就保存，支持恢复
```

### 4.4 事实提取器（FactualExtractor）

**目标**：提取"X 是什么"类型的知识——数据点、定义、统计、表格。

**算法**：

```
1. 调用 LLM (temperature=0.3)：
   - 发送 chunk 内容
   - 请求 JSON 数组输出，每项是一个独立事实
   - 特殊规则：表格/JSON 数组/CSV 必须作为整体保留，不可拆行
   - 遵循 MECE 原则（互斥穷尽）

2. 对每个提取的事实：
   - 生成唯一 ID：sku_000, sku_001, ...（全局递增计数器）
   - 判断内容类型：markdown 或 json
   - 创建 SKU 文件夹：
     output/factual/sku_NNN/
     ├── header.md    (元数据：名称、分类、字符数、来源 chunk、描述)
     └── content.md   (Markdown 内容) 或 content.json (JSON 内容)

3. 返回 SKU 信息列表（ID、名称、路径、描述等）
```

### 4.5 关系提取器（RelationalExtractor）

**目标**：提取概念之间的关系，维护全局标签层级树和术语表。

**算法**（读取-更新模式）：

```
1. 加载持久化状态：
   - label_tree.json → LabelTree 实例
   - glossary.json → Glossary 实例
   - relationships.json → Relationships 集合

2. 调用 LLM (temperature=0.3, max_tokens=8000)：
   - 发送当前状态作为上下文（标签树 + 术语表摘要，上限 6000 字符）
   - 发送新 chunk 内容
   - 请求 JSON 输出：
     {
       "label_tree": 更新后的层级树,
       "glossary": 新增/更新的术语条目,
       "relationships": 类型化语义关系
     }

3. 合并更新：
   _merge_label_tree(new_tree):
     递归合并新节点到现有树
     大小写不敏感匹配
     保留已有节点，仅添加新节点

   _merge_glossary(new_glossary):
     对每个条目调用 Glossary.add_or_update()：
       - 保留更长的定义（更丰富）
       - 累积来源 chunks
       - 合并 labels、aliases、related_terms（去重）

   更新 relationships 集合（按 subject+predicate+object 去重）

4. 保存更新后的 JSON 文件
```

**关系类型**（13 种）：is-a, has-a, part-of, causes, caused-by, requires, enables, contradicts, related-to, depends-on, regulates, implements, example-of

**数据结构**：

```
LabelTree（标签层级树）：
  add_path(["金融", "风险", "信用风险"]) → 创建嵌套路径
  get_all_paths() → 展平为路径列表

Glossary（术语表）：
  get_entry(term) → 大小写不敏感 + 别名支持
  add_or_update(entry) → 合并策略
  get_terms_by_label(label) → 按类别查询

GlossaryEntry：
  { term, definition, labels[], source_chunks[], aliases[], related_terms[] }
```

### 4.6 程序提取器（ProceduralExtractor）

**目标**：提取可操作的流程、技能和最佳实践，输出为 Claude Code 兼容的 SKILL.md 格式。

**算法**：

```
1. 调用 LLM (temperature=0.3, max_tokens=6000)：
   - 发送 chunk 内容
   - 请求 JSON 数组，每项是一个程序/技能：
     {
       "name": "hyphen-case 标识符（≤64 字符）",
       "description": "何时使用（≤200 字符，无尖括号）",
       "body": "Markdown 指令（概述+步骤+决策点+预期结果）",
       "has_scripts": boolean,
       "scripts": [{"name": "脚本名", "content": "脚本内容"}],
       "has_references": boolean,
       "references": [{"name": "参考名", "content": "参考内容"}]
     }

2. 对每个程序：
   - 生成唯一 ID：skill_000, skill_001, ...
   - 名称转 hyphen-case
   - 描述去尖括号、截断到 200 字符
   - 创建技能文件夹：
     output/procedural/skill_NNN/
     ├── header.md
     ├── SKILL.md      (YAML 前言 + Markdown 正文)
     ├── scripts/       (若有脚本)
     │   ├── script_0.py
     │   └── script_1.py
     └── references/    (若有参考)
         └── reference_0.md

SKILL.md 格式（Claude Code 兼容）：
  ---
  name: skill-name
  description: When to use this skill
  ---

  [完整 Markdown 指令]
```

### 4.7 元提取器（MetaExtractor）

**目标**：生成知识库的"关于知识的知识"——SKU 路由表（mapping.md）和跨域创意洞察（eureka.md）。

**算法**（双轨处理）：

```
轨道 A：更新 mapping.md（精确度导向，temperature=0.2）
  1. 调用 LLM：
     - 输入：当前所有 SKU 列表 + 现有 mapping.md + 当前 chunk_id
     - 输出：更新后的 mapping.md（Markdown 格式的 SKU 路由目录）
     - 系统提示强调：准确性、不幻觉、仅包含实际存在的 SKU
  2. 收缩保护：若新内容比旧内容缩减 >50%（除非是首次），则拒绝更新
  3. 写入 mapping.md

轨道 B：更新 eureka.md（创造性导向，temperature=0.7）
  1. 调用 LLM：
     - 输入：现有 eureka.md + 新 chunk 内容（前 8000 字符）
     - 输出：{ "updated": bool, "eureka_content": "更新后的内容" }
  2. 质量门控（提示词强制）：
     - 洞察必须跨越多个领域（跨域模式）
     - 必须揭示令人惊讶的连接或设计原则
     - 不是简单的功能建议或领域内细节
     - 全文最多 20 条要点
     - 按主题（## 标题）组织，而非按 chunk
     - 包含来源 chunk 引用：[chunk_001, chunk_005]
  3. 合并策略：
     - 新洞察强化现有要点 → 合并并更新引用
     - 现有要点被更好表述替代 → 删除旧的
  4. 收缩保护：同 mapping.md
```

### 4.8 后处理子流水线

在主提取完成后，可选运行三步后处理进行质量控制。

#### 4.8.1 步骤一：聚类（Bucketing）

**目标**：将事实和程序 SKU 按相似度分组，每组不超过 `max_bucket_tokens`（默认 100K）。

**多维相似度评分算法**：

```
总相似度 = w₁ × 字面相似度 + w₂ × 标签相似度 + w₃ × 向量相似度

其中：
  字面相似度 (w₁=0.2)：TF-IDF 向量化 + 余弦相似度
  标签相似度 (w₂=0.3)：标签树路径的 Jaccard 距离
  向量相似度 (w₃=0.5)：通过 SiliconFlow bge-m3 API 获取嵌入向量 + 余弦相似度

自适应权重：若嵌入 API 不可用，自动将权重重分配到剩余维度
```

**递归二分算法**：

```
使用层次凝聚聚类（Hierarchical Agglomerative Clustering）
递归将 SKU 集合二分，直到每个桶的总 token 数 ≤ max_bucket_tokens

输出：bucketing_result.json
  - 事实桶列表
  - 程序桶列表
  - 每个桶：bucket_id, total_tokens, sku_count, entries[]
```

#### 4.8.2 步骤二：去重（Dedup）

**目标**：检测并处理重复和矛盾的 SKU。

**两层 LLM 判断算法**：

```
第一层：标题扫描（快速筛选）
  对每个桶内的 SKU：
    批量发送 header.md（每批最多 80 个 SKU，避免 token 溢出）
    LLM 快速判断哪些可能是重复对
    输出：疑似重复对列表 [(sku_a, sku_b, reason)]

第二层：深度对比（精确判断）
  对每个疑似重复对：
    读取两个 SKU 的完整内容（前 8000 字符）
    LLM 做出判断，返回操作：
      "keep"          → 两者不同，保留
      "delete"        → 明确重复，删除其一
      "rewrite"       → 需要修改其一的内容
      "merge"         → 合并为一个 SKU
      "contradiction" → 保留但标记矛盾（仅记录，不执行）

安全机制：
  - 验证 LLM 返回的 SKU ID 确实在当前桶中（防止幻觉 ID）
  - 更新 mapping.md 删除被删 SKU 的引用
  - 保存详细 dedup_report.json
```

#### 4.8.3 步骤三：置信度评分（Proofreading）

**目标**：通过 RAG 验证为每个 SKU 计算置信度分数。

**两步置信度计算**：

```
步骤一：源头完整性检查（惩罚项，0.0–0.5）
  将提取的 SKU 与原始源 chunk 对比
  只能降低置信度（检测幻觉/失真）
  若源不可用则不惩罚

步骤二：外部验证（主信号，0.0–1.0）
  通过 Jina API (https://s.jina.ai/) 进行网络搜索
  限速：~100 RPM（0.6 秒间隔）
  提取前 5 条结果的标题、URL、摘要
  LLM 评估网络信息是否佐证 SKU 声明

最终分数 = max(0.0, min(1.0, 外部验证分 - 源头惩罚分))
```

**可恢复**：跳过已评分的 SKU（检查 `sku_entry.confidence` 字段）。

**输出**：
- 更新每个 SKU 的 `header.md`（添加置信度行）
- 更新 `skus_index.json`
- 保存 `confidence_report.json`

### 4.9 数据模型

#### SKUsIndex（主索引）

```
{
  created_at, updated_at,
  total_skus,
  total_characters,
  chunks_processed: [chunk_id, ...],  // 已处理的 chunk，支持断点续传
  skus: [
    { sku_id, name, classification, path, source_chunk,
      character_count, description, confidence }
  ],
  factual_count, relational_count, procedural_count, meta_count
}
```

### 4.10 LLM 调用工具

```
call_llm_json(prompt, ..., max_retries=2):
  第一次调用：请求结构化 JSON 格式
  若解析失败：重试（最多 max_retries 次）
    - 将错误信息追加到提示词中
    - 略微降低 temperature (temp - 0.1)
    - LLM 根据错误反馈自我纠正

  parse_json_response(text):
    - 去除 Markdown 代码块标记
    - 尝试 JSON 解析
    - 回退：单引号转双引号后重试
```

---

## 五、模块四：SKUs2Ontology — 本体组装

### 5.1 职责

将萃取的 SKU 组装为自包含的本体，编程 Agent 可直接使用。三步流程：复制组织 → 交互式生成 spec.md → 生成 README.md。

### 5.2 步骤一：组装（Assembler）

**算法**：

```
OntologyAssembler.assemble():
  1. 验证源目录存在
  2. 创建 ontology/skus/ 目录

  3. 复制子目录：
     factual/ → ontology/skus/factual/
     procedural/ → ontology/skus/procedural/
     relational/ → ontology/skus/relational/
     postprocessing/ → ontology/skus/postprocessing/ (若存在)
     （先删除目标目录再整体复制，确保干净）

  4. 路径重写 skus_index.json：
     遍历每个 SKU 条目的 "path" 字段
     将任意前缀（如 "output/skus/", "test_data/..."）
     统一重写为 "skus/"

  5. 复制 eureka.md → ontology/eureka.md（根目录）

  6. 路径重写 mapping.md → ontology/mapping.md：
     全文搜索替换所有 SKU 路径的前缀为 "skus/"

  7. 返回 OntologyManifest（统计信息）
```

**路径重写正则表达式**：

```regex
(?:^|(?<=[\s(/\"']))[\w./\-]+?(?=(?:factual|procedural|relational|meta)(?:/|$|\s|\"|\)|,))
```

匹配 `factual`、`procedural`、`relational`、`meta` 前的任意路径前缀，替换为 `skus/`。

示例：
- `output/skus/factual/sku_001` → `skus/factual/sku_001`
- `test_data/basel_skus/procedural/skill_003` → `skus/procedural/skill_003`

### 5.3 步骤二：交互式 Chatbot（生成 spec.md）

**算法**：

```
SpecChatbot.run():
  1. 构建系统提示词：
     a. 加载 mapping.md 并压缩（上限 30,000 字符）：
        - 保留标题行（#, ##, ###）
        - 保留 SKU 路径行
        - 保留描述行（**Description:**）
        - 移除冗长的"何时使用"文本
     b. 加载 eureka.md 摘要（上限 5,000 字符）
     c. 格式化系统提示模板

  2. 获取初始问候语：
     调用 call_llm_chat([system_message])
     显示 AI 回复

  3. 多轮对话循环：
     while 轮次 < MAX_CHAT_ROUNDS:
       用户输入
       若输入 = "/confirm"：
         → 最终化 spec.md
         → 保存到 ontology/spec.md
         → 退出循环

       将用户消息追加到对话历史
       调用 call_llm_chat(完整对话历史)
       显示 AI 回复

       若剩余轮次 ≤ 1：显示警告

  4. 最大轮次用尽时自动最终化

  5. 保存 chat_log.json（完整对话记录）
```

**Spec 提取算法**（从 LLM 回复中提取 spec 内容）：

```
_extract_spec(response):
  优先级：
  1. 寻找 ```markdown 代码块 → 提取内容
  2. 寻找最大的 ``` 代码块 → 提取内容
  3. 若回复以 # 开头（有效 Markdown 标题）→ 使用完整回复
  4. 否则 → 使用去空白后的完整回复
```

**映射压缩算法**（Token 节约）：

```
_compress_mapping(content):
  保留：标题行、SKU 路径行、描述行、分隔线
  移除：详细使用说明文本
  截断到 MAPPING_SUMMARY_MAX_CHARS (30,000)
```

### 5.4 步骤三：README 生成

**算法**：

```
ReadmeGenerator.write(manifest):
  1. 从 manifest 提取统计信息：
     - 事实 SKU 数量
     - 程序 SKU 数量
     - 关系知识是否存在
     - 复制文件总数

  2. 使用双语模板（en/zh）填充：
     - 快速开始（3 步）
     - 目录结构（ASCII 树形图）
     - SKU 类型说明表
     - 统计数据
     - 使用指南（4 步）

  3. 写入 ontology/README.md
```

### 5.5 数据模型

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

## 六、全局设计模式

### 6.1 敏捷 Schema 设计

所有数据模型采用**固定部分 + JIT 部分**设计：

```
固定部分：始终存在的标准字段（source_path, status, sku_id 等）
JIT 部分：灵活的 metadata 字典，各组件按需自定义

优势：解析器/提取器可存储自定义元数据而无需修改 Schema
```

### 6.2 松散耦合

模块通过文件系统上的索引文件通信：

```
模块一 → parse_results_index.json → 模块二
模块二 → chunks_index.json → 模块三
模块三 → skus_index.json → 模块四
```

每个模块可独立开发、测试和运行。

### 6.3 断点续传

全系统支持中断恢复：

| 组件 | 恢复机制 |
|------|---------|
| 模块一 流水线 | 检测已有非空输出文件，跳过已处理的 |
| PaddleOCR-VL | `.progress.jsonl` 逐页增量保存 |
| 模块三 流水线 | `chunks_processed` 列表 + 每 chunk 保存索引 |
| 置信度评分 | 跳过已有 `confidence` 字段的 SKU |

### 6.4 双格式日志

所有模块使用 `structlog` 同时输出：

```
控制台：彩色文本（实时反馈）
JSON 文件：logs/json/模块名_时间戳.json（机器解析）
文本文件：logs/text/模块名_时间戳.log（人类阅读）
```

### 6.5 双语支持

所有 LLM 提示词和 CLI 输出都以 `dict[str, str]` 存储双语版本：

```python
PROMPT = {
    "en": "English prompt text...",
    "zh": "中文提示词文本..."
}

# 调用时：
prompt = PROMPT[settings.language]
```

**重要规则**：JSON 字段名、枚举值和格式规范在两种语言中保持英文不变。

### 6.6 重试与降级策略

```
文件处理降级链：
  文件输入
  ├─ 按扩展名路由到解析器
  ├─ 若 PDF + MarkItDown → 解析
  │  └─ 输出质量差（< MIN_VALID_CHARS）？
  │     → 降级：PaddleOCR-VL 逐页 OCR
  └─ 其他格式 → 直接解析

LLM 调用重试：
  call_llm_json：最多 max_retries 次
  每次将错误信息反馈给 LLM 自我纠正
  temperature 略微下降

全局重试：
  每个文件/URL 1 次重试（共 2 次尝试）
  逐页 OCR 2 次尝试（初始 + 1 次重试）
```

### 6.7 配置体系

所有配置通过 `.env` 文件加载，各模块独立的 `config.py` 使用 Pydantic BaseSettings：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `INPUT_DIR` | `./input` | 输入目录 |
| `OUTPUT_DIR` | `./output` | 输出目录 |
| `MAX_PDF_SIZE_MB` | 10 | PDF 大小阈值 |
| `MIN_VALID_CHARS` | 500 | OCR 降级阈值 |
| `OCR_DPI` | 150 | 页面渲染分辨率 |
| `MAX_TOKEN_LENGTH` | 100,000 | 分块上限 |
| `K_NEAREST_TOKENS` | 50 | LLM 切分点上下文 |
| `EXTRACTION_MODEL` | `Pro/zai-org/GLM-5` | 知识萃取模型 |
| `EMBEDDING_MODEL` | `Pro/BAAI/bge-m3` | 嵌入模型 |
| `MAX_BUCKET_TOKENS` | 100,000 | 聚类桶上限 |
| `CHATBOT_MODEL` | `Pro/zai-org/GLM-5` | Chatbot 模型 |
| `MAX_CHAT_ROUNDS` | 5 | 最大对话轮次 |
| `LANGUAGE` | `en` | 语言（en/zh） |
| `LOG_FORMAT` | `both` | 日志格式 |

### 6.8 CLI 入口

通过 `pyproject.toml` 定义四个独立的 CLI 工具：

```ini
[project.scripts]
anything2md = "anything2markdown.cli:main"
md2chunks = "markdown2chunks.cli:main"
chunks2skus = "chunks2skus.cli:main"
skus2ontology = "skus2ontology.cli:main"
```

每个工具支持 `run`、`init` 等子命令和 `-v`（verbose）选项。
