import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def send_magic_link_email(to_email: str, magic_link_url: str) -> bool:
    """Send a magic link login email via the Envelope API.

    Returns True if sent successfully, False otherwise.
    Always fails silently (logs errors but never raises).
    """
    settings = get_settings()

    if not settings.ENVELOPE_API_URL:
        logger.warning(
            "ENVELOPE_API_URL not configured — magic link email not sent to %s",
            to_email,
        )
        return False

    payload = {
        "account_id": settings.ENVELOPE_ACCOUNT_ID,
        "to": to_email,
        "subject": "Your Volodin Family Book Login Link",
        "html": (
            "<p>Hi!</p>"
            f"<p><a href=\"{magic_link_url}\">Click here to log into the Volodin Family Book</a></p>"
            "<p>This link expires in 15 minutes. If you didn't request this, you can safely ignore it.</p>"
        ),
        "text": (
            "Hi!\n\n"
            f"Click here to log into the Volodin Family Book: {magic_link_url}\n\n"
            "This link expires in 15 minutes. If you didn't request this, you can safely ignore it."
        ),
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{settings.ENVELOPE_API_URL.rstrip('/')}/send",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.ENVELOPE_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            logger.info("Magic link email sent to %s", to_email)
            return True
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Envelope API returned %s when sending to %s: %s",
            exc.response.status_code,
            to_email,
            exc.response.text[:200],
        )
    except httpx.RequestError as exc:
        logger.error("Failed to reach Envelope API for %s: %s", to_email, exc)

    return False
