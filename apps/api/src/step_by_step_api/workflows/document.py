"""The Workflow document: what a Draft holds, and what a save is allowed to be.

One self-contained document per Draft — `steps` and `variables` together — so
that publishing it later is a copy rather than a join, and a Version stays
executable forever without the code that wrote it.

The field names on the wire are the ones the spec pinned for this document
(`timeoutMs`, `outputName`), because the recorder and the editor both write it
in JavaScript. The rest of the API stays snake_case; this document is the one
place that does not.

Shape is Pydantic's: the eight Step types are a union discriminated by `type`,
so an unknown type and a payload that does not fit its type are told apart
before any rule reads the document. What is left — a repeated Variable name,
a repeated Step id, a `{{name}}` nothing declares — reads the document as a
whole, and lives in `validated`.
"""

import re
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from step_by_step_api.errors import ApiError

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


UNKNOWN_TAG = "union_tag_invalid"
"""Pydantic's word for a `type` that names none of the eight Step types."""


def shape_refusal(complaints: list[Any]) -> ApiError:
    """What a document that does not fit the models is refused with.

    Two codes, because a client does two different things about them: an
    unknown type means the document came from something newer or something
    else, and a malformed payload means one Step is wrong and the editor can
    point at it.
    """
    first = complaints[0] if complaints else {}
    where = ".".join(str(part) for part in first.get("loc", ()))
    said = first.get("msg", "the document does not fit the Step contract")
    if any(complaint.get("type") == UNKNOWN_TAG for complaint in complaints):
        return ApiError(400, "unknown_step_type", f"{where}: {said}")
    return ApiError(400, "malformed_payload", f"{where}: {said}")


def validated(document: WorkflowDocument) -> WorkflowDocument:
    """The document, or the refusal that says what is wrong with it.

    Shape is Pydantic's; what is left are the rules that read the document as
    a whole — the three ways a document can be well-formed and still be wrong.

    The declaration list is read first, because everything after it is read
    against that list, and a list that names one Variable twice does not say
    what it declares — which of the two rows a reader picks would decide
    whether the value is masked. Names are compared as written, never folded:
    `{{name}}` matches exactly, so `Password` and `password` are two Variables.
    """
    declared: set[str] = set()
    for variable in document.variables:
        if variable.name in declared:
            raise ApiError(
                400,
                "duplicate_variable_name",
                f"two Variables carry the name {variable.name}",
            )
        declared.add(variable.name)
    seen: set[UUID] = set()
    for step in document.steps:
        if step.id in seen:
            raise ApiError(
                400, "duplicate_step_id", f"two Steps carry the id {step.id}"
            )
        seen.add(step.id)
        for name in step.references():
            if name not in declared:
                raise ApiError(
                    400,
                    "undeclared_variable",
                    f"a Step value references {{{{{name}}}}}, "
                    "which this Workflow does not declare",
                )
    return document


def empty() -> dict[str, Any]:
    """The document a Workflow starts with, in the form the column stores."""
    return stored(WorkflowDocument())


def stored(document: WorkflowDocument) -> dict[str, Any]:
    """The document as JSONB holds it — the wire names, and JSON scalars.

    A field nobody set is left out rather than written as `null`: every
    optional field in this document means "absent" by being absent, and a
    saved document that read back with a hundred added nulls would not be the
    document the editor sent.
    """
    return document.model_dump(mode="json", by_alias=True, exclude_none=True)


def with_fresh_step_ids(document: dict[str, Any]) -> dict[str, Any]:
    """The same document, with every Step under an id of its own.

    A copy is the same automation and not the same Steps. The id is the thread
    that ties a Step to its Step Results and its Selector Drift across every
    Version it appears in, and a copy that kept them would tie the copy's
    history to the original's.

    Everything else is carried across untouched, including the order: nothing
    in this document refers to a Step by id, so re-minting them changes what a
    Step is called internally and nothing about what it does.
    """
    steps = [{**step, "id": str(uuid4())} for step in document.get("steps", [])]
    return {**document, "steps": steps}


class DraftState(StrEnum):
    """Where a Draft stands against what has been published, in three words."""

    NEVER_PUBLISHED = "never-published"
    UNPUBLISHED_CHANGES = "unpublished-changes"
    IN_SYNC = "in-sync"


def draft_state(draft: dict[str, Any], published: dict[str, Any] | None) -> DraftState:
    """The Draft's standing, derived rather than stored.

    Derived, because a stored flag is a second truth: it would have to be set
    by every path that writes a Draft — the editor, the recorder's finalize, a
    restore — and the one that forgot would leave a Workflow claiming to be in
    sync with a Version it no longer matches.

    The comparison is of the whole document and not of the Steps alone: a
    Variable renamed or a secret flag flipped changes what a Run does, so a
    Draft that differs by nothing else is still ahead of its Version.
    """
    return standing(published is not None, draft == published)


def standing(published: bool, matches: bool) -> DraftState:
    """The three words, from the two facts they are made of.

    Split out because the Workflows list asks the same question of a hundred
    rows at once, and answering it the way `draft_state` does would drag every
    Draft and every Version document across the wire to compare them here. It
    compares them in the database instead and brings back the boolean — so the
    comparison moves, and the rule that turns it into a word does not.
    """
    if not published:
        return DraftState.NEVER_PUBLISHED
    return DraftState.IN_SYNC if matches else DraftState.UNPUBLISHED_CHANGES


class StepRef(BaseModel):
    """One Step in a diff: what names it in a modal, and nothing else."""

    id: UUID
    label: str


class DocumentDiff(BaseModel):
    """What publishing the Draft would change, Step by Step.

    Three lists with no defaults: each is always answered, so a reader renders
    "nothing changes" from an empty list rather than from a missing key.
    """

    added: list[StepRef]
    changed: list[StepRef]
    removed: list[StepRef]


def diff(published: WorkflowDocument, draft: WorkflowDocument) -> DocumentDiff:
    """The Steps a publish would add, change, and remove.

    Keyed on the Step id, because an id is the one thing an edit never
    rewrites. Positions move whenever anything above them is inserted or
    deleted, so a diff that read them would report every later Step as changed
    and bury the one Step the user actually touched.

    A Step that only moved therefore appears in none of the three lists. Its
    place in the list is not what a Worker does with it — the payload is — and
    the draft state says the Draft is ahead of its Version either way.
    """
    before = {step.id: step for step in published.steps}
    after = {step.id for step in draft.steps}
    return DocumentDiff(
        added=[named(step) for step in draft.steps if step.id not in before],
        changed=[
            named(step)
            for step in draft.steps
            if step.id in before and before[step.id] != step
        ],
        removed=[named(step) for step in published.steps if step.id not in after],
    )


def named(step: Step) -> StepRef:
    """A Step as a diff carries it."""
    return StepRef(id=step.id, label=step.label)
