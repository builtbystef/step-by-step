from uuid import uuid4

import pytest
from pydantic import ValidationError
from step_by_step_core.document import CandidateKind, Target, Variable, WorkflowDocument


def test_sparse_steps_observe_execution_defaults() -> None:
    document = WorkflowDocument.model_validate(
        {
            "steps": [
                {
                    "id": str(uuid4()),
                    "type": "navigate",
                    "label": "Open invoices",
                    "payload": {"url": "https://example.test/invoices"},
                }
            ],
            "variables": [],
        }
    )

    step = document.steps[0]
    assert step.optional is False
    assert step.disabled is False
    assert step.screenshot is False
    assert step.timeout_ms is None


def test_target_reads_the_stored_document_shape() -> None:
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


def test_a_secret_variable_may_carry_a_vault_pointer() -> None:
    secret_id = uuid4()
    variable = Variable.model_validate(
        {
            "name": "password",
            "secret": True,
            "secretId": str(secret_id),
            "secretName": "acme-portal-password",
        }
    )

    assert variable.secret is True
    assert variable.secret_id == secret_id
    assert variable.secret_name == "acme-portal-password"


def test_a_secret_variable_without_a_vault_pointer_is_still_a_variable() -> None:
    variable = Variable.model_validate({"name": "password", "secret": True})

    assert variable.secret_id is None
    assert variable.secret_name is None


def test_a_non_secret_variable_may_not_carry_a_vault_pointer() -> None:
    with pytest.raises(ValidationError, match="secretId") as refused:
        Variable.model_validate(
            {
                "name": "tenant",
                "secret": False,
                "secretId": str(uuid4()),
                "secretName": "acme-portal-password",
            }
        )

    assert "secretId" in str(refused.value)
