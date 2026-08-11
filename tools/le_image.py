#!/usr/bin/env python3
"""Parse DOS Linear Executable (LE) images and rebuild their linear objects.

The project's targets are `MZ` stubs wrapping an `LE` image with a bound DOS
extender. Nothing in the standard cloud toolchain reads that container:
`objdump` reports "file format not recognized" and `file` identifies it but
cannot lay it out. This module supplies the missing piece, so the rest of the
static pipeline can work in virtual addresses instead of raw file offsets.

It fails closed. Every structural assumption is checked, and anything this
parser has not been validated against — a different byte order, iterated or
zero-filled pages, an `LX` image — is refused with a message naming the exact
feature rather than guessed at.

Field offsets are relative to the start of the LE header and follow the
published LE layout; they were cross-checked against the project's targets by
verifying that object page counts sum to the header page count, that page
numbers form a complete sequence, and that the entry point lands inside an
executable object (see docs/experiments/CF2-cloud-static-re.md).
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import pathlib
import struct
import sys

MZ_MAGIC = b"MZ"
LE_MAGIC = b"LE"
LX_MAGIC = b"LX"
E_LFANEW = 0x3C

# Offsets within the LE header.
H_LEVEL = 0x04
H_CPU = 0x08
H_OS = 0x0A
H_VER = 0x0C
H_MFLAGS = 0x10
H_MPAGES = 0x14
H_STARTOBJ = 0x18
H_EIP = 0x1C
H_STACKOBJ = 0x20
H_ESP = 0x24
H_PAGESIZE = 0x28
H_LASTPAGESIZE = 0x2C
H_FIXUPSIZE = 0x30
H_LDRSIZE = 0x38
H_OBJTAB = 0x40
H_OBJCNT = 0x44
H_OBJMAP = 0x48
H_ITERMAP = 0x4C
H_DATAPAGE = 0x70
H_DEBUGINFO = 0x88
H_DEBUGLEN = 0x8C
H_MIN_SIZE = 0x90

OBJECT_ENTRY_SIZE = 24
PAGE_MAP_ENTRY_SIZE = 4

OBJECT_FLAGS = (
    (0x0001, "readable"),
    (0x0002, "writable"),
    (0x0004, "executable"),
    (0x0008, "resource"),
    (0x0010, "discardable"),
    (0x0020, "shared"),
    (0x0040, "preload"),
    (0x0080, "invalid"),
    (0x1000, "alias16"),
    (0x2000, "big32"),
    (0x4000, "conforming"),
    (0x8000, "iopl"),
)

# Page-map entry flags. Only 0 has been observed and validated on the project's
# targets, so the others are refused rather than handled speculatively.
PAGE_FLAG_NAMES = {
    0x00: "legal",
    0x01: "iterated",
    0x02: "invalid",
    0x03: "zero-filled",
    0x04: "range",
}

KNOWN_CPU = {0x01: "80286", 0x02: "80386", 0x03: "80486", 0x04: "80586"}

PRINTABLE = bytes(range(0x20, 0x7F)) + b"\t"


class LEError(Exception):
    """The image is not an LE this parser has been validated against."""


def flag_names(flags: int) -> list[str]:
    return [name for bit, name in OBJECT_FLAGS if flags & bit]


@dataclasses.dataclass(frozen=True)
class LEObject:
    index: int
    virtual_size: int
    base_address: int
    flags: int
    first_page: int
    page_count: int

    @property
    def names(self) -> list[str]:
        return flag_names(self.flags)

    @property
    def kind(self) -> str:
        if self.flags & 0x0004:
            return "code"
        if self.flags & 0x0002:
            return "data"
        return "other"

    @property
    def end_address(self) -> int:
        return self.base_address + self.virtual_size

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "kind": self.kind,
            "virtual_size": self.virtual_size,
            "base_address": self.base_address,
            "end_address": self.end_address,
            "flags": self.flags,
            "flag_names": self.names,
            "first_page": self.first_page,
            "page_count": self.page_count,
        }


class LEImage:
    """A parsed LE image with its objects rebuilt as linear byte ranges."""

    def __init__(self, data: bytes, name: str = "<bytes>") -> None:
        self.name = name
        self._data = data
        self.size = len(data)
        self.sha256 = hashlib.sha256(data).hexdigest()

        self._parse_header()
        self._parse_objects()
        self._parse_page_map()
        self._check_invariants()

    # -- parsing -----------------------------------------------------------

    def _u16(self, offset: int) -> int:
        return struct.unpack_from("<H", self._data, offset)[0]

    def _u32(self, offset: int) -> int:
        return struct.unpack_from("<I", self._data, offset)[0]

    def _parse_header(self) -> None:
        if self.size < E_LFANEW + 4:
            raise LEError(f"file is too small to hold an MZ header: {self.size} bytes")
        if self._data[:2] != MZ_MAGIC:
            raise LEError(f"not an MZ executable: magic {self._data[:2]!r}")

        self.lfanew = self._u32(E_LFANEW)
        if not 0 < self.lfanew or self.lfanew + H_MIN_SIZE > self.size:
            raise LEError(
                f"e_lfanew 0x{self.lfanew:x} does not leave room for an LE header "
                f"in {self.size} bytes"
            )

        magic = self._data[self.lfanew : self.lfanew + 2]
        if magic == LX_MAGIC:
            raise LEError(
                "image is LX, not LE. LX uses a different page-table layout and "
                "this parser has not been validated against it"
            )
        if magic != LE_MAGIC:
            raise LEError(f"no LE signature at 0x{self.lfanew:x}: found {magic!r}")

        h = self.lfanew
        self.byte_order = self._data[h + 2]
        self.word_order = self._data[h + 3]
        if self.byte_order != 0 or self.word_order != 0:
            raise LEError(
                f"big-endian LE image (border={self.byte_order}, "
                f"worder={self.word_order}); only little-endian is supported"
            )

        self.format_level = self._u32(h + H_LEVEL)
        if self.format_level != 0:
            raise LEError(f"unsupported LE format level {self.format_level}")

        self.cpu = self._u16(h + H_CPU)
        if self.cpu not in KNOWN_CPU:
            raise LEError(f"unknown CPU type 0x{self.cpu:x} in LE header")
        self.cpu_name = KNOWN_CPU[self.cpu]

        self.os_type = self._u16(h + H_OS)
        self.module_version = self._u32(h + H_VER)
        self.module_flags = self._u32(h + H_MFLAGS)
        self.page_count = self._u32(h + H_MPAGES)
        self.start_object = self._u32(h + H_STARTOBJ)
        self.eip = self._u32(h + H_EIP)
        self.stack_object = self._u32(h + H_STACKOBJ)
        self.esp = self._u32(h + H_ESP)
        self.page_size = self._u32(h + H_PAGESIZE)
        self.last_page_size = self._u32(h + H_LASTPAGESIZE)
        self.fixup_size = self._u32(h + H_FIXUPSIZE)
        self.loader_size = self._u32(h + H_LDRSIZE)
        self.object_table_offset = self._u32(h + H_OBJTAB)
        self.object_count = self._u32(h + H_OBJCNT)
        self.page_map_offset = self._u32(h + H_OBJMAP)
        self.iterated_map_offset = self._u32(h + H_ITERMAP)
        self.data_page_offset = self._u32(h + H_DATAPAGE)
        self.debug_offset = self._u32(h + H_DEBUGINFO)
        self.debug_size = self._u32(h + H_DEBUGLEN)

        if self.page_size == 0 or self.page_size & (self.page_size - 1):
            raise LEError(f"page size {self.page_size} is not a power of two")
        if self.page_count == 0:
            raise LEError("LE header declares zero pages")
        if not 0 < self.last_page_size <= self.page_size:
            raise LEError(
                f"last page size {self.last_page_size} is outside "
                f"1..{self.page_size}"
            )
        if self.object_count == 0:
            raise LEError("LE header declares zero objects")

    def _parse_objects(self) -> None:
        start = self.lfanew + self.object_table_offset
        end = start + self.object_count * OBJECT_ENTRY_SIZE
        if end > self.size:
            raise LEError(
                f"object table (0x{start:x}..0x{end:x}) runs past end of file "
                f"(0x{self.size:x})"
            )

        self.objects: list[LEObject] = []
        for i in range(self.object_count):
            vsize, base, flags, first_page, pages, _reserved = struct.unpack_from(
                "<6I", self._data, start + i * OBJECT_ENTRY_SIZE
            )
            if flags & 0x0080:
                raise LEError(f"object {i + 1} is marked invalid (flags 0x{flags:04x})")
            if pages and not 1 <= first_page <= self.page_count:
                raise LEError(
                    f"object {i + 1} first page {first_page} is outside "
                    f"1..{self.page_count}"
                )
            if pages and first_page + pages - 1 > self.page_count:
                raise LEError(
                    f"object {i + 1} maps pages {first_page}..{first_page + pages - 1}, "
                    f"beyond the {self.page_count} pages declared in the header"
                )
            self.objects.append(
                LEObject(i + 1, vsize, base, flags, first_page, pages)
            )

    def _parse_page_map(self) -> None:
        start = self.lfanew + self.page_map_offset
        end = start + self.page_count * PAGE_MAP_ENTRY_SIZE
        if end > self.size:
            raise LEError(
                f"page map (0x{start:x}..0x{end:x}) runs past end of file "
                f"(0x{self.size:x})"
            )

        self.page_numbers: list[int] = []
        for i in range(self.page_count):
            entry = self._data[start + i * 4 : start + i * 4 + 4]
            # LE stores the page number as 24-bit big-endian, then a flag byte.
            number = (entry[0] << 16) | (entry[1] << 8) | entry[2]
            flags = entry[3]
            if flags != 0x00:
                raise LEError(
                    f"page map entry {i} has flags 0x{flags:02x} "
                    f"({PAGE_FLAG_NAMES.get(flags, 'unknown')}); this parser has only "
                    f"been validated against 'legal' pages. Implement and test the "
                    f"handling before relying on such an image"
                )
            if not 1 <= number <= self.page_count:
                raise LEError(
                    f"page map entry {i} refers to page {number}, outside "
                    f"1..{self.page_count}"
                )
            self.page_numbers.append(number)

    def _check_invariants(self) -> None:
        mapped = sum(obj.page_count for obj in self.objects)
        if mapped != self.page_count:
            raise LEError(
                f"objects map {mapped} pages but the header declares "
                f"{self.page_count}"
            )

        last = self.data_page_offset + (self.page_count - 1) * self.page_size
        self.page_data_end = last + self.last_page_size
        if self.page_data_end > self.size:
            raise LEError(
                f"page data ends at 0x{self.page_data_end:x}, past end of file "
                f"(0x{self.size:x})"
            )

        if not 1 <= self.start_object <= self.object_count:
            raise LEError(
                f"entry object {self.start_object} is outside 1..{self.object_count}"
            )
        entry_object = self.objects[self.start_object - 1]
        if self.eip >= entry_object.virtual_size:
            raise LEError(
                f"entry eip 0x{self.eip:x} is outside object "
                f"{self.start_object} (virtual size 0x{entry_object.virtual_size:x})"
            )
        if not entry_object.flags & 0x0004:
            raise LEError(
                f"entry object {self.start_object} is not executable "
                f"(flags 0x{entry_object.flags:04x})"
            )

        # Anything after the page data is not described by the LE structures.
        self.trailing_offset = self.page_data_end
        self.trailing_size = self.size - self.page_data_end

    # -- access ------------------------------------------------------------

    @property
    def entry_address(self) -> int:
        return self.objects[self.start_object - 1].base_address + self.eip

    def page_file_offset(self, number: int) -> int:
        return self.data_page_offset + (number - 1) * self.page_size

    def page_length(self, number: int) -> int:
        return self.last_page_size if number == self.page_count else self.page_size

    def object_bytes(self, index: int) -> bytes:
        """Rebuild one object as a linear byte range of exactly virtual_size."""
        if not 1 <= index <= self.object_count:
            raise LEError(f"no object {index}; image has {self.object_count}")
        obj = self.objects[index - 1]

        chunks = []
        for i in range(obj.page_count):
            number = self.page_numbers[obj.first_page - 1 + i]
            offset = self.page_file_offset(number)
            chunks.append(self._data[offset : offset + self.page_length(number)])
        image = b"".join(chunks)

        if len(image) > obj.virtual_size:
            # Page granularity overshoots the declared size; the tail is padding.
            return image[: obj.virtual_size]
        # Short of virtual_size means uninitialised space (bss/stack/heap).
        return image + b"\x00" * (obj.virtual_size - len(image))

    def object_containing(self, address: int) -> LEObject | None:
        for obj in self.objects:
            if obj.base_address <= address < obj.end_address:
                return obj
        return None

    def strings(self, min_length: int = 4) -> list[dict]:
        """Printable ASCII runs, reported with the virtual address they load at."""
        found = []
        table = PRINTABLE
        for obj in self.objects:
            data = self.object_bytes(obj.index)
            run_start = None
            for i, byte in enumerate(data):
                if byte in table:
                    if run_start is None:
                        run_start = i
                    continue
                if run_start is not None and i - run_start >= min_length:
                    found.append(
                        {
                            "object": obj.index,
                            "address": obj.base_address + run_start,
                            "length": i - run_start,
                            "text": data[run_start:i].decode("ascii"),
                        }
                    )
                run_start = None
            if run_start is not None and len(data) - run_start >= min_length:
                found.append(
                    {
                        "object": obj.index,
                        "address": obj.base_address + run_start,
                        "length": len(data) - run_start,
                        "text": data[run_start:].decode("ascii"),
                    }
                )
        return found

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "sha256": self.sha256,
            "file_size": self.size,
            "container": {
                "mz_lfanew": self.lfanew,
                "signature": "LE",
                "format_level": self.format_level,
                "cpu": self.cpu,
                "cpu_name": self.cpu_name,
                "os_type": self.os_type,
                "module_version": self.module_version,
                "module_flags": self.module_flags,
            },
            "pages": {
                "count": self.page_count,
                "size": self.page_size,
                "last_page_size": self.last_page_size,
                "data_offset": self.data_page_offset,
                "data_end": self.page_data_end,
                "numbers_are_sequential": self.page_numbers
                == list(range(1, self.page_count + 1)),
            },
            "loader": {
                "fixup_size": self.fixup_size,
                "loader_size": self.loader_size,
                "iterated_map_offset": self.iterated_map_offset,
                "debug_offset": self.debug_offset,
                "debug_size": self.debug_size,
            },
            "entry": {
                "object": self.start_object,
                "eip": self.eip,
                "address": self.entry_address,
                "stack_object": self.stack_object,
                "esp": self.esp,
            },
            "objects": [obj.to_dict() for obj in self.objects],
            "trailing": {
                "offset": self.trailing_offset,
                "size": self.trailing_size,
                "note": "not described by the LE structures; not parsed",
            },
        }


def load(path: pathlib.Path) -> LEImage:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise LEError(f"cannot read {path}: {exc}") from exc
    return LEImage(data, name=path.name)


# -- CLI -------------------------------------------------------------------


def _cmd_info(args: argparse.Namespace) -> int:
    image = load(args.file)
    if args.json:
        print(json.dumps(image.to_dict(), indent=2))
        return 0

    print(f"{image.name}  sha256={image.sha256}")
    print(f"  file size      : {image.size}")
    print(f"  LE header at   : 0x{image.lfanew:x}")
    print(f"  cpu            : {image.cpu_name} (0x{image.cpu:x}), os type {image.os_type}")
    print(f"  module flags   : 0x{image.module_flags:x}")
    print(
        f"  pages          : {image.page_count} x {image.page_size}"
        f" (last {image.last_page_size}), data at 0x{image.data_page_offset:x}"
    )
    print(f"  entry point    : object {image.start_object} +0x{image.eip:x}"
          f" -> 0x{image.entry_address:x}")
    print(f"  stack          : object {image.stack_object}, esp 0x{image.esp:x}")
    print(f"  trailing bytes : {image.trailing_size} at 0x{image.trailing_offset:x}"
          f" (unparsed)")
    print("  objects:")
    for obj in image.objects:
        print(
            f"    {obj.index}: {obj.kind:5s} 0x{obj.base_address:08x}"
            f"-0x{obj.end_address:08x} size 0x{obj.virtual_size:x}"
            f" pages {obj.first_page}..{obj.first_page + obj.page_count - 1}"
            f" [{','.join(obj.names)}]"
        )
    return 0


def _cmd_extract(args: argparse.Namespace) -> int:
    image = load(args.file)
    data = image.object_bytes(args.object)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    obj = image.objects[args.object - 1]
    print(
        f"wrote {len(data)} bytes to {args.output} "
        f"(object {obj.index} {obj.kind}, base 0x{obj.base_address:x})"
    )
    return 0


def _cmd_strings(args: argparse.Namespace) -> int:
    image = load(args.file)
    found = image.strings(args.min_length)
    if args.json:
        print(json.dumps({"sha256": image.sha256, "strings": found}, indent=2))
        return 0
    for item in found:
        print(f"0x{item['address']:08x}  obj{item['object']}  {item['text']}")
    print(f"# {len(found)} strings of at least {args.min_length} characters",
          file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    info = sub.add_parser("info", help="print the container layout")
    info.add_argument("file", type=pathlib.Path)
    info.add_argument("--json", action="store_true")
    info.set_defaults(func=_cmd_info)

    extract = sub.add_parser("extract", help="write one object as a flat image")
    extract.add_argument("file", type=pathlib.Path)
    extract.add_argument("--object", type=int, required=True)
    extract.add_argument("-o", "--output", type=pathlib.Path, required=True)
    extract.set_defaults(func=_cmd_extract)

    strings = sub.add_parser("strings", help="printable runs with virtual addresses")
    strings.add_argument("file", type=pathlib.Path)
    strings.add_argument("--min-length", type=int, default=4)
    strings.add_argument("--json", action="store_true")
    strings.set_defaults(func=_cmd_strings)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except LEError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
