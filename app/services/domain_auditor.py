"""Engine 1: B2B Domain Intelligence, Tech-Stack Profiler, Security/SEO Auditor & Pitch Generator."""
from __future__ import annotations

import asyncio
import re
import socket
import ssl
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,10}")
PHONE_REGEX = re.compile(
    r"(?:\+\d{1,3}[\s.\-]?)?(?:\(\d{1,4}\)[\s.\-]?)?\d{2,4}[\s.\-]?\d{2,4}[\s.\-]?\d{2,4}"
)

IGNORED_EMAIL_DOMAINS = {
    "example.com",
    "domain.com",
    "email.com",
    "yoursite.com",
    "sentry.io",
    "wixpress.com",
    "w3.org",
}
IGNORED_EMAIL_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".js", ".css", ".woff", ".woff2")

TECH_SIGNATURES: dict[str, list[tuple[str, str]]] = {
    # CMS & E-Commerce
    "WordPress": [("html", "wp-content"), ("html", "wp-includes"), ("meta_generator", "wordpress")],
    "Shopify": [("html", "cdn.shopify.com"), ("html", "shopify.theme"), ("header", "x-shopid")],
    "Webflow": [("html", "data-wf-site"), ("html", "webflow.com")],
    "Wix": [("html", "wix.com"), ("html", "wixstatic.com"), ("header", "x-wix-request-id")],
    "Squarespace": [("html", "squarespace.com"), ("html", "static1.squarespace.com")],
    "PrestaShop": [("html", "prestashop"), ("cookie", "prestashop")],
    "Magento": [("html", "mage/cookies"), ("html", "magento")],
    "WooCommerce": [("html", "woocommerce")],
    # Frontend & JS Frameworks
    "Next.js": [("html", "/_next/static"), ("html", "__NEXT_DATA__"), ("header", "x-nextjs-cache")],
    "Nuxt.js": [("html", "/_nuxt/"), ("html", "__NUXT__")],
    "React": [("html", "react-dom"), ("html", "data-reactroot"), ("html", "__NEXT_DATA__")],
    "Vue.js": [("html", "data-v-"), ("html", "vue.runtime"), ("html", "__NUXT__")],
    "Angular": [("html", "ng-version"), ("html", "ng-app")],
    "Svelte": [("html", "svelte-")],
    "Tailwind CSS": [("html", "tailwind")],
    "Bootstrap": [("html", "bootstrap.min.css"), ("html", "bootstrap.bundle")],
    # Analytics, Marketing & Pixels
    "Google Tag Manager": [("html", "googletagmanager.com/gtm.js")],
    "Google Analytics (GA4)": [("html", "googletagmanager.com/gtag/js"), ("html", "google-analytics.com")],
    "Meta Pixel (Facebook)": [("html", "connect.facebook.net"), ("html", "fbq(")],
    "Hotjar": [("html", "static.hotjar.com")],
    "HubSpot": [("html", "js.hs-scripts.com"), ("html", "hs-analytics")],
    "Intercom": [("html", "widget.intercom.io")],
    "Crisp Chat": [("html", "client.crisp.chat")],
    "Klaviyo": [("html", "static.klaviyo.com")],
    "Stripe": [("html", "js.stripe.com")],
    # Infrastructure & CDN
    "Cloudflare": [("header", "cf-ray"), ("header", "cf-cache-status"), ("server", "cloudflare")],
    "Vercel": [("header", "x-vercel-id"), ("server", "vercel")],
    "Netlify": [("header", "x-nf-request-id"), ("server", "netlify")],
    "AWS CloudFront": [("header", "x-amz-cf-id"), ("header", "x-amz-cf-pop")],
    "Fastly": [("header", "x-fastly-request-id"), ("header", "fastly-restarts")],
    "Nginx": [("server", "nginx")],
    "Apache": [("server", "apache")],
}

