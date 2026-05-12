from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from domain.provider_name import ProviderName


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LLMRequest:
    request_id: str = field(default_factory=lambda: str(uuid4()))
    model: str | None = None
    provider: ProviderName | None = None
    messages: list[LLMMessage] = field(default_factory=list)
    input: str | list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def chat(
        cls,
        messages: list[dict[str, str]] | list[LLMMessage],
        model: str | None = None,
        provider: str | ProviderName | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "LLMRequest":
        return cls(
            model=model,
            provider=ProviderName.from_value(provider) if provider else None,
            messages=[
                message
                if isinstance(message, LLMMessage)
                else LLMMessage(
                    role=message["role"],
                    content=message["content"],
                )
                for message in messages
            ],
            metadata=metadata or {},
        )

    @classmethod
    def embedding(
        cls,
        input: str | list[str],
        model: str | None = None,
        provider: str | ProviderName | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "LLMRequest":
        return cls(
            model=model,
            provider=ProviderName.from_value(provider) if provider else None,
            input=input,
            metadata=metadata or {},
        )
