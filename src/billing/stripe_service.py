import logging

import stripe

from api.config import settings
from src.services.registry import services

logger = logging.getLogger(__name__)

_processed_webhook_events: set[str] = set()


# Price mapping based on registry
def get_price_id(plan: str, annual: bool) -> str | None:
    PRICE_MAP = {
        ("pro", False): services.stripe.price_pro_monthly,
        ("pro", True): services.stripe.price_pro_annual,
        ("team", False): services.stripe.price_team_monthly,
        ("team", True): services.stripe.price_team_annual,
        ("enterprise", False): services.stripe.price_enterprise,
        ("enterprise", True): services.stripe.price_enterprise,
    }
    return PRICE_MAP.get((plan, annual))


class StripeService:
    def __init__(self):
        stripe.api_key = settings.stripe_secret_key

    async def create_checkout_session(
        self, db_pool, workos_user_id: str, email: str, plan: str, annual: bool = False, quantity: int = 1
    ) -> dict:
        """Create a Checkout Session for a new subscription."""
        try:
            # Get existing stripe customer id
            row = await db_pool.fetchrow(
                "SELECT stripe_customer_id FROM users WHERE workos_user_id = $1", workos_user_id
            )
            customer_id = row["stripe_customer_id"] if row else None

            price_id = get_price_id(plan, annual)
            if not price_id:
                return {
                    "error": f"No Stripe price configured for {plan} {'annual' if annual else 'monthly'}"  # noqa: E501
                }

            session_params = {
                "payment_method_types": ["card"],
                "line_items": [{"price": price_id, "quantity": quantity}],
                "mode": "subscription",
                "success_url": services.stripe.success_url,
                "cancel_url": services.stripe.cancel_url,
                "customer_email": email if not customer_id else None,
                "customer": customer_id,
                "client_reference_id": workos_user_id,
                "metadata": {
                    "workos_user_id": workos_user_id,
                    "type": "subscription",
                    "plan": plan,
                },
            }
            # Remove None values
            session_params = {k: v for k, v in session_params.items() if v is not None}

            import asyncio

            session = await asyncio.to_thread(stripe.checkout.Session.create, **session_params)
            return {"url": session.url}
        except Exception as e:
            logger.error(f"Stripe checkout error: {e}")
            raise

    async def create_credit_purchase_session(
        self, db_pool, workos_user_id: str, amount: int, price_cents: int
    ) -> dict:
        """Create a Checkout Session for one-off PAYG credits."""
        try:
            row = await db_pool.fetchrow(
                "SELECT stripe_customer_id, email FROM users WHERE workos_user_id = $1",
                workos_user_id,
            )
            if not row:
                raise ValueError("User not found")

            customer_id = row["stripe_customer_id"]

            session_params = {
                "payment_method_types": ["card"],
                "line_items": [
                    {
                        "price_data": {
                            "currency": "usd",
                            "product_data": {"name": f"{amount} GPTCGT AI Credits"},
                            "unit_amount": price_cents,
                        },
                        "quantity": 1,
                    }
                ],
                "mode": "payment",
                "success_url": services.stripe.success_url,
                "cancel_url": services.stripe.cancel_url,
                "customer": customer_id,
                "customer_email": row["email"] if not customer_id else None,
                "client_reference_id": workos_user_id,
                "metadata": {
                    "workos_user_id": workos_user_id,
                    "type": "credits",
                    "amount": str(amount),
                },
            }
            session_params = {k: v for k, v in session_params.items() if v is not None}

            import asyncio

            session = await asyncio.to_thread(stripe.checkout.Session.create, **session_params)
            return {"url": session.url}
        except Exception as e:
            logger.error(f"Stripe credit checkout error: {e}")
            raise

    async def create_customer_portal(self, db_pool, workos_user_id: str) -> dict:
        """Create a customer portal session for managing billing."""
        try:
            row = await db_pool.fetchrow(
                "SELECT stripe_customer_id FROM users WHERE workos_user_id = $1", workos_user_id
            )
            if not row or not row["stripe_customer_id"]:
                return {"error": "No active Stripe customer"}

            import asyncio

            session = await asyncio.to_thread(
                stripe.billing_portal.Session.create,
                customer=row["stripe_customer_id"],
                return_url=services.stripe.portal_return_url,
            )
            return {"url": session.url}
        except Exception as e:
            logger.error(f"Stripe portal error: {e}")
            raise

    async def handle_webhook(self, db_pool, payload: bytes, sig_header: str) -> dict:
        """Process incoming Stripe webhooks."""
        webhook_secret = settings.stripe_webhook_secret
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except ValueError:
            raise ValueError("Invalid payload")
        except stripe.SignatureVerificationError:
            raise ValueError("Invalid signature")

        event_type = event["type"]
        data = event["data"]["object"]

        event_id = event.get("id", "")
        if event_id in _processed_webhook_events:
            return {"status": "duplicate"}
        _processed_webhook_events.add(event_id)

        # Prevent unbounded growth — keep only last 1000 events
        if len(_processed_webhook_events) > 1000:
            _processed_webhook_events.clear()

        logger.info(f"Processing Stripe webhook: {event_type}")

        if event_type == "checkout.session.completed":
            await self._handle_checkout(db_pool, data)
        elif event_type == "customer.subscription.updated":
            await self._handle_subscription_update(db_pool, data)
        elif event_type == "customer.subscription.deleted":
            await self._handle_subscription_cancel(db_pool, data)
        elif event_type == "invoice.paid":
            await self._handle_invoice_paid(db_pool, data)
        elif event_type == "invoice.payment_failed":
            customer_id = data.get("customer")
            if customer_id:
                user_row = await db_pool.fetchrow(
                    "SELECT email FROM users WHERE stripe_customer_id = $1", customer_id
                )
                if user_row and user_row["email"]:
                    from src.services.email import email_service

                    await email_service.send_payment_failed(user_row["email"])

        return {"status": "success"}

    async def _handle_checkout(self, db_pool, session: dict) -> None:
        """Handle successful checkout (either subscription or packs)."""
        workos_user_id = session.get("client_reference_id")
        if not workos_user_id:
            workos_user_id = session.get("metadata", {}).get("workos_user_id")
        if not workos_user_id:
            return

        customer_id = session.get("customer")
        action_type = session.get("metadata", {}).get("type")

        # Fetch email for notifications
        user_row = await db_pool.fetchrow(
            "SELECT email FROM users WHERE workos_user_id = $1", workos_user_id
        )
        email = user_row["email"] if user_row else None

        from src.services.analytics import track_async
        from src.services.email import email_service

        if action_type == "subscription":
            sub_id = session.get("subscription")
            plan = session.get("metadata", {}).get("plan", "pro")
            credits_monthly = 2000 if plan == "team" else 1000  # Default allocations

            await db_pool.execute(
                """
                UPDATE users
                SET stripe_customer_id = $1, stripe_subscription_id = $2,
                    plan = $3, credits_monthly = $4, credits_remaining = $4,
                    subscription_status = 'active'
                WHERE workos_user_id = $5
                """,
                customer_id,
                sub_id,
                plan,
                credits_monthly,
                workos_user_id,
            )

            if email:
                await email_service.send_subscription_started(email, plan)
            await track_async(workos_user_id, "subscription_started", {"plan": plan})
        elif action_type == "credits":
            amount = int(session.get("metadata", {}).get("amount", "0"))
            await db_pool.execute(
                """
                UPDATE users
                SET stripe_customer_id = $1, credits_remaining = credits_remaining + $2
                WHERE workos_user_id = $3
                """,
                customer_id,
                amount,
                workos_user_id,
            )

    async def _handle_subscription_update(self, db_pool, subscription: dict) -> None:
        """Update subscription status (e.g. past_due, active)."""
        customer_id = subscription.get("customer")
        status = subscription.get("status")
        period_end = subscription.get("current_period_end")

        # We need to find by customer_id because webhooks often lack metadata on the root object
        await db_pool.execute(
            """
            UPDATE users
            SET subscription_status = $1,
                current_period_end = to_timestamp($2)
            WHERE stripe_customer_id = $3
            """,
            status,
            period_end,
            customer_id,
        )

    async def _handle_subscription_cancel(self, db_pool, subscription: dict) -> None:
        """Handle cancellation -> downgrade to Free."""
        customer_id = subscription.get("customer")

        user_row = await db_pool.fetchrow(
            "SELECT workos_user_id, email FROM users WHERE stripe_customer_id = $1", customer_id
        )

        await db_pool.execute(
            """
            UPDATE users
            SET plan = 'free',
                subscription_status = 'canceled',
                credits_monthly = 0,
                stripe_subscription_id = NULL
            WHERE stripe_customer_id = $1
            """,
            customer_id,
        )

        if user_row:
            from src.services.analytics import track_async

            await track_async(user_row["workos_user_id"], "subscription_canceled", {})

    async def _handle_invoice_paid(self, db_pool, invoice: dict) -> None:
        """Trigger monthly credit replenishment when an invoice is fully paid."""
        reason = invoice.get("billing_reason")
        if reason == "subscription_cycle":
            customer_id = invoice.get("customer")

            # Reset credits to their monthly allowance
            await db_pool.execute(
                """
                UPDATE users
                SET credits_remaining = credits_monthly
                WHERE stripe_customer_id = $1 AND plan != 'free'
                """,
                customer_id,
            )
