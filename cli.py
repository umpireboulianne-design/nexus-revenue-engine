"""CLI tool for Nexus Pulse: scan live bounties, audit B2B domains, export RapidAPI OpenAPI spec, or serve."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import uvicorn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.database import init_db, save_audited_lead, save_bounties
from app.main import app
from app.services.bounty_hunter import fetch_live_bounties
from app.services.domain_auditor import audit_domain
from app.services.outreach_mailer import generate_leads_csv


async def cmd_bounties(min_usd: int, query_filter: str) -> None:
    init_db()
    print(f"[*] Recherche en direct des primes Open-Source >= {min_usd} $ USD...")
    bounties = await fetch_live_bounties(min_reward_usd=min_usd, query_filter=query_filter)
    save_bounties(bounties)
    total_usd = sum(b["reward_usd"] for b in bounties)
    print(f"[+] {len(bounties)} primes actives trouvées ! Cagnotte totale : {total_usd} $ USD\n")
    for idx, b in enumerate(bounties[:12], 1):
        print(
            f"  {idx:02d}. [{b['reward_usd']} $ | {b['source_platform']}] {b['repo_full_name']} — {b['title'][:72]}"
        )
        print(f"      URL : {b['html_url']} ({b['comments_count']} commentaires | Score ROI: {b['roi_score']})")


async def cmd_audit(domain: str) -> None:
    init_db()
    print(f"[*] Audit B2B complet de {domain} en cours...")
    report = await audit_domain(domain)
    save_audited_lead(report)
    print(
        f"[+] Domaine : {report['domain']} | Score Global : {report['scores']['overall']}/100 "
        f"(SEO: {report['scores']['seo']}/100, Sécurité: {report['scores']['security']}/100)"
    )
    print(f"[+] Stack détectée : {', '.join(report['tech_stack']) or 'Standard'}")
    print(f"[+] Forfait recommandé : {report['sales_intelligence']['estimated_fix_fee_usd']} $ USD")
    print("\n--- OBJET COLD EMAIL ---")
    print(report["sales_intelligence"]["cold_email_pitch"]["subject"])
    print("\n--- CORPS COLD EMAIL ---")
    print(report["sales_intelligence"]["cold_email_pitch"]["body"])


def cmd_export_openapi(out_path: str) -> None:
    schema = app.openapi()
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[+] Spécification OpenAPI 3.1 exportée vers : {target.resolve()}")


async def cmd_seed_campaign() -> None:
    init_db()
    targets = ["python.org", "sqlite.org", "lua.org", "gnu.org", "apache.org"]
    for t in targets:
        try:
            rep = await audit_domain(t)
            save_audited_lead(rep)
            print(
                f"[+] Audité : {t} | Score: {rep['scores']['overall']}/100 | "
                f"Emails: {rep['contacts']['emails'][:2]} | Forfait: {rep['sales_intelligence']['estimated_fix_fee_usd']} $"
            )
        except Exception as exc:
            print(f"[-] Erreur sur {t}: {exc}")
    csv_text = generate_leads_csv()
    out_csv = Path("deploy/campagne_b2b_prete.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_csv.write_text(csv_text, encoding="utf-8")
    print(f"[+] Campagne CSV exportée vers : {out_csv.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Nexus Autonomous Revenue & Bounty Engine CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_bounties = sub.add_parser("bounties", help="Scanner en direct les primes GitHub / Algora en dollars")
    p_bounties.add_argument("--min-usd", type=int, default=25, help="Prime minimale en USD")
    p_bounties.add_argument("--filter", type=str, default="", help="Filtre par langage ou mot-clé")

    p_audit = sub.add_parser("audit", help="Auditer un domaine B2B et générer son pitch commercial")
    p_audit.add_argument("domain", type=str, help="Domaine ou URL à analyser")

    p_openapi = sub.add_parser("export-openapi", help="Exporter le fichier JSON OpenAPI pour RapidAPI Hub")
    p_openapi.add_argument("--out", type=str, default="deploy/openapi_rapidapi.json", help="Chemin de sortie")

    sub.add_parser("seed-campaign", help="Scanner un lot de domaines B2B et générer deploy/campagne_b2b_prete.csv")

    p_serve = sub.add_parser("serve", help="Lancer le serveur SaaS & API FastAPI")
    p_serve.add_argument("--host", type=str, default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()
    if args.command == "bounties":
        asyncio.run(cmd_bounties(args.min_usd, args.filter))
    elif args.command == "audit":
        asyncio.run(cmd_audit(args.domain))
    elif args.command == "export-openapi":
        cmd_export_openapi(args.out)
    elif args.command == "seed-campaign":
        asyncio.run(cmd_seed_campaign())
    elif args.command == "serve":
        init_db()
        uvicorn.run("app.main:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
