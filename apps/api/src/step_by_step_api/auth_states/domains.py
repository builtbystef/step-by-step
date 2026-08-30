import ctypes
import ctypes.util
from functools import cache


@cache
def _libpsl() -> ctypes.CDLL:
    library = ctypes.util.find_library("psl")
    if library is None:
        raise RuntimeError("libpsl is required to compute registrable domains")
    psl = ctypes.CDLL(library)
    psl.psl_builtin.restype = ctypes.c_void_p
    psl.psl_registrable_domain.argtypes = (ctypes.c_void_p, ctypes.c_char_p)
    psl.psl_registrable_domain.restype = ctypes.c_char_p
    return psl


def registrable_domain(hostname: str) -> str:
    normalized = hostname.rstrip(".").lower().encode("idna")
    psl = _libpsl()
    found = psl.psl_registrable_domain(psl.psl_builtin(), normalized)
    if found is None:
        raise ValueError(f"{hostname!r} has no registrable domain")
    return found.decode("ascii")
