"""Step 2: Interactive chatbot for generating spec.md."""

import re
from pathlib import Path

import click
import structlog

from skus2ontology.config import settings
from skus2ontology.schemas.ontology import ChatMessage, ChatSession
from skus2ontology.utils.llm_client import call_llm_chat

logger = structlog.get_logger(__name__)

# Max characters from mapping.md to include in compressed summary
MAPPING_SUMMARY_MAX_CHARS = 30000
# Max characters from eureka.md to include
EUREKA_SNIPPET_MAX_CHARS = 5000

SYSTEM_PROMPT_TEMPLATE = {
    "en": """You are a product specification assistant helping a user design an application.

You have access to a comprehensive knowledge base of Standard Knowledge Units (SKUs) organized into factual data, procedural skills, and relational knowledge. Your job is to:

1. Interview the user about their application goals, target users, and key features
2. Draft a spec.md document based on their answers
3. Iterate on the spec based on user feedback
4. Finalize the spec when the user is satisfied

AVAILABLE KNOWLEDGE BASE:
{mapping_summary}

CREATIVE IDEAS FROM KNOWLEDGE BASE:
{eureka_snippet}

RULES:
- Reference SKUs by ontology-relative paths (e.g., skus/factual/sku_012, skus/procedural/skill_005)
- When drafting the spec, wrap it in a ```markdown code block
- The user types /confirm to finalize the current spec
- Be concise in your questions — ask 2-3 focused questions at a time
- The spec should include: App name, Overview, Target users, Core features (with SKU references), Technical notes, and MVP scope""",

    "zh": """你是一个产品规格助手，帮助用户设计应用程序。

你可以访问一个由标准知识单元（SKU）组成的综合知识库，包含事实数据、程序技能和关系知识。你的任务是：

1. 询问用户的应用目标、目标用户和关键功能
2. 根据用户回答起草 spec.md 文档
3. 根据用户反馈迭代规格
4. 用户满意后定稿

可用知识库：
{mapping_summary}

知识库中的创意：
{eureka_snippet}

规则：
- 使用本体相对路径引用SKU（如 skus/factual/sku_012、skus/procedural/skill_005）
- 起草规格时，用 ```markdown 代码块包裹
- 用户输入 /confirm 来确认当前规格
- 提问要简洁——每次问2-3个针对性问题
- 规格应包含：应用名称、概述、目标用户、核心功能（附SKU引用）、技术说明、MVP范围""",
}

FINALIZE_PROMPT = {
    "en": """The user has confirmed the spec. Please output the FINAL, clean version of spec.md.

Output ONLY the spec content inside a ```markdown code block. No extra commentary.
Include all sections discussed. Make sure all SKU references use ontology-relative paths (skus/factual/..., skus/procedural/..., etc.).""",

    "zh": """用户已确认规格。请输出最终、整洁的 spec.md 版本。

仅在 ```markdown 代码块内输出规格内容。不要额外评论。
包含所有讨论过的章节。确保所有SKU引用使用本体相对路径（skus/factual/...、skus/procedural/... 等）。""",
}

UI_MESSAGES = {
    "en": {
        "finalizing": "\nFinalizing spec...",
        "spec_saved": "\nspec.md saved to {path}",
        "max_rounds": "\nMax rounds ({rounds}) reached. Auto-finalizing...",
        "remaining": "  ({remaining} round remaining — type /confirm to finalize)",
        "error_llm": "Error: Failed to get LLM response. Check your API key.",
        "error_response": "Error: Failed to get LLM response.",
        "chat_ended": "\nChat ended by user.",
    },
    "zh": {
        "finalizing": "\n正在生成最终规格...",
        "spec_saved": "\nspec.md 已保存至 {path}",
        "max_rounds": "\n已达最大轮次（{rounds}）。自动生成最终规格...",
        "remaining": "  （剩余 {remaining} 轮——输入 /confirm 确认规格）",
        "error_llm": "错误：无法获取LLM响应。请检查API密钥。",
        "error_response": "错误：无法获取LLM响应。",
        "chat_ended": "\n用户结束对话。",
    },
}


def _compress_mapping(content: str) -> str:
    """
    Compress mapping.md by keeping section headers, SKU paths, and descriptions.
    Strips verbose "When to use" text to save tokens.
    """
    lines = content.split("\n")
    compressed = []

    for line in lines:
        stripped = line.strip()
        # Keep headers
        if stripped.startswith("#"):
            compressed.append(line)
        # Keep SKU path lines (### skus/factual/...)
        elif stripped.startswith("### "):
            compressed.append(line)
        # Keep description lines
        elif stripped.startswith("**Description:**"):
            compressed.append(line)
        # Skip "When to use" and blank lines between entries
        elif stripped == "---":
            compressed.append(line)

    result = "\n".join(compressed)
    if len(result) > MAPPING_SUMMARY_MAX_CHARS:
        result = result[:MAPPING_SUMMARY_MAX_CHARS] + "\n... (truncated)"
    return result


