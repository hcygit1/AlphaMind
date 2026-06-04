"""Registry for future multi-tool skills."""

from __future__ import annotations

from alphamind.agent_runtime.skills.base import AgentSkill


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, AgentSkill] = {}

    def register(self, skill: AgentSkill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> AgentSkill | None:
        return self._skills.get(name)
