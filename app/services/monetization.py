"""Engine 3: Autonomous Monetization, Webhook Provisioning (Stripe / LemonSqueezy), and White-Label HTML Reports."""
from __future__ import annotations

import hashlib
import hmac
from typing import Any

from app.config import settings
from app.database import create_api_key, record_revenue_event

PRICING_CATALOG: dict[str, dict[str, Any]] = {
    "audit_forfait": {
        "name": "Audit Complet + Plan de Remédiation (Montant Forfaitaire)",
        "type": "one_off",
        "price_usd": 49.0,
        "checkout_url": settings.checkout_url_audit_oneoff,
        "features": [
            "Audit complet SEO, Sécurité TLS/Headers & Stack Technique",
            "Rapport HTML/PDF Marque Blanche prêt à livrer au client",
            "Checklist de correction priorisée + Script de configuration serveur",
        ],
    },
    "pro_monthly": {
        "name": "Forfait API Pro (Revenu Récurrent SaaS)",
        "type": "subscription",
        "price_usd": 29.0,
        "monthly_quota": 5000,
        "checkout_url": settings.checkout_url_pro_monthly,
        "features": [
            "5 000 appels API / mois (Domain Intelligence & Lead Extractor)",
            "Extraction d'emails B2B et profils sociaux en temps réel",
            "Générateur automatique de Cold Emails personnalisés",
        ],
    },
    "agency_monthly": {
        "name": "Forfait Agence & Prospection Illimitée",
        "type": "subscription",
        "price_usd": 99.0,
        "monthly_quota": 50000,
        "checkout_url": settings.checkout_url_agency_monthly,
        "features": [
            "50 000 appels API / mois + Scanner par lot (Batch B2B Leads)",
            "Rapports d'audit en Marque Blanche (revendables 150 $–490 $ / client)",
            "Accès complet au Radar de Primes Open-Source (Bounty Hunter)",
        ],
    },
}


