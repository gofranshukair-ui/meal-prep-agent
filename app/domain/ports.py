from __future__ import annotations

from typing import Protocol


class AIClient(Protocol):
    def generate_text(
        self,
        prompt: str,
        max_output_tokens: int = 900,
        temperature: float = 0.3,
        request_id: str | None = None,
        operation_name: str | None = None,
    ) -> str:
        ...
