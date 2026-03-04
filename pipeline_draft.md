# **Description**

I am building a knowledge management and modelling pipeline called 'Anything2Ontology'. From user's view, this pipeline has a variety of media as input, and a comprehensive workspace as output. The workspace is fully equipped with all the data, knowledge and instructions that are necessary to build a complicated app. Ideally, user can open coding agents like Claude Code in this workspace with only very simple prompts like 'Read this file and start building', and then get a working app.

This pipeline runs with a selection models provided by SiliconFlow. I will put the api key of Silicon in .env for testing.

# **Key Concepts When Building This System**

These are what we need to remember during building. Create and update claude.md base on these in this project.

1. The design of any schema or structure should be agile. This means that we can pre-define part of the schema (fixed part of schema), and also give the LLMs freedom to define another part of the schema (JIT part of schema, JIT standing for Just In Time), case by case, based on the specific scenario.
2. The calculation of any indicator should be agile. This means that we can set certain aspects to consider, but we also need to build a mechanism to calculate and assign different weight to these aspects, via sample testing using SOTA models. Conceptually, this is kinda like model distillation.
3. Instead of generating a one-time, summary kind of file after the entire looping process is finished, updating the content and structure of the file during each iteration of the loop is a much better idea.
4. Load context as needed, when needed. Like how Claude code reads SKILL.md, first header to decide whether to use it or not, then read content or skip accordingly.
5. Encapsulate human's behavioral sequences expressed in natural language into atomic, deterministic tools.
6. This pipeline, when running, should generate well-structured log files.

# **Key Modules of Pipeline**

This is what this pipeline should do. Remember when building the pipeline, do it module by module. **Keep Loose Coupling for modules.**

## 1. **Anything2Markdown**

Practically an anything parser, with a front desk script based on file extension and size, deciding which of the following parser each file should be sent to.

- MarkItDown: From GitHub: microsoft/markitdown, handles normal PDFs, PPTs, MP3 and MP4 format of media.

- MinerU: A better pdf parser based on VLM, but also slower and more expensive. Handles Scanned PDFs or PDF with lots of pictures. I have an api key for MinerU and I will put it in the .env file. This module show call MinerU to handle a pdf file when it is large than 'max pdf size' or MarkItDown gives results with valid characters less than 'min valid characters'. These two are defined in .env and, for now, let's set it to 10mb and 500.

- xlsx/csv2JSON: For datasets like xlsx or csv, converting them into Markdown is not a good choice, use some script or simple tools to convert them into JSON.

An empty url list file for user to write down urls they want to input, including websites, youtube videos and Git repo. Parse as follows:

- FireCrawl: From firecrawl.dev , handles a website with multiple layers of webpages, crawls the content of all pages and combines in a markdown file with good level format.

- Youtube-to-MD: Available on Github, takes youtube URLs and gives the content in markdown or txt format.

- RepoMix: Available on Github, turns an entire git repo into a markdown file.

When parsing, user may copy folders with layers. Walk through the folders can parse each file into Markdown or JSON. Parsed results are saved and laid flat. Just append the original path to file name, no need to restore the original folder layer.

## 2. **Markdown2Chunks**

This module processes markdown files that are too long for Large Language Models to process in a single session, by cutting them into smaller chunks. 'max token length' can be defined in .env and for now let's set it to 100k. Use a good, small, multi-lingual token estimator. For most Markdown files with good level format, we could do this easily, like peeling onion. But for those corner cases where we have superlong plain text, or after chunking by Markdown level there are still chunks exceeding max length, we design a fallback mechansim with two core concepts: **Driving Wedges** and **Rolling Context Window**.

- **Driving Wedges**: We use LLM instead of keyword mechanism to decide where to cut. LLM reads a 'max length' of original markdown and print the K nearest (both before and after) tokens of where it thinks should cut. Then a script uses the output of LLM and Levenshtein Distance to relocate and cut. This will reduce errors and output tokens massively comparing with asking LLM to print full content of separated chunks. In this step, the LLM should also give each chunk a title, which could be the title from original text or a short summary of it, serving as part of the metadata of the chunk.

- **Rolling Context Window**: Since the original text cannot be loaded in a single session, we load the first max length of the remaining text and chunk it. When finish chunking, we load another max length starting from the last cut in the previous window. We repeat this process until the entire Markdown file is processed.

- Please note that even if the original markdown level is good and has multiple layers, DO NOT cut too many times and make the chunks too small. Bigger chunk size means less information loss. When a newly cut chunk falls below max length, DO NOT chunk again.

- Each chunk should have metadata, including a title, character count, original file path and file name, and others if necessary.

## 3. **Chunks2SKUs**

This module does **knowledge extraction** by extracting SKUs (Standard Knowledge Units) from chunks. The extraction process handles one chunk at a time.

### 3.1 Classification of knowledge:

- **Factual Knowledge**: Basic facts, data, what is what.

- **Relational Knowledge**: Relations, causal and contextual knowledge, the whys becauses buts if-thens.

- **Procedural Knowledge**: Actionable and skill-based knowledge, like description of a workflow or a framework of analysis.

