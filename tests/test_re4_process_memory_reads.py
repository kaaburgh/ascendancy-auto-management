from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_re4_runtime_state as re4


class ProcessMemoryReadTests(unittest.TestCase):
    def test_exact_read_returns_bytes_unchanged(self) -> None:
        payload = b"\x01\x02\x03\x04"
        with (
            mock.patch.object(os, "open", return_value=17),
            mock.patch.object(os, "pread", return_value=payload) as pread,
            mock.patch.object(os, "close") as close,
        ):
            self.assertEqual(re4.read_process(7, 0x1234, len(payload)), payload)

        pread.assert_called_once_with(17, len(payload), 0x1234)
        close.assert_called_once_with(17)

    def test_short_read_fails_closed(self) -> None:
        with (
            mock.patch.object(os, "open", return_value=17),
            mock.patch.object(os, "pread", return_value=b"\x00\x00"),
            mock.patch.object(os, "close") as close,
        ):
            with self.assertRaisesRegex(
                re4.RE4Error,
                r"short process-memory read at 0x1234: expected 4 bytes, got 2",
            ):
                re4.read_process(7, 0x1234, 4)

        close.assert_called_once_with(17)

    def test_oserror_is_preserved_and_fd_is_closed(self) -> None:
        failure = OSError("pread failed")
        with (
            mock.patch.object(os, "open", return_value=17),
            mock.patch.object(os, "pread", side_effect=failure),
            mock.patch.object(os, "close") as close,
        ):
            with self.assertRaises(OSError) as caught:
                re4.read_process(7, 0x1234, 4)

        self.assertIs(caught.exception, failure)
        close.assert_called_once_with(17)


if __name__ == "__main__":
    unittest.main()
