"""Schemas for ontology assembly."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OntologyManifest(BaseModel):
    """Metadata about the assembled ontology."""

    created_at: datetime = Field(default_factory=datetime.now)
    source_skus_dir: str = ""
    ontology_dir: str = ""
    factual_count: int = 0
    procedural_count: int = 0
    has_relational: bool = False
    has_mapping: bool = False
    has_eureka: bool = False
    has_spec: bool = False
    has_readme: bool = False
    total_files_copied: int = 0
    paths_rewritten: int = 0


class ChatMessage(BaseModel):
    """A single message in the chatbot conversation."""

    role: str  # system, assistant, user
    content: str


class ChatSession(BaseModel):
    """Full chatbot session metadata."""

    started_at: datetime = Field(default_factory=datetime.now)
    messages: list[ChatMessage] = Field(default_factory=list)
    rounds_used: int = 0
    max_rounds: int = 5
    confirmed: bool = False
    spec_content: Optional[str] = None
