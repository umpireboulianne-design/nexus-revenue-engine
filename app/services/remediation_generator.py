"""Engine 4: Zero-Work Client Fulfillment — Auto-generates the complete Technical Remediation Pack."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse
from xml.sax.saxutils import escape

import httpx
from bs4 import BeautifulSoup


async def extract_internal_links(base_url: str, max_links: int = 40) -> list[str]:
    """Crawl homepage internal links to build a valid XML sitemap for the client."""
    parsed_base = urlparse(base_url)
    origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
    found: set[str] = {origin + "/"}

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=8.0, verify=False) as client:
            resp = await client.get(base_url, headers={"User-Agent": "Nexus-Sitemap-Builder/1.0"})
            soup = BeautifulSoup(resp.text or "", "lxml")
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                    continue
                full = urljoin(origin, href).split("#")[0].rstrip("/")
                p = urlparse(full)
                if p.netloc.lower() == parsed_base.netloc.lower() and p.scheme in ("http", "https"):
                    found.add(full or (origin + "/"))
                    if len(found) >= max_links:
                        break
    except Exception:
        pass

    return sorted(found)


def generate_sitemap_xml(urls: list[str]) -> str:
    """Build a standards-compliant sitemap.xml string."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    items = []
    for u in urls:
        prio = "1.0" if u.count("/") <= 3 else "0.8"
        items.append(
            f"  <url>\n"
            f"    <loc>{escape(u)}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>weekly</changefreq>\n"
            f"    <priority>{prio}</priority>\n"
            f"  </url>"
        )
    body = "\n".join(items)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</urlset>"
    )


def generate_robots_txt(domain: str) -> str:
    """Build an SEO-optimized robots.txt file."""
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /private/\n"
        "Disallow: /cgi-bin/\n\n"
        f"Sitemap: https://{domain}/sitemap.xml\n"
    )


def generate_security_configs(domain: str) -> dict[str, str]:
    """Generate copy-paste 100/100 security header configurations for Nginx, Apache, Caddy, and Vercel."""
    nginx_conf = f"""# === Configuration Sécurité 100/100 pour {domain} (Nginx) ===
# À placer dans votre bloc server {{ ... }} (ex: /etc/nginx/sites-available/{domain})

add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()" always;
add_header Content-Security-Policy "default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval'; frame-ancestors 'self';" always;
"""

    apache_htaccess = f"""# === Configuration Sécurité 100/100 pour {domain} (Apache .htaccess) ===
<IfModule mod_headers.c>
    Header always set Strict-Transport-Security "max-age=63072000; includeSubDomains; preload"
    Header always set X-Frame-Options "SAMEORIGIN"
    Header always set X-Content-Type-Options "nosniff"
    Header always set Referrer-Policy "strict-origin-when-cross-origin"
    Header always set Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()"
    Header always set Content-Security-Policy "default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval'; frame-ancestors 'self';"
</IfModule>
"""

    caddy_conf = f"""# === Configuration Sécurité 100/100 pour {domain} (Caddyfile) ===
{domain} {{
    header {{
        Strict-Transport-Security "max-age=63072000; includeSubDomains; preload"
        X-Frame-Options "SAMEORIGIN"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()"
        Content-Security-Policy "default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval'; frame-ancestors 'self';"
        -Server
    }}
}}
"""

    vercel_json = json.dumps(
        {
            "headers": [
                {
                    "source": "/(.*)",
                    "headers": [
                        {
                            "key": "Strict-Transport-Security",
                            "value": "max-age=63072000; includeSubDomains; preload",
                        },
                        {"key": "X-Frame-Options", "value": "SAMEORIGIN"},
                        {"key": "X-Content-Type-Options", "value": "nosniff"},
                        {"key": "Referrer-Policy", "value": "strict-origin-when-cross-origin"},
                        {
                            "key": "Permissions-Policy",
                            "value": "camera=(), microphone=(), geolocation=(), payment=()",
                        },
                    ],
                }
            ]
        },
        indent=2,
    )

    return {
        "nginx": nginx_conf,
        "apache_htaccess": apache_htaccess,
        "caddy": caddy_conf,
        "vercel_json": vercel_json,
    }


