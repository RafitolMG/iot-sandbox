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
_EM_MIPS = 8
_EM_ARM = 40

# Resto de e_machine que aparecen en el malware IoT real. No tienen perfil de emulación,
# pero conviene reconocerlas: si no, un ELF de SPARC o m68k se confunde con "esto no es un
# ELF" y el rechazo dice una cosa por otra. Vistas todas en muestras de MalwareBazaar.
_EM_NOMBRES = {
    2: "sparc",
    3: "i386",
    4: "m68k",
    20: "ppc",
    21: "ppc64",
    42: "sh",          # SuperH (SH4)
    43: "sparcv9",
    62: "x86_64",
    93: "arc",         # ARCompact / ARC700
    183: "aarch64",
    243: "riscv",
}

# Descripción legible de las ISAs que se reconocen pero no se pueden emular (mensaje 400).
_KNOWN_UNSUPPORTED = {
    "i386": "x86 de 32 bits",
    "aarch64": "ARM de 64 bits",
    "sparc": "SPARC de 32 bits",
    "sparcv9": "SPARC de 64 bits",
    "m68k": "Motorola 68000",
    "ppc": "PowerPC de 32 bits",
    "ppc64": "PowerPC de 64 bits",
    "sh": "SuperH",
    "arc": "Synopsys ARC",
    "riscv": "RISC-V",
}


def is_elf(head: bytes) -> bool:
    """True si `head` empieza por el magic de ELF."""
    return len(head) >= 20 and head[:4] == b"\x7fELF"


def detect_arch_from_bytes(head: bytes) -> str | None:
    """Nombre de la ISA del ELF, o None si no es un ELF o su e_machine es desconocido.

    Devuelve el nombre de perfil ('arm'|'mips'|'mipsel'|'x86_64') cuando la sandbox
    puede emularla, y el nombre de la ISA a secas ('sparc', 'm68k'…) cuando solo se
    reconoce. Para distinguir "no es un ELF" de "ELF que no sé emular", usa `is_elf`.
    """
    if not is_elf(head):
        return None
    ei_data = head[5]
    endian = "<" if ei_data == ELFDATA2LSB else ">"
    (e_machine,) = struct.unpack_from(endian + "H", head, 18)

    if e_machine == _EM_ARM:
        return "arm"
    if e_machine == _EM_MIPS:
        # EM_MIPS es el mismo para ambos endianness; los diferencia EI_DATA.
        return "mips" if ei_data == ELFDATA2MSB else "mipsel"
    return _EM_NOMBRES.get(e_machine)


def is_known_unsupported(arch: str | None) -> bool:
    """True si la ISA se reconoce pero no tiene perfil en la sandbox."""
    return arch in _KNOWN_UNSUPPORTED
