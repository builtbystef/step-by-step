"""The Postgres store turns a claimed row into exactly the document it names."""

from uuid import uuid4

from step_by_step_worker.store import work_from_claim


def test_test_run_executes_its_draft_snapshot_instead_of_the_latest_version() -> None:
    run_id = uuid4()
    draft_step = uuid4()
    version_step = uuid4()
    claimed = {
        "id": run_id,
        "is_test": True,
        "draft_snapshot": {
            "variables": [],
            "steps": [
                {
                    "id": str(draft_step),
                    "type": "navigate",
                    "label": "Draft destination",
                    "payload": {"url": "https://draft.example"},
                }
            ],
        },
        "version_document": {
            "variables": [],
            "steps": [
                {
                    "id": str(version_step),
                    "type": "navigate",
                    "label": "Published destination",
                    "payload": {"url": "https://published.example"},
                }
            ],
        },
        "default_step_timeout_ms": 30_000,
        "timeout_ms": 1_800_000,
        "variables": {},
    }

    work = work_from_claim(claimed)

    assert [step.id for step in work.document.steps] == [draft_step]
