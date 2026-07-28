"""Core data models"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class WorkspaceConfig(BaseModel):
    """Workspace configuration"""

    name: str
    slug: str
    description: str
    # Loaded from the workspace's system.md by WorkspaceManager, which
    # has always passed it to this constructor. Without the field
    # declared, pydantic silently dropped it and every read raised
    # AttributeError — declaring it is what makes system.md take effect.
    system_prompt: str = ""
    default_text_model: str = "gpt-4"
    default_image_model: str = "dall-e-3"
    default_tts_model: str = "tts-1"
    voice: str = "alloy"

    kb: Dict[str, Any] = {
        "roots": ["./knowledge"],
        "auto_ingest_extensions": [".md", ".txt", ".json"]
    }

    tools: Dict[str, Any] = {
        "enabled": ["kb_search", "file_read", "git"],
        "shell": {"allow_write": False, "allow_network": False}
    }

    prompting: Dict[str, Any] = {
        "include_workspace_system": True,
        "max_kb_chunks": 6,
        "max_recent_messages": 12
    }

    security: Dict[str, Any] = {
        "redact_env_vars": True,
        "require_confirmation_for": ["shell_write", "file_delete"]
    }

class Session(BaseModel):
    """Chat session"""

    id: str
    workspace_slug: str
    title: str
    created_at: datetime
    updated_at: datetime

class Message(BaseModel):
    """Chat message"""

    id: str
    session_id: str
    role: str  # user, assistant, system
    content: str
    created_at: datetime

class KBResult(BaseModel):
    """Knowledge base search result"""

    title: str
    content: str
    source: Optional[str] = None
    score: float = 0.0