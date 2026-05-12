import argparse
import asyncio

from application.ports.for_managing_llm_requests import (
    ForManagingLLMRequests,
)
from configurator import configure_llm_gateway
from domain.llm_request import LLMRequest


async def run(gateway: ForManagingLLMRequests) -> None:
    parser = argparse.ArgumentParser(prog="llm-gateway")
    subparsers = parser.add_subparsers(dest="command", required=True)

    chat_parser = subparsers.add_parser("chat")
    chat_parser.add_argument("prompt")
    chat_parser.add_argument("--model")
    chat_parser.add_argument("--provider")

    embeddings_parser = subparsers.add_parser("embeddings")
    embeddings_parser.add_argument("input")
    embeddings_parser.add_argument("--model")
    embeddings_parser.add_argument("--provider")

    subparsers.add_parser("models")

    args = parser.parse_args()

    if args.command == "chat":
        response = await gateway.chat_completion(
            LLMRequest.chat(
                messages=[{"role": "user", "content": args.prompt}],
                model=args.model,
                provider=args.provider,
            )
        )
        print(response.content or response.error)
        return

    if args.command == "embeddings":
        response = await gateway.embeddings(
            LLMRequest.embedding(
                input=args.input,
                model=args.model,
                provider=args.provider,
            )
        )
        print(response.embeddings or response.error)
        return

    models = await gateway.list_models()
    for provider, provider_models in models.items():
        print(f"{provider}: {', '.join(provider_models)}")


if __name__ == "__main__":
    asyncio.run(run(configure_llm_gateway()))
