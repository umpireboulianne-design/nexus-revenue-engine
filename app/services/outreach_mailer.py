"""Engine 5: Automated B2B Outreach Mailer (SMTP) & Campaign CSV Exporter."""
from __future__ import annotations

import csv
import io
import os
import smtplib
from email.message import EmailMessage
from typing import Any

from app.config import settings
from app.database import get_dashboard_metrics


def generate_leads_csv() -> str:
    """Export all audited B2B leads, extracted emails, report links, and personalized cold pitches to CSV."""
    metrics = get_dashboard_metrics()
    leads = metrics["recent_leads"]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "domain",
            "primary_email",
            "all_emails",
            "overall_score",
            "seo_score",
            "security_score",
            "tech_stack",
            "estimated_fee_usd",
            "cold_pitch_subject",
            "cold_pitch_body",
        ]
    )

    for lead in leads:
        emails = lead.get("emails") or []
        primary = emails[0] if emails else ""
        writer.writerow(
            [
                lead["domain"],
                primary,
                "; ".join(emails),
                lead["overall_score"],
                lead["seo_score"],
                lead["security_score"],
                ", ".join(lead.get("tech_stack") or []),
                lead["estimated_deal_value_usd"],
                lead["cold_pitch_subject"],
                lead["cold_pitch_body"],
            ]
        )
    return output.getvalue()


def send_cold_pitch_smtp(
    to_email: str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    """Send a personalized B2B audit outreach email via SMTP if credentials are configured in environment."""
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")

    if not smtp_host or not smtp_user or not smtp_pass:
        return {
            "sent": False,
            "mode": "simulation_ready",
            "message": (
                "Identifiants SMTP non configurés dans .env (SMTP_HOST, SMTP_USER, SMTP_PASSWORD). "
                "L'email est prêt dans le presse-papiers et dans l'export CSV."
            ),
            "to": to_email,
            "subject": subject,
        }

    msg = EmailMessage()
    msg["From"] = f"{settings.owner_name} <{smtp_user}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)

    return {
        "sent": True,
        "mode": "live_smtp",
        "to": to_email,
        "subject": subject,
    }
