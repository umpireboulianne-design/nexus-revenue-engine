"""SQLite persistence layer for API keys, B2B audited leads, bounties, and revenue tracking."""
from __future__ import annotations

import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from app.config import settings


def get_db_path() -> Path:
    return Path(settings.database_path)


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Initialize SQLite tables and seed a default demo/owner API key if empty."""
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_value TEXT UNIQUE NOT NULL,
                customer_email TEXT NOT NULL,
                plan TEXT NOT NULL DEFAULT 'pro',
                monthly_quota INTEGER NOT NULL DEFAULT 5000,
                calls_used INTEGER NOT NULL DEFAULT 0,
                mrr_usd REAL NOT NULL DEFAULT 0.0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audited_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                url TEXT NOT NULL,
                overall_score INTEGER NOT NULL,
                seo_score INTEGER NOT NULL,
                security_score INTEGER NOT NULL,
                emails_json TEXT NOT NULL,
                tech_stack_json TEXT NOT NULL,
                missing_critical_json TEXT NOT NULL,
                cold_pitch_subject TEXT NOT NULL,
                cold_pitch_body TEXT NOT NULL,
                estimated_deal_value_usd INTEGER NOT NULL DEFAULT 250,
                report_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bounties (
                issue_id INTEGER PRIMARY KEY,
                repo_full_name TEXT NOT NULL,
                title TEXT NOT NULL,
                html_url TEXT NOT NULL,
                reward_usd INTEGER NOT NULL,
                source_platform TEXT NOT NULL,
                language TEXT NOT NULL,
                comments_count INTEGER NOT NULL,
                roi_score REAL NOT NULL,
                antigravity_prompt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                discovered_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS revenue_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                event_type TEXT NOT NULL,
                amount_usd REAL NOT NULL,
                customer_or_repo TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        # Ensure a default owner master key exists for immediate testing
        cur = conn.execute("SELECT COUNT(*) as cnt FROM api_keys")
        if cur.fetchone()["cnt"] == 0:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO api_keys (key_value, customer_email, plan, monthly_quota, calls_used, mrr_usd, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                ("nx_live_owner_master_key_2026", settings.owner_email, "agency", 100000, 0, 0.0, now),
            )


def create_api_key(
    customer_email: str,
    plan: str = "pro",
    monthly_quota: int = 2500,
    mrr_usd: float = 29.0,
) -> dict[str, Any]:
    """Generate and persist a new customer API key."""
    key_value = f"nx_live_{secrets.token_urlsafe(20)}"
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO api_keys (key_value, customer_email, plan, monthly_quota, calls_used, mrr_usd, is_active, created_at)
            VALUES (?, ?, ?, ?, 0, ?, 1, ?)
            """,
            (key_value, customer_email, plan, monthly_quota, mrr_usd, now),
        )
    return {
        "api_key": key_value,
        "customer_email": customer_email,
        "plan": plan,
        "monthly_quota": monthly_quota,
        "mrr_usd": mrr_usd,
        "created_at": now,
    }


def validate_and_increment_key(key_value: str) -> dict[str, Any] | None:
    """Validate an API key, check quota, increment usage count, and return key metadata."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM api_keys WHERE key_value = ? AND is_active = 1",
            (key_value,),
        ).fetchone()
        if not row:
            return None
        if row["calls_used"] >= row["monthly_quota"]:
            return {"error": "quota_exceeded", **dict(row)}
        conn.execute(
            "UPDATE api_keys SET calls_used = calls_used + 1 WHERE id = ?",
            (row["id"],),
        )
        updated = dict(row)
        updated["calls_used"] += 1
        return updated


def save_audited_lead(report: dict[str, Any]) -> int:
    """Persist an audited domain and its B2B outreach pitch into SQLite."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO audited_leads (
                domain, url, overall_score, seo_score, security_score,
                emails_json, tech_stack_json, missing_critical_json,
                cold_pitch_subject, cold_pitch_body, estimated_deal_value_usd,
                report_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report["domain"],
                report["final_url"],
                report["scores"]["overall"],
                report["scores"]["seo"],
                report["scores"]["security"],
                json.dumps(report["contacts"]["emails"]),
                json.dumps(report["tech_stack"]),
                json.dumps(report["sales_intelligence"]["critical_weaknesses"]),
                report["sales_intelligence"]["cold_email_pitch"]["subject"],
                report["sales_intelligence"]["cold_email_pitch"]["body"],
                report["sales_intelligence"]["estimated_fix_fee_usd"],
                json.dumps(report),
                now,
            ),
        )
        return int(cur.lastrowid or 0)


