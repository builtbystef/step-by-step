from datetime import timedelta
from uuid import UUID

import pytest
from fake_vnc import FakeVnc
from sqlalchemy import func, select
from starlette.testclient import WebSocketDenialResponse
from starlette.websockets import WebSocketDisconnect
from step_by_step_api import clock
from step_by_step_api.runs.models import Run, RunTakeoverTicket
from step_by_step_api.runs.vnc import (
    VNC_CONTROL_PASSWORD_VARIABLE,
    VNC_VIEW_PASSWORD_VARIABLE,
)
from step_by_step_core.bus import get_redis
from step_by_step_core.db import session_scope
from test_heartbeats import TOKEN, claimed_run
from test_runs import published_workflow, start
from test_takeover import org_session, park
from test_workflows import NewAccount

pytestmark = pytest.mark.integration
DISPATCH_LIST = "runs:dispatch"
VIEW_PASSWORD = "devview1"
CONTROL_PASSWORD = "devctl01"
KEY_A = bytes([4, 1, 0, 0, 0, 0, 0, 0x41])


@pytest.fixture(autouse=True)
def empty_dispatch_list() -> None:
    get_redis().delete(DISPATCH_LIST)


@pytest.fixture(autouse=True)
def internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_TOKEN", TOKEN)


@pytest.fixture(autouse=True)
def vnc_passwords(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VNC_VIEW_PASSWORD_VARIABLE, VIEW_PASSWORD)
    monkeypatch.setenv(VNC_CONTROL_PASSWORD_VARIABLE, CONTROL_PASSWORD)


def tickets_for(run_id: str) -> int:
    with session_scope() as db:
        return db.execute(
            select(func.count()).where(RunTakeoverTicket.run_id == UUID(run_id))
        ).scalar_one()


def point_at(run_id: str, endpoint: str) -> None:
    with session_scope() as db:
        run = db.get(Run, UUID(run_id))
        assert run is not None
        run.worker_vnc_endpoint = endpoint
        db.commit()


def open_rfb(ws):
    assert ws.receive_bytes() == b"RFB 003.008\n"
    ws.send_bytes(b"RFB 003.008\n")
    types = ws.receive_bytes()
    assert types[0] >= 1
    ws.send_bytes(b"\x01")
    assert ws.receive_bytes() == b"\x00\x00\x00\x00"
    ws.send_bytes(b"\x01")
    return ws.receive_bytes()


def mint_stream(client, run_id: str) -> str:
    minted = client.post(f"/api/runs/{run_id}/stream-ticket")
    assert minted.status_code == 200, minted.text
    return minted.json()["ticket"]


