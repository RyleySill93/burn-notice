import abc
import datetime
import os
import smtplib
import webbrowser
from email.message import EmailMessage

import boto3
import sentry_sdk
from botocore.exceptions import BotoCoreError, ClientError
from loguru import logger

from src import settings
from src.common.domain import BaseDomain
from src.common.nanoid import generate_custom_nanoid
from src.platform.sms.exceptions import SMSFailedToSend


class SMSMessage(BaseDomain):
    """
    Domain object for sending SMS messages.
    All SMS clients must accept this object.
    """

    phone_number: str  # E.164 format: +1234567890
    message: str
    sender_id: str | None = None  # Optional sender ID (e.g., "Burn Notice")


class AbstractSMSClient(abc.ABC):
    def __init__(self, *args, **kwargs): ...

    @abc.abstractmethod
    def send(self, sms: SMSMessage): ...


class MockSMSClient(AbstractSMSClient):
    """
    Mock SMS client for testing.
    Stores messages in memory instead of sending.
    """

    def __init__(self, *args, **kwargs):
        self.sms_catcher = self.get_sms_catcher()
        super().__init__(*args, **kwargs)

    def send(self, sms: SMSMessage):
        logger.info(f'[MOCK SMS] To: {sms.phone_number} | Message: {sms.message}')
        self.sms_catcher.append(sms)

    def get_sms_catcher(self) -> list:
        """
        Mock this object in tests to capture SMS messages
        """
        return []


class AWSSNSSMSClient(AbstractSMSClient):
    """
    AWS SNS SMS client.
    Uses AWS SNS to send SMS messages.

    Requirements:
    - AWS credentials with SNS permissions
    - Phone numbers in E.164 format (+1234567890)
    """

    def __init__(self, *args, **kwargs):
        # Require SNS-specific credentials - no fallback to generic AWS credentials
        if not settings.AWS_SNS_ACCESS_KEY_ID or not settings.AWS_SNS_SECRET_ACCESS_KEY:
            raise ValueError(
                'AWS_SNS_ACCESS_KEY_ID and AWS_SNS_SECRET_ACCESS_KEY must be configured for SMS functionality'
            )

        self.client = boto3.client(
            'sns',
            region_name=settings.AWS_REGION_NAME,
            aws_access_key_id=settings.AWS_SNS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SNS_SECRET_ACCESS_KEY,
        )
        super().__init__(*args, **kwargs)

    def send(self, sms: SMSMessage):
        """
        Send SMS using AWS SNS.

        Args:
            sms: SMSMessage with phone_number (E.164 format), message, and optional sender_id

        Raises:
            SMSFailedToSend: If SMS fails to send
        """
        logger.info(f'Sending SMS to {sms.phone_number}')

        try:
            # Prepare message attributes
            message_attributes = {
                'AWS.SNS.SMS.SMSType': {
                    'DataType': 'String',
                    'StringValue': 'Transactional',  # Optimized for delivery over cost
                }
            }

            # Add sender ID if provided (not supported in all regions/countries)
            if sms.sender_id:
                message_attributes['AWS.SNS.SMS.SenderID'] = {'DataType': 'String', 'StringValue': sms.sender_id}

            response = self.client.publish(
                PhoneNumber=sms.phone_number, Message=sms.message, MessageAttributes=message_attributes
            )

            logger.info(f'SMS sent successfully. MessageId: {response.get("MessageId")}')
            return response

        except (BotoCoreError, ClientError) as exc:
            logger.exception(f'Failed to send SMS to {sms.phone_number}')
            raise SMSFailedToSend(message=f'AWS SNS failed: {sms.phone_number}') from exc


