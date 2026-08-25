"""RFB DES and VNC authentication, without a Worker or a database."""

from step_by_step_api.runs.rfb import des_encrypt, vnc_response


def test_des_encrypts_the_fips_46_vector() -> None:
    key = bytes.fromhex("133457799BBCDFF1")
    plain = bytes.fromhex("0123456789ABCDEF")

    assert des_encrypt(plain, key) == bytes.fromhex("85E813540F0AB405")


def test_vnc_response_is_two_des_blocks_under_a_bit_reversed_password() -> None:
    """VNC auth: 8-byte password, each byte bit-reversed, DES-ECB the challenge."""
    challenge = bytes(range(16))
    password = "pass"

    response = vnc_response(password, challenge)

    reversed_key = bytes(
        int(f"{byte:08b}"[::-1], 2) for byte in b"pass\x00\x00\x00\x00"
    )
    expected = des_encrypt(challenge[:8], reversed_key) + des_encrypt(
        challenge[8:], reversed_key
    )
    assert response == expected
    assert len(response) == 16
