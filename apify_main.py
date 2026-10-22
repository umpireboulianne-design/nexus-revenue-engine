"""Apify Store Actor entrypoint for Pay-Per-Result monetization on Apify Marketplace."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from app.services.domain_auditor import audit_domain


async def run_apify_actor() -> None:
    """Read input domains from Apify key-value store (or local input.json) and output structured B2B dataset items."""
    input_path = Path(os.environ.get("APIFY_INPUT_PATH", "storage/key_value_stores/default/INPUT.json"))
    domains = ["python.org"]
    if input_path.exists():
        data = json.loads(input_path.read_text(encoding="utf-8"))
        domains = data.get("domains") or domains

    results = []
    for d in domains[:50]:
        try:
            report = await audit_domain(d)
            results.append(report)
        except Exception as exc:
            results.append({"domain": d, "error": str(exc)})

    output_dir = Path("storage/datasets/default")
    output_dir.mkdir(parents=True, exist_ok=True)
    for idx, item in enumerate(results, 1):
        (output_dir / f"{idx:06d}.json").write_text(json.dumps(item, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[Apify Actor] {len(results)} domain intelligence reports generated successfully.")


if __name__ == "__main__":
    asyncio.run(run_apify_actor())
