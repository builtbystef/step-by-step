from __future__ import annotations

from asyncio import StreamReader, StreamWriter
from ctypes import POINTER, Structure, c_char, c_int, cdll
from ctypes.util import find_library
from typing import Protocol

from fastapi import WebSocket

RFB_VERSION = b"RFB 003.008\n"
SECURITY_NONE = 1
SECURITY_VNC = 2


class RfbError(Exception):
    pass


class BytePipe(Protocol):
    async def readexactly(self, n: int) -> bytes: ...

    async def write(self, data: bytes) -> None: ...


class _DESKeySchedule(Structure):
    _fields_ = [("ks", c_char * 128)]


def _libcrypto():
    name = find_library("crypto")
    if name is None:
        raise RfbError("libcrypto is required for VNC authentication")
    lib = cdll.LoadLibrary(name)
    lib.DES_set_key_unchecked.argtypes = [c_char * 8, POINTER(_DESKeySchedule)]
    lib.DES_ecb_encrypt.argtypes = [
        c_char * 8,
        c_char * 8,
        POINTER(_DESKeySchedule),
        c_int,
    ]
    return lib


_DES = _libcrypto()


def des_encrypt(block: bytes, key: bytes) -> bytes:
    if len(block) != 8 or len(key) != 8:
        raise ValueError("DES acts on 8-byte blocks with an 8-byte key")
    schedule = _DESKeySchedule()
    _DES.DES_set_key_unchecked((c_char * 8).from_buffer_copy(key), schedule)
    out = (c_char * 8)()
    _DES.DES_ecb_encrypt(
        (c_char * 8).from_buffer_copy(block),
        out,
        schedule,
        1,
    )
    return bytes(out)


def vnc_key(password: str) -> bytes:
    raw = password.encode("latin-1")[:8].ljust(8, b"\x00")
    return bytes(int(f"{byte:08b}"[::-1], 2) for byte in raw)


def vnc_response(password: str, challenge: bytes) -> bytes:
    key = vnc_key(password)
    return des_encrypt(challenge[:8], key) + des_encrypt(challenge[8:], key)


async def authenticate_as_client(pipe: BytePipe, password: str) -> None:
    version = await pipe.readexactly(12)
    if not version.startswith(b"RFB "):
        raise RfbError(f"not an RFB banner: {version!r}")
    await pipe.write(RFB_VERSION)
    count = (await pipe.readexactly(1))[0]
    types = await pipe.readexactly(count)
    if SECURITY_VNC in types:
        await pipe.write(bytes([SECURITY_VNC]))
        challenge = await pipe.readexactly(16)
        await pipe.write(vnc_response(password, challenge))
    elif SECURITY_NONE in types:
        await pipe.write(bytes([SECURITY_NONE]))
    else:
        raise RfbError(f"no usable security type in {types!r}")
    result = int.from_bytes(await pipe.readexactly(4), "big")
    if result != 0:
        raise RfbError("VNC authentication failed")


async def offer_none(pipe: BytePipe) -> None:
    await pipe.write(RFB_VERSION)
    version = await pipe.readexactly(12)
    if not version.startswith(b"RFB "):
        raise RfbError(f"client sent {version!r}, not an RFB banner")
    await pipe.write(bytes([1, SECURITY_NONE]))
    chosen = (await pipe.readexactly(1))[0]
    if chosen != SECURITY_NONE:
        raise RfbError(f"client chose security type {chosen}")
    await pipe.write(b"\x00\x00\x00\x00")


class StreamPipe:
    def __init__(self, reader: StreamReader, writer: StreamWriter) -> None:
        self._reader = reader
        self._writer = writer

    async def readexactly(self, n: int) -> bytes:
        return await self._reader.readexactly(n)

    async def write(self, data: bytes) -> None:
        self._writer.write(data)
        await self._writer.drain()


class WebsocketPipe:
    def __init__(self, socket: WebSocket) -> None:
        self._socket = socket
        self._buf = bytearray()

    async def readexactly(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = await self._socket.receive_bytes()
            self._buf.extend(chunk)
        out = bytes(self._buf[:n])
        del self._buf[:n]
        return out

    async def write(self, data: bytes) -> None:
        await self._socket.send_bytes(data)
