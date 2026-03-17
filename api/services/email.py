"""Email notification service.

Sends transactional emails for alerts, reports, and subscription changes.
Uses aiosmtplib for non-blocking SMTP or logs emails in dev mode.
"""

from __future__ import annotations

import html
import logging
import os

logger = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────────────────

SMTP_HOST: str = os.getenv("SMTP_HOST", "")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@carbonscope.io")

_smtp_configured = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


async def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send an email asynchronously. Returns True on success, False on failure."""
    if not _smtp_configured:
        logger.info("Email (dev mode — SMTP not configured): to=%s subject=%s", to, subject)
        logger.debug("Email body: %s", html_body[:200])
        return True

    try:
        import aiosmtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html"))

        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            start_tls=True,
        )

        logger.info("Email sent: to=%s subject=%s", to, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


def _esc(text: str) -> str:
    """Escape user-provided text for safe HTML embedding."""
    return html.escape(str(text))


async def send_alert_email(to: str, alert_title: str, alert_message: str, severity: str) -> bool:
    """Send an alert notification email."""
    color = {"critical": "#dc2626", "warning": "#f59e0b", "info": "#3b82f6"}.get(severity, "#6b7280")
    html_body = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: {_esc(color)}; color: white; padding: 16px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">&#9888;&#65039; CarbonScope Alert</h2>
        </div>
        <div style="border: 1px solid #e5e7eb; padding: 24px; border-radius: 0 0 8px 8px;">
            <h3 style="margin-top: 0;">{_esc(alert_title)}</h3>
            <p>{_esc(alert_message)}</p>
            <p style="color: #6b7280; font-size: 12px;">
                This is an automated alert from CarbonScope. Log in to your dashboard for details.
            </p>
        </div>
    </div>
    """
    return await send_email(to, f"[CarbonScope] {_esc(severity).upper()}: {_esc(alert_title)}", html_body)


async def send_report_ready_email(to: str, report_year: int, total_emissions: float) -> bool:
    """Send email when a new emission report is ready."""
    html_body = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #059669; color: white; padding: 16px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">&#128202; New Emission Report Ready</h2>
        </div>
        <div style="border: 1px solid #e5e7eb; padding: 24px; border-radius: 0 0 8px 8px;">
            <p>Your {_esc(str(report_year))} emission report has been generated.</p>
            <p><strong>Total Emissions:</strong> {total_emissions:,.1f} tCO&#8322;e</p>
            <p>Log in to CarbonScope to view the full breakdown, recommendations, and export options.</p>
        </div>
    </div>
    """
    return await send_email(to, f"[CarbonScope] {report_year} Emission Report Ready", html_body)


async def send_subscription_change_email(to: str, old_plan: str, new_plan: str) -> bool:
    """Send email when subscription plan changes."""
    html_body = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #7c3aed; color: white; padding: 16px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">&#128179; Subscription Updated</h2>
        </div>
        <div style="border: 1px solid #e5e7eb; padding: 24px; border-radius: 0 0 8px 8px;">
            <p>Your subscription has been updated.</p>
            <p><strong>Previous plan:</strong> {_esc(old_plan.title())}</p>
            <p><strong>New plan:</strong> {_esc(new_plan.title())}</p>
            <p>Log in to your dashboard to see your updated features and credit balance.</p>
        </div>
    </div>
    """
    return await send_email(to, f"[CarbonScope] Subscription changed to {_esc(new_plan.title())}", html_body)


async def send_password_reset_email(to: str, reset_token: str) -> bool:
    """Send password reset email with token."""
    html_body = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #2563eb; color: white; padding: 16px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">&#128272; Password Reset</h2>
        </div>
        <div style="border: 1px solid #e5e7eb; padding: 24px; border-radius: 0 0 8px 8px;">
            <p>You requested a password reset. Use this code to reset your password:</p>
            <p style="text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 4px;
               background: #f3f4f6; padding: 16px; border-radius: 8px;">{_esc(reset_token)}</p>
            <p style="color: #6b7280; font-size: 12px;">
                This code expires in 15 minutes. If you did not request this, ignore this email.
            </p>
        </div>
    </div>
    """
    return await send_email(to, "[CarbonScope] Password Reset", html_body)


async def send_marketplace_purchase_email(
    to: str, listing_title: str, price_credits: int, data_type: str,
) -> bool:
    """Send email to buyer confirming a marketplace purchase."""
    html_body = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #0891b2; color: white; padding: 16px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">&#128722; Marketplace Purchase Confirmed</h2>
        </div>
        <div style="border: 1px solid #e5e7eb; padding: 24px; border-radius: 0 0 8px 8px;">
            <p>Your marketplace purchase has been completed.</p>
            <p><strong>Listing:</strong> {_esc(listing_title)}</p>
            <p><strong>Data type:</strong> {_esc(data_type)}</p>
            <p><strong>Credits spent:</strong> {price_credits}</p>
            <p>Log in to your dashboard to access the purchased data.</p>
        </div>
    </div>
    """
    return await send_email(
        to, f"[CarbonScope] Purchase confirmed: {_esc(listing_title)}", html_body,
    )


async def send_marketplace_sale_email(
    to: str, listing_title: str, price_credits: int,
) -> bool:
    """Send email to seller when one of their listings is purchased."""
    html_body = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #059669; color: white; padding: 16px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">&#128176; Marketplace Sale</h2>
        </div>
        <div style="border: 1px solid #e5e7eb; padding: 24px; border-radius: 0 0 8px 8px;">
            <p>Your marketplace listing has been purchased!</p>
            <p><strong>Listing:</strong> {_esc(listing_title)}</p>
            <p><strong>Credits earned:</strong> {price_credits}</p>
            <p>The credits have been added to your account balance.
               Log in to view your updated credit balance and sales history.</p>
        </div>
    </div>
    """
    return await send_email(
        to, f"[CarbonScope] Your listing was purchased: {_esc(listing_title)}", html_body,
    )
