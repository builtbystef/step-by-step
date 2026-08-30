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


@dataclass(frozen=True, slots=True)
class Deadline:
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
    NO_CANDIDATE_RESOLVED = "no_candidate_resolved"


@dataclass(frozen=True, slots=True)
class Resolved:
    locator: Locator
    rank: int
    candidate_count: int
    walks: int


@dataclass(frozen=True, slots=True)
class SelectorFailure:
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
    try:
        return found.count() == 1
    except PlaywrightError:
        return False


def addressed_frame(page: Page, hops: Sequence[FrameHop]) -> Frame | None:
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
    scope: Frame | Locator = root
    for hop in candidate.shadow_path or ():
        scope = scope.locator(hop)
    return matching(scope, candidate)


def matching(scope: Frame | Locator, candidate: SelectorCandidate) -> Locator:
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
