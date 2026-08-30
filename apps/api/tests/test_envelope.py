from dataclasses import replace

import pytest
from nacl.exceptions import CryptoError
from step_by_step_api.envelope import open_sealed, rewrap, seal

MASTER = bytes(range(32))

OTHER_MASTER = bytes(range(32, 64))

THIRD_MASTER = bytes(range(64, 96))


def must_rewrap(sealed_data_key: bytes, current: bytes, new: bytes) -> bytes:
    rotated = rewrap(sealed_data_key, current, new)
    assert rotated is not None
    return rotated


def flip_a_byte(blob: bytes) -> bytes:
    middle = len(blob) // 2
    return blob[:middle] + bytes([blob[middle] ^ 0x01]) + blob[middle + 1 :]


def test_a_sealed_value_opens_to_the_bytes_it_was_sealed_from() -> None:
    sealed = seal(b"hunter2", MASTER)

    assert open_sealed(sealed, MASTER) == b"hunter2"


def test_the_same_plaintext_seals_to_a_different_record_every_time() -> None:
    once = seal(b"hunter2", MASTER)
    twice = seal(b"hunter2", MASTER)

    assert once.value != twice.value
    assert once.data_key != twice.data_key


def test_a_tampered_value_is_an_error_rather_than_partial_plaintext() -> None:
    sealed = seal(b"hunter2", MASTER)

    tampered = replace(sealed, value=flip_a_byte(sealed.value))

    with pytest.raises(CryptoError):
        open_sealed(tampered, MASTER)


def test_a_tampered_data_key_is_an_error_too() -> None:
    sealed = seal(b"hunter2", MASTER)

    tampered = replace(sealed, data_key=flip_a_byte(sealed.data_key))

    with pytest.raises(CryptoError):
        open_sealed(tampered, MASTER)


def test_a_wrong_master_key_is_an_error_rather_than_garbage() -> None:
    sealed = seal(b"hunter2", MASTER)

    with pytest.raises(CryptoError):
        open_sealed(sealed, OTHER_MASTER)


def test_re_wrapping_moves_a_record_to_a_new_master_key_intact() -> None:
    sealed = seal(b"hunter2", MASTER)

    rotated = replace(
        sealed, data_key=must_rewrap(sealed.data_key, MASTER, OTHER_MASTER)
    )

    assert rotated.value == sealed.value
    assert open_sealed(rotated, OTHER_MASTER) == b"hunter2"
    with pytest.raises(CryptoError):
        open_sealed(rotated, MASTER)


def test_re_wrapping_an_already_rotated_record_reports_it_and_changes_nothing() -> None:
    sealed = seal(b"hunter2", MASTER)
    rotated = replace(
        sealed, data_key=must_rewrap(sealed.data_key, MASTER, OTHER_MASTER)
    )

    assert rewrap(rotated.data_key, MASTER, OTHER_MASTER) is None
    assert open_sealed(rotated, OTHER_MASTER) == b"hunter2"


def test_re_wrapping_a_record_under_neither_key_fails_rather_than_passing() -> None:
    sealed = seal(b"hunter2", MASTER)

    with pytest.raises(CryptoError):
        rewrap(sealed.data_key, OTHER_MASTER, THIRD_MASTER)
