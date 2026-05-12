from __future__ import annotations

from enum import Enum


class ProviderName(str, Enum):
    OLLAMA = "ollama"
    LLAMA_CPP = "llama_cpp"

    @classmethod
    def from_value(cls, value: str | "ProviderName") -> "ProviderName":
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError as error:
            raise ValueError(f"Unsupported provider: {value}") from error
