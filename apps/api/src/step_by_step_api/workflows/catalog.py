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
from sqlalchemy.orm import InstrumentedAttribute, Session
from step_by_step_core.objects import artifact_bucket, object_store

from step_by_step_api.accounts.orgs import ActiveMembership
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import ApiError, errors
from step_by_step_api.runs.models import NON_TERMINAL, Artifact, Run, RunStatus
from step_by_step_api.schedules.models import Schedule
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


class LastRun(BaseModel):
    """The newest Run of a Workflow, as the list row's meta line draws it."""

    id: UUID
    status: RunStatus
    finished_at: datetime | None


class WorkflowSummary(BaseModel):
    """A Workflow as a list row: everything the row draws, and no document."""

    id: UUID
    name: str
    created_at: datetime
    last_activity_at: datetime
    """The latest thing that happened to this Workflow — the newest Run's
    creation time, falling back to the later of the Workflow's own stamp and
    its Draft's."""
    draft_state: DraftState
    published_version: int | None = None
    """The newest Version's number, absent while the Workflow is unpublished."""
    default_step_timeout_ms: int
    """What a Step with no override of its own waits. The editor draws the
    fallback under every empty timeout field, and a number it knew by heart
    would be a second truth the moment a Workflow carried another one."""
    last_run: LastRun | None = None
    schedule_count: int
    schedule_label: str | None = None
    """A compact readback of the one Schedule, absent when there is not
    exactly one."""
    recent_run_median_ms: int | None = None
    """Median duration of the last ten succeeded Runs, absent below three."""
    run_count: int


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
        items=summarise(db, rows[:limit]),
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

    The newest Run's creation time, falling back to the later of the
    Workflow's own stamp and its Draft's: renaming, editing, and running are
    all things that happened to this Workflow. Postgres `GREATEST` is null if
    any argument is, so a never-run Workflow coalesces the missing Run time
    onto a stamp it already has.
    """
    latest_run_at = (
        select(func.max(Run.queued_at))
        .where(Run.workflow_id == Workflow.id)
        .correlate(Workflow)
        .scalar_subquery()
    )
    return func.greatest(
        Workflow.updated_at,
        WorkflowDraft.updated_at,
        func.coalesce(latest_run_at, Workflow.updated_at),
    )


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


def summarise(db: Session, rows: list[Any]) -> list[WorkflowSummary]:
    """The page's rows, with the Run and Schedule facts each one draws."""
    ids = [row.Workflow.id for row in rows]
    last_runs = last_runs_of(db, ids)
    schedules = schedules_of(db, ids)
    run_counts = run_counts_of(db, ids)
    medians = medians_of(db, ids)
    return [
        summary(
            row,
            last_run=last_runs.get(row.Workflow.id),
            schedule_count=schedules.get(row.Workflow.id, (0, None))[0],
            schedule_cron=schedules.get(row.Workflow.id, (0, None))[1],
            run_count=run_counts.get(row.Workflow.id, 0),
            recent_run_median_ms=medians.get(row.Workflow.id),
        )
        for row in rows
    ]


def summary(
    row: Any,
    *,
    last_run: LastRun | None,
    schedule_count: int,
    schedule_cron: str | None,
    run_count: int,
    recent_run_median_ms: int | None,
) -> WorkflowSummary:
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
        last_run=last_run,
        schedule_count=schedule_count,
        schedule_label=(
            compact_schedule(schedule_cron)
            if schedule_count == 1 and schedule_cron is not None
            else None
        ),
        recent_run_median_ms=recent_run_median_ms,
        run_count=run_count,
    )


def last_runs_of(db: Session, ids: list[UUID]) -> dict[UUID, LastRun]:
    """The newest Run of each Workflow, by creation time."""
    if not ids:
        return {}
    rows = db.execute(
        select(Run)
        .distinct(Run.workflow_id)
        .where(Run.workflow_id.in_(ids))
        .order_by(Run.workflow_id, Run.queued_at.desc(), Run.id.desc())
    ).scalars()
    return {
        run.workflow_id: LastRun(id=run.id, status=run.status, finished_at=run.ended_at)
        for run in rows
    }


def schedules_of(db: Session, ids: list[UUID]) -> dict[UUID, tuple[int, str | None]]:
    """How many Schedules each Workflow has, and the cron when there is one."""
    if not ids:
        return {}
    rows = db.execute(
        select(Schedule.workflow_id, func.count(), func.min(Schedule.cron))
        .where(Schedule.workflow_id.in_(ids))
        .group_by(Schedule.workflow_id)
    )
    return {
        workflow_id: (count, cron if count == 1 else None)
        for workflow_id, count, cron in rows
    }


