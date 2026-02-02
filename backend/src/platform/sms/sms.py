"""
SMS service wrapper similar to Email service.
Provides a simple interface for sending SMS messages.
"""

from loguru import logger

from src import settings
from src.platform.sms.client import (
    AbstractSMSClient,
    MockSMSClient,
    ResilientLiveSMSClient,
    SMSFileClient,
    SMSMailpitClient,
    SMSMessage,
)


class SMS:
    """
    High-level SMS sending interface.
    Automatically selects the appropriate SMS client based on environment.

    Usage:
        sms = SMS(
            phone_number="+12345678900",
            message="Your verification code is: 123456"
        )
        sms.send()
    """

    def __init__(
        self,
        phone_number: str,
        message: str,
        sender_id: str | None = 'Burn Notice',
        client: AbstractSMSClient | None = None,
    ):
        """
        Initialize SMS message.

        Args:
            phone_number: Recipient phone number in E.164 format (+1234567890)
            message: Message content (max 160 chars for single SMS)
            sender_id: Optional sender ID (not supported in all regions)
            client: Optional custom SMS client (defaults to environment-based selection)
        """
        self.phone_number = phone_number
        self.message = message
        self.sender_id = sender_id

        # Select appropriate client based on SMS_BACKEND setting
        if client is not None:
            self.client = client
        elif settings.USE_MOCK_SMS_CLIENT:
            # For testing - captures messages in memory
            self.client = MockSMSClient()
        elif settings.SMS_BACKEND == 'file':
            # Development - creates phone-styled HTML previews in browser
            self.client = SMSFileClient()
        elif settings.SMS_BACKEND == 'mailpit':
            # Staging - sends SMS preview as email to Mailpit
            self.client = SMSMailpitClient()
        elif settings.SMS_BACKEND == 'live':
            # Production - sends real SMS via AWS SNS (with Twilio fallback in future)
            self.client = ResilientLiveSMSClient()
        else:
            # Default to file for safety
            logger.warning(f'Unknown SMS_BACKEND: {settings.SMS_BACKEND}, using SMSFileClient')
            self.client = SMSFileClient()

    def send(self):
        """Send the SMS message"""
        sms_domain = SMSMessage(
            phone_number=self.phone_number,
            message=self.message,
            sender_id=self.sender_id,
        )
        self.client.send(sms_domain)
        logger.info(f'SMS sent to {self.phone_number}')
