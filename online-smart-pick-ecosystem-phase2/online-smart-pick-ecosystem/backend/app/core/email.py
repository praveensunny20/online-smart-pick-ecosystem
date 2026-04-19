"""
Email service.

Sends transactional emails (verification, password reset, invitations).

If RESEND_API_KEY is set in .env, emails are sent via the Resend HTTP API.
If not set, emails are logged to stdout — so you can develop without an account.
Look for lines starting with "📧 EMAIL (console mode)" in the backend logs.

To use Resend in production:
    1. Sign up at https://resend.com
    2. Verify your sending domain (or use the Resend onboarding domain while testing)
    3. Put RESEND_API_KEY=re_xxx in backend/.env
    4. Update EMAIL_FROM_ADDRESS to an address on your verified domain
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


class EmailServiceError(Exception):
    """Raised when email sending fails."""


async def _send_via_resend(
    to: str,
    subject: str,
    html: str,
    text: Optional[str] = None,
) -> None:
    """Send a single email via the Resend HTTP API."""
    from_line = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>"
    payload: dict = {
        "from": from_line,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text

    headers = {
        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(RESEND_API_URL, json=payload, headers=headers)
        if resp.status_code >= 300:
            raise EmailServiceError(
                f"Resend API returned {resp.status_code}: {resp.text}"
            )


def _console_log_email(to: str, subject: str, html: str) -> None:
    """Fallback when no Resend API key is configured."""
    divider = "=" * 70
    print(f"\n{divider}")
    print(f"📧 EMAIL (console mode — set RESEND_API_KEY to actually send)")
    print(f"{divider}")
    print(f"TO:      {to}")
    print(f"FROM:    {settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>")
    print(f"SUBJECT: {subject}")
    print(f"{'-' * 70}")
    print(html)
    print(f"{divider}\n")


async def send_email(
    to: str,
    subject: str,
    html: str,
    text: Optional[str] = None,
) -> None:
    """
    Send an email. Uses Resend if configured, otherwise logs to console.
    Never raises on console-mode; raises EmailServiceError on Resend failure.
    """
    if not settings.RESEND_API_KEY:
        _console_log_email(to, subject, html)
        return

    try:
        await _send_via_resend(to=to, subject=subject, html=html, text=text)
    except httpx.HTTPError as e:
        raise EmailServiceError(f"Failed to send email via Resend: {e}") from e


# ---------------------------------------------------------------
# Email templates
# ---------------------------------------------------------------

_BASE_STYLES = """
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
         background: #f6f7fb; margin: 0; padding: 24px; color: #1f2a44; }
  .card { max-width: 560px; margin: 0 auto; background: #fff; border-radius: 12px;
          padding: 32px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
  h1 { color: #1E3A5F; margin-top: 0; }
  .btn { display: inline-block; background: #10B981; color: #fff !important;
         padding: 12px 24px; border-radius: 8px; text-decoration: none;
         font-weight: 600; margin: 16px 0; }
  .muted { color: #6b7280; font-size: 13px; line-height: 1.5; }
  a { color: #1E3A5F; word-break: break-all; }
</style>
"""


def _render(body: str) -> str:
    return f"<html><head>{_BASE_STYLES}</head><body><div class='card'>{body}</div></body></html>"


async def send_verification_email(to: str, full_name: str, verify_token: str) -> None:
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={verify_token}"
    body = f"""
        <h1>Welcome to Online Smart Pick 👋</h1>
        <p>Hi {full_name},</p>
        <p>Thanks for signing up. Click the button below to verify your email address:</p>
        <p><a class="btn" href="{verify_url}">Verify my email</a></p>
        <p class="muted">Or copy and paste this link into your browser:<br>
          <a href="{verify_url}">{verify_url}</a></p>
        <p class="muted">This link expires in {settings.EMAIL_VERIFY_TOKEN_EXPIRE_HOURS} hours.
          If you didn't create this account, you can safely ignore this email.</p>
    """
    await send_email(
        to=to,
        subject="Verify your Online Smart Pick account",
        html=_render(body),
    )


async def send_password_reset_email(to: str, full_name: str, reset_token: str) -> None:
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
    body = f"""
        <h1>Reset your password</h1>
        <p>Hi {full_name},</p>
        <p>We received a request to reset your password. Click the button below to pick a new one:</p>
        <p><a class="btn" href="{reset_url}">Reset my password</a></p>
        <p class="muted">Or copy this link:<br><a href="{reset_url}">{reset_url}</a></p>
        <p class="muted">This link expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS} hours.
          If you didn't ask for a reset, ignore this email — your password won't change.</p>
    """
    await send_email(
        to=to,
        subject="Reset your Online Smart Pick password",
        html=_render(body),
    )


async def send_invitation_email(
    to: str, full_name: str, agency_name: str, temp_password: str
) -> None:
    login_url = f"{settings.FRONTEND_URL}/login"
    body = f"""
        <h1>You've been invited to {agency_name}</h1>
        <p>Hi {full_name},</p>
        <p>An admin has created an account for you on Online Smart Pick.</p>
        <p><strong>Temporary password:</strong> <code>{temp_password}</code></p>
        <p>Please log in and change your password immediately.</p>
        <p><a class="btn" href="{login_url}">Log in now</a></p>
        <p class="muted">If you weren't expecting this invitation, please ignore this email.</p>
    """
    await send_email(
        to=to,
        subject=f"You've been invited to {agency_name} on Online Smart Pick",
        html=_render(body),
    )
