"""The Workflow catalogue: the list a user lands on, and the housekeeping
routes that need no editor.

The document is `routes.py`'s. What lives here is everything around it — what
a row says before it is opened, and listing, renaming, duplicating, and
deleting a Workflow. The split follows the specs: the document store owns
Drafts and Versions, and this contract is the app shell's ground.
"""

import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, Select, func, literal, select, true, tuple_
from sqlalchemy.orm import InstrumentedAttribute

from step_by_step_api.accounts.orgs import ActiveMembership
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import ApiError, errors
from step_by_step_api.workflows import document
from step_by_step_api.workflows.document import DraftState
from step_by_step_api.workflows.models import (
    NAME_LENGTH,
    Workflow,
    WorkflowDraft,
    WorkflowVersion,
)

router = APIRouter()


class WorkflowSort(StrEnum):
    """The three orders the list offers, and nothing else.

    Three rather than a free-form order-by: every one of them is a keyset the
    cursor can be built on, and a fourth would have to earn its index first.
    """

    ACTIVITY = "activity"
    NAME = "name"
    CREATED = "created"


class WorkflowSummary(BaseModel):
    """A Workflow as a list row: everything the row draws, and no document."""

    id: UUID
    name: str
    created_at: datetime
    last_activity_at: datetime
    """The latest thing that happened to this Workflow — for now the later of
    its own stamp and its Draft's; the latest Run's, once Runs exist."""
    draft_state: DraftState
    published_version: int | None = None
    """The newest Version's number, absent while the Workflow is unpublished."""
    default_step_timeout_ms: int
    """What a Step with no override of its own waits. The editor draws the
    fallback under every empty timeout field, and a number it knew by heart
    would be a second truth the moment a Workflow carried another one."""


class WorkflowPage(BaseModel):
    """One page of the list, and where the next one starts.

    `next_cursor` is absent on the last page, which is how a caller knows it
    has reached the end: an empty page would be one request too many, and a
    count would be a second query nobody asked for.
    """

    items: list[WorkflowSummary]
    next_cursor: str | None = None


PAGE_SIZE = 25
"""How many rows a page holds when the caller does not say."""

MAX_PAGE_SIZE = 100
"""The most one request may ask for. A list is paged, not downloaded."""


@router.get(
    "/api/workflows",
    operation_id="listWorkflows",
    response_model_exclude_none=True,
    responses=errors(400, 401, 403),
)
def list_workflows(
    member: ActiveMembership,
    db: SessionDep,
    q: Annotated[str, Query(max_length=NAME_LENGTH)] = "",
    sort: WorkflowSort = WorkflowSort.ACTIVITY,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = PAGE_SIZE,
    cursor: str | None = None,
) -> WorkflowPage:
    """The acting Organization's Workflows, narrowed by what was typed.

    Activity by default, because a list of automations is a list of what has
    been happening; the other two orders are for finding one by hand.

    One row more than was asked for is read, and dropped: whether a next page
    exists is a fact about the data, and asking for it as a count would be a
    second query over the same rows.
    """
    page = catalogue(member, q, sort).where(*after(cursor, sort)).limit(limit + 1)
    rows = list(db.execute(page))
    return WorkflowPage(
        items=[summary(row) for row in rows[:limit]],
        next_cursor=cut(rows[limit - 1], sort) if len(rows) > limit else None,
    )


def cut(row: Any, sort: WorkflowSort) -> str:
    """Where this page ended, as the token that asks for what follows it.

    The position rather than the offset: it names the last row's sort key and
    its id, so rows arriving, leaving, or moving between two requests shift
    nothing that has already been served.
    """
    return urlsafe_b64encode(
        json.dumps(
            {"s": sort.value, "k": key_of(row, sort), "i": str(row.Workflow.id)}
        ).encode()
    ).decode()


def key_of(row: Any, sort: WorkflowSort) -> str:
    """The sort key of a row, as the cursor carries it."""
    if sort is WorkflowSort.NAME:
        return row.Workflow.name
    if sort is WorkflowSort.CREATED:
        return row.Workflow.created_at.isoformat()
    return row.last_activity_at.isoformat()


def after(cursor: str | None, sort: WorkflowSort) -> list[ColumnElement[bool]]:
    """The keyset condition a cursor stands for, or nothing on a first page.

    One row-value comparison against the same pair the order runs on, so the
    index that serves the order serves the page too.
    """
    if cursor is None:
        return []
    key, last = read(cursor, sort)
    place = tuple_(sort_key(sort), Workflow.id)
    behind = tuple_(literal(key), literal(last))
    return [place > behind if ascending(sort) else place < behind]


