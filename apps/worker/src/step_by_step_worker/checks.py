from os import environ
from socket import create_connection
from socket import gethostname as host_name
from subprocess import run

from sqlalchemy import text
from step_by_step_core.bus import get_redis
from step_by_step_core.db import session_scope
from step_by_step_core.objects import artifact_bucket, object_store


def worker_id() -> str:
    return environ.get("WORKER_ID") or host_name()


def redis_reachable() -> str:
    client = get_redis()
    client.ping()
    reached = client.connection_pool.connection_kwargs
    return f"PONG from {reached.get('host')}:{reached.get('port')}"


def database_reachable() -> str:
    with session_scope() as session:
        version = session.execute(text("SHOW server_version")).scalar_one()
    return f"PostgreSQL {version}"


def display_open() -> str:
    display = environ["DISPLAY"]
    shown = run(
        ["xdpyinfo", "-display", display],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    dimensions = next(
        (
            line.split(":", 1)[1].strip()
            for line in shown.stdout.splitlines()
            if line.strip().startswith("dimensions:")
        ),
        "size unknown",
    )
    return f"{display}, {dimensions}"


def vnc_listening() -> str:
    port = int(environ.get("VNC_PORT", "5900"))
    with create_connection(("127.0.0.1", port), timeout=5) as vnc:
        banner = vnc.recv(12).decode("ascii", "replace").strip()
    if not banner.startswith("RFB"):
        raise ConnectionError(f"port {port} answered {banner!r}, not an RFB banner")
    return f"port {port}, {banner}"


def store_reachable() -> str:
    bucket = artifact_bucket()
    key = f"_readiness/{worker_id()}"
    store = object_store()
    store.put_object(Bucket=bucket, Key=key, Body=b"ready")
    read_back = store.get_object(Bucket=bucket, Key=key)["Body"].read()
    store.delete_object(Bucket=bucket, Key=key)
    if read_back != b"ready":
        raise ValueError(f"bucket {bucket!r} read back {read_back!r}")
    return f"bucket {bucket!r}, wrote and read one object"


STARTUP_CHECKS = {
    "redis": redis_reachable,
    "postgres": database_reachable,
    "display": display_open,
    "vnc": vnc_listening,
    "artifact store": store_reachable,
}