def _extract_spec(response: str) -> str:
    """
    Extract spec content from LLM response.

    Priority:
    1. ```markdown code block
    2. Largest ``` code block
    3. Full response if it starts with #
    """
    # Try ```markdown block first
    markdown_pattern = re.compile(r"```markdown\s*\n(.*?)```", re.DOTALL)
    match = markdown_pattern.search(response)
    if match:
        return match.group(1).strip()

    # Try largest ``` block
    code_blocks = re.findall(r"```(?:\w*)\s*\n(.*?)```", response, re.DOTALL)
    if code_blocks:
        return max(code_blocks, key=len).strip()

    # If response starts with #, treat as spec
    if response.strip().startswith("#"):
        return response.strip()

    return response.strip()


class SpecChatbot:
    """Interactive chatbot that generates spec.md through conversation."""

    def __init__(self, ontology_dir: Path):
        self.ontology_dir = Path(ontology_dir).resolve()
        self.max_rounds = settings.max_chat_rounds
        self.session = ChatSession(max_rounds=self.max_rounds)
        self.lang = settings.language
        self.ui = UI_MESSAGES[self.lang]

    def run(self) -> str:
        """
        Run the interactive chatbot loop.

        Returns:
            The final spec content.
        """
        logger.info("Starting spec chatbot", max_rounds=self.max_rounds)

        # Build context
        system_prompt = self._build_system_prompt()
        self.session.messages.append(ChatMessage(role="system", content=system_prompt))

        # Get initial greeting from LLM
        messages_for_api = [{"role": m.role, "content": m.content} for m in self.session.messages]
        greeting = call_llm_chat(messages_for_api)

        if not greeting:
            click.echo(self.ui["error_llm"])
            return ""

        self.session.messages.append(ChatMessage(role="assistant", content=greeting))
        click.echo(f"\nAssistant: {greeting}\n")

        # Chat loop
        while self.session.rounds_used < self.max_rounds:
            # Get user input
            try:
                user_input = click.prompt("You", type=str)
            except (click.Abort, EOFError, KeyboardInterrupt):
                click.echo(self.ui["chat_ended"])
                break

            if not user_input.strip():
                continue

            # Check for /confirm
            if user_input.strip().lower() == "/confirm":
                self.session.confirmed = True
                click.echo(self.ui["finalizing"])
                spec = self._finalize()
                if spec:
                    self.session.spec_content = spec
                    self._save_spec(spec)
                    click.echo(self.ui["spec_saved"].format(path=self.ontology_dir / "spec.md"))
                return spec or ""

            # Add user message and increment round
            self.session.messages.append(ChatMessage(role="user", content=user_input))
            self.session.rounds_used += 1

            remaining = self.max_rounds - self.session.rounds_used
            if remaining <= 1:
                click.echo(self.ui["remaining"].format(remaining=remaining))

            # Get LLM response
            messages_for_api = [
                {"role": m.role, "content": m.content} for m in self.session.messages
            ]
            response = call_llm_chat(messages_for_api)

            if not response:
                click.echo(self.ui["error_response"])
                continue

            self.session.messages.append(ChatMessage(role="assistant", content=response))
            click.echo(f"\nAssistant: {response}\n")

        # Max rounds reached — auto-finalize
        if not self.session.confirmed:
            click.echo(self.ui["max_rounds"].format(rounds=self.max_rounds))
            spec = self._finalize()
            if spec:
                self.session.spec_content = spec
                self._save_spec(spec)
                click.echo(self.ui["spec_saved"].format(path=self.ontology_dir / "spec.md"))
            return spec or ""

        return self.session.spec_content or ""

    def _build_system_prompt(self) -> str:
        """Build system prompt with compressed mapping and eureka snippet."""
        mapping_summary = ""
        eureka_snippet = ""

        mapping_path = self.ontology_dir / "mapping.md"
        if mapping_path.exists():
            content = mapping_path.read_text(encoding="utf-8")
            mapping_summary = _compress_mapping(content)
            logger.info(
                "Loaded mapping.md",
                original_chars=len(content),
                compressed_chars=len(mapping_summary),
            )

        eureka_path = self.ontology_dir / "eureka.md"
        if eureka_path.exists():
            content = eureka_path.read_text(encoding="utf-8")
            eureka_snippet = content[:EUREKA_SNIPPET_MAX_CHARS]
            if len(content) > EUREKA_SNIPPET_MAX_CHARS:
                eureka_snippet += "\n... (truncated)"
            logger.info("Loaded eureka.md", chars=len(eureka_snippet))

        return SYSTEM_PROMPT_TEMPLATE[self.lang].format(
            mapping_summary=mapping_summary or "(no mapping available)",
            eureka_snippet=eureka_snippet or "(no eureka notes available)",
        )

    def _finalize(self) -> str | None:
        """Send finalize prompt and extract clean spec."""
        self.session.messages.append(
            ChatMessage(role="user", content=FINALIZE_PROMPT[self.lang])
        )

        messages_for_api = [
            {"role": m.role, "content": m.content} for m in self.session.messages
        ]
        response = call_llm_chat(messages_for_api)

        if not response:
            logger.error("Failed to get final spec from LLM")
            return None

        self.session.messages.append(ChatMessage(role="assistant", content=response))
        return _extract_spec(response)

    def _save_spec(self, content: str) -> None:
        """Save spec.md to ontology."""
        spec_path = self.ontology_dir / "spec.md"
        spec_path.write_text(content, encoding="utf-8")
        logger.info("Saved spec.md", path=str(spec_path), chars=len(content))

    def get_session(self) -> ChatSession:
        """Return the current chat session for logging."""
        return self.session
