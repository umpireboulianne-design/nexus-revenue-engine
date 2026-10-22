"""FastAPI application for Nexus Pulse — B2B Intelligence API, Auto-Remediation, SaaS Portal & Live Bounty Radar."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.auth import verify_api_access
from app.config import settings
from app.database import (
    create_api_key,
    get_dashboard_metrics,
    init_db,
    record_revenue_event,
    save_audited_lead,
    save_bounties,
)
from app.services.bounty_hunter import fetch_live_bounties
from app.services.domain_auditor import audit_domain
from app.services.monetization import (
    PRICING_CATALOG,
    process_payment_webhook,
    render_whitelabel_audit_html,
    verify_hmac_signature,
)
from app.services.outreach_mailer import generate_leads_csv, send_cold_pitch_smtp
from app.services.remediation_generator import (
    build_full_remediation_pack,
    render_remediation_pack_html,
)

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API Commerciale d'Intelligence B2B (Audit SEO, Sécurité SSL/Headers, Détection de Stack Technologique, "
        "Extraction de Contacts, Générateur Automatique de Livrables de Remédiation & Prospection) + "
        "Radar Vérifié de Primes Open-Source (Algora Escrow / Cash Bounties)."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class AuditRequest(BaseModel):
    url: str = Field(..., description="Nom de domaine ou URL complète à auditer (ex: stripe.com ou https://shopify.com)")
    save_lead: bool = Field(default=True, description="Enregistrer dans le pipeline de prospection B2B")


class BatchAuditRequest(BaseModel):
    urls: list[str] = Field(..., description="Liste de domaines à scanner en parallèle (max 15 par lot)")


class CreateKeyRequest(BaseModel):
    customer_email: str = Field(..., description="Email du client")
    plan: str = Field(default="pro", description="Forfait (pro, agency, audit_forfait)")
    monthly_quota: int = Field(default=5000, description="Quota mensuel d'appels API")
    mrr_usd: float = Field(default=29.0, description="Revenu mensuel récurrent associé en USD")


class RecordRevenueRequest(BaseModel):
    source: str = Field(..., description="Source du revenu (ex: Algora Bounty, Client Direct, RapidAPI, Stripe)")
    event_type: str = Field(default="bounty_or_sale", description="Type d'encaissement")
    amount_usd: float = Field(..., description="Montant encaissé en USD")
    customer_or_repo: str = Field(..., description="Nom du client ou du dépôt GitHub")
    details: str = Field(default="", description="Notes ou référence")


class SendPitchRequest(BaseModel):
    to_email: str = Field(..., description="Email du prospect B2B")
    subject: str = Field(..., description="Objet de l'email")
    body: str = Field(..., description="Corps de l'email de prospection")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root_dashboard(request: Request):
    """Render the unified SaaS Landing Page & Autonomous Revenue Command Center."""
    metrics = get_dashboard_metrics()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.app_name,
            "metrics": metrics,
            "pricing": PRICING_CATALOG,
            "owner_email": settings.owner_email,
        },
    )


@app.get("/api/v1/health", tags=["System"])
async def health_check() -> dict[str, Any]:
    """Vérifie l'état de santé du serveur et des moteurs de revenus."""
    return {
        "status": "operational",
        "service": settings.app_name,
        "version": settings.app_version,
        "engines": {
            "b2b_domain_auditor": "ready",
            "auto_remediation_packager": "ready",
            "verified_bounty_radar": "ready",
            "monetization_webhooks": "ready",
        },
    }


