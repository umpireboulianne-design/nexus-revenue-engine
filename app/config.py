"""Configuration settings for the Nexus Autonomous Revenue & Bounty Engine."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env file."""

    app_name: str = "Nexus Pulse — B2B Intelligence API & Bounty Radar"
    app_version: str = "1.0.0"
    environment: str = "production"
    host: str = "0.0.0.0"
    port: int = 8000

    # Database path
    database_path: str = "nexus_revenue.db"

    # Admin & Marketplace Secrets
    admin_secret_key: str = "nexus-admin-master-key-change-me"
    rapidapi_proxy_secret: str = ""  # Optional: Verify requests coming from RapidAPI Hub
    stripe_webhook_secret: str = ""  # Optional: Stripe checkout webhook secret
    lemonsqueezy_webhook_secret: str = ""  # Optional: LemonSqueezy webhook signing secret

    # Payment Checkout Links (user plugs their Stripe Payment Link or LemonSqueezy URL)
    checkout_url_audit_oneoff: str = "https://buy.stripe.com/test_audit_forfait_49"
    checkout_url_pro_monthly: str = "https://buy.stripe.com/test_api_pro_29"
    checkout_url_agency_monthly: str = "https://buy.stripe.com/test_api_agency_99"

    # GitHub Optional Token (increases rate limit for live Bounty Hunter radar)
    github_token: str = ""

    # Owner Identity (used in auto-generated B2B cold outreach pitches & reports)
    owner_name: str = "Direction Consulting & Audit Numérique"
    owner_email: str = "contact@votredomaine.com"
    owner_booking_url: str = "https://cal.com/votre-nom/audit-15min"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
