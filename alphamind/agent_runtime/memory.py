"""Short-term memory interface for Phase 1."""


class ShortTermMemory:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
