#!/usr/bin/env python3
"""Tests for tools/fetch_free_targets.py.

Every test builds its own synthetic zip fixture and serves it over a ``file://``
URL, so the real download/verify/extract code path runs with no network access
and no proprietary bytes.
"""

from __future__ import annotations

import hashlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import fetch_free_targets as fft  # noqa: E402

MEMBER_NAME = "PAYLOAD.EXE"
MEMBER_BYTES = b"MZ synthetic payload; not a real game executable.\n" * 4


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_zip(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buffer.getvalue()


class FixtureCase(unittest.TestCase):
    """Base class providing a temp workspace, a zip fixture, and a manifest."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name)
        self.dest = self.tmp / "out"
        self.archive_bytes = make_zip({MEMBER_NAME: MEMBER_BYTES})
        self.archive_path = self.write_archive("good.zip", self.archive_bytes)

    def write_archive(self, name: str, data: bytes) -> pathlib.Path:
        path = self.tmp / name
        path.write_bytes(data)
        return path

    def source(self, path: pathlib.Path, **overrides) -> dict:
        data = path.read_bytes()
        source = {
            "url": path.as_uri(),
            "archive_size": len(data),
            "archive_sha256": sha256(data),
            "member": MEMBER_NAME,
        }
        source.update(overrides)
        return source

    def manifest(self, sources: list[dict] | None = None, **overrides) -> pathlib.Path:
        entry = {
            "id": "synthetic",
            "role": "test-fixture",
            "locale": "none",
            "output": "PAYLOAD.EXE",
            "member_size": len(MEMBER_BYTES),
            "member_sha256": sha256(MEMBER_BYTES),
            "sources": sources if sources is not None else [self.source(self.archive_path)],
        }
        entry.update(overrides)
        path = self.tmp / "manifest.json"
        path.write_text(json.dumps({"schema": 1, "entries": [entry]}), encoding="utf-8")
        return path

    def run_tool(self, manifest: pathlib.Path, *args: str) -> int:
        # manifest_path is a function parameter, not a CLI option: the shipped
        # command line must not be able to name an unreviewed source.
        return fft.main([*args], manifest_path=manifest)

    def assertFails(self, manifest: pathlib.Path, *args: str) -> None:
        self.assertNotEqual(0, self.run_tool(manifest, *args))

    @property
    def output(self) -> pathlib.Path:
        return self.dest / "PAYLOAD.EXE"

    def base_args(self) -> list[str]:
        return ["--dest", str(self.dest), "--allow-unignored-dest"]


class TestHappyPath(FixtureCase):
    def test_fetch_writes_verified_member(self) -> None:
        manifest = self.manifest()
        self.assertEqual(0, self.run_tool(manifest, *self.base_args()))
        self.assertEqual(MEMBER_BYTES, self.output.read_bytes())

    def test_second_run_is_idempotent(self) -> None:
        manifest = self.manifest()
        args = [manifest, *self.base_args()]
        self.assertEqual(0, self.run_tool(*args))
        mtime = self.output.stat().st_mtime_ns
        self.assertEqual(0, self.run_tool(*args))
        self.assertEqual(mtime, self.output.stat().st_mtime_ns)

    def test_verify_mode_accepts_good_output(self) -> None:
        manifest = self.manifest()
        args = [manifest, *self.base_args()]
        self.assertEqual(0, self.run_tool(*args))
        self.assertEqual(0, self.run_tool(*args, "--verify"))

    def test_list_mode_needs_no_destination(self) -> None:
        manifest = self.manifest()
        self.assertEqual(0, self.run_tool(manifest, "--list"))

    def test_no_partial_file_is_left_behind(self) -> None:
        manifest = self.manifest()
        self.assertEqual(0, self.run_tool(manifest, *self.base_args()))
        self.assertEqual([], list(self.dest.glob("*.part")))


class TestFailsClosed(FixtureCase):
    def test_unknown_id_is_rejected(self) -> None:
        manifest = self.manifest()
        self.assertFails(manifest, *self.base_args(), "does-not-exist")
        self.assertFalse(self.dest.exists())

    def test_archive_hash_mismatch_writes_nothing(self) -> None:
        manifest = self.manifest(
            sources=[self.source(self.archive_path, archive_sha256="00" * 32)]
        )
        self.assertFails(manifest, *self.base_args())
        self.assertFalse(self.output.exists())

    def test_archive_size_mismatch_writes_nothing(self) -> None:
        manifest = self.manifest(
            sources=[self.source(self.archive_path, archive_size=len(self.archive_bytes) + 1)]
        )
        self.assertFails(manifest, *self.base_args())
        self.assertFalse(self.output.exists())

    def test_oversized_response_is_refused(self) -> None:
        # A source that pins a smaller size than the served body must not be
        # downloaded past the pinned length.
        manifest = self.manifest(
            sources=[self.source(self.archive_path, archive_size=8)]
        )
        self.assertFails(manifest, *self.base_args())
        self.assertFalse(self.output.exists())

    def test_member_hash_mismatch_writes_nothing(self) -> None:
        manifest = self.manifest(member_sha256="11" * 32)
        self.assertFails(manifest, *self.base_args())
        self.assertFalse(self.output.exists())

    def test_member_size_mismatch_writes_nothing(self) -> None:
        manifest = self.manifest(member_size=len(MEMBER_BYTES) + 1)
        self.assertFails(manifest, *self.base_args())
        self.assertFalse(self.output.exists())

    def test_missing_member_writes_nothing(self) -> None:
        manifest = self.manifest(
            sources=[self.source(self.archive_path, member="ABSENT.EXE")]
        )
        self.assertFails(manifest, *self.base_args())
        self.assertFalse(self.output.exists())

    def test_ambiguous_member_is_rejected(self) -> None:
        # Two members differing only by case must not be silently disambiguated.
        ambiguous = self.write_archive(
            "ambiguous.zip",
            make_zip({MEMBER_NAME: MEMBER_BYTES, MEMBER_NAME.lower(): b"other"}),
        )
        manifest = self.manifest(sources=[self.source(ambiguous)])
        self.assertFails(manifest, *self.base_args())
        self.assertFalse(self.output.exists())

    def test_corrupt_archive_is_rejected(self) -> None:
        corrupt = self.write_archive("corrupt.zip", b"this is not a zip file")
        manifest = self.manifest(sources=[self.source(corrupt)])
        self.assertFails(manifest, *self.base_args())
        self.assertFalse(self.output.exists())

    def test_unreachable_source_is_rejected(self) -> None:
        missing = self.tmp / "gone.zip"
        manifest = self.manifest(
            sources=[
                {
                    "url": missing.as_uri(),
                    "archive_size": len(self.archive_bytes),
                    "archive_sha256": sha256(self.archive_bytes),
                    "member": MEMBER_NAME,
                }
            ]
        )
        self.assertFails(manifest, *self.base_args())
        self.assertFalse(self.output.exists())

    def test_verify_mode_rejects_tampered_output(self) -> None:
        manifest = self.manifest()
        args = [manifest, *self.base_args()]
        self.assertEqual(0, self.run_tool(*args))
        self.output.write_bytes(MEMBER_BYTES + b"tampered")
        self.assertFails(*args, "--verify")

    def test_verify_mode_rejects_missing_output(self) -> None:
        manifest = self.manifest()
        self.assertFails(manifest, *self.base_args(), "--verify")

    def test_existing_mismatched_output_is_not_overwritten(self) -> None:
        manifest = self.manifest()
        self.dest.mkdir(parents=True)
        self.output.write_bytes(b"local edit")
        self.assertFails(manifest, *self.base_args())
        self.assertEqual(b"local edit", self.output.read_bytes())

    def test_force_replaces_mismatched_output(self) -> None:
        manifest = self.manifest()
        self.dest.mkdir(parents=True)
        self.output.write_bytes(b"local edit")
        self.assertEqual(0, self.run_tool(manifest, *self.base_args(), "--force"))
        self.assertEqual(MEMBER_BYTES, self.output.read_bytes())


class TestManifestOverrideIsNotExposed(FixtureCase):
    """The CLI must not offer a way to name an unreviewed source.

    Hash pinning proves the bytes are intact, not that anyone approved the
    source, so a manifest option on the command line would let the normal
    fetcher pull an artifact that never passed repository review.
    """

    def test_cli_rejects_a_manifest_option(self) -> None:
        manifest = self.manifest()
        with self.assertRaises(SystemExit):
            fft.main(["--manifest", str(manifest)])

    def test_cli_rejects_a_url_option(self) -> None:
        with self.assertRaises(SystemExit):
            fft.main(["--url", "https://example.invalid/evil.zip"])

    def test_parser_exposes_no_source_naming_flags(self) -> None:
        flags = {
            option
            for action in fft.build_parser()._actions
            for option in action.option_strings
        }
        for forbidden in ("--manifest", "--url", "--source", "--sha256"):
            self.assertNotIn(forbidden, flags)

    def test_cli_default_is_the_committed_manifest(self) -> None:
        # With no manifest parameter, main() must read the reviewed manifest.
        self.assertEqual(0, fft.main(["--list"]))


class TestSourceIndex(FixtureCase):
    def test_selects_the_requested_source(self) -> None:
        broken = self.write_archive("broken.zip", b"not a zip")
        manifest = self.manifest(
            sources=[self.source(broken), self.source(self.archive_path)]
        )
        # Index 1 is the good mirror; index 0 would fail on its own.
        self.assertEqual(
            0, self.run_tool(manifest, *self.base_args(), "--source-index", "1")
        )
        self.assertEqual(MEMBER_BYTES, self.output.read_bytes())

    def test_does_not_fall_back_to_other_sources(self) -> None:
        broken = self.write_archive("broken.zip", b"not a zip")
        manifest = self.manifest(
            sources=[self.source(broken), self.source(self.archive_path)]
        )
        self.assertFails(manifest, *self.base_args(), "--source-index", "0")
        self.assertFalse(self.output.exists())

    def test_out_of_range_index_is_rejected(self) -> None:
        manifest = self.manifest()
        for index in ("1", "-1", "99"):
            with self.subTest(index=index):
                self.assertFails(
                    manifest, *self.base_args(), "--source-index", index
                )
                self.assertFalse(self.output.exists())


class TestMirrorFallback(FixtureCase):
    def test_later_source_is_used_when_an_earlier_one_fails(self) -> None:
        broken = self.write_archive("broken.zip", b"not a zip")
        manifest = self.manifest(
            sources=[self.source(broken), self.source(self.archive_path)]
        )
        self.assertEqual(0, self.run_tool(manifest, *self.base_args()))
        self.assertEqual(MEMBER_BYTES, self.output.read_bytes())

    def test_mirrors_may_repackage_the_same_member_differently(self) -> None:
        # The two real Antagonizer repacks have different outer zip hashes and
        # different member names but byte-identical payloads.
        renamed = self.write_archive(
            "renamed.zip", make_zip({"F_PAYLOAD.EXE": MEMBER_BYTES})
        )
        manifest = self.manifest(
            sources=[self.source(renamed, member="F_PAYLOAD.EXE")]
        )
        self.assertEqual(0, self.run_tool(manifest, *self.base_args()))
        self.assertEqual(MEMBER_BYTES, self.output.read_bytes())

    def test_all_sources_failing_is_a_failure(self) -> None:
        broken = self.write_archive("broken.zip", b"not a zip")
        manifest = self.manifest(sources=[self.source(broken), self.source(broken)])
        self.assertFails(manifest, *self.base_args())
        self.assertFalse(self.output.exists())


class TestManifestValidation(FixtureCase):
    def write_manifest(self, payload: object) -> pathlib.Path:
        path = self.tmp / "bad.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_missing_manifest_is_rejected(self) -> None:
        self.assertFails(self.tmp / "nope.json", "--list")

    def test_invalid_json_is_rejected(self) -> None:
        path = self.tmp / "bad.json"
        path.write_text("{not json", encoding="utf-8")
        self.assertFails(path, "--list")

    def test_unsupported_schema_is_rejected(self) -> None:
        path = self.write_manifest({"schema": 99, "entries": []})
        self.assertFails(path, "--list")

    def test_empty_entries_is_rejected(self) -> None:
        path = self.write_manifest({"schema": 1, "entries": []})
        self.assertFails(path, "--list")

    def test_entry_missing_required_key_is_rejected(self) -> None:
        path = self.write_manifest({"schema": 1, "entries": [{"id": "x"}]})
        self.assertFails(path, "--list")

    def test_entry_without_sources_is_rejected(self) -> None:
        manifest = self.manifest(sources=[])
        self.assertFails(manifest, "--list")

    def test_duplicate_ids_are_rejected(self) -> None:
        entry = {
            "id": "dup",
            "output": "A.EXE",
            "member_size": 1,
            "member_sha256": "00" * 32,
            "sources": [self.source(self.archive_path)],
        }
        other = dict(entry, output="B.EXE")
        path = self.write_manifest({"schema": 1, "entries": [entry, other]})
        self.assertFails(path, "--list")

    def test_duplicate_outputs_are_rejected(self) -> None:
        entry = {
            "id": "one",
            "output": "A.EXE",
            "member_size": 1,
            "member_sha256": "00" * 32,
            "sources": [self.source(self.archive_path)],
        }
        other = dict(entry, id="two")
        path = self.write_manifest({"schema": 1, "entries": [entry, other]})
        self.assertFails(path, "--list")

    def test_output_path_traversal_is_rejected(self) -> None:
        # Windows separators and drive prefixes must be rejected too: they look
        # like bare filenames to PurePosixPath but escape the destination once
        # joined with a native Path on Windows.
        for output in (
            "../escaped.exe",
            "nested/dir.exe",
            "/absolute.exe",
            "..\\escaped.exe",
            "C:\\escaped.exe",
            "C:escaped.exe",
            "nested\\dir.exe",
            "",
        ):
            with self.subTest(output=output):
                manifest = self.manifest(output=output)
                self.assertFails(manifest, "--list")

    def test_bare_filename_accepts_plain_names(self) -> None:
        for output in ("ANTAG_EN.EXE", "patch.exe", "a.b.c"):
            with self.subTest(output=output):
                self.assertTrue(fft.is_bare_filename(output))

    def test_source_missing_required_key_is_rejected(self) -> None:
        source = self.source(self.archive_path)
        del source["archive_sha256"]
        manifest = self.manifest(sources=[source])
        self.assertFails(manifest, *self.base_args())
        self.assertFalse(self.output.exists())


class TestDestinationSafety(FixtureCase):
    def test_tracked_repository_path_is_refused(self) -> None:
        manifest = self.manifest()
        self.assertFails(
            manifest, "--dest", str(ROOT / "docs" / "re"),
        )
        self.assertFalse((ROOT / "docs" / "re" / "PAYLOAD.EXE").exists())

    def test_ignored_repository_root_is_allowed(self) -> None:
        for root in fft.IGNORED_ROOTS:
            with self.subTest(root=root):
                fft.resolve_dest(ROOT / root, allow_unignored=False)

    def test_path_outside_repository_is_allowed(self) -> None:
        fft.resolve_dest(self.dest, allow_unignored=False)

    def test_override_permits_a_tracked_path(self) -> None:
        resolved = fft.resolve_dest(ROOT / "docs", allow_unignored=True)
        self.assertEqual((ROOT / "docs").resolve(), resolved)


class TestRealManifest(unittest.TestCase):
    """The committed manifest must stay loadable and policy-compliant."""

    def setUp(self) -> None:
        self.entries = fft.load_manifest(fft.DEFAULT_MANIFEST)

    def test_manifest_loads(self) -> None:
        self.assertTrue(self.entries)

    def test_every_pinned_hash_is_a_sha256(self) -> None:
        for entry in self.entries:
            with self.subTest(entry=entry["id"]):
                self.assertRegex(entry["member_sha256"], r"^[0-9a-f]{64}$")
                self.assertGreater(entry["member_size"], 0)
                for source in entry["sources"]:
                    self.assertRegex(source["archive_sha256"], r"^[0-9a-f]{64}$")
                    self.assertGreater(source["archive_size"], 0)

    def test_every_source_is_https(self) -> None:
        for entry in self.entries:
            for source in entry["sources"]:
                with self.subTest(url=source["url"]):
                    self.assertTrue(source["url"].startswith("https://"))

    def test_default_destination_is_git_ignored(self) -> None:
        relative = fft.DEFAULT_DEST.resolve().relative_to(ROOT.resolve())
        self.assertIn(relative.parts[0], fft.IGNORED_ROOTS)


if __name__ == "__main__":
    unittest.main()