def read(cursor: str, sort: WorkflowSort) -> tuple[str | datetime, UUID]:
    """The position a cursor names, or the refusal that it names none.

    The order it was cut from travels inside it and has to be the order it is
    spent in: the same token means a different place in a different order, and
    a page served from that would be a page of the wrong rows. Everything else
    here is a token somebody wrote by hand, and it is refused as one thing —
    a caller does nothing different about a bad date than about bad base64.
    """
    try:
        cut_at = json.loads(urlsafe_b64decode(cursor.encode()))
        if cut_at["s"] != sort.value:
            raise ValueError(cut_at["s"])
        key = cut_at["k"]
        return (
            key if sort is WorkflowSort.NAME else datetime.fromisoformat(key)
        ), UUID(cut_at["i"])
    except Exception:
        raise ApiError(
            400, "bad_cursor", "that cursor did not come from this list, in this order"
        ) from None


def activity() -> ColumnElement[datetime]:
    """When a Workflow was last active, as the database computes it.

    The later of the Workflow's own stamp and its Draft's: renaming touches the
    one and editing the document touches the other, and both are things that
    happened to this Workflow.
    """
    return func.greatest(Workflow.updated_at, WorkflowDraft.updated_at)


def catalogue(member: ActiveMembership, q: str, sort: WorkflowSort) -> Select[Any]:
    """One row per Workflow of the acting Organization, and no document in sight.

    The Draft and the newest Version are joined for two facts alone — when the
    document was last touched, and whether it still matches what is published.
    Both are computed in the database, so a page of rows travels as a page of
    names rather than as a hundred Step documents.
    """
    latest = (
        select(WorkflowVersion.number, WorkflowVersion.document)
        .where(WorkflowVersion.workflow_id == Workflow.id)
        .order_by(WorkflowVersion.number.desc())
        .limit(1)
        .lateral("latest")
    )
    return (
        select(
            Workflow,
            activity().label("last_activity_at"),
            latest.c.number.label("published_version"),
            (latest.c.document == WorkflowDraft.document).label("matches_published"),
        )
        .join(WorkflowDraft, WorkflowDraft.workflow_id == Workflow.id)
        .outerjoin(latest, true())
        .where(Workflow.org_id == member.org_id, *matching(q))
        .order_by(*ordering(sort))
    )


SortKey = ColumnElement[Any] | InstrumentedAttribute[Any]
"""A column or a computed expression — the three orders use both."""


def sort_key(sort: WorkflowSort) -> SortKey:
    """What the chosen order sorts on. The id breaks its ties."""
    if sort is WorkflowSort.NAME:
        return Workflow.name
    if sort is WorkflowSort.CREATED:
        return Workflow.created_at
    return activity()


def ascending(sort: WorkflowSort) -> bool:
    """Which way the chosen order runs.

    A name reads from A, and a time reads from the newest: "created" and
    "activity" both answer the question "what have I been doing".
    """
    return sort is WorkflowSort.NAME


def ordering(sort: WorkflowSort) -> list[ColumnElement[Any]]:
    """The chosen order, made total by the id — which is what a keyset needs."""
    key, tiebreak = sort_key(sort), Workflow.id
    if ascending(sort):
        return [key.asc(), tiebreak.asc()]
    return [key.desc(), tiebreak.desc()]


def matching(q: str) -> list[ColumnElement[bool]]:
    """The name filter, or nothing at all when nothing was typed.

    A substring, case-insensitively, and the wildcards are escaped: `%` and `_`
    are characters a Workflow can be called, and a search box that read them as
    a pattern would answer a question nobody asked.
    """
    if q == "":
        return []
    wanted = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return [Workflow.name.ilike(f"%{wanted}%", escape="\\")]


def summary(row: Any) -> WorkflowSummary:
    """One catalogue row as the list answers with it."""
    workflow: Workflow = row.Workflow
    return WorkflowSummary(
        id=workflow.id,
        name=workflow.name,
        created_at=workflow.created_at,
        last_activity_at=row.last_activity_at,
        draft_state=document.standing(
            row.published_version is not None, row.matches_published is True
        ),
        published_version=row.published_version,
        default_step_timeout_ms=workflow.default_step_timeout_ms,
    )


