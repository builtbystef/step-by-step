"""Finding a Step's element again, weeks after it was recorded.

A Target carries several verified ways of finding one element, ranked
best-first. This module walks them in that order and takes the first that
resolves to **exactly one** element. Zero matches and several matches are the
same answer — not this one — because a page that grew a second Save button is
a page where guessing would click the wrong thing. Nothing here uses
`.first()`, `.nth()`, or `locator.or_()`, for that reason.

If the whole list fails, the walk starts again, until the deadline: the Step's
timeout **is** the retry budget, so there is no separate retry counter and no
backoff schedule to tune. What comes back on success is the element and the
rank that found it — the Selector Drift signal a Step Result records.

No call in this module waits on Playwright: a candidate is counted, never
awaited. So no library default timeout is in play anywhere here, and the
deadline the caller passes is the only clock a resolution runs on.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from time import monotonic, sleep

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Frame, Locator, Page
from step_by_step_core.document import (
    CandidateKind,
    FrameHop,
    SelectorCandidate,
    Target,
)

POLL_INTERVAL_MS = 100
"""How long a failed walk waits before the next one."""


@dataclass(frozen=True, slots=True)
class Deadline:
    """When resolution gives up, on a clock no page can move."""

    at: float

    @classmethod
    def in_ms(cls, milliseconds: float) -> Deadline:
        return cls(monotonic() + milliseconds / 1000)

    @property
    def expired(self) -> bool:
        return monotonic() >= self.at

    @property
    def remaining_ms(self) -> float:
        return max(0.0, (self.at - monotonic()) * 1000)


class FailureReason(StrEnum):
    """Why a Target did not yield an element, in the word a Step Result keeps."""

    NO_CANDIDATE_RESOLVED = "no_candidate_resolved"
    """The deadline passed with no candidate matching exactly one element."""


@dataclass(frozen=True, slots=True)
class Resolved:
    """The element, and which candidate found it."""

    locator: Locator
    rank: int
    """The matching candidate's place in the list, best-first from zero."""
    candidate_count: int
    walks: int
    """How many times the list was walked. One means it matched immediately."""


@dataclass(frozen=True, slots=True)
class SelectorFailure:
    """The Target addressed nothing this page could show, before time ran out."""

    reason: FailureReason
    message: str
    candidate_count: int
    walks: int


type Resolution = Resolved | SelectorFailure


def resolve(
    page: Page,
    target: Target,
    deadline: Deadline,
    on_walk: Callable[[int], None] | None = None,
) -> Resolution:
    """The one element this Target addresses, or the failure that says why not.

    `on_walk` is called with the number of each walk before it starts, which
    is the one moment in a resolution where nothing has been clicked yet: a
    Run checks its control state there, and raising from the hook is how it
    stops a resolution that is still waiting.
    """
    walks = 0
    while True:
        walks += 1
        if on_walk is not None:
            on_walk(walks)
        root = addressed_frame(page, target.frame or ())
        if root is not None:
            for rank, candidate in enumerate(target.candidates):
                found = locate(root, candidate)
                if matches_one(found):
                    return Resolved(
                        locator=found,
                        rank=rank,
                        candidate_count=len(target.candidates),
                        walks=walks,
                    )
        if deadline.expired:
            return SelectorFailure(
                reason=FailureReason.NO_CANDIDATE_RESOLVED,
                message=(
                    f"none of the {len(target.candidates)} recorded candidates "
                    f"matched exactly one element, in {walks} walks of the list"
                ),
                candidate_count=len(target.candidates),
                walks=walks,
            )
        sleep(min(POLL_INTERVAL_MS, deadline.remaining_ms) / 1000)


def matches_one(found: Locator) -> bool:
    """Whether this candidate addresses exactly one element on the page now.

    A candidate the engine refuses answers the same as one that matched
    nothing. Candidates are stored data a person may write by hand in the
    editor, and one that is malformed costs its own rank rather than the Run.
    """
    try:
        return found.count() == 1
    except PlaywrightError:
        return False


def addressed_frame(page: Page, hops: Sequence[FrameHop]) -> Frame | None:
    """The frame the Target lives in, or nothing if it is not on the page yet.

    A frame that has not loaded is the ordinary case rather than an error: the
    walk finds nothing this time around and the deadline decides the rest.
    """
    frame = page.main_frame
    for hop in hops:
        children = frame.child_frames
        named = [child for child in children if hop.name and child.name == hop.name]
        if len(named) == 1:
            frame = named[0]
        elif 0 <= hop.index < len(children):
            frame = children[hop.index]
        else:
            return None
    return frame


def locate(root: Frame, candidate: SelectorCandidate) -> Locator:
    """The locator one candidate stands for, inside the scope it was recorded in."""
    scope: Frame | Locator = root
    for hop in candidate.shadow_path or ():
        scope = scope.locator(hop)
    return matching(scope, candidate)


def matching(scope: Frame | Locator, candidate: SelectorCandidate) -> Locator:
    """One candidate, read by the engine its kind names."""
    match candidate.kind:
        case CandidateKind.TESTID:
            return scope.get_by_test_id(candidate.value)
        case CandidateKind.ROLE:
            return scope.locator(f"role={candidate.value}")
        case CandidateKind.PLACEHOLDER:
            return scope.get_by_placeholder(candidate.value, exact=True)
        case CandidateKind.LABEL:
            return scope.get_by_label(candidate.value, exact=True)
        case CandidateKind.ALT:
            return scope.get_by_alt_text(candidate.value, exact=True)
        case CandidateKind.TEXT:
            return scope.get_by_text(candidate.value, exact=True)
        case CandidateKind.TITLE:
            return scope.get_by_title(candidate.value, exact=True)
        case CandidateKind.CSS:
            return scope.locator(f"css={candidate.value}")
