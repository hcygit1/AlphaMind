"""Future skill protocol."""

from __future__ import annotations

from typing import Protocol


class AgentSkill(Protocol):
    name: str