@router.get(
    "/api/workflows/{workflow_id}",
    operation_id="getWorkflow",
    response_model_exclude_none=True,
    responses=errors(400, 401, 403, 404),
)
def get_workflow(
    workflow_id: UUID, member: ActiveMembership, db: SessionDep
) -> WorkflowSummary:
    """One Workflow, as the same row the list would have drawn.

    The Workflow page needs it: opened by its address rather than by a click,
    it has no row to have carried the name and the draft state across. The
    same query answers it, so the header a reload draws is the header the row
    promised.
    """
    row = db.execute(
        catalogue(member, "", WorkflowSort.ACTIVITY).where(Workflow.id == workflow_id)
    ).first()
    if row is None:
        raise ApiError(404, "workflow_not_found", "no such Workflow")
    return summary(row)


class WorkflowRename(BaseModel):
    """Everything renaming asks for. A name is all a row shows of a Workflow."""

    name: str = Field(min_length=1, max_length=NAME_LENGTH)


class WorkflowNamed(BaseModel):
    """A Workflow and what it is called: what renaming and duplicating answer."""

    id: UUID
    name: str


@router.patch(
    "/api/workflows/{workflow_id}",
    operation_id="renameWorkflow",
    responses=errors(400, 401, 403, 404),
)
def rename_workflow(
    workflow_id: UUID, asked: WorkflowRename, member: ActiveMembership, db: SessionDep
) -> WorkflowNamed:
    """Change what a Workflow is called, and nothing else about it.

    The name is the only field a row shows and the only one housekeeping
    touches; the timeouts and the document have their own routes.
    """
    workflow = owned(db, member, workflow_id)
    workflow.name = asked.name
    db.commit()
    return WorkflowNamed(id=workflow.id, name=workflow.name)


def owned(db: SessionDep, member: ActiveMembership, workflow_id: UUID) -> Workflow:
    """The Workflow itself, when the acting Organization owns it.

    Somebody else's and missing answer the same, for the reason `routes.draft_of`
    gives: a refusal that admitted the id exists would let anyone map another
    tenant's Workflows one guess at a time.
    """
    workflow = db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id, Workflow.org_id == member.org_id
        )
    ).scalar_one_or_none()
    if workflow is None:
        raise ApiError(404, "workflow_not_found", "no such Workflow")
    return workflow


COPY_SUFFIX = " (copy)"
"""What a duplicate is called. Nothing else in the app names a Workflow for
the user, so the copy arrives with a name they can see and then rename."""


@router.post(
    "/api/workflows/{workflow_id}/duplicate",
    operation_id="duplicateWorkflow",
    status_code=201,
    responses=errors(400, 401, 403, 404),
)
def duplicate_workflow(
    workflow_id: UUID, member: ActiveMembership, db: SessionDep
) -> WorkflowNamed:
    """A second Workflow holding a copy of this one's Draft.

    The Draft and nothing else. Versions are not copied — a Version is what a
    Schedule and a Batch execute, and a copy that arrived already published
    would be an automation nobody has looked at that is ready to act on a real
    website. The copy starts never-published, which is exactly true of it.
    """
    source = owned(db, member, workflow_id)
    draft = db.execute(
        select(WorkflowDraft).where(WorkflowDraft.workflow_id == source.id)
    ).scalar_one()
    copy = Workflow(
        org_id=source.org_id,
        name=named_as_a_copy(source.name),
        default_step_timeout_ms=source.default_step_timeout_ms,
        takeover_timeout_ms=source.takeover_timeout_ms,
    )
    db.add(copy)
    db.flush()
    db.add(
        WorkflowDraft(
            workflow_id=copy.id,
            document=document.with_fresh_step_ids(draft.document),
        )
    )
    db.commit()
    return WorkflowNamed(id=copy.id, name=copy.name)


def named_as_a_copy(name: str) -> str:
    """The copy's name, trimmed from the left so the suffix always survives.

    A name at the column's limit would otherwise lose the one word that says
    which of the two rows is the copy.
    """
    return name[: NAME_LENGTH - len(COPY_SUFFIX)] + COPY_SUFFIX


@router.delete(
    "/api/workflows/{workflow_id}",
    operation_id="deleteWorkflow",
    status_code=204,
    responses=errors(400, 401, 403, 404),
)
def delete_workflow(
    workflow_id: UUID, member: ActiveMembership, db: SessionDep
) -> Response:
    """Delete a Workflow, and everything that only existed because of it.

    Its Draft and its Versions go with it, on the foreign keys that already say
    so — there is no orphan half of a Workflow, and nothing is left behind to
    be found by a later query. The Schedules, Batches, and Runs the confirm
    dialog will also name are the follow-up slice's, once those objects exist.
    """
    db.delete(owned(db, member, workflow_id))
    db.commit()
    return Response(status_code=204)