def test_a_stream_ticket_for_an_owned_running_run_is_minted(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = claimed_run(account)

    minted = account.client.post(f"/api/runs/{run_id}/stream-ticket")

    assert minted.status_code == 200, minted.text
    body = minted.json()
    assert body["ticket"]
    assert body["ws_url"] == f"/api/runs/{run_id}/vnc?ticket={body['ticket']}"
    assert body["expires_at"]
    assert "deadline_at" not in body


def test_another_organizations_run_mints_no_stream_ticket(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    stranger = new_account()
    run_id = claimed_run(owner)

    refused = stranger.client.post(f"/api/runs/{run_id}/stream-ticket")

    assert refused.status_code == 404
    assert refused.json()["code"] == "run_not_found"
    assert tickets_for(run_id) == 0


def test_a_terminal_run_mints_no_stream_ticket(new_account: NewAccount) -> None:
    account = new_account()
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]
    assert account.client.post(f"/api/runs/{run_id}/cancel").status_code == 202

    refused = account.client.post(f"/api/runs/{run_id}/stream-ticket")

    assert refused.status_code == 409
    assert refused.json()["code"] == "run_terminal"
    assert tickets_for(run_id) == 0


def test_a_stream_ticket_opens_a_view_only_rfb_socket(new_account: NewAccount) -> None:
    account = new_account()
    run_id = claimed_run(account)
    with FakeVnc(view_password=VIEW_PASSWORD, control_password=CONTROL_PASSWORD) as vnc:
        point_at(run_id, vnc.endpoint)
        ticket = mint_stream(account.client, run_id)

        with account.client.websocket_connect(
            f"/api/runs/{run_id}/vnc?ticket={ticket}"
        ) as ws:
            frames = open_rfb(ws)
            ws.send_bytes(KEY_A)
            _wait_until(lambda: vnc.clients and vnc.clients[0].seen_keys)

        assert b"test" in frames
        assert vnc.connection_count == 1
        assert vnc.clients[0].password_used == VIEW_PASSWORD
        assert vnc.clients[0].applied_keys == []


def test_a_takeover_holders_socket_accepts_keystrokes(new_account: NewAccount) -> None:
    account = new_account()
    run_id = claimed_run(account)
    park(run_id)
    with FakeVnc(view_password=VIEW_PASSWORD, control_password=CONTROL_PASSWORD) as vnc:
        point_at(run_id, vnc.endpoint)
        taken = account.client.post(f"/api/runs/{run_id}/takeover")
        assert taken.status_code == 200, taken.text
        ticket = taken.json()["ticket"]

        with account.client.websocket_connect(
            f"/api/runs/{run_id}/vnc?ticket={ticket}"
        ) as ws:
            frames = open_rfb(ws)
            ws.send_bytes(KEY_A)
            _wait_until(lambda: vnc.clients and vnc.clients[0].applied_keys)

        assert b"test" in frames
        assert vnc.clients[0].password_used == CONTROL_PASSWORD
        assert 0x41 in vnc.clients[0].applied_keys


def test_takeover_ending_closes_control_and_a_new_stream_is_view_only(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = claimed_run(account)
    park(run_id)
    with FakeVnc(view_password=VIEW_PASSWORD, control_password=CONTROL_PASSWORD) as vnc:
        point_at(run_id, vnc.endpoint)
        ticket = account.client.post(f"/api/runs/{run_id}/takeover").json()["ticket"]
        with account.client.websocket_connect(
            f"/api/runs/{run_id}/vnc?ticket={ticket}"
        ) as ws:
            open_rfb(ws)
            assert (
                account.client.post(f"/api/runs/{run_id}/handback").status_code == 202
            )
            with pytest.raises(WebSocketDisconnect):
                for _ in range(20):
                    ws.receive_bytes()

        ticket = mint_stream(account.client, run_id)
        with account.client.websocket_connect(
            f"/api/runs/{run_id}/vnc?ticket={ticket}"
        ) as ws:
            open_rfb(ws)
            ws.send_bytes(KEY_A)
            _wait_until(lambda: len(vnc.clients) >= 2 and vnc.clients[-1].seen_keys)

        assert vnc.clients[-1].password_used == VIEW_PASSWORD
        assert vnc.clients[-1].applied_keys == []


def test_a_ticket_cannot_be_redeemed_twice(new_account: NewAccount) -> None:
    account = new_account()
    run_id = claimed_run(account)
    with FakeVnc(view_password=VIEW_PASSWORD, control_password=CONTROL_PASSWORD) as vnc:
        point_at(run_id, vnc.endpoint)
        ticket = mint_stream(account.client, run_id)
        with account.client.websocket_connect(
            f"/api/runs/{run_id}/vnc?ticket={ticket}"
        ) as ws:
            open_rfb(ws)

        with (
            pytest.raises(WebSocketDenialResponse) as denied,
            account.client.websocket_connect(f"/api/runs/{run_id}/vnc?ticket={ticket}"),
        ):
            pass

        assert denied.value.status_code == 404
        assert vnc.connection_count == 1


def test_an_expired_ticket_never_connects_to_the_worker(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = new_account()
    run_id = claimed_run(account)
    with FakeVnc(view_password=VIEW_PASSWORD, control_password=CONTROL_PASSWORD) as vnc:
        point_at(run_id, vnc.endpoint)
        ticket = mint_stream(account.client, run_id)
        later = clock.now() + timedelta(seconds=61)
        monkeypatch.setattr(clock, "now", lambda: later)

        with (
            pytest.raises(WebSocketDenialResponse) as denied,
            account.client.websocket_connect(f"/api/runs/{run_id}/vnc?ticket={ticket}"),
        ):
            pass

        assert denied.value.status_code == 404
        assert vnc.connection_count == 0


def test_another_organizations_run_never_connects_to_the_worker(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    stranger = new_account()
    run_id = claimed_run(owner)
    with FakeVnc(view_password=VIEW_PASSWORD, control_password=CONTROL_PASSWORD) as vnc:
        point_at(run_id, vnc.endpoint)

        with (
            pytest.raises(WebSocketDenialResponse) as denied,
            stranger.client.websocket_connect(
                f"/api/runs/{run_id}/vnc?ticket=not-a-ticket"
            ),
        ):
            pass

        assert denied.value.status_code == 404
        assert vnc.connection_count == 0


def test_a_terminal_run_never_connects_to_the_worker(new_account: NewAccount) -> None:
    account = new_account()
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]
    assert account.client.post(f"/api/runs/{run_id}/cancel").status_code == 202
    with FakeVnc(view_password=VIEW_PASSWORD, control_password=CONTROL_PASSWORD) as vnc:
        point_at(run_id, vnc.endpoint)
        with (
            pytest.raises(WebSocketDenialResponse) as denied,
            account.client.websocket_connect(
                f"/api/runs/{run_id}/vnc?ticket=not-a-ticket"
            ),
        ):
            pass

        assert denied.value.status_code == 404
        assert vnc.connection_count == 0


def test_a_second_session_can_watch_while_the_first_holds_control(
    new_account: NewAccount,
) -> None:
    account = new_account()
    other = org_session(account)
    run_id = claimed_run(account)
    park(run_id)
    with FakeVnc(view_password=VIEW_PASSWORD, control_password=CONTROL_PASSWORD) as vnc:
        point_at(run_id, vnc.endpoint)
        control_ticket = account.client.post(f"/api/runs/{run_id}/takeover").json()[
            "ticket"
        ]
        view_ticket = mint_stream(other, run_id)

        with (
            account.client.websocket_connect(
                f"/api/runs/{run_id}/vnc?ticket={control_ticket}"
            ) as control_ws,
            other.websocket_connect(
                f"/api/runs/{run_id}/vnc?ticket={view_ticket}"
            ) as view_ws,
        ):
            control_frames = open_rfb(control_ws)
            view_frames = open_rfb(view_ws)
            control_ws.send_bytes(KEY_A)
            view_ws.send_bytes(KEY_A)
            _wait_until(
                lambda: (
                    len(vnc.clients) == 2
                    and any(client.applied_keys for client in vnc.clients)
                )
            )

        assert b"test" in control_frames
        assert b"test" in view_frames
        used = {client.password_used for client in vnc.clients}
        assert used == {VIEW_PASSWORD, CONTROL_PASSWORD}
        applied = [client.applied_keys for client in vnc.clients]
        assert [0x41] in applied
        assert [] in applied


def _wait_until(ready, tries: int = 20) -> None:
    import time

    for _ in range(tries):
        if ready():
            return
        time.sleep(0.05)
    raise AssertionError("timed out")
