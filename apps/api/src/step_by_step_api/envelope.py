from base64 import b64decode
from binascii import Error as NotBase64
from dataclasses import dataclass
from functools import lru_cache
from os import environ

from nacl.exceptions import CryptoError
from nacl.secret import SecretBox
from nacl.utils import random

KEY_BYTES = SecretBox.KEY_SIZE

MASTER_KEY_VARIABLE = "STEPBYSTEP_MASTER_KEY"

NEW_MASTER_KEY_VARIABLE = "STEPBYSTEP_NEW_MASTER_KEY"


class MasterKeyError(RuntimeError):
    pass


def read_master_key(variable: str) -> bytes:
    try:
        supplied = environ[variable]
    except KeyError:
        raise MasterKeyError(f"{variable} is not set") from None

    try:
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
    return read_master_key(MASTER_KEY_VARIABLE)


@dataclass(frozen=True, slots=True)
class Sealed:
    value: bytes

    data_key: bytes


def seal(plaintext: bytes, master: bytes) -> Sealed:
    data_key = random(KEY_BYTES)
    return Sealed(
        value=bytes(SecretBox(data_key).encrypt(plaintext)),
        data_key=bytes(SecretBox(master).encrypt(data_key)),
    )


def open_sealed(sealed: Sealed, master: bytes) -> bytes:
    data_key = SecretBox(master).decrypt(sealed.data_key)
    return SecretBox(data_key).decrypt(sealed.value)


def rewrap(sealed_data_key: bytes, current: bytes, new: bytes) -> bytes | None:
    try:
        data_key = SecretBox(current).decrypt(sealed_data_key)
    except CryptoError:
        SecretBox(new).decrypt(sealed_data_key)
        return None
    return bytes(SecretBox(new).encrypt(data_key))
