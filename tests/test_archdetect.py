"""Autodetección de ISA por cabecera ELF (ADR-021).

Los casos no son inventados: todas las arquitecturas que se comprueban aquí aparecieron en
el corpus real de CP-7, y la distinción entre "no es un ELF" y "ELF de ISA desconocida" está
porque confundirlas hacía que la API rechazase ejecutables SPARC o m68k perfectamente válidos
diciendo que no eran ELF.
"""
import struct

import pytest
from archdetect import detect_arch_from_bytes, is_elf, is_known_unsupported

ELFDATA2LSB, ELFDATA2MSB = 1, 2


def elf(e_machine: int, ei_data: int = ELFDATA2LSB) -> bytes:
    """Cabecera ELF32 mínima: solo importan el magic, EI_DATA y e_machine."""
    h = bytearray(64)
    h[0:4] = b"\x7fELF"
    h[4] = 1                                   # EI_CLASS = ELF32
    h[5] = ei_data
    endian = "<" if ei_data == ELFDATA2LSB else ">"
    struct.pack_into(endian + "H", h, 16, 2)   # e_type = ET_EXEC
    struct.pack_into(endian + "H", h, 18, e_machine)
    return bytes(h)


@pytest.mark.parametrize(
    "e_machine, ei_data, esperado",
    [
        (40, ELFDATA2LSB, "arm"),
        (62, ELFDATA2LSB, "x86_64"),
        (3, ELFDATA2LSB, "i386"),
        (183, ELFDATA2LSB, "aarch64"),
        (2, ELFDATA2MSB, "sparc"),
        (4, ELFDATA2MSB, "m68k"),
        (20, ELFDATA2MSB, "ppc"),
        (93, ELFDATA2LSB, "arc"),
        (243, ELFDATA2LSB, "riscv"),
    ],
)
def test_reconoce_las_isas_del_corpus(e_machine, ei_data, esperado):
    assert detect_arch_from_bytes(elf(e_machine, ei_data)) == esperado


def test_mips_se_discrimina_por_endianness():
    """EM_MIPS es el mismo valor para ambas variantes; las separa EI_DATA."""
    assert detect_arch_from_bytes(elf(8, ELFDATA2MSB)) == "mips"
    assert detect_arch_from_bytes(elf(8, ELFDATA2LSB)) == "mipsel"


def test_e_machine_se_lee_en_la_endianness_del_fichero():
    """Leer el campo con la endianness equivocada daría 0x2800 en vez de 0x28 para ARM."""
    assert detect_arch_from_bytes(elf(40, ELFDATA2MSB)) == "arm"


def test_lo_que_no_es_elf_no_lo_es():
    for datos in (b"MZ\x90\x00" + bytes(60), b"#!/bin/sh\n" + bytes(54), bytes(64)):
        assert not is_elf(datos)
        assert detect_arch_from_bytes(datos) is None


def test_cabecera_truncada_no_revienta():
    assert detect_arch_from_bytes(b"\x7fELF") is None
    assert detect_arch_from_bytes(b"") is None


def test_elf_de_isa_desconocida_sigue_siendo_elf():
    """La distinción que motivó el cambio: es ELF, pero no sabemos qué máquina es.

    Sin esto la API respondía «¿no es un ELF?» a binarios válidos, que era falso.
    """
    raro = elf(0x7777)
    assert is_elf(raro)
    assert detect_arch_from_bytes(raro) is None


@pytest.mark.parametrize("isa", ["i386", "aarch64", "sparc", "m68k", "ppc", "arc", "riscv"])
def test_isas_reconocidas_pero_sin_perfil(isa):
    assert is_known_unsupported(isa)


@pytest.mark.parametrize("isa", ["arm", "mips", "mipsel", "x86_64", None])
def test_las_emulables_no_se_marcan_como_no_soportadas(isa):
    assert not is_known_unsupported(isa)
