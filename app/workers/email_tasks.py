"""Email notification tasks dispatched via Celery."""

from pathlib import Path

import jinja2
import resend
import structlog

from app.core.config import get_settings
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

# Initialize Jinja2 Environment
templates_dir = Path(__file__).resolve().parent.parent / "templates"
jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir))


def _dispatch_email(to_email: str, subject: str, html_body: str) -> None:
    """Route email via Resend (staging) or SES (production)."""
    settings = get_settings()
    if settings.APP_ENV in ("development", "staging"):
        resend.api_key = settings.RESEND_API_KEY
        sender = settings.RESEND_SENDER
        params = {
            "from": sender,
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        }
        resend.Emails.send(params)
    else:
        # SES API call would go here:
        # ses_client.send_email(...)
        pass


@celery_app.task(name="send_verification_email", bind=True, max_retries=3)
def send_verification_email(self, email: str, token: str) -> bool:
    """Send email verification link.

    Retries up to 3 times with exponential backoff.
    """
    try:
        logger.info("sending_verification_email", email=email)
        template = jinja_env.get_template("emails/verification.html")

        name = email.split("@")[0].capitalize()
        settings = get_settings()
        verification_link = f"{settings.FRONTEND_URL}/verify?token={token}"

        html_body = template.render(
            token=token,
            name=name,
            email=email,
            verification_link=verification_link,
            company_name="Glowey",
            team_name="The Glowey Team",
            company_address="123 Skincare Lane, Beauty City",
            logo_url="",  # Fall back to frontend logo
            frontend_url=settings.FRONTEND_URL,
            hero_image_url=f"{settings.FRONTEND_URL}/hero-image.png",
            unsubscribe_link=f"{settings.FRONTEND_URL}/unsubscribe",
            current_year="2026",
        )

        _dispatch_email(email, "Verify your Glowey account", html_body)
        return True
    except Exception as exc:
        logger.error("verification_email_failed", email=email, error=str(exc))
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))  # noqa: B904


@celery_app.task(name="send_password_reset_email", bind=True, max_retries=3)
def send_password_reset_email(self, email: str, token: str) -> bool:
    """Send password reset link."""
    try:
        logger.info("sending_password_reset_email", email=email)
        html_body = f"<p>Your password reset token is: <strong>{token}</strong></p>"
        _dispatch_email(email, "Password Reset Request", html_body)
        return True
    except Exception as exc:
        logger.error("password_reset_email_failed", email=email, error=str(exc))
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@celery_app.task(name="send_order_confirmation", bind=True, max_retries=3)
def send_order_confirmation(self, order_id: str) -> bool:
    """Send order confirmation to customer and vendor."""
    try:
        logger.info("sending_order_confirmation", order_id=order_id)
        html_body = f"<p>Your order <strong>{order_id}</strong> has been confirmed.</p>"
        _dispatch_email("customer@example.com", f"Order Confirmation: {order_id}", html_body)
        return True
    except Exception as exc:
        logger.error("order_confirmation_failed", order_id=order_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@celery_app.task(name="send_order_shipped", bind=True, max_retries=3)
def send_order_shipped(self, order_id: str) -> bool:
    """Notify customer that their order has shipped."""
    try:
        logger.info("sending_order_shipped", order_id=order_id)
        html_body = f"<p>Your order <strong>{order_id}</strong> has shipped.</p>"
        _dispatch_email("customer@example.com", f"Order Shipped: {order_id}", html_body)
        return True
    except Exception as exc:
        logger.error("order_shipped_email_failed", order_id=order_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@celery_app.task(name="send_payout_notification", bind=True, max_retries=3)
def send_payout_notification(self, vendor_email: str, amount: str) -> bool:
    """Notify vendor about successful payout."""
    try:
        logger.info("sending_payout_notification", email=vendor_email, amount=amount)
        html_body = f"<p>A payout of <strong>{amount}</strong> has been sent to your account.</p>"
        _dispatch_email(vendor_email, "Payout Successful", html_body)
        return True
    except Exception as exc:
        logger.error("payout_notification_failed", email=vendor_email, error=str(exc))
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))
