from __future__ import annotations

import argparse
import asyncio
import json

from app.config import load_settings
from app.logging_config import configure_logging
from app.service import RagService


async def _run(args: argparse.Namespace) -> None:
    settings = load_settings(args.config)
    configure_logging(settings.app.log_level)
    service = RagService(settings)

    if args.command == "rescan":
        result = await service.rescan_documents()
        print(result.model_dump_json(indent=2))
        return

    if args.command == "ask":
        response = await service.answer_question(
            args.question,
            top_k=args.top_k,
            metadata_filter=json.loads(args.metadata_filter) if args.metadata_filter else None,
            use_cache=not args.no_cache,
        )
        print(response.model_dump_json(indent=2))
        return

    raise ValueError(f"Unsupported command: {args.command}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local RAG CLI")
    parser.add_argument("--config", default="config/config.yaml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    rescan = subparsers.add_parser("rescan", help="Reindex documents")
    rescan.set_defaults(command="rescan")

    ask = subparsers.add_parser("ask", help="Ask a question")
    ask.add_argument("question")
    ask.add_argument("--top-k", type=int, default=None)
    ask.add_argument("--metadata-filter", default=None)
    ask.add_argument("--no-cache", action="store_true")
    ask.set_defaults(command="ask")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
