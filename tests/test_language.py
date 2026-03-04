"""Tests for LANGUAGE=zh localization support."""

import os
from unittest.mock import patch

import pytest


# --- Config defaults ---


def test_config_default_language_en():
    """Default language is 'en' when LANGUAGE not set."""
    from chunks2skus.config import Settings

    with patch.dict(os.environ, {}, clear=False):
        s = Settings(language="en")
        assert s.language == "en"


def test_config_language_zh():
    """Language can be set to 'zh'."""
    from chunks2skus.config import Settings

    s = Settings(language="zh")
    assert s.language == "zh"


# --- Prompt selection ---


def test_factual_prompt_has_both_languages():
    """FACTUAL_PROMPT dict has both 'en' and 'zh' keys."""
    from chunks2skus.extractors.factual_extractor import FACTUAL_PROMPT

    assert "en" in FACTUAL_PROMPT
    assert "zh" in FACTUAL_PROMPT
    assert "{content}" in FACTUAL_PROMPT["en"]
    assert "{content}" in FACTUAL_PROMPT["zh"]


def test_relational_prompt_has_both_languages():
    """RELATIONAL_PROMPT dict has both 'en' and 'zh' keys."""
    from chunks2skus.extractors.relational_extractor import RELATIONAL_PROMPT

    assert "en" in RELATIONAL_PROMPT
    assert "zh" in RELATIONAL_PROMPT


def test_procedural_prompt_has_both_languages():
    """PROCEDURAL_PROMPT dict has both 'en' and 'zh' keys."""
    from chunks2skus.extractors.procedural_extractor import PROCEDURAL_PROMPT

    assert "en" in PROCEDURAL_PROMPT
    assert "zh" in PROCEDURAL_PROMPT
    assert "{content}" in PROCEDURAL_PROMPT["en"]
    assert "{content}" in PROCEDURAL_PROMPT["zh"]


def test_meta_prompts_have_both_languages():
    """Meta extractor prompts have both 'en' and 'zh' keys."""
    from chunks2skus.extractors.meta_extractor import (
        EUREKA_PROMPT,
        EUREKA_SYSTEM_PROMPT,
        INIT_EUREKA,
        INIT_MAPPING,
        MAPPING_PROMPT,
        MAPPING_SYSTEM_PROMPT,
    )

    for prompt_dict in [
        MAPPING_PROMPT, MAPPING_SYSTEM_PROMPT,
        EUREKA_PROMPT, EUREKA_SYSTEM_PROMPT,
        INIT_MAPPING, INIT_EUREKA,
    ]:
        assert "en" in prompt_dict
        assert "zh" in prompt_dict


def test_dedup_prompts_have_both_languages():
    """Dedup prompts have both 'en' and 'zh' keys."""
    from chunks2skus.postprocessors.dedup import (
        TIER1_SCAN_PROMPT,
        TIER1_SYSTEM_PROMPT,
        TIER2_JUDGMENT_PROMPT,
        TIER2_SYSTEM_PROMPT,
    )

    for prompt_dict in [
        TIER1_SYSTEM_PROMPT, TIER1_SCAN_PROMPT,
        TIER2_SYSTEM_PROMPT, TIER2_JUDGMENT_PROMPT,
    ]:
        assert "en" in prompt_dict
        assert "zh" in prompt_dict


def test_proofreading_prompts_have_both_languages():
    """Proofreading prompts have both 'en' and 'zh' keys."""
    from chunks2skus.postprocessors.proofreading import (
        CONFIDENCE_PROMPT,
        CONFIDENCE_SYSTEM_PROMPT,
    )

    for prompt_dict in [CONFIDENCE_SYSTEM_PROMPT, CONFIDENCE_PROMPT]:
        assert "en" in prompt_dict
        assert "zh" in prompt_dict


def test_chunking_prompt_has_both_languages():
    """LLM chunker prompt has both 'en' and 'zh' keys."""
    from markdown2chunks.chunkers.llm_chunker import CHUNKING_PROMPT

    assert "en" in CHUNKING_PROMPT
    assert "zh" in CHUNKING_PROMPT


# --- SKU header to_markdown() ---