class SMSMailpitClient(AbstractSMSClient):
    """
    Send SMS preview as HTML email to Mailpit.
    Perfect for staging environments - check SMS messages in Mailpit instead of sending real texts.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.smtp_host = settings.EMAIL_SMTP_HOST
        self.smtp_port = settings.EMAIL_SMTP_PORT

    def send(self, sms: SMSMessage):
        """Send SMS preview as an email to Mailpit"""
        html_content = self._generate_sms_html(sms)

        # Create email message
        msg = EmailMessage()
        msg['Subject'] = f'SMS to {sms.phone_number[:7]}***'
        msg['From'] = 'sms-preview@burn_notice.com'
        msg['To'] = 'sms-inbox@burn_notice.com'

        # Add HTML content
        msg.add_alternative(html_content, subtype='html')

        # Send to Mailpit
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.send_message(msg)
            logger.info(f'[MAILPIT SMS] Sent SMS preview to Mailpit: {sms.phone_number}')

    def _generate_sms_html(self, sms: SMSMessage) -> str:
        """Generate the phone-styled HTML preview"""
        masked_phone = self._mask_phone(sms.phone_number)

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>SMS to {masked_phone}</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    background: linear-gradient(135deg, #f5f5f5 0%, #e8e8e8 100%);
                    min-height: 100vh;
                    margin: 0;
                    padding: 0;
                }}
                .dev-banner {{
                    background: #000;
                    color: #fff;
                    padding: 15px 20px;
                    text-align: left;
                    font-size: 13px;
                    line-height: 1.6;
                    border-bottom: 3px solid #4CAF50;
                }}
                .dev-banner strong {{
                    color: #4CAF50;
                    font-weight: 600;
                }}
                .container {{
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: calc(100vh - 80px);
                    padding: 20px;
                }}
                .phone-container {{
                    background: #000;
                    border-radius: 40px;
                    padding: 15px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    max-width: 375px;
                    width: 100%;
                }}
                .phone-screen {{
                    background: #fff;
                    border-radius: 30px;
                    overflow: hidden;
                    box-shadow: inset 0 0 10px rgba(0,0,0,0.1);
                }}
                .status-bar {{
                    background: #f6f6f6;
                    padding: 8px 20px;
                    display: flex;
                    justify-content: space-between;
                    font-size: 12px;
                    color: #000;
                    border-bottom: 1px solid #e0e0e0;
                }}
                .message-header {{
                    background: #f6f6f6;
                    padding: 15px 20px;
                    border-bottom: 1px solid #e0e0e0;
                }}
                .contact-name {{
                    font-weight: 600;
                    font-size: 16px;
                    color: #000;
                }}
                .contact-number {{
                    font-size: 13px;
                    color: #8e8e93;
                    margin-top: 2px;
                }}
                .messages {{
                    background: #fff;
                    padding: 20px;
                    min-height: 300px;
                }}
                .message-bubble {{
                    background: #e5e5ea;
                    border-radius: 18px;
                    padding: 10px 15px;
                    max-width: 80%;
                    word-wrap: break-word;
                    margin-bottom: 10px;
                    animation: slideIn 0.3s ease-out;
                }}
                .timestamp {{
                    font-size: 11px;
                    color: #8e8e93;
                    text-align: center;
                    margin: 15px 0;
                }}
                @keyframes slideIn {{
                    from {{
                        opacity: 0;
                        transform: translateY(10px);
                    }}
                    to {{
                        opacity: 1;
                        transform: translateY(0);
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="dev-banner">
                <strong>Staging SMS Preview</strong><br>
                To: {sms.phone_number}<br>
                From: {sms.sender_id or 'Burn Notice'}<br>
                Message Length: {len(sms.message)} characters
            </div>
            <div class="container">
                <div class="phone-container">
                    <div class="phone-screen">
                        <div class="status-bar">
                            <span>9:41</span>
                            <span>📶 🔋</span>
                        </div>
                        <div class="message-header">
                            <div class="contact-name">{sms.sender_id or 'Burn Notice'}</div>
                            <div class="contact-number">To: {masked_phone}</div>
                        </div>
                        <div class="messages">
                            <div class="timestamp">{datetime.datetime.now().strftime('%B %d, %Y at %I:%M %p')}</div>
                            <div class="message-bubble">
                                {sms.message}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

    def _mask_phone(self, phone_number: str) -> str:
        """Mask phone number for privacy: +1****567890"""
        if len(phone_number) > 8:
            return f'{phone_number[:2]}****{phone_number[-6:]}'
        return phone_number


class SMSFileClient(AbstractSMSClient):
    """
    Write SMS messages to HTML files styled like a phone message.
    Opens in browser for development.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_path = os.path.join(settings.BASE_DIR, 'tmp')

        os.makedirs(self.file_path, exist_ok=True)
        # Make sure that sms file_path is writable.
        if not os.access(self.file_path, os.W_OK):
            raise ValueError(f"Can't write to directory: {self.file_path}")

    def send(self, sms: SMSMessage):
        file_path = self.write_sms(sms)
        webbrowser.open(f'file:///{file_path}')

    def write_sms(self, sms: SMSMessage) -> str:
        """Create a phone-styled HTML preview of the SMS message."""
        # Mask phone number for privacy
        masked_phone = self._mask_phone(sms.phone_number)

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>SMS to {masked_phone}</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    background: linear-gradient(135deg, #f5f5f5 0%, #e8e8e8 100%);
                    min-height: 100vh;
                    margin: 0;
                    padding: 0;
                }}
                .dev-banner {{
                    background: #000;
                    color: #fff;
                    padding: 15px 20px;
                    text-align: left;
                    font-size: 13px;
                    line-height: 1.6;
                    border-bottom: 3px solid #4CAF50;
                }}
                .dev-banner strong {{
                    color: #4CAF50;
                    font-weight: 600;
                }}
                .container {{
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: calc(100vh - 45px);
                    padding: 20px;
                }}
                .phone-container {{
                    background: #000;
                    border-radius: 40px;
                    padding: 15px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    max-width: 375px;
                    width: 100%;
                }}
                .phone-screen {{
                    background: #fff;
                    border-radius: 30px;
                    overflow: hidden;
                    box-shadow: inset 0 0 10px rgba(0,0,0,0.1);
                }}
                .status-bar {{
                    background: #f6f6f6;
                    padding: 8px 20px;
                    display: flex;
                    justify-content: space-between;
                    font-size: 12px;
                    color: #000;
                    border-bottom: 1px solid #e0e0e0;
                }}
                .message-header {{
                    background: #f6f6f6;
                    padding: 15px 20px;
                    border-bottom: 1px solid #e0e0e0;
                }}
                .contact-name {{
                    font-weight: 600;
                    font-size: 16px;
                    color: #000;
                }}
                .contact-number {{
                    font-size: 13px;
                    color: #8e8e93;
                    margin-top: 2px;
                }}
                .messages {{
                    background: #fff;
                    padding: 20px;
                    min-height: 300px;
                }}
                .message-bubble {{
                    background: #e5e5ea;
                    border-radius: 18px;
                    padding: 10px 15px;
                    max-width: 80%;
                    word-wrap: break-word;
                    margin-bottom: 10px;
                    animation: slideIn 0.3s ease-out;
                }}
                .timestamp {{
                    font-size: 11px;
                    color: #8e8e93;
                    text-align: center;
                    margin: 15px 0;
                }}
                @keyframes slideIn {{
                    from {{
                        opacity: 0;
                        transform: translateY(10px);
                    }}
                    to {{
                        opacity: 1;
                        transform: translateY(0);
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="dev-banner">
                <strong>Development Mode</strong><br>
                To: {sms.phone_number}<br>
                From: {sms.sender_id or 'Burn Notice'}<br>
                Message Length: {len(sms.message)} characters
            </div>
            <div class="container">
                <div class="phone-container">
                    <div class="phone-screen">
                        <div class="status-bar">
                            <span>9:41</span>
                            <span>📶 🔋</span>
                        </div>
                        <div class="message-header">
                            <div class="contact-name">{sms.sender_id or 'Burn Notice'}</div>
                            <div class="contact-number">To: {masked_phone}</div>
                        </div>
                        <div class="messages">
                            <div class="timestamp">{datetime.datetime.now().strftime('%B %d, %Y at %I:%M %p')}</div>
                            <div class="message-bubble">
                                {sms.message}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        file_with_path = self._get_full_filename(sms)
        with open(file_with_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f'[FILE SMS] Saved to: {file_with_path}')
        return file_with_path

    def _mask_phone(self, phone_number: str) -> str:
        """Mask phone number for privacy: +1****567890"""
        if len(phone_number) > 8:
            return f'{phone_number[:2]}****{phone_number[-6:]}'
        return phone_number

    def _get_full_filename(self, sms: SMSMessage) -> str:
        """Return a unique file name."""
        timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        random = generate_custom_nanoid(size=4)
        masked_phone = self._mask_phone(sms.phone_number)
        file_name = f'{timestamp}-{random}-sms-{masked_phone}.html'
        file_with_path = os.path.join(self.file_path, file_name)
        return file_with_path


class ResilientLiveSMSClient(AbstractSMSClient):
    """
    Resilient SMS client with failover support.
    Tries multiple SMS providers in priority order.

    Current priority:
    1. AWS SNS (primary)
    2. Future: Twilio, etc.
    """

    CLIENT_PRIORITY_ORDER = [
        AWSSNSSMSClient,
        # Future: TwilioSMSClient,
    ]

    def send(self, sms: SMSMessage):
        message_sent = False

        for sms_client_class in self.CLIENT_PRIORITY_ORDER:
            client = sms_client_class()
            try:
                client.send(sms)
            except SMSFailedToSend:
                logger.warning(f'{sms_client_class.__name__} failed to send SMS')
                sentry_sdk.capture_exception()
            except Exception as exc:
                logger.exception(f'Unexpected error with {sms_client_class.__name__}')
                raise SMSFailedToSend(message=f'Unexpected failure using {sms_client_class.__name__}') from exc
            else:
                # Success
                message_sent = True
                break

        if not message_sent:
            raise SMSFailedToSend(message=f'Exhausted all SMS clients for {sms.phone_number}')
