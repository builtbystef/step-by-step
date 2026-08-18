"""The mailer seam: one send, three adapters, chosen by the environment.

Every email the product sends — the Sign-in Code and the Invitation, and
nothing else in v1 — goes through `send()`. Which adapter carries it is
configuration and never a caller's concern: `MAILER=console|smtp|resend`,
console by default.

The console adapter prints the message and keeps it in an in-process outbox,
which is what makes a self-hoster's dev instance work with no mail service at
all and what the seam tests read sent mail from.
"""

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
"""Which adapter carries the mail: console, smtp, or resend."""

MAIL_FROM_VARIABLE = "MAIL_FROM"
"""The address every email is sent from."""

DEFAULT_MAIL_FROM = "step-by-step@localhost"
"""The dev sender. A hosted adapter needs a domain it is allowed to send for."""

SMTP_HOST_VARIABLE = "SMTP_HOST"
SMTP_PORT_VARIABLE = "SMTP_PORT"
SMTP_USERNAME_VARIABLE = "SMTP_USERNAME"
SMTP_PASSWORD_VARIABLE = "SMTP_PASSWORD"

DEFAULT_SMTP_PORT = 587
"""The submission port, where STARTTLS is the norm."""

SMTP_TIMEOUT = 30
"""Seconds. A mail server that stops answering must not hold a request open."""

RESEND_API_KEY_VARIABLE = "RESEND_API_KEY"
RESEND_ENDPOINT = "https://api.resend.com/emails"
RESEND_TIMEOUT = 30
"""Seconds, on the same terms as SMTP_TIMEOUT."""


class MailerConfigurationError(RuntimeError):
    """The mailer is misconfigured, and the backend must not start."""


@dataclass(frozen=True, slots=True)
class Message:
    """One email: the three fields every adapter carries, and no more."""

    to: str
    subject: str
    text: str


class Mailer(Protocol):
    """What an adapter is: something that carries a `Message` away."""

    def send(self, message: Message) -> None: ...


@dataclass(slots=True)
class ConsoleMailer:
    """Prints the message, and keeps it.

    The outbox is what a seam test reads: an accounts test asks for a Sign-in
    Code over HTTP and takes the code out of the message that came back here,
    rather than reaching into the table that holds its hash.
    """

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
    """A required variable's value, or a failure that names it.

    Blank counts as missing: compose passes an unset variable through as an
    empty string, and an adapter configured with "" fails later and worse.
    """
    value = environ.get(variable, "").strip()
    if not value:
        raise MailerConfigurationError(f"{variable} is not set")
    return value


class SmtpConnection(Protocol):
    """The part of `smtplib.SMTP` the adapter uses, and all it may use.

    Naming it is what lets the SMTP conversation be tested without a mail
    server: the adapter is handed something that opens a connection, and a
    test hands it something that records the conversation instead.
    """

    def ehlo(self) -> object: ...
    def has_extn(self, opt: str) -> bool: ...
    def starttls(self) -> object: ...
    def login(self, user: str, password: str) -> object: ...
    def send_message(self, msg: EmailMessage) -> object: ...
    def quit(self) -> object: ...


type OpenSmtp = Callable[[str, int], SmtpConnection]
"""How the adapter reaches a mail server: host and port in, connection out."""


def open_smtp(host: str, port: int) -> SmtpConnection:
    """The real thing: a socket to the mail server."""
    return smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT)


@dataclass(frozen=True, slots=True)
class SmtpMailer:
    """Sends through a mail server, with the standard library and no provider.

    This is what keeps self-hosting free of an account anywhere: an instance
    with its own relay, or with any mailbox provider's submission server,
    needs nothing this repository does not already carry.
    """

    sender: str
    host: str
    port: int = DEFAULT_SMTP_PORT
    credentials: tuple[str, str] | None = None
    connect: OpenSmtp = open_smtp

    def send(self, message: Message) -> None:
        connection = self.connect(self.host, self.port)
        try:
            connection.ehlo()
            # STARTTLS when the server offers it, rather than always: a relay
            # on the same host commonly offers none, and refusing to send
            # through it would cost self-hosters a working mailer for a
            # protection that the loopback already gives.
            if connection.has_extn("starttls"):
                connection.starttls()
                # A second EHLO, because the server's answer to the first one
                # describes the connection before the upgrade.
                connection.ehlo()
            if self.credentials is not None:
                connection.login(*self.credentials)
            connection.send_message(as_email(message, self.sender))
        finally:
            connection.quit()


def as_email(message: Message, sender: str) -> EmailMessage:
    """The message as the mail world wants it: headers and a plain-text body."""
    mail = EmailMessage()
    mail["From"] = sender
    mail["To"] = message.to
    mail["Subject"] = message.subject
    mail.set_content(message.text)
    return mail


def smtp_port() -> int:
    """The port to submit on, 587 unless the environment says another."""
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
    """The credentials to authenticate with, or `None` for an open relay.

    Neither variable set means the server takes mail unauthenticated, which a
    relay on the instance's own host usually does. One of the two set means
    the operator meant to authenticate, so the other one is missing.
    """
    username = environ.get(SMTP_USERNAME_VARIABLE, "").strip()
    password = environ.get(SMTP_PASSWORD_VARIABLE, "").strip()
    if not username and not password:
        return None
    # Through `configured`, so that whichever one is missing names itself.
    return (configured(SMTP_USERNAME_VARIABLE), configured(SMTP_PASSWORD_VARIABLE))


@dataclass(frozen=True, slots=True)
class ResendMailer:
    """Sends through Resend's HTTP API — the recommended hosted path.

    An API call rather than a mail submission, which is what makes it the
    least work to configure: a key, a verified sender domain, and no port
    that a host's provider might block.
    """

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
    """The configured adapter, built once.

    The backend calls this at startup, so an adapter whose configuration is
    missing stops the boot rather than the first Sign-in Code.
    """
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
    """Send one plain-text email through the configured adapter."""
    mailer().send(Message(to=to, subject=subject, text=text))


def outbox() -> list[Message]:
    """What the console adapter has captured — the seam tests' mailbox.

    Only the console adapter has one, and a test that asks for it while
    another is configured is looking at an instance that sends real mail.
    """
    adapter = mailer()
    if not isinstance(adapter, ConsoleMailer):
        raise MailerConfigurationError(
            f"the outbox is the console adapter's, and {MAILER_VARIABLE} "
            f"selects {type(adapter).__name__}"
        )
    return adapter.outbox
