import asyncio
import logging
from collections.abc import Awaitable, Callable

import stripe

from api.config import settings
from src.services.registry import services

logger = logging.getLogger(__name__)
PostCommitAction = tuple[str, Callable[[], Awaitable[None]]]


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

    def _error(self, message: str, exc: Exception | None = None) -> dict:
        if exc is not None:
            logger.error("Stripe error: %s", message, exc_info=exc)
        else:
            logger.error("Stripe error: %s", message)
        return {"error": message}

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
                    "quantity": str(quantity),
                },
            }
            # Remove None values
            session_params = {k: v for k, v in session_params.items() if v is not None}

            session = await asyncio.to_thread(stripe.checkout.Session.create, **session_params)
            return {"url": session.url}
        except Exception as e:
            return self._error("Unable to create checkout session. Please try again later.", e)

    async def create_credit_purchase_session(self, db_pool, workos_user_id: str, amount: int, price_cents: int) -> dict:
        """Create a Checkout Session for one-off PAYG credits."""
        try:
            row = await db_pool.fetchrow(
                "SELECT stripe_customer_id, email FROM users WHERE workos_user_id = $1",
                workos_user_id,
            )
            if not row:
                return self._error("User not found")

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

            session = await asyncio.to_thread(stripe.checkout.Session.create, **session_params)
            return {"url": session.url}
        except Exception as e:
            return self._error("Unable to create credit checkout session. Please try again later.", e)

    async def create_customer_portal(self, db_pool, workos_user_id: str) -> dict:
        """Create a customer portal session for managing billing."""
        try:
            row = await db_pool.fetchrow(
                "SELECT stripe_customer_id FROM users WHERE workos_user_id = $1", workos_user_id
            )
            if not row or not row["stripe_customer_id"]:
                return {"error": "No active Stripe customer"}

            session = await asyncio.to_thread(
                stripe.billing_portal.Session.create,
                customer=row["stripe_customer_id"],
                return_url=services.stripe.portal_return_url,
            )
            return {"url": session.url}
        except Exception as e:
            return self._error("Unable to open billing portal. Please try again later.", e)

    async def handle_webhook(self, db_pool, payload: bytes, sig_header: str) -> dict:
        """Process incoming Stripe webhooks."""
        webhook_secret = settings.stripe_webhook_secret
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except ValueError:
            return {"status": "invalid_payload", "error": "Invalid payload"}
        except stripe.SignatureVerificationError:
            return {"status": "invalid_signature", "error": "Invalid signature"}

        event_type = event["type"]
        data = event["data"]["object"]

        event_id = event.get("id", "")
        post_commit_actions: list[PostCommitAction] = []

        # P1-03: Postgres-backed transactional status machine idempotency
        try:
            async with db_pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute(
                            "INSERT INTO webhook_events (event_id, status) VALUES ($1, 'received') ON CONFLICT DO NOTHING",
                            event_id,
                        )
                        existing = await conn.fetchrow("SELECT status FROM webhook_events WHERE event_id = $1 FOR UPDATE", event_id)
                        if existing and existing["status"] == "processed":
                            return {"status": "duplicate"}

                        logger.info(f"Processing Stripe webhook: {event_type}")

                        if event_type == "checkout.session.completed":
                            post_commit_actions.extend(await self._handle_checkout(conn, data))
                        elif event_type == "customer.subscription.updated":
                            await self._handle_subscription_update(conn, data)
                        elif event_type == "customer.subscription.deleted":
                            post_commit_actions.extend(await self._handle_subscription_cancel(conn, data))
                        elif event_type == "invoice.paid":
                            await self._handle_invoice_paid(conn, data)
                        elif event_type == "invoice.payment_failed":
                            customer_id = data.get("customer")
                            if customer_id:
                                user_row = await conn.fetchrow("SELECT email FROM users WHERE stripe_customer_id = $1", customer_id)
                                if user_row and user_row["email"]:
                                    from src.services.email import email_service
                                    post_commit_actions.append(
                                        (
                                            "send_payment_failed_email",
                                            lambda email=user_row["email"]: email_service.send_payment_failed(email),
                                        )
                                    )

                        await conn.execute("UPDATE webhook_events SET status = 'processed', processed_at = CURRENT_TIMESTAMP WHERE event_id = $1", event_id)

                    except Exception as pg_exc:
                        logger.error(f"Transaction failed processing webhook {event_id}: {pg_exc}")
                        raise
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            raise

        for action_name, action in post_commit_actions:
            try:
                await action()
            except Exception as side_effect_error:
                logger.error(f"Post-commit Stripe side effect '{action_name}' failed: {side_effect_error}")

        return {"status": "success"}

    async def _handle_checkout(self, conn, session: dict) -> list[PostCommitAction]:
        """Handle successful checkout (either subscription or packs)."""
        workos_user_id = session.get("client_reference_id")
        if not workos_user_id:
            workos_user_id = session.get("metadata", {}).get("workos_user_id")
        if not workos_user_id:
            return []

        customer_id = session.get("customer")
        action_type = session.get("metadata", {}).get("type")
        post_commit_actions: list[PostCommitAction] = []

        # Fetch email for notifications
        user_row = await conn.fetchrow("SELECT email FROM users WHERE workos_user_id = $1", workos_user_id)
        email = user_row["email"] if user_row else None

        from src.services.analytics import track_async
        from src.services.email import email_service

        if action_type == "subscription":
            sub_id = session.get("subscription")
            plan = session.get("metadata", {}).get("plan", "pro")
            quantity = int(session.get("metadata", {}).get("quantity", "1"))
            base_credits = 2000 if plan == "team" else 1000
            credits_monthly = base_credits * quantity

            await conn.execute(
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

            # Also deposit subscription credits into the Team Wallet
            user_team_row = await conn.fetchrow(
                "SELECT team_id FROM users WHERE workos_user_id = $1", workos_user_id
            )
            if user_team_row and user_team_row["team_id"]:
                await conn.execute(
                    """
                    UPDATE teams
                    SET shared_credits_remaining = $1, plan = $2, seats_purchased = $3
                    WHERE id = $4
                    """,
                    credits_monthly,
                    plan,
                    quantity,
                    user_team_row["team_id"],
                )

            if email:
                post_commit_actions.append(
                    (
                        "send_subscription_started_email",
                        lambda email=email, plan=plan: email_service.send_subscription_started(email, plan),
                    )
                )
            post_commit_actions.append(
                (
                    "track_subscription_started",
                    lambda workos_user_id=workos_user_id, plan=plan: track_async(
                        workos_user_id,
                        "subscription_started",
                        {"plan": plan},
                    ),
                )
            )
        elif action_type == "credits":
            amount = int(session.get("metadata", {}).get("amount", "0"))

            # Fetch the user's team workspace
            user_team_row = await conn.fetchrow(
                "SELECT team_id FROM users WHERE workos_user_id = $1", workos_user_id
            )

            if user_team_row and user_team_row["team_id"]:
                # Deposit the purchased credits into the Team Wallet
                await conn.execute(
                    """
                    UPDATE teams
                    SET shared_credits_remaining = shared_credits_remaining + $1
                    WHERE id = $2
                    """,
                    amount,
                    user_team_row["team_id"],
                )
            else:
                # Solo user — deposit credits to personal balance
                await conn.execute(
                    """
                    UPDATE users
                    SET credits_remaining = credits_remaining + $1
                    WHERE workos_user_id = $2
                    """,
                    amount,
                    workos_user_id,
                )
        return post_commit_actions

    async def _handle_subscription_update(self, conn, subscription: dict) -> None:
        """Update subscription status (e.g. past_due, active) and sync seat quantity."""
        customer_id = subscription.get("customer")
        status = subscription.get("status")
        period_end = subscription.get("current_period_end")

        # Extract quantity to handle seat changes
        items = subscription.get("items", {}).get("data", [])
        quantity = items[0].get("quantity", 1) if items else 1

        user_row = await conn.fetchrow("SELECT plan FROM users WHERE stripe_customer_id = $1", customer_id)

        if user_row:
            plan = user_row["plan"]
            base_credits = 2000 if plan == "team" else 1000
            new_monthly = base_credits * quantity

            await conn.execute(
                """
                UPDATE users
                SET subscription_status = $1,
                    current_period_end = to_timestamp($2),
                    credits_monthly = $3
                WHERE stripe_customer_id = $4
                """,
                status,
                period_end,
                new_monthly,
                customer_id,
            )

            user_team_row = await conn.fetchrow(
                "SELECT team_id FROM users WHERE stripe_customer_id = $1",
                customer_id,
            )
            if user_team_row and user_team_row["team_id"]:
                await conn.execute(
                    """
                    UPDATE teams
                    SET plan = $1, seats_purchased = $2
                    WHERE id = $3
                    """,
                    plan,
                    quantity,
                    user_team_row["team_id"],
                )

    async def _handle_subscription_cancel(self, conn, subscription: dict) -> list[PostCommitAction]:
        """Handle cancellation -> downgrade to Free and zero out team wallet credits (H2)."""
        customer_id = subscription.get("customer")

        user_row = await conn.fetchrow(
            "SELECT workos_user_id, email, team_id FROM users WHERE stripe_customer_id = $1", customer_id
        )

        await conn.execute(
            """
            UPDATE users
            SET plan = 'free',
                subscription_status = 'cancelled',
                credits_monthly = 0,
                stripe_subscription_id = NULL
            WHERE stripe_customer_id = $1
            """,
            customer_id,
        )

        if user_row:
            if user_row["team_id"]:
                await conn.execute(
                    "UPDATE teams SET plan = 'free', shared_credits_remaining = 0, seats_purchased = 1 WHERE id = $1",
                    user_row["team_id"]
                )

            from src.services.analytics import track_async

            return [
                (
                    "track_subscription_canceled",
                    lambda workos_user_id=user_row["workos_user_id"]: track_async(
                        workos_user_id,
                        "subscription_canceled",
                        {},
                    ),
                )
            ]
        return []

    async def _handle_invoice_paid(self, conn, invoice: dict) -> None:
        """Trigger monthly credit replenishment when an invoice is fully paid."""
        reason = invoice.get("billing_reason")
        if reason == "subscription_cycle":
            customer_id = invoice.get("customer")

            # Reset credits to their monthly allowance (both user and team wallet)
            await conn.execute(
                """
                UPDATE users
                SET credits_remaining = credits_monthly
                WHERE stripe_customer_id = $1 AND plan != 'free'
                """,
                customer_id,
            )
            # Also reset the Team Wallet
            await conn.execute(
                """
                UPDATE teams t
                SET shared_credits_remaining = u.credits_monthly
                FROM users u
                WHERE u.team_id = t.id AND u.stripe_customer_id = $1 AND u.plan != 'free'
                """,
                customer_id,
            )
