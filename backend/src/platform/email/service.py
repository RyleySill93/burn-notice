from loguru import logger

from src import settings
from src.common.utils import make_lazy
from src.platform.email import client

EMAIL_CLIENT_MAP = {
    'file': client.EmailFileClient,
    'mailpit': client.MailPitClient,
    'live': client.ResilientLiveEmailClient,
}

EmailClient = EMAIL_CLIENT_MAP[settings.EMAIL_BACKEND]

if settings.USE_MOCK_EMAIL_CLIENT:
    # Override with mock client
    EmailClient = client.MockEmailClient


class EmailService:
    def __init__(self):
        # Don't establish any connections on instantiation!
        self.client: client.AbstractEmailClient = make_lazy(self._get_client)

    def _get_client(self):
        return EmailClient()

    @classmethod
    def factory(cls) -> 'EmailService':
        return cls()

    def _enhance_subject(self, subject: str) -> str:
        """
        Append environment to non production mail
        """
        if settings.ENVIRONMENT != 'production':
            subject += f' - [{settings.ENVIRONMENT}]'

        return subject

    def send(
        self,
        subject: str,
        recipients: list[str],
        plain_message: str | None = None,
        html_message: str | None = None,
    ):
        """
        Send an email using client configured by environment
        """
        message = client.EmailClientDomain(
            # Something like Burn Notice <no-reply@burn_notice.com
            from_email=(settings.EMAIL_FROM_ADDRESS, settings.COMPANY_NAME),
            to_emails=recipients,
            bcc_emails=['app-mail@burn_notice.com'],
            subject=self._enhance_subject(subject),
            plain_text_content=plain_message,
            html_content=html_message,
        )
        logger.info(f'sending {subject} email to {recipients}')
        self.client.send(message)