SOCIAL_PATTERNS: dict[str, str] = {
    "linkedin": r"https?://(?:www\.)?linkedin\.com/(?:company|in)/[a-zA-Z0-9_\-]+",
    "twitter_x": r"https?://(?:www\.)?(?:twitter\.com|x\.com)/[a-zA-Z0-9_]+",
    "facebook": r"https?://(?:www\.)?facebook\.com/[a-zA-Z0-9.\-_]+",
    "instagram": r"https?://(?:www\.)?instagram\.com/[a-zA-Z0-9._]+",
    "youtube": r"https?://(?:www\.)?youtube\.com/(?:@|channel/|c/|user/)[a-zA-Z0-9_\-]+",
    "github": r"https?://(?:www\.)?github\.com/[a-zA-Z0-9_\-]+",
}

SECURITY_HEADERS_SPEC: list[tuple[str, str, int, str]] = [
    (
        "strict-transport-security",
        "Strict-Transport-Security (HSTS)",
        25,
        "Protège contre les attaques de rétrogradation HTTPS (man-in-the-middle).",
    ),
    (
        "content-security-policy",
        "Content-Security-Policy (CSP)",
        25,
        "Bloque les injections XSS et les scripts tiers non autorisés.",
    ),
    (
        "x-frame-options",
        "X-Frame-Options",
        15,
        "Empêche le détournement de clic (Clickjacking) via iframe.",
    ),
    (
        "x-content-type-options",
        "X-Content-Type-Options",
        15,
        "Empêche le navigateur de deviner le type MIME (MIME-sniffing).",
    ),
    (
        "referrer-policy",
        "Referrer-Policy",
        10,
        "Contrôle les données de provenance envoyées aux sites externes.",
    ),
    (
        "permissions-policy",
        "Permissions-Policy",
        10,
        "Restreint l'accès aux API sensibles du navigateur (caméra, micro, géolocalisation).",
    ),
]


def normalize_url(target: str) -> tuple[str, str]:
    """Normalize a domain or URL into (clean_domain, full_https_url)."""
    raw = target.strip()
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    domain = (parsed.hostname or raw).lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain, raw


