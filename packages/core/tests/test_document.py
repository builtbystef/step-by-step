"""The shared Workflow document contract."""

from step_by_step_core.document import CandidateKind, Target


def test_target_reads_the_stored_document_shape() -> None:
    """A Worker reads the same camelCase Target that the backend stored."""
    target = Target.from_document(
        {
            "candidates": [
                {
                    "kind": "css",
                    "value": "button.save",
                    "shadowPath": ["account-card"],
                }
            ],
            "frame": [{"index": 1, "name": "details"}],
        }
    )

    assert target.candidates[0].kind is CandidateKind.CSS
    assert target.candidates[0].shadow_path == ["account-card"]
    assert target.frame is not None
    assert target.frame[0].index == 1
