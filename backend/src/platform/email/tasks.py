import dramatiq

from src.platform.email.service import EmailService
from src.platform.email.utils import render_template


@dramatiq.actor(max_retries=0)
def _send_template_email(subject, recipients, context, template_name):
    html_message = render_template(
        template_name=template_name,
        context=context,
    )

    service = EmailService.factory()
    service.send(
        subject=subject,
        recipients=recipients,
        html_message=html_message,
    )
