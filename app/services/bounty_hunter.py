"""Engine 2: Live Open-Source Cash Bounty Radar with Anti-Honeypot Shield & Algora Escrow Verification."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings

DOLLAR_PATTERNS = [
    re.compile(r"💎\s*\$\s*([0-9]{1,2}(?:,[0-9]{3})+|[0-9]{2,5})\b", re.I),
    re.compile(r"\$\s*([0-9]{1,2}(?:,[0-9]{3})+|[0-9]{2,5})\s*(?:usd|bounty|reward)?\b", re.I),
    re.compile(r"\b([0-9]{2,5})\s*(?:usd|dollars|\$)\s*(?:bounty|reward)?\b", re.I),
]

PLATFORM_SIGNATURES = [
    ("Algora Escrow", ("algora.io", "💎")),
    ("Opire", ("opire.dev", "opire")),
    ("Polar", ("polar.sh",)),
    ("GitHub Bounty", ("bounty", "reward", "cash")),
]

# Repositories & accounts verified as honeypots, fake benchmarks, discontinued programs, or mirror bots
BLOCKED_REPOS_AND_USERS = {
    "clankernation",
    "securebananalabs",
    "unsafelabs",
    "xaviercallens",
    "devpool-directory",
    "freedom-winds",
    "dev-kp-eloper",
    "ariahendrawan-sudo",
    "habibdxb01",
    "zhangjiayang6835-cyber",
    "coollabsio",  # Discontinued Algora program per maintainer notice
}

HONEYPOT_PHRASES = (
    "initialization payload",
    "pre-conversation",
    "system prompt",
    "no money, fiat currency",
    "0.00 eur / usd",
    "bounty alert:",
    "bounty scout",
    "open bounties right now",
)


def is_safe_and_authentic_issue(repo_full_name: str, title: str, body: str) -> bool:
    """Filter out prompt-injection honeypots, symbolic 0-USD tokens, and mirror bot issues."""
    repo_lower = repo_full_name.lower()
    owner = repo_lower.split("/")[0] if "/" in repo_lower else repo_lower
    if owner in BLOCKED_REPOS_AND_USERS or repo_lower in BLOCKED_REPOS_AND_USERS:
        return False

    combined = f"{title}\n{body or ''}".lower()
    if any(phrase in combined for phrase in HONEYPOT_PHRASES):
        return False
    return True


def extract_reward_usd(title: str, labels: list[str], body: str) -> int:
    """Extract the cash bounty value in USD from issue title, labels, and body."""
    label_str = " | ".join(labels)
    for source in (f"{title} {label_str}", (body or "")[:2500]):
        candidates: list[int] = []
        for pattern in DOLLAR_PATTERNS:
            for match in pattern.findall(source):
                clean_num = match.replace(",", "").strip()
                if clean_num.isdigit():
                    val = int(clean_num)
                    if 20 <= val <= 15000 and val not in (2020, 2021, 2022, 2023, 2024, 2025, 2026):
                        candidates.append(val)
        if candidates:
            return max(candidates)
    return 0


def detect_bounty_platform(title: str, labels: list[str], body: str) -> str:
    """Identify which bounty platform is escrow-backing the reward."""
    combined = f"{title} {' '.join(labels)} {(body or '')[:1500]}".lower()
    for platform_name, keywords in PLATFORM_SIGNATURES:
        if any(k.lower() in combined for k in keywords):
            return platform_name
    return "GitHub Direct Bounty"


def infer_stack_from_text(repo_name: str, title: str, labels: list[str], body: str) -> str:
    """Infer likely programming language or stack from issue metadata."""
    blob = f"{repo_name} {title} {' '.join(labels)} {(body or '')[:800]}".lower()
    mapping = [
        ("TypeScript / React / Vue", ("typescript", "nextjs", "next.js", "react", "vue", "svelte", "tsx")),
        ("Python", ("python", "fastapi", "django", "pytest", "pydantic", "langchain")),
        ("Rust", ("rust", "cargo", "crate", "tokio")),
        ("Go", ("golang", "go ", "goroutine")),
        ("JavaScript / Node", ("javascript", "nodejs", "node.js", "npm")),
        ("Scala / JVM", ("scala", "zio", "java", "gradle", "kotlin")),
        ("C++ / C", ("c++", "cmake", "clang")),
    ]
    for label, tokens in mapping:
        if any(t in blob for t in tokens):
            return label
    return "Open-Source Stack"


def build_antigravity_execution_prompt(
    repo_full_name: str,
    issue_number: int,
    title: str,
    html_url: str,
    reward_usd: int,
    platform: str,
) -> str:
    """Generate a ready-to-paste prompt for Antigravity to autonomously solve the bounty."""
    return (
        f"Je veux que tu résolves cette prime Open-Source vérifiée ({reward_usd} $ sur {platform}) :\n"
        f"- Issue : {html_url} ({title})\n"
        f"- Dépôt : https://github.com/{repo_full_name} (Issue #{issue_number})\n\n"
        f"Exécute les étapes suivantes de bout en bout :\n"
        f"1. Clone le dépôt `https://github.com/{repo_full_name}.git` dans notre dossier scratch et lis les détails complets de l'issue #{issue_number}.\n"
        f"2. Identifie les fichiers concernés, implémente le correctif exact ou la fonctionnalité demandée en respectant le style du projet.\n"
        f"3. Écris et exécute les tests unitaires pour prouver que la solution fonctionne à 100 %.\n"
        f"4. Prépare la branche Git, le commit propre et le texte exact de la Pull Request (avec `/claim #{issue_number}`) pour encaisser la prime de {reward_usd} $."
    )


async def fetch_live_bounties(
    min_reward_usd: int = 25,
    max_results: int = 30,
    query_filter: str = "",
) -> list[dict[str, Any]]:
    """Query GitHub Search API for verified, honeypot-filtered open issues offering cash bounties."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Nexus-Revenue-Engine-Bounty-Radar/1.0",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    exclusions = "archived:false -user:SecureBananaLabs -user:ClankerNation -user:UnsafeLabs -user:xaviercallens -user:coollabsio"
    queries = [
        f'is:issue is:open commenter:algora-pbc[bot] NOT "has been awarded" in:comments {exclusions} sort:updated-desc',
        f'is:issue is:open "💎" "$" {exclusions} sort:updated-desc',
        f'is:issue is:open label:bounty "$" {exclusions} sort:updated-desc',
    ]
    if query_filter.strip():
        queries.insert(0, f'is:issue is:open "{query_filter.strip()}" "$" {exclusions} sort:updated-desc')

    discovered_by_id: dict[int, dict[str, Any]] = {}

    async with httpx.AsyncClient(timeout=12.0) as client:
        for q_idx, q in enumerate(queries[:3]):
            try:
                resp = await client.get(
                    "https://api.github.com/search/issues",
                    params={"q": q, "per_page": 25},
                    headers=headers,
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                for item in data.get("items", []):
                    if "pull_request" in item:
                        continue
                    issue_id = int(item["id"])
                    if issue_id in discovered_by_id:
                        continue

                    repo_url = item.get("repository_url") or ""
                    repo_full_name = "/".join(repo_url.rstrip("/").split("/")[-2:]) if repo_url else "unknown/repo"
                    title = item.get("title") or ""
                    body = item.get("body") or ""

                    if not is_safe_and_authentic_issue(repo_full_name, title, body):
                        continue

                    labels = [lbl.get("name", "") for lbl in item.get("labels", []) if isinstance(lbl, dict)]
                    issue_number = int(item.get("number") or 0)
                    reward_usd = extract_reward_usd(title, labels, body)
                    platform = detect_bounty_platform(title, labels, body)

                    # For algora-pbc[bot] issues where the $ amount is inside the bot's comment, inspect comments
                    if reward_usd == 0 and q_idx == 0 and len(discovered_by_id) < 12:
                        c_resp = await client.get(
                            f"https://api.github.com/repos/{repo_full_name}/issues/{issue_number}/comments",
                            params={"per_page": 20},
                            headers=headers,
                        )
                        if c_resp.status_code == 200:
                            awarded = False
                            for c in c_resp.json():
                                u_login = c.get("user", {}).get("login", "").lower()
                                c_body = c.get("body", "")
                                if "algora" in u_login:
                                    if "has been awarded" in c_body or "bounty has been claimed" in c_body.lower():
                                        awarded = True
                                        break
                                    val = extract_reward_usd("", [], c_body)
                                    if val > reward_usd:
                                        reward_usd = val
                                        platform = "Algora Escrow Verified"
                            if awarded:
                                continue

                    if reward_usd < min_reward_usd:
                        continue

                    html_url = item.get("html_url") or ""
                    comments_count = int(item.get("comments") or 0)
                    created_at = item.get("created_at") or datetime.now(timezone.utc).isoformat()
                    language = infer_stack_from_text(repo_full_name, title, labels, body)

                    competition_multiplier = (
                        1.6 if comments_count <= 2 else (1.2 if comments_count <= 10 else 0.7)
                    )
                    if "Verified" in platform:
                        competition_multiplier *= 1.35
                    roi_score = round((reward_usd * competition_multiplier) / max(1.0, (comments_count * 0.15) + 1.0), 1)

                    prompt = build_antigravity_execution_prompt(
                        repo_full_name=repo_full_name,
                        issue_number=issue_number,
                        title=title,
                        html_url=html_url,
                        reward_usd=reward_usd,
                        platform=platform,
                    )

                    discovered_by_id[issue_id] = {
                        "issue_id": issue_id,
                        "issue_number": issue_number,
                        "repo_full_name": repo_full_name,
                        "title": title,
                        "html_url": html_url,
                        "reward_usd": reward_usd,
                        "source_platform": platform,
                        "language": language,
                        "comments_count": comments_count,
                        "roi_score": roi_score,
                        "antigravity_prompt": prompt,
                        "created_at": created_at,
                    }
            except Exception:
                continue

    results = sorted(
        discovered_by_id.values(),
        key=lambda x: (x["roi_score"], x["reward_usd"]),
        reverse=True,
    )
    return results[:max_results]
