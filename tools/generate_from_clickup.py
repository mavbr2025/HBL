from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from mtm_hbl.clickup_connector.client import ClickUpClient
from mtm_hbl.clickup_connector.oauth import LocalTokenStore
from mtm_hbl.clickup_hbl_generator import generate_hbl_from_clickup
from mtm_hbl.config import AppConfig, get_settings


async def main_async() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a draft or issued HBL package from a pasted ClickUp task link."
    )
    parser.add_argument("task_ref", help="ClickUp task URL or task ID.")
    parser.add_argument("--mode", choices=["auto", "draft", "issue"], default="auto")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--logo-path", default="assets/mtm_logix_logo.png")
    parser.add_argument("--attach-to-clickup", action="store_true")
    parser.add_argument("--post-comment", action="store_true")
    parser.add_argument("--verification-base-url", default="")
    parser.add_argument("--bucket", default="")
    parser.add_argument("--table", default="")
    parser.add_argument("--region", default="")
    parser.add_argument("--issued-by", default="Andrea Piedad Velasquez Castellon")
    args = parser.parse_args()

    settings = get_settings()
    token = LocalTokenStore(settings.token_store_path).load()
    if token is None:
        raise SystemExit("ClickUp is not connected. Open /auth/clickup/start in the local API first.")

    result = await generate_hbl_from_clickup(
        task_ref=args.task_ref,
        client=ClickUpClient(settings, token.access_token),
        settings=settings,
        app_config=AppConfig(settings.config_dir),
        mode=args.mode,
        output_dir=Path(args.output_dir) if args.output_dir else None,
        logo_path=Path(args.logo_path) if args.logo_path else None,
        attach_to_clickup=args.attach_to_clickup,
        post_comment=args.post_comment,
        verification_base_url=args.verification_base_url,
        bucket=args.bucket,
        table=args.table,
        region=args.region,
        issued_by=args.issued_by,
    )
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
