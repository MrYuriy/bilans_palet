"""Sending mail over SMTP (credentials in .env)."""

import asyncio
import smtplib
from email.message import EmailMessage

from app.core.config import settings


class Mailer:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        sender: str,
        starttls: bool,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.sender = sender
        self.starttls = starttls

    def _send(self, recipients: list[str], subject: str, body: str) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.sender
        message["To"] = ", ".join(recipients)
        message.set_content(body)
        with smtplib.SMTP(self.host, self.port, timeout=20) as server:
            if self.starttls:
                server.starttls()
            if self.username:
                server.login(self.username, self.password)
            server.send_message(message)

    async def send(self, recipients: list[str], subject: str, body: str) -> None:
        # smtplib blocks; keep the event loop free.
        await asyncio.to_thread(self._send, recipients, subject, body)


def configured_mailer() -> Mailer | None:
    """The mailer from the settings, or None while SMTP_HOST is not set."""
    app = settings.app
    if not app.SMTP_HOST:
        return None
    return Mailer(
        app.SMTP_HOST,
        app.SMTP_PORT,
        app.SMTP_USER,
        app.SMTP_PASSWORD,
        app.SMTP_FROM or app.SMTP_USER,
        app.SMTP_STARTTLS,
    )