def run_counts_of(db: Session, ids: list[UUID]) -> dict[UUID, int]:
    """How many Runs each Workflow has, for the delete dialog's blast radius."""
    if not ids:
        return {}
    rows = db.execute(
        select(Run.workflow_id, func.count())
        .where(Run.workflow_id.in_(ids))
        .group_by(Run.workflow_id)
    )
    return {workflow_id: count for workflow_id, count in rows}


def medians_of(db: Session, ids: list[UUID]) -> dict[UUID, int]:
    """Median duration of the last ten succeeded Runs, once there are three."""
    if not ids:
        return {}
    rows = db.execute(
        select(Run.workflow_id, Run.started_at, Run.queued_at, Run.ended_at)
        .where(
            Run.workflow_id.in_(ids),
            Run.status == RunStatus.SUCCEEDED,
            Run.ended_at.is_not(None),
        )
        .order_by(Run.workflow_id, Run.queued_at.desc())
    )
    samples: dict[UUID, list[int]] = {}
    for workflow_id, started, queued, ended in rows:
        assert ended is not None
        bucket = samples.setdefault(workflow_id, [])
        if len(bucket) < 10:
            start = started or queued
            bucket.append(int((ended - start).total_seconds() * 1000))
    return {
        workflow_id: int(median(durations))
        for workflow_id, durations in samples.items()
        if len(durations) >= 3
    }


def median(values: list[int]) -> float:
    ordered = sorted(values)
    count = len(ordered)
    mid = count // 2
    if count % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


WEEKDAY_NAMES = (
    "Sundays",
    "Mondays",
    "Tuesdays",
    "Wednesdays",
    "Thursdays",
    "Fridays",
    "Saturdays",
)


def compact_schedule(cron: str) -> str:
    """A list-row label for one Schedule, or the expression when it is not one."""
    fields = cron.split()
    if len(fields) != 5:
        return cron
    minute, hour, day, month, weekday = fields
    if month != "*":
        return cron
    if minute.startswith("*/") and hour == day == weekday == "*":
        step = minute[2:]
        if step.isdigit() and 1 <= int(step) <= 59:
            return f"every {int(step)} min"
        return cron
    clock = clock_of(hour, minute)
    if hour == day == weekday == "*" and minute.isdigit() and 0 <= int(minute) <= 59:
        return "hourly" if int(minute) == 0 else f"hourly :{int(minute):02d}"
    if clock is None:
        return cron
    if day == weekday == "*":
        return f"daily {clock}"
    if day == "*" and weekday == "1-5":
        return f"weekdays {clock}"
    if day == "*" and _distinct_weekdays(weekday):
        names = [WEEKDAY_NAMES[int(part)] for part in weekday.split(",")]
        if len(names) == 1:
            return f"{names[0]} {clock}"
        return f"{', '.join(names[:-1])} and {names[-1]} {clock}"
    if weekday == "*" and day.isdigit() and 1 <= int(day) <= 31:
        return f"day {int(day)} {clock}"
    return cron


def clock_of(hour: str, minute: str) -> str | None:
    if hour.isdigit() and minute.isdigit():
        hours, minutes = int(hour), int(minute)
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            return f"{hours:02d}:{minutes:02d}"
    return None


def _distinct_weekdays(field: str) -> bool:
    parts = field.split(",")
    return (
        bool(parts)
        and len(parts) == len(set(parts))
        and all(part.isdigit() and 0 <= int(part) <= 6 for part in parts)
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
    return summarise(db, [row])[0]


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
    responses=errors(400, 401, 403, 404, 409),
)
def delete_workflow(
    workflow_id: UUID, member: ActiveMembership, db: SessionDep
) -> Response:
    """Delete a Workflow, and everything that only existed because of it.

    Drafts, Versions, Schedules, Batches, Runs, Step Results, and Artifact
    rows go with it on the foreign keys that already say so. Garage objects
    do not: they are purged here, the same way deleting one Run purges them.
    A live Run refuses the delete — two copies of one Workflow never act at
    once, and deleting the Workflow under one would be the same as cancelling
    it from the wrong end.
    """
    workflow = owned(db, member, workflow_id)
    live = db.scalar(
        select(func.count())
        .select_from(Run)
        .where(Run.workflow_id == workflow.id, Run.status.in_(NON_TERMINAL))
    )
    if live:
        raise ApiError(
            409, "run_active", "this Workflow has a Run that is still active"
        )
    keys = list(
        db.execute(
            select(Artifact.object_key)
            .join(Run, Artifact.run_id == Run.id)
            .where(Run.workflow_id == workflow.id)
        )
        .scalars()
        .all()
    )
    bucket = artifact_bucket()
    store = object_store()
    for key in keys:
        store.delete_object(Bucket=bucket, Key=key)
    db.delete(workflow)
    db.commit()
    return Response(status_code=204)