def inspect_ssl_certificate(hostname: str, port: int = 443, timeout: float = 4.0) -> dict[str, Any]:
    """Inspect TLS/SSL certificate validity, issuer, and days until expiration."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                if not cert:
                    return {"valid": False, "error": "Empty certificate"}
                not_after_str = cert.get("notAfter", "")
                expires_at = None
                days_remaining = None
                if not_after_str:
                    expires_dt = datetime.strptime(not_after_str, "%b %d %H:%M:%S %Y %Z").replace(
                        tzinfo=timezone.utc
                    )
                    expires_at = expires_dt.isoformat()
                    days_remaining = (expires_dt - datetime.now(timezone.utc)).days

                issuer_parts = dict(x[0] for x in cert.get("issuer", []))
                return {
                    "valid": True,
                    "issuer": issuer_parts.get("organizationName") or issuer_parts.get("commonName") or "Unknown CA",
                    "protocol": ssock.version(),
                    "expires_at": expires_at,
                    "days_remaining": days_remaining,
                }
    except Exception as exc:
        return {"valid": False, "error": str(exc), "days_remaining": 0}


def extract_clean_emails(text: str, html: str) -> list[str]:
    """Extract unique business email addresses while filtering out false positives."""
    combined = f"{text}\n{html}"
    found = set()
    for match in EMAIL_REGEX.findall(combined):
        email = match.lower().strip(".,;:/\"'()[]<>")
        if any(email.endswith(ext) for ext in IGNORED_EMAIL_EXTENSIONS):
            continue
        domain_part = email.split("@")[-1]
        if domain_part in IGNORED_EMAIL_DOMAINS:
            continue
        found.add(email)
    return sorted(found)[:25]


def detect_tech_stack(html_lower: str, headers_lower: dict[str, str], generator_meta: str) -> list[str]:
    """Fingerprint technologies, frameworks, analytics, and CDNs from HTML and HTTP headers."""
    detected: list[str] = []
    server_header = headers_lower.get("server", "")
    cookie_header = headers_lower.get("set-cookie", "")

    for tech_name, rules in TECH_SIGNATURES.items():
        for source_type, pattern in rules:
            pat = pattern.lower()
            if source_type == "html" and pat in html_lower:
                detected.append(tech_name)
                break
            if source_type == "header" and pat in headers_lower:
                detected.append(tech_name)
                break
            if source_type == "server" and pat in server_header:
                detected.append(tech_name)
                break
            if source_type == "cookie" and pat in cookie_header:
                detected.append(tech_name)
                break
            if source_type == "meta_generator" and pat in generator_meta.lower():
                detected.append(tech_name)
                break
    return detected


def build_sales_intelligence(
    domain: str,
    seo_score: int,
    security_score: int,
    response_time_ms: int,
    missing_headers: list[str],
    seo_issues: list[str],
    tech_stack: list[str],
) -> dict[str, Any]:
    """Generate actionable B2B sales intelligence, recommended service pricing, and a ready-to-send cold pitch."""
    critical_weaknesses: list[str] = []
    for issue in seo_issues[:3]:
        critical_weaknesses.append(f"SEO : {issue}")
    for hdr in missing_headers[:3]:
        critical_weaknesses.append(f"Sécurité : En-tête {hdr} manquant")
    if response_time_ms > 1200:
        critical_weaknesses.append(f"Performance : Temps de réponse lent ({response_time_ms} ms)")

    if not critical_weaknesses:
        critical_weaknesses.append("Optimisation avancée du taux de conversion & données structurées Schema.org")

    # Estimate consulting / fix package value in USD based on number of findings
    severity_points = (100 - seo_score) + (100 - security_score)
    if severity_points >= 80:
        estimated_fee = 490
    elif severity_points >= 45:
        estimated_fee = 290
    else:
        estimated_fee = 150

    bullet_list = "\n".join(f"  • {w}" for w in critical_weaknesses[:4])
    stack_str = ", ".join(tech_stack[:4]) if tech_stack else "votre infrastructure web actuelle"

    subject = f"Audit technique rapide pour {domain} ({len(critical_weaknesses)} points d'attention détectés)"
    body = (
        f"Bonjour,\n\n"
        f"En analysant l'infrastructure publique de {domain} ({stack_str}), notre système d'audit automatisé "
        f"a relevé quelques points techniques qui freinent actuellement votre référencement naturel (Score SEO : {seo_score}/100) "
        f"et la sécurité de vos visiteurs (Score Sécurité : {security_score}/100) :\n\n"
        f"{bullet_list}\n\n"
        f"Ces correctifs sont rapides à déployer et permettent généralement d'améliorer immédiatement la visibilité Google "
        f"ainsi que la confiance navigateur.\n\n"
        f"Nous proposons une intervention clé en main au forfait ({estimated_fee} $) incluant le rapport complet et la mise en conformité.\n"
        f"Souhaitez-vous que je vous envoie le rapport détaillé PDF ou qu'on en discute 10 minutes ?\n\n"
        f"Cordialement,\n"
        f"{settings.owner_name}\n"
        f"Réservation directe : {settings.owner_booking_url}"
    )

    return {
        "lead_qualification": "HOT" if severity_points >= 55 else ("WARM" if severity_points >= 25 else "OPTIMIZED"),
        "estimated_fix_fee_usd": estimated_fee,
        "critical_weaknesses": critical_weaknesses,
        "cold_email_pitch": {
            "subject": subject,
            "body": body,
        },
    }


async def audit_domain(target_url: str, timeout: float = 12.0) -> dict[str, Any]:
    """Perform a full B2B intelligence, SEO, security, and contact extraction scan on a domain."""
    domain, normalized_url = normalize_url(target_url)
    headers_req = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    t0 = time.perf_counter()
    ssl_task = asyncio.to_thread(inspect_ssl_certificate, domain)

    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, verify=False) as client:
        try:
            resp = await client.get(normalized_url, headers=headers_req)
        except Exception:
            # Fallback to http if https fails
            http_url = normalized_url.replace("https://", "http://", 1)
            resp = await client.get(http_url, headers=headers_req)

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        final_url = str(resp.url)
        parsed_final = urlparse(final_url)
        base_origin = f"{parsed_final.scheme}://{parsed_final.netloc}"

        # Parallel check for robots.txt and sitemap.xml
        robots_req = client.get(urljoin(base_origin, "/robots.txt"), headers=headers_req, timeout=4.0)
        sitemap_req = client.get(urljoin(base_origin, "/sitemap.xml"), headers=headers_req, timeout=4.0)
        robots_res, sitemap_res, ssl_info = await asyncio.gather(
            robots_req, sitemap_req, ssl_task, return_exceptions=True
        )

    has_robots = (
        not isinstance(robots_res, Exception)
        and robots_res.status_code == 200
        and "user-agent" in robots_res.text.lower()
    )
    has_sitemap = (
        not isinstance(sitemap_res, Exception)
        and sitemap_res.status_code == 200
        and ("<urlset" in sitemap_res.text.lower() or "<sitemapindex" in sitemap_res.text.lower())
    )
    if isinstance(ssl_info, Exception):
        ssl_info = {"valid": False, "error": str(ssl_info), "days_remaining": 0}

    html_content = resp.text or ""
    html_lower = html_content.lower()
    headers_lower = {k.lower(): v for k, v in resp.headers.items()}

    soup = BeautifulSoup(html_content, "lxml")
    visible_text = soup.get_text(separator=" ", strip=True)

    # 1. SEO Audit
    title_tag = soup.find("title")
    title_text = title_tag.get_text(strip=True) if title_tag else ""

    meta_desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    meta_desc = (meta_desc_tag.get("content") or "").strip() if meta_desc_tag else ""

    meta_gen_tag = soup.find("meta", attrs={"name": re.compile(r"^generator$", re.I)})
    meta_generator = (meta_gen_tag.get("content") or "").strip() if meta_gen_tag else ""

    canonical_tag = soup.find("link", attrs={"rel": re.compile(r"canonical", re.I)})
    canonical_url = (canonical_tag.get("href") or "").strip() if canonical_tag else ""

    og_title_tag = soup.find("meta", attrs={"property": "og:title"})
    og_image_tag = soup.find("meta", attrs={"property": "og:image"})

    h1_tags = [h.get_text(strip=True) for h in soup.find_all("h1") if h.get_text(strip=True)]
    h2_tags = [h.get_text(strip=True) for h in soup.find_all("h2") if h.get_text(strip=True)]
    images = soup.find_all("img")
    images_missing_alt = sum(1 for img in images if not (img.get("alt") or "").strip())
    json_ld_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})

    seo_score = 100
    seo_issues: list[str] = []

    if not title_text:
        seo_score -= 20
        seo_issues.append("Balise <title> absente")
    elif len(title_text) < 15 or len(title_text) > 70:
        seo_score -= 8
        seo_issues.append(f"Longueur du <title> sous-optimale ({len(title_text)} caractères)")

    if not meta_desc:
        seo_score -= 20
        seo_issues.append("Meta description absente")
    elif len(meta_desc) < 50 or len(meta_desc) > 170:
        seo_score -= 8
        seo_issues.append(f"Longueur de la meta description sous-optimale ({len(meta_desc)} caractères)")

    if len(h1_tags) == 0:
        seo_score -= 18
        seo_issues.append("Aucune balise <h1> détectée sur la page")
    elif len(h1_tags) > 1:
        seo_score -= 6
        seo_issues.append(f"Plusieurs balises <h1> détectées ({len(h1_tags)} trouvées)")

    if not canonical_url:
        seo_score -= 10
        seo_issues.append("Balise link rel='canonical' manquante")

    if not og_title_tag or not og_image_tag:
        seo_score -= 8
        seo_issues.append("Balises OpenGraph (partage réseaux sociaux) incomplètes")

    if images and images_missing_alt > 0:
        seo_score -= min(12, images_missing_alt * 2)
        seo_issues.append(f"{images_missing_alt}/{len(images)} images sans attribut alt")

    if not has_robots:
        seo_score -= 7
        seo_issues.append("Fichier /robots.txt introuvable")

    if not has_sitemap:
        seo_score -= 7
        seo_issues.append("Fichier /sitemap.xml introuvable")

    if not json_ld_scripts:
        seo_score -= 5
        seo_issues.append("Aucune donnée structurée Schema.org (JSON-LD) détectée")

    seo_score = max(0, seo_score)

    # 2. Security Audit
    security_score = 0
    present_headers: list[dict[str, str]] = []
    missing_headers: list[str] = []

    for header_key, display_name, weight, description in SECURITY_HEADERS_SPEC:
        if header_key in headers_lower:
            security_score += weight
            present_headers.append(
                {"header": display_name, "value": headers_lower[header_key][:120], "description": description}
            )
        else:
            missing_headers.append(display_name)

    if not ssl_info.get("valid"):
        security_score = max(0, security_score - 30)

    # 3. Contacts & Socials Extraction
    emails = extract_clean_emails(visible_text, html_content)
    # Also scan mailto links explicitly
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if href.lower().startswith("mailto:"):
            clean_mail = href[7:].split("?")[0].strip().lower()
            if EMAIL_REGEX.match(clean_mail) and clean_mail not in emails:
                emails.append(clean_mail)

    socials: dict[str, list[str]] = {}
    for platform, pattern in SOCIAL_PATTERNS.items():
        matches = sorted(set(re.findall(pattern, html_content, flags=re.I)))
        if matches:
            socials[platform] = matches[:5]

    # 4. Tech Stack Fingerprinting
    tech_stack = detect_tech_stack(html_lower, headers_lower, meta_generator)

    # 5. Performance Score
    perf_score = 100
    if elapsed_ms > 2500:
        perf_score = 45
    elif elapsed_ms > 1500:
        perf_score = 70
    elif elapsed_ms > 800:
        perf_score = 85

    overall_score = int(round((seo_score * 0.45) + (security_score * 0.35) + (perf_score * 0.20)))

    sales_intel = build_sales_intelligence(
        domain=domain,
        seo_score=seo_score,
        security_score=security_score,
        response_time_ms=elapsed_ms,
        missing_headers=missing_headers,
        seo_issues=seo_issues,
        tech_stack=tech_stack,
    )

    return {
        "domain": domain,
        "final_url": final_url,
        "status_code": resp.status_code,
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "scores": {
            "overall": overall_score,
            "seo": seo_score,
            "security": security_score,
            "performance": perf_score,
        },
        "performance": {
            "response_time_ms": elapsed_ms,
            "page_size_kb": round(len(resp.content) / 1024, 1),
        },
        "seo": {
            "title": title_text,
            "meta_description": meta_desc,
            "canonical_url": canonical_url,
            "h1_count": len(h1_tags),
            "h1_samples": h1_tags[:5],
            "h2_count": len(h2_tags),
            "images_total": len(images),
            "images_missing_alt": images_missing_alt,
            "has_robots_txt": has_robots,
            "has_sitemap_xml": has_sitemap,
            "has_json_ld_schema": len(json_ld_scripts) > 0,
            "issues": seo_issues,
        },
        "security": {
            "ssl": ssl_info,
            "present_headers": present_headers,
            "missing_headers": missing_headers,
        },
        "tech_stack": tech_stack,
        "contacts": {
            "emails": emails,
            "social_profiles": socials,
        },
        "sales_intelligence": sales_intel,
    }
