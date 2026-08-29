"""Envelope encryption: what every vault row is sealed with (ADR 0003).

Two levels, both PyNaCl `SecretBox` (XSalsa20-Poly1305). Sealing a value mints
a fresh 32-byte data key, seals the plaintext under it, and seals that data key
under the master key; the row stores the two sealed blobs and nothing else, so
Postgres never sees plaintext or an unwrapped data key. A fresh data key per
record is what keeps the master key rotatable without touching a plaintext:
re-wrapping re-seals the data key alone.

Every function here takes the master key it works with. The one that reads a
key from the environment is `read_master_key()`; `master_key()` is that
function on `STEPBYSTEP_MASTER_KEY`, and the backend calls it at startup.

The module is the backend's alone. It never ships in the Worker image, because
Workers never hold the master key (ADR 0004).
"""

from base64 import b64decode
from binascii import Error as NotBase64
from dataclasses import dataclass
from functools import lru_cache
from os import environ

from nacl.exceptions import CryptoError
from nacl.secret import SecretBox
from nacl.utils import random

KEY_BYTES = SecretBox.KEY_SIZE
"""32 — the size of the master key and of every data key."""

MASTER_KEY_VARIABLE = "STEPBYSTEP_MASTER_KEY"
"""Where the master key arrives: base64 of 32 bytes, in the environment."""

NEW_MASTER_KEY_VARIABLE = "STEPBYSTEP_NEW_MASTER_KEY"
"""The replacement key `rotate-master-key` re-wraps every sealed row onto."""


class MasterKeyError(RuntimeError):
    """The master key is missing or unusable, and the backend must not start."""


def read_master_key(variable: str) -> bytes:
    """Decode a 32-byte master key from the named environment variable.

    Every failure is the same kind — the operator has one variable to fix —
    and the message says which of the three ways it is wrong. The current key
    and the rotation's replacement both come through here, so they refuse for
    the same reasons.
    """
    try:
        supplied = environ[variable]
    except KeyError:
        raise MasterKeyError(f"{variable} is not set") from None

    try:
        # Stripped, because a key handed over as a compose secret arrives
        # with the trailing newline of the file it was written into.
        key = b64decode(supplied.strip(), validate=True)
    except NotBase64 as malformed:
        raise MasterKeyError(
            f"{variable} is not valid base64: {malformed}"
        ) from malformed

    if len(key) != KEY_BYTES:
        raise MasterKeyError(
            f"{variable} decodes to {len(key)} bytes; a master key is {KEY_BYTES}"
        )
    return key


@lru_cache(maxsize=1)
def master_key() -> bytes:
    """The instance's master key, decoded from the environment.

    The backend calls this at startup so that a key it cannot use stops the
    process rather than the first vault write.
    """
    return read_master_key(MASTER_KEY_VARIABLE)


@dataclass(frozen=True, slots=True)
class Sealed:
    """One sealed record: what a vault row stores, and all it stores.

    Each blob carries its own nonce, prepended by `SecretBox`, so nothing else
    has to be kept beside them.
    """

    value: bytes
    """The plaintext, sealed under the data key."""

    data_key: bytes
    """The data key, sealed under the master key."""


def seal(plaintext: bytes, master: bytes) -> Sealed:
    """Seal a value under a data key of its own, and that key under `master`."""
    data_key = random(KEY_BYTES)
    return Sealed(
        value=bytes(SecretBox(data_key).encrypt(plaintext)),
        data_key=bytes(SecretBox(master).encrypt(data_key)),
    )


def open_sealed(sealed: Sealed, master: bytes) -> bytes:
    """Return the plaintext, or raise `nacl.exceptions.CryptoError`.

    Both levels are authenticated, so a tampered blob or a wrong master key
    raises rather than returning bytes that only look like the plaintext.
    """
    data_key = SecretBox(master).decrypt(sealed.data_key)
    return SecretBox(data_key).decrypt(sealed.value)


def rewrap(sealed_data_key: bytes, current: bytes, new: bytes) -> bytes | None:
    """Re-seal a record's data key from `current` to `new`, or report it done.

    `None` means the key already opens under `new` — the record was re-wrapped
    by an earlier pass — so the caller writes nothing for it. That is what
    makes a rotation re-runnable: a pass interrupted halfway leaves a table
    holding both, and a second pass completes it rather than corrupting the
    records the first one finished.

    The plaintext is neither read nor rewritten; only the sealed data key
    changes, which is the whole point of the envelope.
    """
    try:
        data_key = SecretBox(current).decrypt(sealed_data_key)
    except CryptoError:
        SecretBox(new).decrypt(sealed_data_key)
        return None
    return bytes(SecretBox(new).encrypt(data_key))
