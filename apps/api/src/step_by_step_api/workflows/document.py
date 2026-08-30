from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel
from step_by_step_core.document import (
    CandidateKind,
    ClickPayload,
    ClickStep,
    DocumentModel,
    DownloadPayload,
    DownloadStep,
    DurationWaitPayload,
    ElementWaitPayload,
    ExtractField,
    ExtractPayload,
    ExtractStep,
    FrameHop,
    ListExtractPayload,
    NavigatePayload,
    NavigateStep,
    ScalarExtractPayload,
    SelectorCandidate,
    SelectPayload,
    SelectStep,
    Step,
    StepEnvelope,
    StepType,
    TakeoverPayload,
    TakeoverStep,
    Target,
    TypePayload,
    TypeStep,
    Unsupported,
    UnsupportedReason,
    Variable,
    WaitPayload,
    WaitStep,
    WorkflowDocument,
)

from step_by_step_api.errors import ApiError

__all__ = [
    "CandidateKind",
    "ClickPayload",
    "ClickStep",
    "DocumentModel",
    "DownloadPayload",
    "DownloadStep",
    "DurationWaitPayload",
    "ElementWaitPayload",
    "ExtractField",
    "ExtractPayload",
    "ExtractStep",
    "FrameHop",
    "ListExtractPayload",
    "NavigatePayload",
    "NavigateStep",
    "ScalarExtractPayload",
    "SelectPayload",
    "SelectStep",
    "SelectorCandidate",
    "Step",
    "StepEnvelope",
    "StepType",
    "TakeoverPayload",
    "TakeoverStep",
    "Target",
    "TypePayload",
    "TypeStep",
    "Unsupported",
    "UnsupportedReason",
    "Variable",
    "WaitPayload",
    "WaitStep",
    "WorkflowDocument",
]

UNKNOWN_TAG = "union_tag_invalid"


def shape_refusal(complaints: list[Any]) -> ApiError:
    first = complaints[0] if complaints else {}
    where = ".".join(str(part) for part in first.get("loc", ()))
    said = first.get("msg", "the document does not fit the Step contract")
    if any(complaint.get("type") == UNKNOWN_TAG for complaint in complaints):
        return ApiError(400, "unknown_step_type", f"{where}: {said}")
    return ApiError(400, "malformed_payload", f"{where}: {said}")


def validated(document: WorkflowDocument) -> WorkflowDocument:
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
    return stored(WorkflowDocument())


def stored(document: WorkflowDocument) -> dict[str, Any]:
    sparse = document.model_dump(
        mode="json", by_alias=True, exclude_none=True, exclude_unset=True
    )
    return {
        "steps": sparse.get("steps", []),
        "variables": sparse.get("variables", []),
    }


def with_fresh_step_ids(document: dict[str, Any]) -> dict[str, Any]:
    steps = [{**step, "id": str(uuid4())} for step in document.get("steps", [])]
    return {**document, "steps": steps}


class DraftState(StrEnum):
    NEVER_PUBLISHED = "never-published"
    UNPUBLISHED_CHANGES = "unpublished-changes"
    IN_SYNC = "in-sync"


def draft_state(draft: dict[str, Any], published: dict[str, Any] | None) -> DraftState:
    return standing(published is not None, draft == published)


def standing(published: bool, matches: bool) -> DraftState:
    if not published:
        return DraftState.NEVER_PUBLISHED
    return DraftState.IN_SYNC if matches else DraftState.UNPUBLISHED_CHANGES


class StepRef(BaseModel):
    id: UUID
    label: str


class DocumentDiff(BaseModel):
    added: list[StepRef]
    changed: list[StepRef]
    removed: list[StepRef]


def diff(published: WorkflowDocument, draft: WorkflowDocument) -> DocumentDiff:
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
    return StepRef(id=step.id, label=step.label)