def generate_seo_head_and_schema(report: dict[str, Any]) -> str:
    """Generate optimized HTML <head> meta tags, OpenGraph tags, and Schema.org JSON-LD."""
    domain = report["domain"]
    final_url = report["final_url"]
    raw_title = report["seo"]["title"] or f"{domain.capitalize()} — Services & Solutions Officielles"
    if len(raw_title) < 20:
        raw_title = f"{raw_title} | Plateforme Officielle {domain}"

    raw_desc = report["seo"]["meta_description"] or (
        f"Découvrez les solutions, services et expertises proposés par {domain}. "
        f"Contactez notre équipe pour un accompagnement sur mesure."
    )

    socials_flat: list[str] = []
    for urls in report["contacts"]["social_profiles"].values():
        socials_flat.extend(urls)

    schema_obj: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": domain.split(".")[0].capitalize(),
        "url": final_url,
    }
    if socials_flat:
        schema_obj["sameAs"] = socials_flat[:8]
    if report["contacts"]["emails"]:
        schema_obj["email"] = report["contacts"]["emails"][0]

    schema_json = json.dumps(schema_obj, indent=2, ensure_ascii=False)

    return f"""<!-- === Correctif SEO, Canonical, OpenGraph & Schema.org JSON-LD pour {domain} === -->
<title>{escape(raw_title[:65])}</title>
<meta name="description" content="{escape(raw_desc[:160])}" />
<link rel="canonical" href="{escape(final_url)}" />

<!-- OpenGraph / Réseaux Sociaux -->
<meta property="og:type" content="website" />
<meta property="og:title" content="{escape(raw_title[:65])}" />
<meta property="og:description" content="{escape(raw_desc[:160])}" />
<meta property="og:url" content="{escape(final_url)}" />
<meta name="twitter:card" content="summary_large_image" />

<!-- Données Structurées Schema.org (Rich Snippets Google) -->
<script type="application/ld+json">
{schema_json}
</script>
"""


async def build_full_remediation_pack(report: dict[str, Any]) -> dict[str, Any]:
    """Produce the complete turnkey technical deliverable for a paying B2B client."""
    domain = report["domain"]
    final_url = report["final_url"]
    internal_urls = await extract_internal_links(final_url)
    sitemap_xml = generate_sitemap_xml(internal_urls)
    robots_txt = generate_robots_txt(domain)
    security_configs = generate_security_configs(domain)
    seo_head_snippet = generate_seo_head_and_schema(report)

    return {
        "domain": domain,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "estimated_value_usd": report["sales_intelligence"]["estimated_fix_fee_usd"],
        "deliverables": {
            "seo_head_and_jsonld_html": seo_head_snippet,
            "robots_txt": robots_txt,
            "sitemap_xml": sitemap_xml,
            "crawled_urls_count": len(internal_urls),
            "security_configs": security_configs,
        },
    }


def render_remediation_pack_html(pack: dict[str, Any]) -> str:
    """Render the client-ready Turnkey Remediation Deliverable Pack as a clean HTML page."""
    domain = pack["domain"]
    d = pack["deliverables"]
    sec = d["security_configs"]

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Pack de Mise en Conformité Clé-en-Main — {domain}</title>
<style>
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 32px; }}
  .wrap {{ max-width: 960px; margin: 0 auto; background: #1e293b; border-radius: 16px; padding: 36px; border: 1px solid #334155; }}
  h1 {{ margin-top: 0; font-size: 26px; color: #38bdf8; }}
  h2 {{ font-size: 18px; color: #e2e8f0; border-bottom: 1px solid #334155; padding-bottom: 8px; margin-top: 28px; }}
  pre {{ background: #090d16; color: #a7f3d0; padding: 16px; border-radius: 10px; overflow-x: auto; font-size: 13px; border: 1px solid #1e293b; }}
  .badge {{ background: #10b981; color: #052e16; font-weight: 800; padding: 4px 12px; border-radius: 999px; font-size: 12px; }}
</style>
</head>
<body>
  <div class="wrap">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">
      <div>
        <span class="badge">LIVRABLE TECHNIQUE CLÉ EN MAIN (VALEUR {pack["estimated_value_usd"]} $)</span>
        <h1 style="margin-top:10px;">Pack de Remédiation SEO & Sécurité — {domain}</h1>
      </div>
      <div style="color:#94a3b8;font-size:13px;">Généré le {pack["generated_at"][:10]}</div>
    </div>

    <p style="color:#cbd5e1;font-size:14px;">
      Ce dossier contient l'intégralité des fichiers et configurations prêts à copier-coller pour faire passer
      <strong>{domain}</strong> à un score de conformité optimal (SEO, Schema.org JSON-LD, Sitemap XML et En-têtes de Sécurité HTTP).
    </p>

    <h2>1. Balises HTML &lt;head&gt; Optimisées + Données Structurées Schema.org (JSON-LD)</h2>
    <pre>{escape(d["seo_head_and_jsonld_html"])}</pre>

    <h2>2. Fichier /robots.txt Optimisé</h2>
    <pre>{escape(d["robots_txt"])}</pre>

    <h2>3. Fichier /sitemap.xml Généré Automatiquement ({d["crawled_urls_count"]} URLs indexées)</h2>
    <pre>{escape(d["sitemap_xml"])}</pre>

    <h2>4. Configuration des En-têtes de Sécurité (Nginx)</h2>
    <pre>{escape(sec["nginx"])}</pre>

    <h2>5. Configuration des En-têtes de Sécurité (Apache .htaccess)</h2>
    <pre>{escape(sec["apache_htaccess"])}</pre>

    <h2>6. Configuration des En-têtes de Sécurité (Caddy / Vercel)</h2>
    <pre>{escape(sec["caddy"])}\n\n// vercel.json :\n{escape(sec["vercel_json"])}</pre>
  </div>
</body>
</html>"""
