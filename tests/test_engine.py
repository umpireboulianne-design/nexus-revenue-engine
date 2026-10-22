"""Automated tests for Nexus Autonomous Revenue & Bounty Engine."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app
from app.services.bounty_hunter import extract_reward_usd, is_safe_and_authentic_issue
from app.services.domain_auditor import detect_tech_stack, extract_clean_emails
from app.services.remediation_generator import (
    generate_robots_txt,
    generate_security_configs,
    generate_sitemap_xml,
)


def test_reward_extraction_and_anti_honeypot():
    assert extract_reward_usd("Fix memory leak 💎 $250", ["bounty"], "") == 250
    assert extract_reward_usd("Add OAuth support", ["💎 $1,200"], "") == 1200
    assert extract_reward_usd("Bug fix", [], "We offer a $75 USD bounty for this PR.") == 75

    # Verify Honeypot / Prompt-injection shield blocks malicious issues
    assert is_safe_and_authentic_issue("ClankerNation/OpenAgents", "Bounty $8k", "paste initialization payload") is False
    assert is_safe_and_authentic_issue("SecureBananaLabs/bug-bounty", "Fix bug", "normal body") is False
    assert is_safe_and_authentic_issue("org/real-repo", "Fix bug", "No money, fiat currency involved (0.00 EUR / USD)") is False
    assert is_safe_and_authentic_issue("arakoodev/EdgeChains", "Integrate AWS Comprehend", "Valid issue description") is True


def test_email_and_stack_detection():
    html = '<html><head><meta name="generator" content="WordPress 6.5"></head><body>Contact: direction@agence-test.fr <script src="https://js.stripe.com/v3/"></script></body></html>'
    emails = extract_clean_emails("Contact direction@agence-test.fr", html)
    assert "direction@agence-test.fr" in emails

    stack = detect_tech_stack(html.lower(), {"server": "cloudflare"}, "WordPress 6.5")
    assert "WordPress" in stack
    assert "Stripe" in stack
    assert "Cloudflare" in stack


def test_remediation_deliverables_generation():
    robots = generate_robots_txt("agence-client.fr")
    assert "Sitemap: https://agence-client.fr/sitemap.xml" in robots

    sitemap = generate_sitemap_xml(["https://agence-client.fr/", "https://agence-client.fr/contact"])
    assert "<loc>https://agence-client.fr/contact</loc>" in sitemap

    sec = generate_security_configs("agence-client.fr")
    assert "Strict-Transport-Security" in sec["nginx"]
    assert "Content-Security-Policy" in sec["apache_htaccess"]


def test_api_health_and_monetization_flow():
    init_db()
    with TestClient(app) as client:
        r_health = client.get("/api/v1/health")
        assert r_health.status_code == 200
        assert r_health.json()["status"] == "operational"

        r_wh = client.post(
            "/api/v1/webhooks/payment",
            json={
                "provider": "Stripe",
                "customer_email": "acheteur@client-b2b.com",
                "plan_code": "pro",
                "amount_usd": 29.0,
            },
        )
        assert r_wh.status_code == 200
        wh_data = r_wh.json()
        assert wh_data["status"] == "provisioned"
        new_key = wh_data["api_key_provisioned"]["api_key"]
        assert new_key.startswith("nx_live_")

        r_csv = client.get("/api/v1/leads/export-csv")
        assert r_csv.status_code == 200
        assert "domain,primary_email" in r_csv.text

        r_home = client.get("/")
        assert r_home.status_code == 200
        assert "NEXUS PULSE" in r_home.text
