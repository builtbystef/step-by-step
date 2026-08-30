import re
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

VARIABLE_NAME_PATTERN = r"[A-Za-z_][A-Za-z0-9_-]*"

REFERENCE = re.compile(r"\{\{\s*(" + VARIABLE_NAME_PATTERN + r")\s*\}\}")


class DocumentModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )


class Variable(DocumentModel):
    name: str = Field(pattern=f"^{VARIABLE_NAME_PATTERN}$", max_length=100)
    secret: bool = False
    secret_id: UUID | None = None
    secret_name: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def vault_pointer_only_when_secret(self) -> Variable:
        if self.secret:
            return self
        if self.secret_id is not None:
            raise ValueError("secretId is only set on a secret Variable")
        if self.secret_name is not None:
            raise ValueError("secretName is only set on a secret Variable")
        return self


class CandidateKind(StrEnum):
    TESTID = "testid"
    ROLE = "role"
    PLACEHOLDER = "placeholder"
    LABEL = "label"
    ALT = "alt"
    TEXT = "text"
    TITLE = "title"
    CSS = "css"


class SelectorCandidate(DocumentModel):
    kind: CandidateKind
    value: str
    shadow_path: list[str] | None = None


class FrameHop(DocumentModel):
    index: int
    name: str | None = None
    url: str | None = None


class UnsupportedReason(StrEnum):
    CLOSED_SHADOW_ROOT = "closed-shadow-root"
    CROSS_ORIGIN_FRAME = "cross-origin-frame"


class Unsupported(DocumentModel):
    reason: UnsupportedReason
    warning: str


class Target(DocumentModel):
    candidates: list[SelectorCandidate]
    frame: list[FrameHop] | None = None
    unsupported: Unsupported | None = None

    @classmethod
    def from_document(cls, target: Mapping[str, Any]) -> Target:
        return cls.model_validate(target)


class NavigatePayload(DocumentModel):
    url: str


class ClickPayload(DocumentModel):
    target: Target
    asserted_navigation: bool = False


class TypePayload(DocumentModel):
    target: Target
    value: str


class SelectPayload(DocumentModel):
    target: Target
    value: str


class DownloadPayload(DocumentModel):
    target: Target


class ExtractField(DocumentModel):
    name: str
    sub_selector: str
    attribute: str | None = None


class ScalarExtractPayload(DocumentModel):
    target: Target
    output_name: str
    mode: Literal["scalar"]
    attribute: str | None = None


class ListExtractPayload(DocumentModel):
    target: Target
    output_name: str
    mode: Literal["list"]
    fields: list[ExtractField] = Field(min_length=1)


ExtractPayload = Annotated[
    ScalarExtractPayload | ListExtractPayload, Field(discriminator="mode")
]


class DurationWaitPayload(DocumentModel):
    mode: Literal["duration"]
    duration_ms: int = Field(gt=0)


class ElementWaitPayload(DocumentModel):
    mode: Literal["element"]
    target: Target


WaitPayload = Annotated[
    DurationWaitPayload | ElementWaitPayload, Field(discriminator="mode")
]


class TakeoverPayload(DocumentModel):
    message: str | None = None
    timeout_ms: int | None = Field(default=None, gt=0)
    success_check: Target | None = None


class StepType(StrEnum):
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    DOWNLOAD = "download"
    EXTRACT = "extract"
    WAIT = "wait"
    PAUSE_FOR_TAKEOVER = "pause-for-takeover"


class StepEnvelope(DocumentModel):
    id: UUID
    label: str = Field(max_length=500)
    optional: bool = False
    disabled: bool = False
    screenshot: bool = False
    timeout_ms: int | None = Field(default=None, gt=0)

    def references(self) -> list[str]:
        return []


class NavigateStep(StepEnvelope):
    type: Literal[StepType.NAVIGATE]
    payload: NavigatePayload

    def references(self) -> list[str]:
        return REFERENCE.findall(self.payload.url)


class ClickStep(StepEnvelope):
    type: Literal[StepType.CLICK]
    payload: ClickPayload


class TypeStep(StepEnvelope):
    type: Literal[StepType.TYPE]
    payload: TypePayload

    def references(self) -> list[str]:
        return REFERENCE.findall(self.payload.value)


class SelectStep(StepEnvelope):
    type: Literal[StepType.SELECT]
    payload: SelectPayload


class DownloadStep(StepEnvelope):
    type: Literal[StepType.DOWNLOAD]
    payload: DownloadPayload


class ExtractStep(StepEnvelope):
    type: Literal[StepType.EXTRACT]
    payload: ExtractPayload


class WaitStep(StepEnvelope):
    type: Literal[StepType.WAIT]
    payload: WaitPayload


class TakeoverStep(StepEnvelope):
    type: Literal[StepType.PAUSE_FOR_TAKEOVER]
    payload: TakeoverPayload


Step = Annotated[
    NavigateStep
    | ClickStep
    | TypeStep
    | SelectStep
    | DownloadStep
    | ExtractStep
    | WaitStep
    | TakeoverStep,
    Field(discriminator="type"),
]


class WorkflowDocument(DocumentModel):
    steps: list[Step] = []
    variables: list[Variable] = []
