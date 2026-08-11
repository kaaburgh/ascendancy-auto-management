"""Capture tool output so CLI tests do not flood the CI log.

The tools print by design; tests that exercise their entry points should assert
on exit codes and side effects, not reproduce their chatter. Captured text is
returned so a test can still assert on it when that is the point.
"""

from __future__ import annotations

import contextlib
import io


@contextlib.contextmanager
def quiet():
    """Redirect stdout and stderr into one buffer for the duration of the block."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        yield buffer
