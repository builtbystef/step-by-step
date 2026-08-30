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
    return _client(environ["S3_ENDPOINT_URL"])


@lru_cache(maxsize=1)
def signing_store() -> BaseClient:
    return _client(environ["S3_PUBLIC_ENDPOINT"])


def artifact_bucket() -> str:
    return environ["S3_BUCKET"]