- **Meta Knowledge**: Knowledge of knowledge, the core logics, the methodologies. In a user's case, this should relate to the core value of the final app the user wants to build and how to use all the above three kinds of knowledge when building and running the app.

### 3.2 Processing of 4 types of knowledge:

When processing a chunk, there should be 4 knowledge extracting agent working separately, extracting different types of SKUs from chunks. Each SKU should be saved in a separate folder, with a 'header.md' in it stating the name, the classification, the total character count and a concise description of the SKU. The extraction should be carried out following MECE (Mutually Exclusive Collectively Exhaustive) principle.

- **Factual Knowledge Extracting Agent**: this agent should extract, re-structure or clone the original factual data/file. The output should be dataframe in JSON or factual knowledge written in Markdown.

- **Relational Knowledge Extracting Agent**: this agent should model domain knowledge into graph or relational data. Because of the nature of relational knowledge, this agent works entirely in the logic of "read next chunk, update knowledge base" and therefore each SKU should be short and concise. The output should at least contain a multi-level label tree in JSON format, and a glossary list. This agent has the freedom to create other Markdown/JSON formats of relational knowledge if necessary.

- **Procedural Knowledge Extracting Agent**: this agent should program procedural knowledge into workflows based on LLM prompts and Python, and express clearly in a Skill.md. The workflow itself can be written in code snippet, natural language or some sort of Pseudocode that fits. One unit of procedural knowledge should have a similar structure to a Claude-Code-callable skill folder. This agent should refer to the instructions of Anthropic's offical skill 'skill-creator'.

- **Meta Knowledge Extracting Agent**: this agent should be based on a less is more, compression is intelligence kind of philosophy. This agent has two core outputs, a 'mapping.md' and a 'eureka.md', which will later be stored in the root path of app-building agent's workspace. The 'mapping.md' serves as the router of all SKUs, should list the path to all SKUs and describe clearly when to call what SKU when building the app. The 'eureka.md', on the other hand, is a very loose but creative notebook that records the surprises, the aha moments, the good ideas about what features could be added into the final app, or even the core design of the app.

### 3.3 Schema Design of SKUs：

We defined 4 classes of SKUs, from here down every schema could be freely defined by agents. Encourage them to be creative and agile, just keep it logical and consistent.

### 3.4 Postprocessing of SKUs：

Postprocessing of SKUs has these steps: bucketing, duplicates/contradiction recognition and handling, proofreading and confidence.

- **Bucketing**: For factual and procedural knowledge, this process will assign relative SKUs to a bucket. 
1. Relativity calculation can be considered from three aspects: literal similarity (straightforward, use some existing python library), label similarity (using the multi-level label tree from relational knowledge, and see the number of sharing labels), vector similarity (for procedural knowledge, using embedding model from SiliconFlow and calculate vector cosine). 
2. Factual and procedural knowledge have two different set of buckets, they do not compare with each other.
3. In the beginning, all SKUs of a class are in one bucket. From here the bucketing process is like peeling onion, where the process repeats until every bucket's size is within 'max bucket length'. It can be defined in .env and, for now, set to 50K.
4. Bucketing process should be an adaptive grouping algorithm, making sure that the most similar SKUs are put into one bucket, while avoiding all buckets being too small to actually do something.

- **Duplicates/contradiction recognition and handling**: In one bucket, this process calls LLM to identify any duplicates or contradiction among the SKUs. LLMs can delete or rewrite one or several SKUs, including combining several SKUs into one. There should also be a mechansim to adjust 'mapping.md' accordingly.

- **Proofreading and Confidence**: This is a independent and objective process that checks if SKUs have common-sense mistakes or directly contradict with original data, and just how good these SKUs are. This process is carried out in a simple RAG way, comparing each SKU with web search result and relevant original context. This process should call LLM to give confidence to each SKU based on a pre-defined universal standard ranging from 0 to 1. No operations to the SKUs should be carried out, as this step is purely for human observation after everything is done.

## 4. **SKUs2Workspace**

This module arranges and sets up the final workspace for coding agents to start building the app the user wants. The output workspace should contain these files:

- **SKUs**: Load the generated SKUs from module 3 to the workspace, put 'mapping.md' and 'eureka.md' in the root path of workspace.

- **spec.md**: This module has a multi-round chatbot in command line that chats with user and generates a clear spec.md for final app building. The chatbot should first read 'mapping.md' and ask the user to give some general instructions regarding the spec of the app. Then, the chatbot should draft a spec.md and print it to the user. The user can give more instructions to chatbot to modify 'spec.md' or enter '/confirm' to save the current version of spec.md as final. A max chat round can be set in .env and we set it to 5 for now.

- **README.md**: This serves as a brief initial prompt for the app-building agent. Basically something like 'spec.md is the app user wants to build, use mapping.md to navigate through SKUs folder and add some secret sauce from eureka.md'.

## 5. Pipeline summary

This is the summary after a full pipeline runs through. Design a good summary template to put in the specific data like initial file count, SKUs total count and each class count, and other important info and data.