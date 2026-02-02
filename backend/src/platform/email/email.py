from typing import Any

from pydantic import EmailStr, Field

from src.common.domain import BaseDomain
from src.network.database.session import on_commit
from src.platform.email.tasks import _send_template_email
from src.platform.email.utils import render_template


class Email(BaseDomain):
    subject: str
    recipients: list[EmailStr]
    template_name: str
    context: dict = Field(default_factory=lambda: {})

    def render_template_with_context(self):
        return render_template(
            template_name=self.template_name,
            context=dict(
                # subject is used for the email's title
                subject=self.subject,
                **self.context,
            ),
        )

    def send(
        self,
        send_on_commit: bool = True,
        send_async: bool = True,
    ):
        # make sure the email generates before dispatching send
        self.render_template_with_context()
        kwargs = dict(
            subject=self.subject,
            recipients=self.recipients,
            context=self.context,
            template_name=self.template_name,
        )
        self._send(
            send_kwargs=kwargs,
            send_on_commit=send_on_commit,
            send_async=send_async,
        )

    def _send(
        self,
        send_kwargs: dict[str, Any],
        send_on_commit: bool = True,
        send_async: bool = True,
    ):
        """
        Broken out to be easily patched during testing
        """
        if send_async:
            # Send this off to a worker
            send_function = _send_template_email.send
        else:
            send_function = _send_template_email

        if send_on_commit:
            # Send this at the end of transaction
            on_commit(lambda session: send_function(**send_kwargs))
        else:
            send_function(**send_kwargs)