@app.post("/api/v1/audit", tags=["Moteur 1 : B2B Domain Intelligence API"])
async def api_audit_domain_post(
    payload: AuditRequest,
    auth: dict[str, Any] = Depends(verify_api_access),
) -> dict[str, Any]:
    """Analyse complète d'un domaine : SEO, Sécurité SSL/Headers, Stack Technique, Emails B2B et Cold Email Pitch."""
    try:
        report = await audit_domain(payload.url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Impossible d'analyser la cible '{payload.url}': {exc}") from exc

    if payload.save_lead:
        lead_id = save_audited_lead(report)
        report["lead_id"] = lead_id
    report["auth_channel"] = auth["channel"]
    return report


@app.get("/api/v1/audit", tags=["Moteur 1 : B2B Domain Intelligence API"])
async def api_audit_domain_get(
    url: str = Query(..., description="Domaine ou URL à analyser (ex: news.ycombinator.com)"),
    save_lead: bool = Query(default=True, description="Sauvegarder dans le CRM de prospection"),
    auth: dict[str, Any] = Depends(verify_api_access),
) -> dict[str, Any]:
    """Endpoint GET compatible RapidAPI / Make / Zapier / n8n pour auditer un site web en 1 appel."""
    try:
        report = await audit_domain(url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Impossible d'analyser la cible '{url}': {exc}") from exc

    if save_lead:
        lead_id = save_audited_lead(report)
        report["lead_id"] = lead_id
    report["auth_channel"] = auth["channel"]
    return report


@app.post("/api/v1/audit/batch", tags=["Moteur 1 : B2B Domain Intelligence API"])
async def api_audit_batch(
    payload: BatchAuditRequest,
    auth: dict[str, Any] = Depends(verify_api_access),
) -> dict[str, Any]:
    """Scanne jusqu'à 15 domaines en parallèle pour identifier les prospects B2B à fort potentiel et générer leurs emails."""
    clean_urls = [u.strip() for u in payload.urls if u.strip()][:15]
    if not clean_urls:
        raise HTTPException(status_code=400, detail="Veuillez fournir au moins un domaine valide.")

    tasks = [audit_domain(u) for u in clean_urls]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    succeeded: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    total_pipeline_usd = 0

    for u, res in zip(clean_urls, raw_results):
        if isinstance(res, Exception):
            failed.append({"url": u, "error": str(res)})
        else:
            lead_id = save_audited_lead(res)
            res["lead_id"] = lead_id
            succeeded.append(res)
            total_pipeline_usd += int(res["sales_intelligence"]["estimated_fix_fee_usd"])

    return {
        "scanned_count": len(succeeded),
        "failed_count": len(failed),
        "total_estimated_pipeline_usd": total_pipeline_usd,
        "auth_channel": auth["channel"],
        "results": succeeded,
        "errors": failed,
    }


@app.get("/api/v1/audit/report-html", response_class=HTMLResponse, tags=["Moteur 1 : B2B Domain Intelligence API"])
async def api_audit_whitelabel_html(
    url: str = Query(..., description="Domaine à auditer pour générer le rapport client en Marque Blanche"),
):
    """Génère un rapport d'audit exécutif en HTML/PDF (Marque Blanche) prêt à être vendu 150 $–490 $ à un client B2B."""
    try:
        report = await audit_domain(url)
        save_audited_lead(report)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la génération du rapport: {exc}") from exc
    return HTMLResponse(content=render_whitelabel_audit_html(report))


@app.get("/api/v1/audit/remediation-pack", tags=["Moteur 1 : B2B Domain Intelligence API"])
async def api_audit_remediation_json(
    url: str = Query(..., description="Domaine pour lequel générer automatiquement tous les correctifs techniques"),
    auth: dict[str, Any] = Depends(verify_api_access),
) -> dict[str, Any]:
    """Génère automatiquement le Livrable Client Clé-en-Main (Configs Nginx/Apache/Caddy/Vercel, robots.txt, sitemap.xml, JSON-LD)."""
    try:
        report = await audit_domain(url)
        pack = await build_full_remediation_pack(report)
        pack["auth_channel"] = auth["channel"]
        return pack
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la génération du pack de remédiation: {exc}") from exc


@app.get("/api/v1/audit/remediation-html", response_class=HTMLResponse, tags=["Moteur 1 : B2B Domain Intelligence API"])
async def api_audit_remediation_html(
    url: str = Query(..., description="Domaine pour lequel afficher le Pack de Mise en Conformité Clé-en-Main"),
):
    """Affiche le Livrable Technique Complet prêt à remettre au client une fois son paiement forfaitaire effectué."""
    try:
        report = await audit_domain(url)
        pack = await build_full_remediation_pack(report)
        return HTMLResponse(content=render_remediation_pack_html(pack))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la génération du livrable: {exc}") from exc


@app.get("/api/v1/bounties/live", tags=["Moteur 2 : Chasseur de Primes Open-Source (Cash Bounties)"])
async def api_live_bounties(
    min_reward_usd: int = Query(default=25, ge=10, description="Montant minimum de la prime en USD"),
    query_filter: str = Query(default="", description="Filtre optionnel par langage ou mot-clé (ex: python, typescript)"),
) -> dict[str, Any]:
    """Scanne en temps réel GitHub / Algora Escrow (filtré anti-honeypot) pour extraire les issues rémunérées en dollars."""
    bounties = await fetch_live_bounties(min_reward_usd=min_reward_usd, query_filter=query_filter)
    if bounties:
        save_bounties(bounties)

    metrics = get_dashboard_metrics()
    active_list = bounties if bounties else metrics["top_bounties"]
    total_pool = sum(b["reward_usd"] for b in active_list)

    return {
        "count": len(active_list),
        "total_pool_usd": total_pool,
        "bounties": active_list,
    }


@app.get("/api/v1/leads/export-csv", tags=["Moteur 3 : Monétisation & Pilotage"])
async def api_export_leads_csv():
    """Exporte tous les prospects B2B audités avec leurs emails et Cold Pitches personnalisés au format CSV."""
    csv_data = generate_leads_csv()
    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="nexus_b2b_leads_campaign.csv"'},
    )


@app.post("/api/v1/leads/send-smtp", tags=["Moteur 3 : Monétisation & Pilotage"])
async def api_send_lead_smtp(payload: SendPitchRequest) -> dict[str, Any]:
    """Envoie automatiquement l'email d'audit B2B au prospect via SMTP."""
    return send_cold_pitch_smtp(
        to_email=payload.to_email,
        subject=payload.subject,
        body=payload.body,
    )


@app.get("/api/v1/dashboard/metrics", tags=["Moteur 3 : Monétisation & Pilotage"])
async def api_dashboard_metrics() -> dict[str, Any]:
    """Retourne tous les indicateurs financiers, le pipeline B2B, les clés API actives et les primes détectées."""
    return get_dashboard_metrics()


@app.post("/api/v1/keys/create", tags=["Moteur 3 : Monétisation & Pilotage"])
async def api_create_customer_key(payload: CreateKeyRequest) -> dict[str, Any]:
    """Crée une nouvelle clé API client (abonnement SaaS ou accès direct) et met à jour le MRR."""
    return create_api_key(
        customer_email=payload.customer_email,
        plan=payload.plan,
        monthly_quota=payload.monthly_quota,
        mrr_usd=payload.mrr_usd,
    )


@app.post("/api/v1/revenue/record", tags=["Moteur 3 : Monétisation & Pilotage"])
async def api_record_revenue(payload: RecordRevenueRequest) -> dict[str, Any]:
    """Enregistre un paiement forfaitaire encaissé (prime GitHub gagnée, vente d'audit B2B, paiement RapidAPI)."""
    return record_revenue_event(
        source=payload.source,
        event_type=payload.event_type,
        amount_usd=payload.amount_usd,
        customer_or_repo=payload.customer_or_repo,
        details=payload.details,
    )


@app.post("/api/v1/webhooks/payment", tags=["Moteur 3 : Monétisation & Pilotage"])
async def api_payment_webhook(
    request: Request,
    x_signature: str = Header(default="", alias="X-Signature"),
) -> dict[str, Any]:
    """Webhook universel (Stripe / LemonSqueezy) qui provisionne automatiquement une clé API dès qu'un client paie."""
    raw_body = await request.body()
    if settings.lemonsqueezy_webhook_secret:
        if not verify_hmac_signature(raw_body, x_signature, settings.lemonsqueezy_webhook_secret):
            raise HTTPException(status_code=401, detail="Signature webhook invalide.")

    try:
        data = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Payload JSON invalide") from exc

    provider = data.get("provider", "Stripe/LemonSqueezy")
    customer_email = (
        data.get("customer_email")
        or data.get("data", {}).get("object", {}).get("customer_details", {}).get("email")
        or data.get("data", {}).get("attributes", {}).get("user_email")
        or "client@acheteur-saas.com"
    )
    amount_usd = float(
        data.get("amount_usd")
        or (data.get("data", {}).get("object", {}).get("amount_total", 2900) / 100.0)
    )
    plan_code = data.get("plan_code") or data.get("metadata", {}).get("plan", "pro")

    return process_payment_webhook(
        provider=provider,
        customer_email=customer_email,
        plan_code=plan_code,
        amount_usd=amount_usd,
    )
