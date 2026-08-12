from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_cf3_runtime_smoke.py"

FAKE_DOSBOX = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
typedef uint32_t Uint32; typedef struct SDL_Surface SDL_Surface;
typedef struct SDL_keysym { unsigned char scancode; int sym; int mod; unsigned short unicode; } SDL_keysym;
typedef struct SDL_KeyboardEvent { unsigned char type,which,state,padding; SDL_keysym keysym; } SDL_KeyboardEvent;
typedef union SDL_Event { unsigned char type; SDL_KeyboardEvent key; unsigned char padding[24]; } SDL_Event;
extern SDL_Surface *SDL_SetVideoMode(int,int,int,Uint32);
extern int SDL_PollEvent(SDL_Event *);
int main(int argc,char **argv){for(int i=0;i<argc;i++){if(!strncmp(argv[i],"mount c ",8)){char path[4096];snprintf(path,sizeof(path),"%s/MUTABLE.CFG",argv[i]+8);FILE *f=fopen(path,"wb");if(f){fwrite("mutated",1,7,f);fclose(f);}}}SDL_SetVideoMode(640,480,32,0);const char *forced=getenv("CF3_FAKE_EXIT_CODE");if(forced)return atoi(forced);for(int i=0;i<100;i++){SDL_Event ev;if(SDL_PollEvent(&ev)&&ev.type==2&&ev.key.keysym.sym==32){usleep(160000);SDL_PollEvent(&ev);return 0;}usleep(5000);}return 3;}
'''

FAKE_SDL = r'''
#include <stdint.h>
#include <stdlib.h>
typedef uint8_t Uint8; typedef uint16_t Uint16; typedef uint32_t Uint32;
typedef struct SDL_Color { Uint8 r,g,b,unused; } SDL_Color;
typedef struct SDL_Palette { int ncolors; SDL_Color *colors; } SDL_Palette;
typedef struct SDL_PixelFormat { SDL_Palette *palette; Uint8 BitsPerPixel,BytesPerPixel,Rloss,Gloss,Bloss,Aloss,Rshift,Gshift,Bshift,Ashift; Uint32 Rmask,Gmask,Bmask,Amask,colorkey; Uint8 alpha; } SDL_PixelFormat;
typedef struct SDL_Surface { Uint32 flags; SDL_PixelFormat *format; int w,h; Uint16 pitch; void *pixels; } SDL_Surface;
typedef union SDL_Event { Uint8 type; Uint8 padding[24]; } SDL_Event;
static uint32_t pixels[4]={0x00ff0000,0x0000ff00,0x000000ff,0x00ffffff};
static SDL_PixelFormat fmt={0,32,4,0,0,0,0,16,8,0,0,0x00ff0000,0x0000ff00,0x000000ff,0,0,255};
static SDL_Surface surf={0,&fmt,2,2,8,pixels};
SDL_Surface *SDL_SetVideoMode(int w,int h,int bpp,Uint32 flags){(void)w;(void)h;(void)bpp;(void)flags;if(getenv("CF3_FAKE_NULL_MODE"))return 0;return &surf;}
int SDL_PollEvent(SDL_Event *ev){(void)ev;return 0;}
'''


def load_runner_module():
    spec = importlib.util.spec_from_file_location("cf3_runtime_smoke", RUNNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RuntimeSmokeTests(unittest.TestCase):
    def build_fixture(self, temp: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path, str]:
        gcc = shutil.which("gcc")
        self.assertIsNotNone(gcc, "gcc is required by the CF3 cloud harness")
        game = temp / "private-user-game"; game.mkdir()
        executable = game / "ASCEND.EXE"
        executable.write_bytes(b"MZ synthetic executable bytes")
        mutable = game / "MUTABLE.CFG"
        mutable.write_bytes(b"original")
        expected_sha = hashlib.sha256(executable.read_bytes()).hexdigest()

        (temp / "fake_sdl.c").write_text(FAKE_SDL)
        (temp / "fake_dosbox.c").write_text(FAKE_DOSBOX)
        library = temp / "libfakesdl.so"
        dosbox = temp / "private-dosbox-path" / "dosbox"; dosbox.parent.mkdir()
        subprocess.run([gcc, "-shared", "-fPIC", "-o", str(library), str(temp / "fake_sdl.c")], check=True)
        subprocess.run([gcc, "-o", str(dosbox), str(temp / "fake_dosbox.c"), "-L", str(temp), "-lfakesdl", f"-Wl,-rpath,{temp}"], check=True)
        return game, mutable, dosbox, expected_sha

    def runner_command(self, game: pathlib.Path, dosbox: pathlib.Path, expected_sha: str, artifact: pathlib.Path) -> list[str]:
        return [
            "python", str(RUNNER),
            "--dosbox", str(dosbox),
            "--game-dir", str(game),
            "--expected-exe-sha256", expected_sha,
            "--key-events", "40:space",
            "--captures-ms", "80",
            "--timeout", "2",
            "--expect-mode", "640x480",
            "--expect-exit-code", "0",
            "--artifact", str(artifact),
        ]

    def test_runner_packages_sanitized_metadata_and_isolates_source_tree(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            temp = pathlib.Path(name)
            game, mutable, dosbox, expected_sha = self.build_fixture(temp)
            artifact = temp / "artifact.zip"
            completed = subprocess.run(
                self.runner_command(game, dosbox, expected_sha, artifact),
                env=os.environ.copy(),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(mutable.read_bytes(), b"original", "guest write escaped the temporary overlay")
            with zipfile.ZipFile(artifact) as zf:
                names = zf.namelist()
                self.assertIn("metadata.json", names)
                self.assertNotIn("ASCEND.EXE", names)
                self.assertNotIn("MUTABLE.CFG", names)
                self.assertTrue(any(item.startswith("captures/frame-") for item in names))
                metadata = json.loads(zf.read("metadata.json"))
            serialized = json.dumps(metadata)
            self.assertNotIn(str(game), serialized)
            self.assertNotIn(str(dosbox.parent), serialized)
            self.assertEqual(metadata["schema"], 2)
            self.assertEqual(metadata["executable"]["sha256"], expected_sha)
            self.assertEqual(metadata["dosbox"]["name"], "dosbox")
            self.assertEqual(metadata["command"][2], "mount c <TEMP_MOUNT>")
            self.assertTrue(metadata["expected_mode_observed"])
            self.assertTrue(metadata["termination_expectation_met"])
            self.assertTrue(any(mode["ok"] and mode["width"] == 640 and mode["height"] == 480 for mode in metadata["video_modes"]))

    def test_mode_then_crash_is_not_runtime_pass(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            temp = pathlib.Path(name)
            game, _mutable, dosbox, expected_sha = self.build_fixture(temp)
            artifact = temp / "crash-artifact.zip"
            env = os.environ.copy()
            env["CF3_FAKE_EXIT_CODE"] = "7"
            completed = subprocess.run(
                self.runner_command(game, dosbox, expected_sha, artifact),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertIn("process exit did not match allowed codes", completed.stderr)
            with zipfile.ZipFile(artifact) as zf:
                metadata = json.loads(zf.read("metadata.json"))
            self.assertTrue(metadata["expected_mode_observed"], "control must prove the successful mode happened before the crash")
            self.assertFalse(metadata["termination_expectation_met"])
            self.assertEqual(metadata["returncode"], 7)

    def test_failed_set_video_mode_does_not_satisfy_expect_mode(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            temp = pathlib.Path(name)
            game, _mutable, dosbox, expected_sha = self.build_fixture(temp)
            artifact = temp / "null-mode-artifact.zip"
            env = os.environ.copy()
            env["CF3_FAKE_NULL_MODE"] = "1"
            completed = subprocess.run(
                self.runner_command(game, dosbox, expected_sha, artifact),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertIn("successful mode 640x480 was not observed", completed.stderr)
            with zipfile.ZipFile(artifact) as zf:
                metadata = json.loads(zf.read("metadata.json"))
            self.assertFalse(metadata["expected_mode_observed"])
            self.assertTrue(any(not mode["ok"] and mode["width"] == 640 and mode["height"] == 480 for mode in metadata["video_modes"]))

    def test_expect_mode_requires_termination_contract(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            temp = pathlib.Path(name)
            game, _mutable, dosbox, expected_sha = self.build_fixture(temp)
            completed = subprocess.run(
                [
                    "python", str(RUNNER), "--dosbox", str(dosbox), "--game-dir", str(game),
                    "--expected-exe-sha256", expected_sha, "--expect-mode", "640x480",
                ],
                env=os.environ.copy(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertIn("requires explicit termination semantics", completed.stderr)

    def test_manifest_tree_verification_is_case_insensitive_and_fail_closed(self) -> None:
        runner = load_runner_module()
        with tempfile.TemporaryDirectory() as name:
            temp = pathlib.Path(name)
            tree = temp / "tree"; tree.mkdir()
            payload = b"fixture bytes"
            (tree / "lower.dat").write_bytes(payload)
            manifest = temp / "manifest.json"
            manifest.write_text(json.dumps({
                "schema": 1,
                "files": [{
                    "name": "LOWER.DAT",
                    "size": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }],
            }))
            runner.verify_manifest_tree(tree, manifest, "fixture")
            (tree / "LOWER.DAT").write_bytes(payload)
            with self.assertRaises(runner.SmokeError):
                runner.verify_manifest_tree(tree, manifest, "fixture")


if __name__ == "__main__":
    unittest.main()
