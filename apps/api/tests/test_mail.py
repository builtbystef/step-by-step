"""The mailer seam and its three adapters.

Every email the product sends goes through one `send()`, and which adapter
carries it is configuration — so this is where the choice is tested, and no
caller ever has to know. The console adapter is also the test capture point
for every later slice: the accounts seam tests read the Sign-in Code out of
this outbox rather than out of a table.

Nothing here talks to a mail server or to Resend. SMTP is driven through a
connection the adapter is handed, Resend through a stubbed HTTP transport, so
this is fast tier.
"""

import json
import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from email.message import EmailMessage

import httpx
import pytest
from step_by_step_api.mail import (
    DEFAULT_MAIL_FROM,
    Mailer,
    MailerConfigurationError,
    Message,
    ResendMailer,
    SmtpConnection,
    SmtpMailer,
    mailer,
    outbox,
    send,
)


@pytest.fixture(autouse=True)
def unconfigured_mailer() -> Iterator[None]:
    """No test here may inherit — or leave behind — a configured adapter."""
    mailer.cache_clear()
    yield
    mailer.cache_clear()


def test_a_send_with_no_mailer_configured_is_captured_by_the_console_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MAILER", raising=False)

    send(to="ada@example.com", subject="Your sign-in code", text="It is 123456.")

    assert outbox() == [
        Message(to="ada@example.com", subject="Your sign-in code", text="It is 123456.")
    ]


