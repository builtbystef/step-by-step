"""Strip a Run's secret values from anything the Worker is about to publish.

Redaction happens here, in the Worker, before Redis or Postgres see the text.
The Worker redacts whatever plaintext it was handed — org values and Personal
Overrides alike — and never learns which layer they came from.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from io import BytesIO
from typing import Any
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile

MASK = "••••"
TEXT_TRACE_SUFFIXES = (".trace", ".network", ".stacks")


def redact(text: str, secrets: Sequence[str]) -> str:
    """Substring-replace every secret. No minimum length."""
    redacted = text
    for secret in sorted((value for value in secrets if value), key=len, reverse=True):
        redacted = redacted.replace(secret, MASK)
    return redacted


def redact_trace(body: bytes, secrets: Sequence[str]) -> bytes:
    """Rewrite a Playwright trace zip so no text member still holds a secret."""
    values = [secret for secret in secrets if secret]
    if not values:
        return body
    try:
        source = ZipFile(BytesIO(body))
    except Exception:
        return body
    output = BytesIO()
    with source, ZipFile(output, "w", compression=ZIP_DEFLATED) as dest:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename.endswith(TEXT_TRACE_SUFFIXES):
                text = data.decode("utf-8", errors="surrogateescape")
                data = redact(text, values).encode("utf-8", errors="surrogateescape")
            dest.writestr(info, data)
    return output.getvalue()


class RedactingStore:
    """A ResultStore wrapper that redacts before the inner store is called."""

    def __init__(self, inner: Any, secrets: Sequence[str]) -> None:
        self._inner = inner
        self._secrets = [secret for secret in secrets if secret]

    def start_interval(self, run_id: UUID, kind: str, at: datetime) -> object:
        return self._inner.start_interval(run_id, kind, at)

    def end_interval(self, handle: object, at: datetime) -> None:
        self._inner.end_interval(handle, at)

    def add_result(self, run_id: UUID, result: Any) -> None:
        if result.error_message:
            result = replace(
                result, error_message=redact(result.error_message, self._secrets)
            )
        self._inner.add_result(run_id, result)

    def finish_run(
        self,
        run_id: UUID,
        status: str,
        failure_reason: str | None,
        failure_detail: str | None,
        automation_ms: int,
        at: datetime,
    ) -> None:
        if failure_detail is not None:
            failure_detail = redact(failure_detail, self._secrets)
        self._inner.finish_run(
            run_id, status, failure_reason, failure_detail, automation_ms, at
        )

    def emit(self, run_id: UUID, event_type: str, payload: Mapping[str, Any]) -> None:
        redacted = dict(payload)
        for key in ("text", "failure_detail", "detail", "error_message"):
            value = redacted.get(key)
            if isinstance(value, str):
                redacted[key] = redact(value, self._secrets)
        self._inner.emit(run_id, event_type, redacted)

    def log(
        self,
        run_id: UUID,
        level: str,
        text: str,
        step_id: UUID | None = None,
    ) -> None:
        self._inner.log(run_id, level, redact(text, self._secrets), step_id=step_id)

    def park(self, run_id: UUID, deadline_at: datetime, at: datetime) -> None:
        self._inner.park(run_id, deadline_at, at)

    def resume(self, run_id: UUID, at: datetime) -> None:
        self._inner.resume(run_id, at)

    def release_holder(self, run_id: UUID, at: datetime) -> None:
        self._inner.release_holder(run_id, at)

    def add_artifact(
        self,
        run_id: UUID,
        *,
        kind: str,
        body: bytes,
        content_type: str,
        index: int,
        step_id: UUID | None = None,
        filename: str = "",
    ) -> UUID:
        if kind == "trace" and self._secrets:
            body = redact_trace(body, self._secrets)
        return self._inner.add_artifact(
            run_id,
            kind=kind,
            body=body,
            content_type=content_type,
            index=index,
            step_id=step_id,
            filename=filename,
        )
