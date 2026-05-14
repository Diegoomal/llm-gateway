import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class ProviderConcurrencyLimiter:
    def __init__(
        self,
        default_limit: int,
        provider_limits: dict[str, int] | None = None,
    ):
        self.default_limit = max(1, default_limit)
        self.provider_limits = provider_limits or {}
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    @asynccontextmanager
    async def limit(self, provider: str) -> AsyncIterator[None]:
        semaphore = self._semaphore_for(provider)
        await semaphore.acquire()
        try:
            yield
        finally:
            semaphore.release()

    def _semaphore_for(self, provider: str) -> asyncio.Semaphore:
        if provider not in self._semaphores:
            limit = max(1, self.provider_limits.get(provider, self.default_limit))
            self._semaphores[provider] = asyncio.Semaphore(limit)
        return self._semaphores[provider]
