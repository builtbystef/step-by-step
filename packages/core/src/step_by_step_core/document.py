"""The shared contract for a Workflow document stored and executed by both processes."""

import re
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

VARIABLE_NAME_PATTERN = r"[A-Za-z_][A-Za-z0-9_-]*"
"""What a Variable may be called, and therefore what `{{name}}` may hold."""

REFERENCE = re.compile(r"\{\{\s*(" + VARIABLE_NAME_PATTERN + r")\s*\}\}")
"""A Variable reference inside a value. Literal text and references mix freely."""


class DocumentModel(BaseModel):
    """Every part of the document: camelCase on the wire, and nothing extra.

    `extra="forbid"` is deliberate. A key nobody reads is a step the recorder
    thinks it saved and the executor will never act on, and finding that out
    at the save is cheaper than finding it out during a Run.
    """

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )


class Variable(DocumentModel):
    """A named input a Workflow declares. Step values reference it by name."""

    name: str = Field(pattern=f"^{VARIABLE_NAME_PATTERN}$", max_length=100)
    secret: bool = False


class CandidateKind(StrEnum):
    """The ways of finding an element, in the order the recorder ranks them."""

    TESTID = "testid"
    ROLE = "role"
    PLACEHOLDER = "placeholder"
    LABEL = "label"
    ALT = "alt"
    TEXT = "text"
    TITLE = "title"
    CSS = "css"


class SelectorCandidate(DocumentModel):
    """One way of finding an element, verified unique when it was recorded."""

    kind: CandidateKind
    value: str
    shadow_path: list[str] | None = None
    """One selector per open shadow-root hop, outermost first."""


class FrameHop(DocumentModel):
    """One step of the path into the frame an element lives in."""

    index: int
    name: str | None = None
    url: str | None = None


class UnsupportedReason(StrEnum):
    """Why a recorded target will not be findable again, whatever we do."""

    CLOSED_SHADOW_ROOT = "closed-shadow-root"
    CROSS_ORIGIN_FRAME = "cross-origin-frame"


class Unsupported(DocumentModel):
    """A target the recorder captured and expects replay to fail on.

    The warning is written at capture, in plain language, because the person
    who can still do something about it is the person recording.
    """

    reason: UnsupportedReason
    warning: str


class Target(DocumentModel):
    """How a Step finds its element: candidates best-first, and where they live."""

    candidates: list[SelectorCandidate]
    frame: list[FrameHop] | None = None
    unsupported: Unsupported | None = None

    @classmethod
    def from_document(cls, target: Mapping[str, Any]) -> Target:
        """Parse a Target from the camelCase shape stored in a document."""
        return cls.model_validate(target)


class NavigatePayload(DocumentModel):
    url: str


class ClickPayload(DocumentModel):
    target: Target
    asserted_navigation: bool = False
    """The click was recorded causing a navigation, so replay expects one."""


class TypePayload(DocumentModel):
    target: Target
    value: str


class SelectPayload(DocumentModel):
    target: Target
    value: str


class DownloadPayload(DocumentModel):
    target: Target
    """A click expected to produce a file rather than a page."""


class ExtractField(DocumentModel):
    """One column of a list extraction, bound within the repeating element."""

    name: str
    sub_selector: str
    attribute: str | None = None


class ScalarExtractPayload(DocumentModel):
    """One named value: an element's text, or one of its attributes."""

    target: Target
    output_name: str
    mode: Literal["scalar"]
    attribute: str | None = None


class ListExtractPayload(DocumentModel):
    """A flat list of records. There is no nesting, by decision."""

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
    """What the person is asked to do, and how the Run can tell they did it."""

    message: str | None = None
    timeout_ms: int | None = Field(default=None, gt=0)
    success_check: Target | None = None
    """The element whose appearance means the human is done. Absent means the
    hand-back stays manual, which is always the case for a heuristic pause."""


class StepType(StrEnum):
    """The eight things a v1 Workflow can do."""

    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    DOWNLOAD = "download"
    EXTRACT = "extract"
    WAIT = "wait"
    PAUSE_FOR_TAKEOVER = "pause-for-takeover"


class StepEnvelope(DocumentModel):
    """What every Step carries, whatever it does.

    The id is app-minted and never rewritten — it is the thread that ties one
    Step across Versions, its Step Results, and its Selector Drift.
    """

    id: UUID
    label: str = Field(max_length=500)
    optional: bool = False
    """The target never appears: skip the Step rather than fail the Run."""
    disabled: bool = False
    """Stays in the Workflow and does not execute."""
    screenshot: bool = False
    """Off by default on every Step: a 200-Step Run would otherwise make 200
    images. A failing Step is captured regardless — that is diagnostics."""
    timeout_ms: int | None = Field(default=None, gt=0)
    """Overrides the Workflow's default step timeout for this Step alone."""

    def references(self) -> list[str]:
        """The Variable names this Step's values interpolate.

        Empty for most types: `{{name}}` is interpolated in a navigate URL and
        a type value, and nowhere else, so a `{{` in any other value is text.
        """
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
"""A Step is its type: the payload a Worker walks follows from the tag."""


class WorkflowDocument(DocumentModel):
    """A Draft, or a Version, as one value: the Steps and the Variables."""

    steps: list[Step] = []
    variables: list[Variable] = []
