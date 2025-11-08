"""Email service for sending transactional emails via Mailgun."""

import logging
from typing import Any

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via Mailgun API."""

    def __init__(self, settings: Settings):
        """Initialize email service with settings."""
        self.settings = settings
        self.api_key = settings.mailgun_api_key
        self.domain = settings.mailgun_domain
        self.from_email = settings.mailgun_from_email
        self.base_url = f"https://api.mailgun.net/v3/{self.domain}/messages"

    def is_configured(self) -> bool:
        """Check if Mailgun is properly configured."""
        return bool(self.api_key and self.domain)

    async def send_email(
        self,
        to: str,
        subject: str,
        text: str,
        html: str | None = None,
    ) -> bool:
        """
        Send an email via Mailgun API.

        Args:
            to: Recipient email address
            subject: Email subject
            text: Plain text body
            html: Optional HTML body

        Returns:
            True if email was sent successfully, False otherwise

        Raises:
            ValueError: If Mailgun is not configured
        """
        if not self.is_configured():
            logger.error(
                "Mailgun is not configured. Set YT_MAILGUN_API_KEY and YT_MAILGUN_DOMAIN."
            )
            raise ValueError("Email service is not configured")

        data: dict[str, Any] = {
            "from": self.from_email,
            "to": to,
            "subject": subject,
            "text": text,
        }

        if html:
            data["html"] = html

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    auth=("api", self.api_key),
                    data=data,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    logger.info(f"Email sent successfully to {to}: {subject}")
                    return True
                else:
                    logger.error(
                        f"Failed to send email to {to}. Status: {response.status_code}, "
                        f"Response: {response.text}"
                    )
                    return False

        except httpx.HTTPError as e:
            logger.error(f"HTTP error while sending email to {to}: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error while sending email to {to}: {e}", exc_info=True
            )
            return False


async def send_account_deletion_email(
    email: str, display_name: str, confirmation_link: str
) -> bool:
    """
    Send account deletion confirmation email.

    Args:
        email: User's email address
        display_name: User's display name
        confirmation_link: Full URL to confirm deletion

    Returns:
        True if email was sent successfully, False otherwise
    """
    settings = get_settings()
    service = EmailService(settings)

    subject = "Confirm Account Deletion - YouTube Feed Aggregator"

    text = f"""Hi {display_name},

You have requested to delete your YouTube Feed Aggregator account.

To confirm this action, please click the link below within 1 hour:

{confirmation_link}

⚠️ WARNING: This action is permanent and cannot be undone.

The following data will be permanently deleted:
• Your account and profile
• All subscription data
• All watched video history

If you did not request this, please ignore this email. Your account will remain active.

---
YouTube Feed Aggregator
"""

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
        <h1 style="color: white; margin: 0; font-size: 24px;">YouTube Feed Aggregator</h1>
    </div>

    <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #e5e7eb;">
        <h2 style="color: #1f2937; margin-top: 0;">Hi {display_name},</h2>

        <p style="color: #4b5563;">You have requested to delete your YouTube Feed Aggregator account.</p>

        <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 4px;">
            <p style="margin: 0; color: #856404; font-weight: bold;">⚠️ WARNING: This action is permanent and cannot be undone.</p>
        </div>

        <p style="color: #4b5563;">To confirm this action, please click the button below within <strong>1 hour</strong>:</p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{confirmation_link}" style="display: inline-block; background: #dc2626; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px;">Confirm Account Deletion</a>
        </div>

        <div style="background: #fee2e2; border-left: 4px solid #dc2626; padding: 15px; margin: 20px 0; border-radius: 4px;">
            <p style="margin: 0 0 10px 0; color: #991b1b; font-weight: bold;">This will permanently delete:</p>
            <ul style="margin: 0; padding-left: 20px; color: #991b1b;">
                <li>Your account and profile</li>
                <li>All subscription data</li>
                <li>All watched video history</li>
            </ul>
        </div>

        <p style="color: #6b7280; font-size: 14px; margin-top: 30px;">If you did not request this, please ignore this email. Your account will remain active.</p>

        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">

        <p style="color: #9ca3af; font-size: 12px; text-align: center; margin: 0;">YouTube Feed Aggregator</p>
    </div>
</body>
</html>
"""

    return await service.send_email(email, subject, text, html)


async def send_data_export_ready_email(
    email: str, display_name: str, download_link: str
) -> bool:
    """
    Send email notification when data export is ready.

    Args:
        email: User's email address
        display_name: User's display name
        download_link: Full URL to download the export

    Returns:
        True if email was sent successfully, False otherwise
    """
    settings = get_settings()
    service = EmailService(settings)

    subject = "Your Data Export is Ready - YouTube Feed Aggregator"

    text = f"""Hi {display_name},

Your requested data export is now ready for download.

Download your data here (link expires in {settings.export_ttl_hours} hours):
{download_link}

Your export includes:
• User profile
• Subscription data
• Watched video history

---
YouTube Feed Aggregator
"""

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
        <h1 style="color: white; margin: 0; font-size: 24px;">YouTube Feed Aggregator</h1>
    </div>

    <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #e5e7eb;">
        <h2 style="color: #1f2937; margin-top: 0;">Hi {display_name},</h2>

        <p style="color: #4b5563;">Your requested data export is now ready for download.</p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{download_link}" style="display: inline-block; background: #2563eb; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px;">Download Your Data</a>
        </div>

        <div style="background: #dbeafe; border-left: 4px solid #2563eb; padding: 15px; margin: 20px 0; border-radius: 4px;">
            <p style="margin: 0 0 10px 0; color: #1e40af; font-weight: bold;">Your export includes:</p>
            <ul style="margin: 0; padding-left: 20px; color: #1e40af;">
                <li>User profile</li>
                <li>Subscription data</li>
                <li>Watched video history</li>
            </ul>
        </div>

        <p style="color: #6b7280; font-size: 14px; margin-top: 30px;">⏱️ This download link will expire in <strong>{settings.export_ttl_hours} hours</strong>.</p>

        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">

        <p style="color: #9ca3af; font-size: 12px; text-align: center; margin: 0;">YouTube Feed Aggregator</p>
    </div>
</body>
</html>
"""

    return await service.send_email(email, subject, text, html)
