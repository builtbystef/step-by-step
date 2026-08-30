import logging
import smtplib
from collections.abc import Callable
from dataclasses import dataclass, field
from email.message import EmailMessage
from functools import lru_cache
from os import environ
from typing import Protocol

import httpx

log = logging.getLogger(__name__)

MAILER_VARIABLE = "MAILER"

MAIL_FROM_VARIABLE = "MAIL_FROM"

DEFAULT_MAIL_FROM = "step-by-step@localhost"

SMTP_HOST_VARIABLE = "SMTP_HOST"
SMTP_PORT_VARIABLE = "SMTP_PORT"
SMTP_USERNAME_VARIABLE = "SMTP_USERNAME"
SMTP_PASSWORD_VARIABLE = "SMTP_PASSWORD"

DEFAULT_SMTP_PORT = 587

SMTP_TIMEOUT = 30

RESEND_API_KEY_VARIABLE = "RESEND_API_KEY"
RESEND_ENDPOINT = "https://api.resend.com/emails"
RESEND_TIMEOUT = 30


class MailerConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Message:
    to: str
    subject: str
    text: str


class Mailer(Protocol):
    def send(self, message: Message) -> None: ...


@dataclass(slots=True)
class ConsoleMailer:
    sender: str = DEFAULT_MAIL_FROM
    outbox: list[Message] = field(default_factory=list)

    def send(self, message: Message) -> None:
        log.info(
            "mail from %s to %s: %s\n%s",
            self.sender,
            message.to,
            message.subject,
            message.text,
        )
        self.outbox.append(message)


def configured(variable: str) -> str:
    value = environ.get(variable, "").strip()
    if not value:
        raise MailerConfigurationError(f"{variable} is not set")
    return value


class SmtpConnection(Protocol):
    def ehlo(self) -> object: ...
    def has_extn(self, opt: str) -> bool: ...
    def starttls(self) -> object: ...
    def login(self, user: str, password: str) -> object: ...
    def send_message(self, msg: EmailMessage) -> object: ...
    def quit(self) -> object: ...


type OpenSmtp = Callable[[str, int], SmtpConnection]


def open_smtp(host: str, port: int) -> SmtpConnection:
    return smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT)


@dataclass(frozen=True, slots=True)
class SmtpMailer:
    sender: str
    host: str
    port: int = DEFAULT_SMTP_PORT
    credentials: tuple[str, str] | None = None
    connect: OpenSmtp = open_smtp

    def send(self, message: Message) -> None:
        connection = self.connect(self.host, self.port)
        try:
            connection.ehlo()
            if connection.has_extn("starttls"):
                connection.starttls()
                # Capabilities may change after TLS negotiation.
                connection.ehlo()
            if self.credentials is not None:
                connection.login(*self.credentials)
            connection.send_message(as_email(message, self.sender))
        finally:
            connection.quit()


def as_email(message: Message, sender: str) -> EmailMessage:
    mail = EmailMessage()
    mail["From"] = sender
    mail["To"] = message.to
    mail["Subject"] = message.subject
    mail.set_content(message.text)
    return mail


def smtp_port() -> int:
    port = environ.get(SMTP_PORT_VARIABLE, "").strip()
    if not port:
        return DEFAULT_SMTP_PORT
    try:
        return int(port)
    except ValueError:
        raise MailerConfigurationError(
            f"{SMTP_PORT_VARIABLE}={port!r} is not a port number"
        ) from None


def smtp_credentials() -> tuple[str, str] | None:
    username = environ.get(SMTP_USERNAME_VARIABLE, "").strip()
    password = environ.get(SMTP_PASSWORD_VARIABLE, "").strip()
    if not username and not password:
        return None
    return (configured(SMTP_USERNAME_VARIABLE), configured(SMTP_PASSWORD_VARIABLE))


@dataclass(frozen=True, slots=True)
class ResendMailer:
    sender: str
    api_key: str
    client: httpx.Client

    def send(self, message: Message) -> None:
        answered = self.client.post(
            RESEND_ENDPOINT,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "from": self.sender,
                "to": [message.to],
                "subject": message.subject,
                "text": message.text,
            },
        )
        answered.raise_for_status()


@lru_cache(maxsize=1)
def mailer() -> Mailer:
    choice = environ.get(MAILER_VARIABLE, "").strip().lower() or "console"
    sender = environ.get(MAIL_FROM_VARIABLE, "").strip() or DEFAULT_MAIL_FROM
    match choice:
        case "console":
            return ConsoleMailer(sender)
        case "smtp":
            return SmtpMailer(
                sender=sender,
                host=configured(SMTP_HOST_VARIABLE),
                port=smtp_port(),
                credentials=smtp_credentials(),
            )
        case "resend":
            return ResendMailer(
                sender=sender,
                api_key=configured(RESEND_API_KEY_VARIABLE),
                client=httpx.Client(timeout=RESEND_TIMEOUT),
            )
        case _:
            raise MailerConfigurationError(
                f"{MAILER_VARIABLE}={choice!r} is not a mailer; "
                "it is one of console, smtp, resend"
            )


def send(to: str, subject: str, text: str) -> None:
    mailer().send(Message(to=to, subject=subject, text=text))


def outbox() -> list[Message]:
    adapter = mailer()
    if not isinstance(adapter, ConsoleMailer):
        raise MailerConfigurationError(
            f"the outbox is the console adapter's, and {MAILER_VARIABLE} "
            f"selects {type(adapter).__name__}"
        )
    return adapter.outbox
