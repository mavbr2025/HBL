#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
from typing import Any

from mtm_hbl.gamma_connector import GammaClient


def _theme_label(theme: dict[str, Any]) -> str:
    for key in ("name", "title", "id"):
        value = theme.get(key)
        if value:
            return str(value)
    return str(theme)


async def main_async(limit: int) -> None:
    client = GammaClient(timeout_seconds=30)
    themes = await client.list_themes()
    print(f"Gamma connection OK. Themes visible: {len(themes)}")
    for theme in themes[:limit]:
        print(f"- {_theme_label(theme)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Gamma API connectivity.")
    parser.add_argument("--limit", type=int, default=8, help="Number of theme names to print.")
    args = parser.parse_args()
    asyncio.run(main_async(args.limit))


if __name__ == "__main__":
    main()
