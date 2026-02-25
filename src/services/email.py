"""Email integration leveraging Resend."""

import logging

import httpx

from src.services.registry import services

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.config = services.resend

    async def _send(self, to: str, subject: str, html: str) -> bool:
        if not self.config.is_configured:
            return False
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {self.config.api_key}"},
                    json={
                        "from": self.config.from_email,
                        "reply_to": self.config.reply_to,
                        "to": [to],
                        "subject": subject,
                        "html": html,
                    },
                    timeout=10.0,
                )
                resp.raise_for_status()
            logger.debug(f"Email sent to {to}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return False

    async def send_welcome(self, to: str) -> bool:
        html = "<h1>Welcome to gptcgt</h1><p>Your ultimate AI coding terminal awaits.</p>"
        return await self._send(to, "Welcome to gptcgt", html)

    async def send_subscription_started(self, to: str, plan_name: str) -> bool:
        html = f"<h1>Upgrade Successful</h1><p>You are now on the {plan_name} plan.</p>"
        return await self._send(to, "gptcgt Subscription Started", html)

    async def send_payment_failed(self, to: str) -> bool:
        html = "<h1>Payment Action Required</h1><p>Your recent payment failed. Please update your billing info.</p>"  # noqa: E501
        return await self._send(to, "gptcgt Payment Failed", html)

    async def send_warning_cap(self, to: str, threshold: float) -> bool:
        html = f"<h1>Spending Alert</h1><p>You have exceeded your ${threshold} spending cap.</p>"
        return await self._send(to, "gptcgt Spending Alert", html)


email_service = EmailService()