def test_the_console_adapter_prints_what_it_captured(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("MAILER", "console")

    with caplog.at_level(logging.INFO):
        send(to="ada@example.com", subject="Your sign-in code", text="It is 123456.")

    assert "ada@example.com" in caplog.text
    assert "Your sign-in code" in caplog.text
    assert "It is 123456." in caplog.text


def test_an_unknown_adapter_name_is_a_configuration_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAILER", "sendmail")

    with pytest.raises(MailerConfigurationError, match="MAILER"):
        mailer()


def test_the_sender_is_a_dev_address_until_mail_from_says_otherwise(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("MAIL_FROM", raising=False)

    with caplog.at_level(logging.INFO):
        send(to="ada@example.com", subject="Your sign-in code", text="It is 123456.")

    assert DEFAULT_MAIL_FROM in caplog.text


def test_mail_from_sets_the_sender(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("MAIL_FROM", "Step by Step <no-reply@example.com>")

    with caplog.at_level(logging.INFO):
        send(to="ada@example.com", subject="Your sign-in code", text="It is 123456.")

    assert "no-reply@example.com" in caplog.text


def test_smtp_without_a_host_is_a_configuration_failure_naming_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAILER", "smtp")
    monkeypatch.delenv("SMTP_HOST", raising=False)

    with pytest.raises(MailerConfigurationError, match="SMTP_HOST"):
        mailer()


@dataclass
class RecordedSmtp:
    """A mail server that records the conversation instead of holding a socket.

    What matters about SMTP is the conversation — upgrade, authenticate,
    send, hang up — so that is what this keeps.
    """

    offers_starttls: bool = True
    fails_to_send: bool = False
    connected_to: tuple[str, int] | None = None
    conversation: list[str] = field(default_factory=list)
    logged_in_as: tuple[str, str] | None = None
    sent: list[EmailMessage] = field(default_factory=list)

    def connect(self, host: str, port: int) -> SmtpConnection:
        self.connected_to = (host, port)
        return self

    def ehlo(self) -> object:
        self.conversation.append("ehlo")
        return None

    def has_extn(self, opt: str) -> bool:
        return opt.lower() == "starttls" and self.offers_starttls

    def starttls(self) -> object:
        self.conversation.append("starttls")
        return None

    def login(self, user: str, password: str) -> object:
        self.logged_in_as = (user, password)
        self.conversation.append("login")
        return None

    def send_message(self, msg: EmailMessage) -> object:
        if self.fails_to_send:
            raise OSError("connection reset")
        self.sent.append(msg)
        self.conversation.append("send")
        return None

    def quit(self) -> object:
        self.conversation.append("quit")
        return None


def smtp_talking_to(recorded: RecordedSmtp) -> SmtpMailer:
    """The configured SMTP adapter, with `recorded` in the mail server's place."""
    adapter = mailer()
    assert isinstance(adapter, SmtpMailer)
    return replace(adapter, connect=recorded.connect)


@pytest.fixture
def smtp_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """MAILER=smtp with a host and nothing else."""
    monkeypatch.setenv("MAILER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "mail.example.com")
    for optional in ("SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD"):
        monkeypatch.delenv(optional, raising=False)


@pytest.mark.usefixtures("smtp_configured")
def test_smtp_submits_the_message_to_the_configured_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAIL_FROM", "no-reply@example.com")
    server = RecordedSmtp()

    smtp_talking_to(server).send(
        Message(to="ada@example.com", subject="Your sign-in code", text="It is 123456.")
    )

    assert server.connected_to == ("mail.example.com", 587)
    submitted = server.sent[0]
    assert submitted["From"] == "no-reply@example.com"
    assert submitted["To"] == "ada@example.com"
    assert submitted["Subject"] == "Your sign-in code"
    assert submitted.get_content().strip() == "It is 123456."


@pytest.mark.usefixtures("smtp_configured")
def test_smtp_port_moves_the_submission_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_PORT", "2525")
    server = RecordedSmtp()

    smtp_talking_to(server).send(Message("ada@example.com", "Subject", "Body"))

    assert server.connected_to == ("mail.example.com", 2525)


@pytest.mark.usefixtures("smtp_configured")
def test_smtp_upgrades_to_tls_when_the_server_offers_it() -> None:
    server = RecordedSmtp(offers_starttls=True)

    smtp_talking_to(server).send(Message("ada@example.com", "Subject", "Body"))

    # The second EHLO is not decoration: the extension list before the upgrade
    # describes a different connection from the one the mail goes over.
    assert server.conversation == ["ehlo", "starttls", "ehlo", "send", "quit"]


@pytest.mark.usefixtures("smtp_configured")
def test_smtp_sends_anyway_to_a_server_that_offers_no_tls() -> None:
    """A relay on the instance's own host commonly offers none."""
    server = RecordedSmtp(offers_starttls=False)

    smtp_talking_to(server).send(Message("ada@example.com", "Subject", "Body"))

    assert server.conversation == ["ehlo", "send", "quit"]


@pytest.mark.usefixtures("smtp_configured")
def test_smtp_authenticates_when_a_username_and_password_are_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SMTP_USERNAME", "postmaster")
    monkeypatch.setenv("SMTP_PASSWORD", "hunter2")
    server = RecordedSmtp()

    smtp_talking_to(server).send(Message("ada@example.com", "Subject", "Body"))

    assert server.logged_in_as == ("postmaster", "hunter2")


@pytest.mark.usefixtures("smtp_configured")
def test_smtp_sends_unauthenticated_when_neither_is_configured() -> None:
    server = RecordedSmtp()

    smtp_talking_to(server).send(Message("ada@example.com", "Subject", "Body"))

    assert server.logged_in_as is None


@pytest.mark.usefixtures("smtp_configured")
def test_a_username_without_a_password_names_the_missing_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SMTP_USERNAME", "postmaster")

    with pytest.raises(MailerConfigurationError, match="SMTP_PASSWORD"):
        mailer()


@pytest.mark.usefixtures("smtp_configured")
def test_a_password_without_a_username_names_the_missing_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SMTP_PASSWORD", "hunter2")

    with pytest.raises(MailerConfigurationError, match="SMTP_USERNAME"):
        mailer()


@pytest.mark.usefixtures("smtp_configured")
def test_a_failed_send_still_hangs_up() -> None:
    """A mail server that drops a message must not also cost a socket."""
    server = RecordedSmtp(fails_to_send=True)

    with pytest.raises(OSError, match="connection reset"):
        smtp_talking_to(server).send(Message("ada@example.com", "Subject", "Body"))

    assert server.conversation[-1] == "quit"


def test_resend_without_an_api_key_is_a_configuration_failure_naming_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAILER", "resend")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    with pytest.raises(MailerConfigurationError, match="RESEND_API_KEY"):
        mailer()


@pytest.fixture
def resend_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAILER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("MAIL_FROM", "no-reply@example.com")


def resend_answered_by(answer: Callable[[httpx.Request], httpx.Response]) -> Mailer:
    """The configured Resend adapter, with `answer` in the API's place."""
    adapter = mailer()
    assert isinstance(adapter, ResendMailer)
    return replace(adapter, client=httpx.Client(transport=httpx.MockTransport(answer)))


@pytest.mark.usefixtures("resend_configured")
def test_resend_posts_the_message_to_its_api() -> None:
    posted: list[httpx.Request] = []

    def accept(request: httpx.Request) -> httpx.Response:
        posted.append(request)
        return httpx.Response(200, json={"id": "6229f547-f3f1-4d3c-a94b-2f0a6f1d7a1e"})

    resend_answered_by(accept).send(
        Message(to="ada@example.com", subject="Your sign-in code", text="It is 123456.")
    )

    request = posted[0]
    assert str(request.url) == "https://api.resend.com/emails"
    assert request.headers["Authorization"] == "Bearer re_test_key"
    assert json.loads(request.content) == {
        "from": "no-reply@example.com",
        "to": ["ada@example.com"],
        "subject": "Your sign-in code",
        "text": "It is 123456.",
    }


@pytest.mark.usefixtures("resend_configured")
def test_a_send_resend_rejects_is_an_error_rather_than_a_silent_drop() -> None:
    def reject(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"message": "The from domain is not verified"})

    with pytest.raises(httpx.HTTPStatusError):
        resend_answered_by(reject).send(Message("ada@example.com", "Subject", "Body"))


@pytest.mark.usefixtures("resend_configured")
def test_the_outbox_says_so_when_another_adapter_is_configured() -> None:
    with pytest.raises(MailerConfigurationError, match="console"):
        outbox()