def save_bounties(bounties: list[dict[str, Any]]) -> None:
    """Upsert discovered cash bounties into SQLite."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        for b in bounties:
            conn.execute(
                """
                INSERT INTO bounties (
                    issue_id, repo_full_name, title, html_url, reward_usd,
                    source_platform, language, comments_count, roi_score,
                    antigravity_prompt, created_at, discovered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(issue_id) DO UPDATE SET
                    reward_usd = excluded.reward_usd,
                    comments_count = excluded.comments_count,
                    roi_score = excluded.roi_score,
                    discovered_at = excluded.discovered_at
                """,
                (
                    b["issue_id"],
                    b["repo_full_name"],
                    b["title"],
                    b["html_url"],
                    b["reward_usd"],
                    b["source_platform"],
                    b.get("language") or "Multi-Stack",
                    b["comments_count"],
                    b["roi_score"],
                    b["antigravity_prompt"],
                    b["created_at"],
                    now,
                ),
            )


def record_revenue_event(
    source: str,
    event_type: str,
    amount_usd: float,
    customer_or_repo: str,
    details: str = "",
) -> dict[str, Any]:
    """Record a revenue transaction (subscription, one-off audit, or bounty claim)."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO revenue_events (source, event_type, amount_usd, customer_or_repo, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source, event_type, amount_usd, customer_or_repo, details, now),
        )
    return {
        "source": source,
        "event_type": event_type,
        "amount_usd": amount_usd,
        "customer_or_repo": customer_or_repo,
        "details": details,
        "created_at": now,
    }


def get_dashboard_metrics() -> dict[str, Any]:
    """Aggregate KPIs for the Revenue Command Center dashboard."""
    with get_db() as conn:
        keys_rows = [dict(r) for r in conn.execute("SELECT * FROM api_keys ORDER BY id DESC").fetchall()]
        leads_rows = [
            {
                "id": r["id"],
                "domain": r["domain"],
                "url": r["url"],
                "overall_score": r["overall_score"],
                "seo_score": r["seo_score"],
                "security_score": r["security_score"],
                "emails": json.loads(r["emails_json"]),
                "tech_stack": json.loads(r["tech_stack_json"]),
                "missing_critical": json.loads(r["missing_critical_json"]),
                "cold_pitch_subject": r["cold_pitch_subject"],
                "cold_pitch_body": r["cold_pitch_body"],
                "estimated_deal_value_usd": r["estimated_deal_value_usd"],
                "created_at": r["created_at"],
            }
            for r in conn.execute("SELECT * FROM audited_leads ORDER BY id DESC LIMIT 50").fetchall()
        ]
        bounties_rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM bounties ORDER BY roi_score DESC, reward_usd DESC LIMIT 50"
            ).fetchall()
        ]
        rev_rows = [
            dict(r) for r in conn.execute("SELECT * FROM revenue_events ORDER BY id DESC LIMIT 50").fetchall()
        ]

        mrr_total = sum(r["mrr_usd"] for r in keys_rows if r["is_active"])
        realized_total = sum(r["amount_usd"] for r in rev_rows)
        bounty_pool_usd = sum(r["reward_usd"] for r in bounties_rows)
        lead_pipeline_usd = sum(r["estimated_deal_value_usd"] for r in leads_rows)
        total_api_calls = sum(r["calls_used"] for r in keys_rows)

        return {
            "kpis": {
                "active_mrr_usd": round(mrr_total, 2),
                "realized_revenue_usd": round(realized_total, 2),
                "available_bounties_pool_usd": bounty_pool_usd,
                "bounties_count": len(bounties_rows),
                "lead_pipeline_value_usd": lead_pipeline_usd,
                "audited_leads_count": len(leads_rows),
                "total_api_calls_served": total_api_calls,
            },
            "api_keys": keys_rows,
            "recent_leads": leads_rows,
            "top_bounties": bounties_rows,
            "revenue_events": rev_rows,
        }
