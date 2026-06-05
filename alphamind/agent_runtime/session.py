"""Agent session data structures."""

from dataclasses import dataclass


@dataclass
class AgentSession:
    id: str
    user_id: str
    workspace_id: str
