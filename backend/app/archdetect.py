"""Autodetección de arquitectura (ISA) por cabecera ELF — CP-6 / ADR-021.

Sin dependencias externas: lee los primeros bytes de la cabecera ELF y mapea
`e_machine` (+ endianness para MIPS) al nombre de perfil de la sandbox
(emulation/profiles/<arch>.env). Se usa en `POST /samples` cuando el que sube no
especifica `arch` (o pide `auto`).

Cabecera ELF (ELF32/ELF64 comparten los primeros 20 bytes relevantes):
    [0:4]  e_ident magic  = 7f 45 4c 46  ("\\x7fELF")
    [4]    EI_CLASS       (1=32-bit, 2=64-bit)  -- no se necesita para el mapeo
    [5]    EI_DATA        (1=little-endian, 2=big-endian)
    [18:20] e_machine     (uint16, en la endianness de EI_DATA)
"""
from __future__ import annotations

import struct

# EI_DATA
ELFDATA2LSB = 1  # little-endian
ELFDATA2MSB = 2  # big-endian

# e_machine (subset relevante para IoT)
_EM_386 = 3
_EM_MIPS = 8
_EM_ARM = 40
_EM_X86_64 = 62
_EM_AARCH64 = 183

# Nombres legibles de ISAs detectables pero SIN perfil en la sandbox (para el mensaje 400).
_KNOWN_UNSUPPORTED = {
    "i386": "x86 de 32 bits",
    "aarch64": "ARM de 64 bits",
}


def detect_arch_from_bytes(head: bytes) -> str | None:
    """Devuelve el nombre de ISA ('arm'|'mips'|'mipsel'|'x86_64'|'i386'|'aarch64')
    o None si `head` no es un ELF reconocible."""
    if len(head) < 20 or head[:4] != b"\x7fELF":
        return None
    ei_data = head[5]
    endian = "<" if ei_data == ELFDATA2LSB else ">"
    (e_machine,) = struct.unpack_from(endian + "H", head, 18)

    if e_machine == _EM_ARM:
        return "arm"
    if e_machine == _EM_MIPS:
        # EM_MIPS es el mismo para ambos endianness; los diferencia EI_DATA.
        return "mips" if ei_data == ELFDATA2MSB else "mipsel"
    if e_machine == _EM_X86_64:
        return "x86_64"
    if e_machine == _EM_386:
        return "i386"
    if e_machine == _EM_AARCH64:
        return "aarch64"
    return None


def is_known_unsupported(arch: str | None) -> bool:
    """True si la ISA se reconoce pero no tiene perfil en la sandbox."""
    return arch in _KNOWN_UNSUPPORTED
