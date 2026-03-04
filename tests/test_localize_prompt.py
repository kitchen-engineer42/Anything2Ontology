"""Tests for bilingual (en/zh) prompt support."""

import os
import re

import pytest


class TestPromptDictsHaveBothLanguages:
    """Verify every prompt dict has both 'en' and 'zh' keys."""

    def test_chunking_prompt(self):
        from markdown2chunks.chunkers.llm_chunker import CHUNKING_PROMPT

        assert "en" in CHUNKING_PROMPT
        assert "zh" in CHUNKING_PROMPT

    def test_factual_prompt(self):
        from chunks2skus.extractors.factual_extractor import FACTUAL_PROMPT

        assert "en" in FACTUAL_PROMPT
        assert "zh" in FACTUAL_PROMPT

    def test_relational_prompt(self):
        from chunks2skus.extractors.relational_extractor import RELATIONAL_PROMPT

        assert "en" in RELATIONAL_PROMPT
        assert "zh" in RELATIONAL_PROMPT

    def test_procedural_prompt(self):
        from chunks2skus.extractors.procedural_extractor import PROCEDURAL_PROMPT

        assert "en" in PROCEDURAL_PROMPT
        assert "zh" in PROCEDURAL_PROMPT

    def test_mapping_prompt(self):
        from chunks2skus.extractors.meta_extractor import MAPPING_PROMPT

        assert "en" in MAPPING_PROMPT
        assert "zh" in MAPPING_PROMPT

    def test_eureka_prompt(self):
        from chunks2skus.extractors.meta_extractor import EUREKA_PROMPT

        assert "en" in EUREKA_PROMPT
        assert "zh" in EUREKA_PROMPT

    def test_dedup_prompts(self):
        from chunks2skus.postprocessors.dedup import (
            TIER1_SCAN_PROMPT,
            TIER1_SYSTEM_PROMPT,
            TIER2_JUDGMENT_PROMPT,
            TIER2_SYSTEM_PROMPT,
        )

        for prompt_dict in [TIER1_SCAN_PROMPT, TIER1_SYSTEM_PROMPT, TIER2_JUDGMENT_PROMPT, TIER2_SYSTEM_PROMPT]:
            assert "en" in prompt_dict
            assert "zh" in prompt_dict

    def test_proofreading_prompts(self):
        from chunks2skus.postprocessors.proofreading import (
            CONFIDENCE_PROMPT,
            CONFIDENCE_SYSTEM_PROMPT,
        )

        assert "en" in CONFIDENCE_PROMPT
        assert "zh" in CONFIDENCE_PROMPT
        assert "en" in CONFIDENCE_SYSTEM_PROMPT
        assert "zh" in CONFIDENCE_SYSTEM_PROMPT

    def test_chatbot_prompts(self):
        from skus2ontology.chatbot import FINALIZE_PROMPT, SYSTEM_PROMPT_TEMPLATE

        assert "en" in SYSTEM_PROMPT_TEMPLATE
        assert "zh" in SYSTEM_PROMPT_TEMPLATE
        assert "en" in FINALIZE_PROMPT
        assert "zh" in FINALIZE_PROMPT

    def test_readme_template(self):
        from skus2ontology.readme_generator import README_TEMPLATE

        assert "en" in README_TEMPLATE
        assert "zh" in README_TEMPLATE


