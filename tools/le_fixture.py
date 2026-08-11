#!/usr/bin/env python3
"""Build synthetic LE executables for testing.

The parser and disassembly tools must be testable in CI without the game's
executables, so the tests build their own LE images here. The fixture follows
Open Watcom's packed ``os2_flat_header`` layout for the fields the project
parses. It is test scaffolding, not a runnable DOS executable.
"""

from __future__ import annotations

import struct

MZ_STUB_SIZE = 0x80
# We populate fields through debug_len at +0x9c.
LE_HEADER_SIZE = 0xA0
OBJECT_ENTRY_SIZE = 24

CODE_FLAGS = 0x2045  # readable | executable | preload | big32
DATA_FLAGS = 0x2043  # readable | writable  | preload | big32


def call_rel32(from_address: int, to_address: int) -> bytes:
    """Encode ``call rel32`` from one virtual address to another."""
    displacement = to_address - (from_address + 5)
    return b"\xe8" + struct.pack("<i", displacement)


def sample_code(base_address: int, size: int = 0x200) -> bytes:
    """A small, genuinely decodable i386 body with two call targets."""
    code = bytearray(b"\x90" * size)

    def put(offset: int, payload: bytes) -> None:
        code[offset : offset + len(payload)] = payload

    entry = bytearray(b"\x55\x89\xe5")
    entry += call_rel32(base_address + len(entry), base_address + 0x80)
    entry += call_rel32(base_address + len(entry), base_address + 0xC0)
    entry += b"\xc9\xc3"
    put(0x00, bytes(entry))
    put(0x80, b"\x55\x89\xe5\x31\xc0\xc9\xc3")
    put(0xC0, b"\x55\x89\xe5\xb8\x01\x00\x00\x00\xc9\xc3")
    return bytes(code)


def build(
    *,
    objects: list[dict] | None = None,
    page_size: int = 0x1000,
    last_page_size: int | None = None,
    lfanew: int = MZ_STUB_SIZE,
    signature: bytes = b"LE",
    mz_magic: bytes = b"MZ",
    byte_order: int = 0,
    word_order: int = 0,
    format_level: int = 0,
    cpu: int = 0x02,
    os_type: int = 0x01,
    start_object: int = 1,
    eip: int = 0,
    stack_object: int = 2,
    esp: int | None = None,
    page_flags: list[int] | None = None,
    page_numbers: list[int] | None = None,
    declared_page_count: int | None = None,
    declared_object_count: int | None = None,
    data_page_offset: int | None = None,
    # Open Watcom os2_flat_header.page_off. Overridable only to build a
    # deliberately malformed legacy fixture for regression tests.
    page_off_field: int = 0x80,
    truncate_to: int | None = None,
) -> bytes:
    """Assemble a minimal LE image. Keyword overrides inject defects."""
    if objects is None:
        objects = [
            {"flags": CODE_FLAGS, "base": 0x10000, "pages": 1, "vsize": 0x200},
            {"flags": DATA_FLAGS, "base": 0x20000, "pages": 1, "vsize": 0x800},
        ]

    total_pages = sum(obj["pages"] for obj in objects)
    if last_page_size is None:
        last_page_size = page_size

    object_table_offset = LE_HEADER_SIZE
    page_map_offset = object_table_offset + len(objects) * OBJECT_ENTRY_SIZE
    page_map_end = lfanew + page_map_offset + total_pages * 4
    if data_page_offset is None:
        data_page_offset = (
            (page_map_end + page_size - 1) // page_size * page_size
        )

    header = bytearray(LE_HEADER_SIZE)
    header[0:2] = signature
    header[2] = byte_order
    header[3] = word_order
    struct.pack_into("<I", header, 0x04, format_level)
    struct.pack_into("<H", header, 0x08, cpu)
    struct.pack_into("<H", header, 0x0A, os_type)
    struct.pack_into("<I", header, 0x10, 0x200)  # module flags
    struct.pack_into(
        "<I",
        header,
        0x14,
        total_pages if declared_page_count is None else declared_page_count,
    )
    struct.pack_into("<I", header, 0x18, start_object)
    struct.pack_into("<I", header, 0x1C, eip)
    struct.pack_into("<I", header, 0x20, stack_object)
    struct.pack_into(
        "<I",
        header,
        0x24,
        objects[stack_object - 1]["vsize"] if esp is None else esp,
    )
    struct.pack_into("<I", header, 0x28, page_size)
    struct.pack_into("<I", header, 0x2C, last_page_size)
    struct.pack_into("<I", header, 0x40, object_table_offset)
    struct.pack_into(
        "<I",
        header,
        0x44,
        len(objects) if declared_object_count is None else declared_object_count,
    )
    struct.pack_into("<I", header, 0x48, page_map_offset)
    struct.pack_into("<I", header, page_off_field, data_page_offset)

    # Match the normal two-object fixture's data object in the authoritative
    # autodata field. Leave it zero for layouts without object 2.
    if len(objects) >= 2:
        struct.pack_into("<I", header, 0x94, 2)

    object_table = bytearray()
    next_page = 1
    for obj in objects:
        object_table += struct.pack(
            "<6I",
            obj["vsize"],
            obj["base"],
            obj["flags"],
            next_page,
            obj["pages"],
            0,
        )
        next_page += obj["pages"]

    numbers = page_numbers or list(range(1, total_pages + 1))
    flags = page_flags or [0] * total_pages
    page_map = bytearray()
    for number, flag in zip(numbers, flags):
        page_map += bytes(
            (
                (number >> 16) & 0xFF,
                (number >> 8) & 0xFF,
                number & 0xFF,
                flag,
            )
        )

    stub = bytearray(MZ_STUB_SIZE)
    stub[0:2] = mz_magic
    struct.pack_into("<I", stub, 0x3C, lfanew)

    image = bytearray(stub)
    image.extend(b"\x00" * max(0, lfanew - len(image)))
    image[lfanew : lfanew + LE_HEADER_SIZE] = header
    image.extend(b"\x00" * max(0, lfanew + LE_HEADER_SIZE - len(image)))

    offset = lfanew + object_table_offset
    image.extend(b"\x00" * max(0, offset + len(object_table) - len(image)))
    image[offset : offset + len(object_table)] = object_table

    offset = lfanew + page_map_offset
    image.extend(b"\x00" * max(0, offset + len(page_map) - len(image)))
    image[offset : offset + len(page_map)] = page_map

    image.extend(b"\x00" * max(0, data_page_offset - len(image)))
    page_index = 0
    for obj in objects:
        body = (
            sample_code(obj["base"], obj["pages"] * page_size)
            if obj["flags"] & 0x0004
            else bytes(
                ((page_index + i) % 251 for i in range(obj["pages"] * page_size))
            )
        )
        start = data_page_offset + page_index * page_size
        image.extend(b"\x00" * max(0, start + len(body) - len(image)))
        image[start : start + len(body)] = body
        page_index += obj["pages"]

    end = data_page_offset + (total_pages - 1) * page_size + last_page_size
    del image[end:]

    if truncate_to is not None:
        del image[truncate_to:]
    return bytes(image)
