"""Drop-in replacement for app.services.storage_service, backed by a local
directory instead of MinIO/S3, so the pipeline can be exercised end-to-end
in environments without a running object store (e.g. this test suite)."""
import shutil
from pathlib import Path

from app.models.video import StorageTier


class _FakeBody:
    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def read(self, size: int | None = None) -> bytes:
        if size is None:
            chunk, self._pos = self._data[self._pos :], len(self._data)
            return chunk
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk

    def iter_chunks(self, chunk_size: int = 1024 * 1024):
        while True:
            chunk = self.read(chunk_size)
            if not chunk:
                break
            yield chunk


class FakeStorageBackend:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, tier: StorageTier, key: str) -> Path:
        p = self.root / tier.value / key
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def ensure_buckets(self) -> None:
        pass

    def put_file(self, tier: StorageTier, key: str, local_path: str) -> None:
        shutil.copyfile(local_path, self._path(tier, key))

    def put_bytes(self, tier: StorageTier, key: str, data: bytes) -> None:
        self._path(tier, key).write_bytes(data)

    def get_object_stream(self, tier: StorageTier, key: str, byte_range: str | None = None) -> dict:
        data = self._path(tier, key).read_bytes()
        if byte_range:
            _, _, spec = byte_range.partition("=")
            start_str, _, end_str = spec.partition("-")
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else len(data) - 1
            data = data[start : end + 1]
        return {"Body": _FakeBody(data)}

    def head_object(self, tier: StorageTier, key: str) -> dict:
        return {"ContentLength": self._path(tier, key).stat().st_size}

    def download_to_path(self, tier: StorageTier, key: str, dest_path: str) -> None:
        shutil.copyfile(self._path(tier, key), dest_path)

    def copy_object(self, tier: StorageTier, source_key: str, dest_key: str) -> None:
        shutil.copyfile(self._path(tier, source_key), self._path(tier, dest_key))

    def move_between_tiers(self, source_tier: StorageTier, dest_tier: StorageTier, key: str) -> None:
        src = self._path(source_tier, key)
        dst = self._path(dest_tier, key)
        shutil.move(str(src), str(dst))

    def delete_object(self, tier: StorageTier, key: str) -> None:
        self._path(tier, key).unlink(missing_ok=True)

    def presigned_url(self, tier: StorageTier, key: str, expires_in: int = 3600) -> str:
        return f"file://{self._path(tier, key)}"


def install(monkeypatch, root: Path) -> FakeStorageBackend:
    """Monkeypatches every function in app.services.storage_service to
    delegate to a FakeStorageBackend rooted at `root`."""
    from app.services import storage_service

    backend = FakeStorageBackend(root)
    for name in (
        "ensure_buckets",
        "put_file",
        "put_bytes",
        "get_object_stream",
        "head_object",
        "download_to_path",
        "copy_object",
        "move_between_tiers",
        "delete_object",
        "presigned_url",
    ):
        monkeypatch.setattr(storage_service, name, getattr(backend, name))
    return backend