class TestPlaceholderParity:
    """Verify en and zh versions have the same format placeholders."""

    @staticmethod
    def _extract_placeholders(template: str) -> set[str]:
        """Extract {name} placeholders, ignoring {{ and }}."""
        # Remove escaped braces
        cleaned = template.replace("{{", "").replace("}}", "")
        return set(re.findall(r"\{(\w+)\}", cleaned))

    def test_factual_prompt_placeholders(self):
        from chunks2skus.extractors.factual_extractor import FACTUAL_PROMPT

        en_ph = self._extract_placeholders(FACTUAL_PROMPT["en"])
        zh_ph = self._extract_placeholders(FACTUAL_PROMPT["zh"])
        assert en_ph == zh_ph, f"Mismatch: en={en_ph}, zh={zh_ph}"

    def test_relational_prompt_placeholders(self):
        from chunks2skus.extractors.relational_extractor import RELATIONAL_PROMPT

        en_ph = self._extract_placeholders(RELATIONAL_PROMPT["en"])
        zh_ph = self._extract_placeholders(RELATIONAL_PROMPT["zh"])
        assert en_ph == zh_ph, f"Mismatch: en={en_ph}, zh={zh_ph}"

    def test_procedural_prompt_placeholders(self):
        from chunks2skus.extractors.procedural_extractor import PROCEDURAL_PROMPT

        en_ph = self._extract_placeholders(PROCEDURAL_PROMPT["en"])
        zh_ph = self._extract_placeholders(PROCEDURAL_PROMPT["zh"])
        assert en_ph == zh_ph, f"Mismatch: en={en_ph}, zh={zh_ph}"

    def test_chunking_prompt_placeholders(self):
        from markdown2chunks.chunkers.llm_chunker import CHUNKING_PROMPT

        en_ph = self._extract_placeholders(CHUNKING_PROMPT["en"])
        zh_ph = self._extract_placeholders(CHUNKING_PROMPT["zh"])
        assert en_ph == zh_ph, f"Mismatch: en={en_ph}, zh={zh_ph}"

    def test_mapping_prompt_placeholders(self):
        from chunks2skus.extractors.meta_extractor import MAPPING_PROMPT

        en_ph = self._extract_placeholders(MAPPING_PROMPT["en"])
        zh_ph = self._extract_placeholders(MAPPING_PROMPT["zh"])
        assert en_ph == zh_ph, f"Mismatch: en={en_ph}, zh={zh_ph}"

    def test_eureka_prompt_placeholders(self):
        from chunks2skus.extractors.meta_extractor import EUREKA_PROMPT

        en_ph = self._extract_placeholders(EUREKA_PROMPT["en"])
        zh_ph = self._extract_placeholders(EUREKA_PROMPT["zh"])
        assert en_ph == zh_ph, f"Mismatch: en={en_ph}, zh={zh_ph}"

    def test_dedup_tier1_placeholders(self):
        from chunks2skus.postprocessors.dedup import TIER1_SCAN_PROMPT

        en_ph = self._extract_placeholders(TIER1_SCAN_PROMPT["en"])
        zh_ph = self._extract_placeholders(TIER1_SCAN_PROMPT["zh"])
        assert en_ph == zh_ph, f"Mismatch: en={en_ph}, zh={zh_ph}"

    def test_dedup_tier2_placeholders(self):
        from chunks2skus.postprocessors.dedup import TIER2_JUDGMENT_PROMPT

        en_ph = self._extract_placeholders(TIER2_JUDGMENT_PROMPT["en"])
        zh_ph = self._extract_placeholders(TIER2_JUDGMENT_PROMPT["zh"])
        assert en_ph == zh_ph, f"Mismatch: en={en_ph}, zh={zh_ph}"

    def test_confidence_prompt_placeholders(self):
        from chunks2skus.postprocessors.proofreading import CONFIDENCE_PROMPT

        en_ph = self._extract_placeholders(CONFIDENCE_PROMPT["en"])
        zh_ph = self._extract_placeholders(CONFIDENCE_PROMPT["zh"])
        assert en_ph == zh_ph, f"Mismatch: en={en_ph}, zh={zh_ph}"

    def test_chatbot_system_prompt_placeholders(self):
        from skus2ontology.chatbot import SYSTEM_PROMPT_TEMPLATE

        en_ph = self._extract_placeholders(SYSTEM_PROMPT_TEMPLATE["en"])
        zh_ph = self._extract_placeholders(SYSTEM_PROMPT_TEMPLATE["zh"])
        assert en_ph == zh_ph, f"Mismatch: en={en_ph}, zh={zh_ph}"

    def test_readme_template_placeholders(self):
        from skus2ontology.readme_generator import README_TEMPLATE

        en_ph = self._extract_placeholders(README_TEMPLATE["en"])
        zh_ph = self._extract_placeholders(README_TEMPLATE["zh"])
        assert en_ph == zh_ph, f"Mismatch: en={en_ph}, zh={zh_ph}"


class TestLanguageConfigDefault:
    """Verify that language defaults to 'en' in all modules."""

    def test_module1_default(self):
        from anything2markdown.config import Settings

        s = Settings(siliconflow_api_key="test")
        assert s.language == "en"

    def test_module2_default(self):
        from markdown2chunks.config import Settings

        s = Settings(siliconflow_api_key="test")
        assert s.language == "en"

    def test_module3_default(self):
        from chunks2skus.config import Settings

        s = Settings(siliconflow_api_key="test")
        assert s.language == "en"

    def test_module4_default(self):
        from skus2ontology.config import Settings

        s = Settings(siliconflow_api_key="test")
        assert s.language == "en"

    def test_module3_accepts_zh(self):
        from chunks2skus.config import Settings

        s = Settings(siliconflow_api_key="test", language="zh")
        assert s.language == "zh"
