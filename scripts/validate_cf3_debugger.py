#!/usr/bin/env python3
"""Prove a cloud DOSBox debugger can break and observe guest memory.

The fixture is a six-byte synthetic COM program. The smoke enters the distro
DOSBox debugger through the standard Alt+Pause mapper binding, installs an
INT 21h/AH=2Ch breakpoint, resumes execution with the debugger's F5 binding,
and only then asks the debugger to dump CS:0100. A byte-exact dump proves both
that execution returned to the debugger on the breakpoint and that guest state
can be observed non-manually.
"""
from __future__ import annotations

import argparse
import fcntl
import os
import pathlib
import pty
import select
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE_SOURCE = ROOT / "tools" / "cf3_sdl12_probe.c"
# mov ah,2ch ; int 21h ; jmp short 0100h
COM_BYTES = bytes.fromhex("b42ccd21ebfa")
# xterm terminfo sequence for F5. DOSBox 0.74 uses F5 to resume emulation.
F5 = b"\x1b[15~"


class DebuggerSmokeError(Exception):
    pass


def compile_probe(directory: pathlib.Path) -> pathlib.Path:
    gcc = shutil.which("gcc")
    if not gcc:
        raise DebuggerSmokeError("gcc is required")
    output = directory / "cf3_sdl12_probe.so"
    completed = subprocess.run(
        [gcc, "-shared", "-fPIC", "-O2", "-Wall", "-Wextra", "-Werror", "-o", str(output), str(PROBE_SOURCE), "-ldl"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        raise DebuggerSmokeError(f"probe build failed ({completed.returncode}): {completed.stderr}")
    return output


def drain(master: int, transcript: bytearray) -> None:
    while True:
        readable, _, _ = select.select([master], [], [], 0)
        if not readable:
            return
        try:
            chunk = os.read(master, 65536)
        except OSError:
            return
        if not chunk:
            return
        transcript.extend(chunk)


def send_command(master: int, text: str, delay: float = 0.25) -> None:
    # DOSBox 0.74 does not accept debugger commands directly in the code view.
    # ENTER first opens the command line ("->"), a second ENTER executes it.
    os.write(master, b"\r")
    time.sleep(0.08)
    os.write(master, text.encode("ascii"))
    time.sleep(0.08)
    os.write(master, b"\r")
    time.sleep(delay)


def send_key(master: int, sequence: bytes, delay: float = 0.25) -> None:
    os.write(master, sequence)
    time.sleep(delay)


def transcript_tail(transcript: bytearray) -> str:
    # Curses output contains terminal control sequences. Keep a bounded,
    # printable diagnostic tail without trying to treat it as evidence.
    text = bytes(transcript[-12000:]).decode("utf-8", errors="replace")
    return "".join(ch if ch.isprintable() or ch in "\n\r\t" else "." for ch in text)


def run_smoke(dosbox_debug: pathlib.Path, timeout: float) -> None:
    with tempfile.TemporaryDirectory(prefix="cf3-debugger-") as temp_name:
        temp = pathlib.Path(temp_name)
        guest = temp / "guest"; guest.mkdir()
        (guest / "PROBE.COM").write_bytes(COM_BYTES)
        probe = compile_probe(temp)
        dump = temp / "MEMDUMP.BIN"

        master, slave = pty.openpty()
        # ncurses refuses or renders unpredictably on a zero-sized pseudo TTY.
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
        env = os.environ.copy()
        env.update({
            "TERM": "xterm",
            "HOME": str(temp / "home"),
            "SDL_VIDEODRIVER": "dummy",
            "SDL_AUDIODRIVER": "dummy",
            "LD_PRELOAD": str(probe),
            "CF3_KEY_EVENTS": "800:alt-pause",
            "CF3_CAPTURES_MS": "999999",
        })
        pathlib.Path(env["HOME"]).mkdir()
        command = [
            str(dosbox_debug), "-noautoexec",
            "-c", f"mount c {guest}",
            "-c", "c:",
            "-c", "probe.com",
        ]
        process = subprocess.Popen(
            command,
            cwd=temp,
            env=env,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            start_new_session=True,
        )
        os.close(slave)
        transcript = bytearray()
        deadline = time.monotonic() + timeout
        try:
            # Allow DOSBox to start the looping COM and the SDL probe to inject
            # the standard debugger shortcut. If that shortcut did not pause
            # execution, the terminal keystrokes below cannot create a dump.
            time.sleep(1.5)
            drain(master, transcript)

            # The 0.74 UI requires ENTER to open its command input.
            send_command(master, "BPINT 21 2C *")
            drain(master, transcript)

            # 0.74 documents F5 as "Run"; it does not rely on newer forks'
            # textual RUN command. The looping fixture immediately executes
            # INT 21h/AH=2Ch again, so the BPINT should return to the debugger.
            send_key(master, F5, delay=0.7)
            drain(master, transcript)

            # Only a debugger that has regained control after the breakpoint
            # can execute this command and create the host-side file.
            send_command(master, "MEMDUMPBIN CS:100 6", delay=0.4)
            send_command(master, "EV AH", delay=0.2)

            while time.monotonic() < deadline and not dump.is_file():
                drain(master, transcript)
                if process.poll() is not None:
                    break
                time.sleep(0.05)
            drain(master, transcript)

            if not dump.is_file():
                raise DebuggerSmokeError(
                    "debugger did not produce MEMDUMP.BIN after BPINT/F5; transcript tail:\n"
                    + transcript_tail(transcript)
                )
            observed = dump.read_bytes()
            if observed != COM_BYTES:
                raise DebuggerSmokeError(
                    f"debugger memory observation mismatch: expected {COM_BYTES.hex()}, got {observed.hex()}"
                )
        finally:
            try:
                os.killpg(process.pid, 15)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, 9)
                except ProcessLookupError:
                    pass
                process.wait(timeout=2)
            os.close(master)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dosbox-debug", type=pathlib.Path, default=pathlib.Path(shutil.which("dosbox-debug") or "dosbox-debug"))
    p.add_argument("--timeout", type=float, default=8.0)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        executable = args.dosbox_debug.resolve()
        if not executable.is_file():
            raise DebuggerSmokeError(f"dosbox-debug not found: {executable}")
        run_smoke(executable, args.timeout)
        print("CF3 debugger smoke: PASS (BPINT hit and byte-exact guest memory observation)")
        return 0
    except DebuggerSmokeError as exc:
        print(f"CF3 debugger smoke: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
