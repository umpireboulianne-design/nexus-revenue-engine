"""Pure-API GitHub Fork, Branch, Commit & Pull Request Submitter (no git CLI required).

Automatically loads GITHUB_TOKEN from .env (or ~/.env) and submits both completed
Algora Escrow Verified bounty PRs on arakoodev/EdgeChains:
  1. Issue #290 ($50 USD) — AWS Comprehend PII Redaction Observable Utility
  2. Issue #273 ($30 USD) — Qdrant Vector Database Support in JS/TS SDK
"""
from __future__ import annotations

import base64
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")
load_dotenv(Path.home() / ".env")

UPSTREAM_OWNER = "arakoodev"
UPSTREAM_REPO = "EdgeChains"
BASE_BRANCH = "ts"


def upsert_file_on_github(
    client: httpx.Client,
    owner: str,
    repo: str,
    branch: str,
    repo_path: str,
    content_str: str,
    commit_message: str,
) -> None:
    """Create or update a file on a GitHub branch via the REST Contents API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{repo_path}"
    existing = client.get(url, params={"ref": branch})
    sha = existing.json().get("sha") if existing.status_code == 200 else None

    payload = {
        "message": commit_message,
        "content": base64.b64encode(content_str.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    resp = client.put(url, json=payload)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Erreur commit sur {repo_path} ({resp.status_code}): {resp.text[:300]}")
    print(f"  [+] Fichier commité sur GitHub : {repo_path}")


def ensure_fork_and_base_sha(client: httpx.Client, username: str) -> str:
    print(f"[*] Création / vérification du fork de {UPSTREAM_OWNER}/{UPSTREAM_REPO}...")
    r_fork = client.post(f"https://api.github.com/repos/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/forks")
    if r_fork.status_code not in (200, 202):
        raise RuntimeError(f"Impossible de forker le dépôt ({r_fork.status_code}): {r_fork.text[:200]}")

    for _ in range(12):
        r_ref = client.get(f"https://api.github.com/repos/{username}/{UPSTREAM_REPO}/git/ref/heads/{BASE_BRANCH}")
        if r_ref.status_code == 200:
            return r_ref.json()["object"]["sha"]
        time.sleep(2)

    r_up_ref = client.get(
        f"https://api.github.com/repos/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/git/ref/heads/{BASE_BRANCH}"
    )
    return r_up_ref.json()["object"]["sha"]


def submit_bounty_290(client: httpx.Client, username: str, base_sha: str) -> None:
    branch = "feat/aws-comprehend-pii-redaction-290"
    bdir = ROOT_DIR / "bounties_ready" / "edgechains_290_aws_comprehend"
    print(f"\n=== [1/2] Préparation de la Prime #290 (50 $ USD — AWS Comprehend Redaction) ===")
    client.post(
        f"https://api.github.com/repos/{username}/{UPSTREAM_REPO}/git/refs",
        json={"ref": f"refs/heads/{branch}", "sha": base_sha},
    )

    upsert_file_on_github(
        client,
        username,
        UPSTREAM_REPO,
        branch,
        "JS/edgechains/arakoodev/src/ai/src/lib/comprehend/comprehendRedactor.ts",
        (bdir / "comprehendRedactor.ts").read_text(encoding="utf-8"),
        "feat(ai): add ComprehendRedactor observable utility (#290)",
    )
    upsert_file_on_github(
        client,
        username,
        UPSTREAM_REPO,
        branch,
        "JS/edgechains/arakoodev/src/ai/src/tests/comprehendRedactor.test.ts",
        (bdir / "comprehendRedactor.test.ts").read_text(encoding="utf-8"),
        "test(ai): add unit tests for ComprehendRedactor and endpoint chaining (#290)",
    )
    upsert_file_on_github(
        client,
        username,
        UPSTREAM_REPO,
        branch,
        "JS/edgechains/examples/comprehend-redaction/index.ts",
        (bdir / "example_comprehend_redaction.ts").read_text(encoding="utf-8"),
        "docs(examples): add working example for AWS Comprehend PII redaction (#290)",
    )

    r_idx = client.get(
        f"https://api.github.com/repos/{username}/{UPSTREAM_REPO}/contents/JS/edgechains/arakoodev/src/ai/src/index.ts",
        params={"ref": branch},
    )
    if r_idx.status_code == 200:
        current_index = base64.b64decode(r_idx.json()["content"]).decode("utf-8")
        export_line = 'export { ComprehendRedactor } from "./lib/comprehend/comprehendRedactor.js";\n'
        if "ComprehendRedactor" not in current_index:
            upsert_file_on_github(
                client,
                username,
                UPSTREAM_REPO,
                branch,
                "JS/edgechains/arakoodev/src/ai/src/index.ts",
                current_index.rstrip() + "\n" + export_line,
                "feat(ai): export ComprehendRedactor from @arakoodev/edgechains.js/ai (#290)",
            )

    pr_body = (
        "/claim #290\n"
        "Fixes #290\n\n"
        "### Summary\n"
        "Integrates AWS Comprehend (`DetectPiiEntitiesCommand`) into the `@arakoodev/edgechains.js` TypeScript SDK "
        "as an RxJS Observable utility (`ComprehendRedactor`) that chains directly with existing AI Endpoint classes "
        "(`OpenAI`, `GeminiAI`, `LlamaAI`) to redact sensitive PII before prompts are sent to LLMs."
    )
    r_pr = client.post(
        f"https://api.github.com/repos/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/pulls",
        json={
            "title": "feat(ai): integrate AWS Comprehend PII redaction observable utility (#290)",
            "head": f"{username}:{branch}",
            "base": BASE_BRANCH,
            "body": pr_body,
        },
    )
    if r_pr.status_code in (200, 201):
        print(f"[SUCCÈS #290] Pull Request ouverte (50 $ USD) : {r_pr.json()['html_url']}")
    else:
        print(f"[!] Statut PR #290 ({r_pr.status_code}): {r_pr.text[:300]}")


def submit_bounty_273(client: httpx.Client, username: str, base_sha: str) -> None:
    branch = "feat/qdrant-vector-db-support-273"
    bdir = ROOT_DIR / "bounties_ready" / "edgechains_273_qdrant"
    print(f"\n=== [2/2] Préparation de la Prime #273 (30 $ USD — Qdrant Vector DB SDK) ===")
    client.post(
        f"https://api.github.com/repos/{username}/{UPSTREAM_REPO}/git/refs",
        json={"ref": f"refs/heads/{branch}", "sha": base_sha},
    )

    upsert_file_on_github(
        client,
        username,
        UPSTREAM_REPO,
        branch,
        "JS/edgechains/arakoodev/src/vector-db/src/lib/qdrant/qdrant.ts",
        (bdir / "qdrant.ts").read_text(encoding="utf-8"),
        "feat(vector-db): add Qdrant vector database client support (#273)",
    )
    upsert_file_on_github(
        client,
        username,
        UPSTREAM_REPO,
        branch,
        "JS/edgechains/arakoodev/src/vector-db/src/tests/qdrant/qdrant.test.ts",
        (bdir / "qdrant.test.ts").read_text(encoding="utf-8"),
        "test(vector-db): add unit tests for Qdrant vector database client (#273)",
    )

    r_idx = client.get(
        f"https://api.github.com/repos/{username}/{UPSTREAM_REPO}/contents/JS/edgechains/arakoodev/src/vector-db/src/index.ts",
        params={"ref": branch},
    )
    if r_idx.status_code == 200:
        current_index = base64.b64decode(r_idx.json()["content"]).decode("utf-8")
        export_line = 'export { Qdrant } from "./lib/qdrant/qdrant.js";\n'
        if "Qdrant" not in current_index:
            upsert_file_on_github(
                client,
                username,
                UPSTREAM_REPO,
                branch,
                "JS/edgechains/arakoodev/src/vector-db/src/index.ts",
                current_index.rstrip() + "\n" + export_line,
                "feat(vector-db): export Qdrant client from @arakoodev/edgechains.js/vector-db (#273)",
            )

    pr_body = (
        "/claim #273\n"
        "Fixes #273\n\n"
        "### Summary\n"
        "Adds `Qdrant` vector database support (`createCollection`, `insertVectorData`, `searchVectorData`, `deleteById`) "
        "with automatic retry handling and unit tests to `@arakoodev/edgechains.js/vector-db`."
    )
    r_pr = client.post(
        f"https://api.github.com/repos/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/pulls",
        json={
            "title": "feat(vector-db): add Qdrant vector database support in JS/TS SDK (#273)",
            "head": f"{username}:{branch}",
            "base": BASE_BRANCH,
            "body": pr_body,
        },
    )
    if r_pr.status_code in (200, 201):
        print(f"[SUCCÈS #273] Pull Request ouverte (30 $ USD) : {r_pr.json()['html_url']}")
    else:
        print(f"[!] Statut PR #273 ({r_pr.status_code}): {r_pr.text[:300]}")


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("[-] GITHUB_TOKEN manquant dans .env.")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Nexus-Bounty-Submitter/1.0",
    }

    with httpx.Client(headers=headers, timeout=25.0) as client:
        r_user = client.get("https://api.github.com/user")
        if r_user.status_code != 200:
            raise RuntimeError(f"Token GitHub invalide ({r_user.status_code}): {r_user.text[:200]}")
        username = r_user.json()["login"]
        print(f"[*] Authentifié sur GitHub en tant que : @{username}")

        base_sha = ensure_fork_and_base_sha(client, username)
        submit_bounty_290(client, username, base_sha)
        submit_bounty_273(client, username, base_sha)


if __name__ == "__main__":
    main()