def verify_hmac_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify webhook HMAC-SHA256 signature when a signing secret is configured."""
    if not secret:
        return True
    computed = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature.strip())


def process_payment_webhook(
    provider: str,
    customer_email: str,
    plan_code: str,
    amount_usd: float,
) -> dict[str, Any]:
    """Automatically provision an API key and log revenue when a Stripe or LemonSqueezy payment succeeds."""
    plan_norm = plan_code.lower()
    if "agency" in plan_norm or amount_usd >= 80:
        quota = 50000
        plan_name = "agency"
        mrr = amount_usd
    elif "pro" in plan_norm or (20 <= amount_usd < 80 and "forfait" not in plan_norm):
        quota = 5000
        plan_name = "pro"
        mrr = amount_usd
    else:
        quota = 500
        plan_name = "audit_forfait"
        mrr = 0.0

    key_data = create_api_key(
        customer_email=customer_email,
        plan=plan_name,
        monthly_quota=quota,
        mrr_usd=mrr,
    )
    rev_event = record_revenue_event(
        source=provider,
        event_type=f"payment_{plan_name}",
        amount_usd=amount_usd,
        customer_or_repo=customer_email,
        details=f"Provisioned API key {key_data['api_key'][:14]}... ({quota} calls/mo)",
    )
    return {
        "status": "provisioned",
        "api_key_provisioned": key_data,
        "revenue_logged": rev_event,
    }


def render_whitelabel_audit_html(report: dict[str, Any]) -> str:
    """Render a clean, printable White-Label HTML Executive Audit Report that can be sold to B2B prospects."""
    domain = report["domain"]
    scores = report["scores"]
    seo = report["seo"]
    sec = report["security"]
    sales = report["sales_intelligence"]
    tech_badges = "".join(
        f'<span style="display:inline-block;background:#e0e7ff;color:#1e40af;padding:4px 10px;border-radius:999px;font-size:12px;margin:3px;font-weight:600;">{t}</span>'
        for t in (report["tech_stack"] or ["Standard Web Stack"])
    )
    seo_issues_html = "".join(f"<li style='margin-bottom:6px;color:#b91c1c;'>{iss}</li>" for iss in seo["issues"]) or (
        "<li style='color:#15803d;'>Aucune erreur SEO critique détectée.</li>"
    )
    missing_hdr_html = "".join(
        f"<li style='margin-bottom:6px;color:#b45309;'>En-tête manquant : <strong>{h}</strong></li>"
        for h in sec["missing_headers"]
    ) or "<li style='color:#15803d;'>Tous les en-têtes de sécurité principaux sont actifs.</li>"

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Rapport d'Audit Exécutif — {domain}</title>
<style>
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; color: #0f172a; background: #f8fafc; margin: 0; padding: 32px; }}
  .card {{ max-width: 860px; margin: 0 auto; background: #ffffff; border-radius: 16px; padding: 36px; box-shadow: 0 10px 25px rgba(15,23,42,0.06); }}
  .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #e2e8f0; padding-bottom: 20px; margin-bottom: 24px; }}
  .scores {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
  .score-box {{ background: #f1f5f9; padding: 16px; border-radius: 12px; text-align: center; }}
  .score-val {{ font-size: 30px; font-weight: 800; color: #1e293b; }}
  .score-lbl {{ font-size: 12px; text-transform: uppercase; color: #64748b; letter-spacing: 0.05em; }}
  h2 {{ font-size: 18px; color: #1e293b; margin-top: 24px; border-left: 4px solid #2563eb; padding-left: 10px; }}
  .footer {{ margin-top: 36px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 13px; color: #64748b; display:flex; justify-content:space-between; }}
  @media print {{ body {{ background: #fff; padding: 0; }} .card {{ box-shadow: none; }} }}
</style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div>
        <div style="font-size:12px;font-weight:700;color:#2563eb;text-transform:uppercase;">Audit Technique & Conformité B2B</div>
        <h1 style="margin:4px 0 0 0;font-size:26px;">{domain}</h1>
        <div style="font-size:13px;color:#64748b;">URL analysée : {report["final_url"]} • Temps de réponse : {report["performance"]["response_time_ms"]} ms</div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:13px;font-weight:600;">Préparé par {settings.owner_name}</div>
        <div style="font-size:12px;color:#64748b;">Date : {report["audited_at"][:10]}</div>
      </div>
    </div>

    <div class="scores">
      <div class="score-box"><div class="score-val">{scores["overall"]}/100</div><div class="score-lbl">Score Global</div></div>
      <div class="score-box"><div class="score-val">{scores["seo"]}/100</div><div class="score-lbl">SEO Technique</div></div>
      <div class="score-box"><div class="score-val">{scores["security"]}/100</div><div class="score-lbl">Sécurité & SSL</div></div>
      <div class="score-box"><div class="score-val">{scores["performance"]}/100</div><div class="score-lbl">Performance</div></div>
    </div>

    <h2>1. Technologies & Infrastructure Détectées</h2>
    <div>{tech_badges}</div>

    <h2>2. Diagnostic Référencement Naturel (SEO)</h2>
    <p style="font-size:14px;color:#334155;">
      <strong>Title :</strong> {seo["title"] or "Non défini"}<br>
      <strong>Meta Description :</strong> {seo["meta_description"] or "Non définie"}<br>
      <strong>Robots.txt :</strong> {"Présent" if seo["has_robots_txt"] else "Manquant"} •
      <strong>Sitemap.xml :</strong> {"Présent" if seo["has_sitemap_xml"] else "Manquant"} •
      <strong>Schema.org JSON-LD :</strong> {"Présent" if seo["has_json_ld_schema"] else "Manquant"}
    </p>
    <ul>{seo_issues_html}</ul>

    <h2>3. Diagnostic Sécurité & En-têtes HTTP</h2>
    <p style="font-size:14px;color:#334155;">
      <strong>Certificat SSL :</strong> {"Valide" if sec["ssl"].get("valid") else "Invalide / Non vérifié"}
      ({sec["ssl"].get("issuer", "N/A")})
    </p>
    <ul>{missing_hdr_html}</ul>

    <h2>4. Plan d'Action & Budget d'Intervention Recommandé</h2>
    <p style="font-size:14px;color:#334155;">
      Forfait de mise en conformité clé en main estimé : <strong>{sales["estimated_fix_fee_usd"]} $ USD</strong>.
      Contactez <strong>{settings.owner_email}</strong> pour planifier le déploiement des correctifs.
    </p>

    <div class="footer">
      <span>Généré par Nexus Pulse B2B Intelligence Engine</span>
      <span>Contact : {settings.owner_email}</span>
    </div>
  </div>
</body>
</html>"""
