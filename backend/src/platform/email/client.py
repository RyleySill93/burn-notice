import abc
import datetime
import os
import smtplib
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import boto3
import resend
import sentry_sdk
from botocore.exceptions import BotoCoreError, ClientError
from loguru import logger
from pydantic import model_validator
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from slugify import slugify

from src import settings
from src.common.domain import BaseDomain
from src.common.nanoid import generate_custom_nanoid
from src.platform.email.exceptions import EmailFailedToSend


class EmailClientDomain(BaseDomain):
    """
    All clients must take in this object to send mail
    """

    # Something like Burn Notice <no-reply@burn_notice.com
    from_email: tuple[str, str] | None = None
    to_emails: list[str] | None = None
    bcc_emails: list[str] | None = None
    subject: str | None = None
    plain_text_content: str | None = None
    html_content: str | None = None

    @model_validator(mode='after')
    def validate_content(self):
        if self.plain_text_content is None and self.html_content is None:
            raise ValueError('Must supply at least one of a plain_text_content or html_content')

        return self


class AbstractEmailClient(abc.ABC):
    def __init__(self, *args, **kwargs): ...

    @abc.abstractmethod
    def send(self, message: EmailClientDomain): ...


class MailPitClient(AbstractEmailClient):
    def __init__(self, *args, **kwargs):
        # Defaults for now
        self.smtp_host = settings.EMAIL_SMTP_HOST
        self.smtp_port = settings.EMAIL_SMTP_PORT
        super().__init__(*args, **kwargs)

    def send(self, message: EmailClientDomain):
        # Create the base text message
        msg = EmailMessage()
        msg['Subject'] = message.subject
        msg['From'] = message.from_email
        msg['To'] = ', '.join(message.to_emails)
        if message.bcc_emails:
            # BCC recipients do not appear in the headers
            # They are included in the SMTP send command separately
            msg['Bcc'] = ', '.join(message.bcc_emails)

        # Text content
        if message.plain_text_content:
            msg.set_content(message.plain_text_content)

        # HTML content
        if message.html_content:
            msg.add_alternative(message.html_content, subtype='html')

        # Send message
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.send_message(msg)
            logger.info(f'Message sent to MailPit server at {self.smtp_host}:{self.smtp_port}')


class MockEmailClient(AbstractEmailClient):
    def __init__(self, *args, **kwargs):
        self.email_catcher = self.get_email_catcher()
        super().__init__(*args, **kwargs)

    def send(self, message: EmailClientDomain):
        self.email_catcher.append(message)

    def get_email_catcher(self) -> list:
        """
        Mock this object in tests to attach emails to it
        """
        return []


class SendGridAPIEmailClient(SendGridAPIClient):
    def __init__(self, *args, **kwargs):
        super().__init__(
            api_key=settings.SENDGRID_API_KEY,
        )

    def send(self, message: EmailClientDomain):
        sendgrid_mail = Mail(
            from_email=message.from_email,
            to_emails=message.to_emails,
            subject=message.subject,
            plain_text_content=message.plain_text_content,
            html_content=message.html_content,
        )
        for bcc in message.bcc_emails:
            sendgrid_mail.add_bcc(bcc)

        response = super().send(sendgrid_mail)
        if 200 <= response.status_code < 300:
            print('Request was successful.')
        else:
            raise EmailFailedToSend(message=f'status_code:{response.status_code} {message.subject}-{message.to_emails}')


class ResendEmailClient(AbstractEmailClient):
    def __init__(self, *args, **kwargs):
        resend.api_key = settings.RESEND_API_KEY
        super().__init__(*args, **kwargs)

    def send(self, message: EmailClientDomain):
        from_email = f'{message.from_email[1]} <{message.from_email[0]}>'

        params: resend.Emails.SendParams = {
            'from': from_email,
            'to': message.to_emails,
            'subject': message.subject,
        }

        if message.bcc_emails:
            params['bcc'] = message.bcc_emails

        if message.html_content:
            params['html'] = message.html_content

        if message.plain_text_content:
            params['text'] = message.plain_text_content

        try:
            response = resend.Emails.send(params)
            logger.info(f'Resend email sent: {response}')
        except Exception as exc:
            logger.exception(f'Resend failed to send email: {exc}')
            raise EmailFailedToSend(message=f'{message.subject}-{message.to_emails}') from exc


