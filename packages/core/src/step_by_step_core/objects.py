"""The Artifact store seam: plain S3 against a configurable endpoint.

Garage is the store, but nothing here knows that. Artifacts are read and
written through the S3 API only, so the store stays swappable — which is also
why this is boto3 rather than any vendor's own SDK.

**Two endpoints, not one.** `object_store()` reads and writes at
`S3_ENDPOINT_URL`, the address a process inside the stack resolves.
`signing_store()` mints presigned URLs against `S3_PUBLIC_ENDPOINT`, the
address the *user's browser* resolves. They are the same on a developer's host
and different in a real deployment; signing with the internal one passes every
in-network test and breaks every real download.

Addressing is path-style in both. Virtual-host style would put the bucket in
the hostname, which no browser can resolve for a compose service and which
Garage serves only with a root domain configured.
"""

from functools import lru_cache
from os import environ

import boto3
from botocore.client import BaseClient
from botocore.config import Config


def _client(endpoint: str) -> BaseClient:
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=environ["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=environ["S3_SECRET_ACCESS_KEY"],
        region_name=environ["S3_REGION"],
        config=Config(s3={"addressing_style": "path"}),
    )


@lru_cache(maxsize=1)
def object_store() -> BaseClient:
    """The client a process reads and writes objects with, inside the stack."""
    return _client(environ["S3_ENDPOINT_URL"])


@lru_cache(maxsize=1)
def signing_store() -> BaseClient:
    """The client presigned URLs are minted with, for a browser to follow."""
    return _client(environ["S3_PUBLIC_ENDPOINT"])


def artifact_bucket() -> str:
    """The bucket every Run's Artifacts live in."""
    return environ["S3_BUCKET"]
