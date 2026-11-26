"""Save uploaded files to disk with a size limit."""

from pathlib import Path
from typing import IO

CHUNK_SIZE = 1024 * 1024  # 1 MiB: bounds memory use whatever the upload size


class UploadTooLargeError(Exception):
    """The upload is larger than the allowed maximum size."""


def save_upload(
    source: IO[bytes],
    destination: Path,
    *,
    max_bytes: int,
    chunk_size: int = CHUNK_SIZE,
) -> int:
    """Copy source to destination in chunks, stopping if it exceeds max_bytes.

    destination must not exist. If anything fails (the size limit, a read or
    write error, or a cancelled request), nothing is left at destination.

    Returns:
        The number of bytes written.

    Raises:
        ValueError: max_bytes or chunk_size is not positive.
        UploadTooLargeError: source holds more than max_bytes bytes.
        FileExistsError: destination already exists; it is left untouched.
    """
    if max_bytes <= 0:
        raise ValueError(f"max_bytes must be positive, got {max_bytes}")
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be positive, got {chunk_size}")

    written = 0
    # Never overwrite; opened outside the try so an existing file survives
    file = destination.open("xb")
    try:
        with file:
            while chunk := source.read(chunk_size):  # bounded memory: one chunk at a time
                if written + len(chunk) > max_bytes:
                    raise UploadTooLargeError(f"Upload exceeds the limit of {max_bytes} bytes")
                file.write(chunk)
                written += len(chunk)
    except BaseException:
        destination.unlink(missing_ok=True)  # the file is closed by now
        raise
    return written
