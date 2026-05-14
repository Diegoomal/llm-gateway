from dataclasses import dataclass

from domain.llm_response import LLMResponse


class IdempotencyConflict(Exception):
    pass


class IdempotencyInProgress(Exception):
    pass


@dataclass(frozen=True)
class IdempotencyReservation:
    status: str
    response: LLMResponse | None = None

    @property
    def is_reserved(self) -> bool:
        return self.status == "reserved"

    @property
    def is_replay(self) -> bool:
        return self.status == "replayed" and self.response is not None