class EmailFileClient(AbstractEmailClient):
    """
    Write emails to a file and return a mock response
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_path = os.path.join(settings.BASE_DIR, 'tmp')

        os.makedirs(self.file_path, exist_ok=True)
        # Make sure that email file_path is writable.
        if not os.access(self.file_path, os.W_OK):
            raise ValueError(f"Can't write to directory: {self.file_path}")

    def send(self, message: EmailClientDomain):
        import webbrowser

        file_path = self.write_email(message)
        webbrowser.open(f'file:///{file_path}')

    def write_email(self, message: EmailClientDomain) -> str:
        if message.html_content is not None:
            # Handle formatting for HTML views
            metadata_html_lines = [
                f'<strong>From:</strong> {message.from_email[1]} ({message.from_email[0]})'
                if message.from_email
                else '<strong>From:</strong> None',
                f"<strong>To:</strong> {', '.join(message.to_emails)}"
                if message.to_emails
                else '<strong>To:</strong> None',
                f"<strong>Bcc:</strong> {', '.join(message.bcc_emails)}"
                if message.bcc_emails
                else '<strong>Bcc:</strong> None',
                f'<strong>Subject:</strong> {message.subject}' if message.subject else '<strong>Subject:</strong> None',
            ]
            metadata_html_content = '<br>'.join(metadata_html_lines)
            # Wrap HTML metadata in a styled block
            metadata_html = f"""
                 <div style="background-color: #f0f0f0; padding: 10px; margin-bottom: 20px; border-radius: 5px; font-family: Arial, sans-serif; font-size: 14px;">
                     <p>{metadata_html_content}</p>
                 </div>
             """
            content = metadata_html + (message.html_content or '')
        else:
            # Handle formatting for plain text views
            metadata_plain_lines = [
                f'From: {message.from_email[1]} ({message.from_email[0]})' if message.from_email else 'From: None',
                f"To: {', '.join(message.to_emails)}" if message.to_emails else 'To: None',
                f"Bcc: {', '.join(message.bcc_emails)}" if message.bcc_emails else 'Bcc: None',
                f'Subject: {message.subject}' if message.subject else 'Subject: None',
            ]
            metadata_plain_content = '\n'.join(metadata_plain_lines)
            content = metadata_plain_content + '\n\n' + (message.plain_text_content or '')

        file_with_path = self._get_full_filename(message)
        with open(file_with_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return file_with_path

    def _get_full_filename(self, message: EmailClientDomain):
        """Return a unique file name."""
        timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        random = generate_custom_nanoid(size=4)
        file_name = f'{timestamp}-{random}-{slugify(str(message.subject))}.html'
        file_with_path = os.path.join(self.file_path, file_name)
        return file_with_path


class AWSEmailClient(AbstractEmailClient):
    def __init__(self, *args, **kwargs):
        self.client = boto3.client(
            'ses',
            region_name=settings.AWS_REGION_NAME,
            aws_access_key_id=settings.AWS_SES_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SES_SECRET_ACCESS_KEY,
        )
        super().__init__(*args, **kwargs)

    def send(self, message: EmailClientDomain):
        """
        Send an email using AWS SES API
        """
        mmp = MIMEMultipart('alternative')

        if message.plain_text_content is not None:
            part1 = MIMEText(message.plain_text_content, 'plain')
            mmp.attach(part1)

        if message.html_content is not None:
            part2 = MIMEText(message.html_content, 'html')
            mmp.attach(part2)

        mmp['Subject'] = message.subject
        mmp['From'] = f'{message.from_email[1]} <{message.from_email[0]}>'
        # mmp['From'] = message.from_email[0]
        mmp['To'] = ', '.join(message.to_emails)
        mmp['Bcc'] = ', '.join(message.bcc_emails)

        logger.info(f'sending {message.subject} email to {message.to_emails}')
        try:
            response = self.client.send_raw_email(
                Source=message.from_email[0],
                Destinations=message.to_emails + message.bcc_emails,
                RawMessage={'Data': mmp.as_string()},
            )
        except (BotoCoreError, ClientError) as exc:
            logger.exception(exc)
            raise EmailFailedToSend(message=f'{message.subject}-{message.to_emails}')

        return response


class ResilientLiveEmailClient(AbstractEmailClient):
    CLIENT_PRIORITY_ORDER = [
        # Primary
        ResendEmailClient,
        # Secondaries...
        SendGridAPIEmailClient,
        AWSEmailClient,
    ]

    def send(self, message: EmailClientDomain):
        message_sent = False
        for email_client in self.CLIENT_PRIORITY_ORDER:
            client = email_client()
            try:
                client.send(message)
            except EmailFailedToSend:
                logger.warning(f'{email_client} failed to send!')
                sentry_sdk.capture_exception()
            except Exception as exc:
                raise EmailFailedToSend(message=f'Unexpected failure using {email_client}') from exc
            else:
                # Success
                message_sent = True
                break

        if not message_sent:
            raise EmailFailedToSend(message=f'Exhausted all clients -> {message.subject}-{message.to_emails}')
