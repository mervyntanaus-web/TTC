from collections.abc import Iterator
from functools import lru_cache

import boto3
from botocore.client import Config as BotoConfig

from app.config import get_settings
from app.models.video import StorageTier

settings = get_settings()

_TIER_BUCKETS = {
    StorageTier.HOT: settings.s3_hot_bucket,
    StorageTier.COLD: settings.s3_cold_bucket,
}


@lru_cache
def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=BotoConfig(signature_version="s3v4"),
    )


def ensure_buckets() -> None:
    client = _client()
    existing = {b["Name"] for b in client.list_buckets().get("Buckets", [])}
    for bucket in _TIER_BUCKETS.values():
        if bucket not in existing:
            client.create_bucket(Bucket=bucket)


def bucket_for(tier: StorageTier) -> str:
    return _TIER_BUCKETS[tier]


def put_file(tier: StorageTier, key: str, local_path: str) -> None:
    _client().upload_file(local_path, bucket_for(tier), key)


def put_bytes(tier: StorageTier, key: str, data: bytes) -> None:
    _client().put_object(Bucket=bucket_for(tier), Key=key, Body=data)


def get_object_stream(tier: StorageTier, key: str, byte_range: str | None = None) -> dict:
    kwargs = {"Bucket": bucket_for(tier), "Key": key}
    if byte_range:
        kwargs["Range"] = byte_range
    return _client().get_object(**kwargs)


def iter_object_bytes(tier: StorageTier, key: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
    body = get_object_stream(tier, key)["Body"]
    while chunk := body.read(chunk_size):
        yield chunk


def head_object(tier: StorageTier, key: str) -> dict:
    return _client().head_object(Bucket=bucket_for(tier), Key=key)


def download_to_path(tier: StorageTier, key: str, dest_path: str) -> None:
    _client().download_file(bucket_for(tier), key, dest_path)


def copy_object(tier: StorageTier, source_key: str, dest_key: str) -> None:
    bucket = bucket_for(tier)
    _client().copy_object(Bucket=bucket, Key=dest_key, CopySource={"Bucket": bucket, "Key": source_key})


def move_between_tiers(source_tier: StorageTier, dest_tier: StorageTier, key: str) -> None:
    """Simulates archive/restore tiering: copy the object into the
    destination tier's bucket and remove it from the source tier."""
    client = _client()
    client.copy_object(
        Bucket=bucket_for(dest_tier),
        Key=key,
        CopySource={"Bucket": bucket_for(source_tier), "Key": key},
    )
    client.delete_object(Bucket=bucket_for(source_tier), Key=key)


def delete_object(tier: StorageTier, key: str) -> None:
    _client().delete_object(Bucket=bucket_for(tier), Key=key)


def presigned_url(tier: StorageTier, key: str, expires_in: int = 3600) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket_for(tier), "Key": key},
        ExpiresIn=expires_in,
    )