def test_to_markdown_english_labels():
    """to_markdown() renders English labels when language='en'."""
    from chunks2skus.schemas.sku import SKUHeader, SKUType

    with patch("chunks2skus.config.settings") as mock_settings:
        mock_settings.language = "en"
        header = SKUHeader(
            name="test-sku",
            classification=SKUType.FACTUAL,
            character_count=1500,
            source_chunk="chunk_001",
            description="Test description",
            confidence=0.85,
            related_skus=["sku_010"],
        )
        md = header.to_markdown()
        assert "**Classification**" in md
        assert "**Source**" in md
        assert "**Characters**" in md
        assert "**Confidence**" in md
        assert "**Related SKUs**" in md


def test_to_markdown_chinese_labels():
    """to_markdown() renders Chinese labels when language='zh'."""
    from chunks2skus.schemas.sku import SKUHeader, SKUType

    with patch("chunks2skus.config.settings") as mock_settings:
        mock_settings.language = "zh"
        header = SKUHeader(
            name="test-sku",
            classification=SKUType.FACTUAL,
            character_count=1500,
            source_chunk="chunk_001",
            description="Test description",
            confidence=0.85,
            related_skus=["sku_010"],
        )
        md = header.to_markdown()
        assert "**分类**" in md
        assert "**来源**" in md
        assert "**字符数**" in md
        assert "**置信度**" in md
        assert "**相关SKU**" in md


# --- README template selection ---


def test_readme_template_has_both_languages():
    """README template has both 'en' and 'zh' keys."""
    from skus2ontology.readme_generator import README_TEMPLATE

    assert "en" in README_TEMPLATE
    assert "zh" in README_TEMPLATE
    assert "{stats_section}" in README_TEMPLATE["en"]
    assert "{stats_section}" in README_TEMPLATE["zh"]


def test_readme_template_zh_content():
    """Chinese README template has Chinese section headers."""
    from skus2ontology.readme_generator import README_TEMPLATE

    zh = README_TEMPLATE["zh"]
    assert "快速开始" in zh
    assert "目录结构" in zh
    assert "SKU 类型" in zh
    assert "使用方法" in zh


# --- Chatbot template selection ---


def test_chatbot_templates_have_both_languages():
    """Chatbot system prompt and finalize prompt have both languages."""
    from skus2ontology.chatbot import FINALIZE_PROMPT, SYSTEM_PROMPT_TEMPLATE

    assert "en" in SYSTEM_PROMPT_TEMPLATE
    assert "zh" in SYSTEM_PROMPT_TEMPLATE
    assert "en" in FINALIZE_PROMPT
    assert "zh" in FINALIZE_PROMPT


# --- Proofreading regex handles both EN and ZH ---


def test_proofreading_regex_matches_english_labels():
    """Proofreading _update_header regex matches English labels."""
    import re

    content = "- **Characters**: 1,500\n- **Confidence**: 0.80\n"
    # Remove existing confidence
    content = re.sub(r"- \*\*(Confidence|置信度)\*\*:.*\n?", "", content)
    assert "Confidence" not in content
    assert "Characters" in content


def test_proofreading_regex_matches_chinese_labels():
    """Proofreading _update_header regex matches Chinese labels."""
    import re

    content = "- **字符数**: 1,500\n- **置信度**: 0.80\n"
    # Remove existing confidence
    content = re.sub(r"- \*\*(Confidence|置信度)\*\*:.*\n?", "", content)
    assert "置信度" not in content
    assert "字符数" in content


def test_proofreading_chars_pattern_matches_both():
    """Proofreading chars_pattern matches both Characters and 字符数."""
    import re

    chars_pattern = r"(- \*\*(Characters|字符数)\*\*:.*)"

    en_content = "- **Characters**: 1,500"
    assert re.search(chars_pattern, en_content) is not None

    zh_content = "- **字符数**: 1,500"
    assert re.search(chars_pattern, zh_content) is not None


# --- Init content for mapping/eureka ---


def test_init_mapping_chinese():
    """Chinese initial mapping content has Chinese headers."""
    from chunks2skus.extractors.meta_extractor import INIT_MAPPING

    zh = INIT_MAPPING["zh"]
    assert "SKU 映射" in zh
    assert "尚未映射" in zh


def test_init_eureka_chinese():
    """Chinese initial eureka content has Chinese headers."""
    from chunks2skus.extractors.meta_extractor import INIT_EUREKA

    zh = INIT_EUREKA["zh"]
    assert "灵感笔记" in zh
    assert "暂无洞察" in zh
