from __future__ import annotations

import hashlib
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
#include <unistd.h>
typedef uint32_t Uint32; typedef struct SDL_Surface SDL_Surface;
typedef struct SDL_keysym { unsigned char scancode; int sym; int mod; unsigned short unicode; } SDL_keysym;
typedef struct SDL_KeyboardEvent { unsigned char type,which,state,padding; SDL_keysym keysym; } SDL_KeyboardEvent;
typedef union SDL_Event { unsigned char type; SDL_KeyboardEvent key; unsigned char padding[24]; } SDL_Event;
extern SDL_Surface *SDL_SetVideoMode(int,int,int,Uint32);
extern int SDL_PollEvent(SDL_Event *);
int main(int argc,char **argv){(void)argc;(void)argv;SDL_SetVideoMode(640,480,32,0);for(int i=0;i<100;i++){SDL_Event ev;if(SDL_PollEvent(&ev)&&ev.type==2&&ev.key.keysym.sym==32){usleep(160000);return 0;}usleep(5000);}return 3;}
'''

FAKE_SDL = r'''
#include <stdint.h>
typedef uint8_t Uint8; typedef uint16_t Uint16; typedef uint32_t Uint32;
typedef struct SDL_Color { Uint8 r,g,b,unused; } SDL_Color;
typedef struct SDL_Palette { int ncolors; SDL_Color *colors; } SDL_Palette;
typedef struct SDL_PixelFormat { SDL_Palette *palette; Uint8 BitsPerPixel,BytesPerPixel,Rloss,Gloss,Bloss,Aloss,Rshift,Gshift,Bshift,Ashift; Uint32 Rmask,Gmask,Bmask,Amask,colorkey; Uint8 alpha; } SDL_PixelFormat;
typedef struct SDL_Surface { Uint32 flags; SDL_PixelFormat *format; int w,h; Uint16 pitch; void *pixels; } SDL_Surface;
typedef union SDL_Event { Uint8 type; Uint8 padding[24]; } SDL_Event;
static uint32_t pixels[4]={0x00ff0000,0x0000ff00,0x000000ff,0x00ffffff};
static SDL_PixelFormat fmt={0,32,4,0,0,0,0,16,8,0,0,0x00ff0000,0x0000ff00,0x000000ff,0,0,255};
static SDL_Surface surf={0,&fmt,2,2,8,pixels};
SDL_Surface *SDL_SetVideoMode(int w,int h,int bpp,Uint32 flags){(void)w;(void)h;(void)bpp;(void)flags;return &surf;}
int SDL_PollEvent(SDL_Event *ev){(void)ev;return 0;}
'''


class RuntimeSmokeTests(unittest.TestCase):
    def test_runner_packages_sanitized_metadata_and_no_game_bytes(self) -> None:
        gcc = shutil.which("gcc")
        self.assertIsNotNone(gcc, "gcc is required by the CF3 cloud harness")
        with tempfile.TemporaryDirectory() as name:
            temp = pathlib.Path(name)
            game = temp / "private-user-game"; game.mkdir()
            executable = game / "ASCEND.EXE"
            executable.write_bytes(b"MZ synthetic executable bytes")
            expected_sha = hashlib.sha256(executable.read_bytes()).hexdigest()

            (temp / "fake_sdl.c").write_text(FAKE_SDL)
            (temp / "fake_dosbox.c").write_text(FAKE_DOSBOX)
            library = temp / "libfakesdl.so"
            dosbox = temp / "private-dosbox-path" / "dosbox"; dosbox.parent.mkdir()
            subprocess.run([gcc, "-shared", "-fPIC", "-o", str(library), str(temp / "fake_sdl.c")], check=True)
            subprocess.run([gcc, "-o", str(dosbox), str(temp / "fake_dosbox.c"), "-L", str(temp), "-lfakesdl", f"-Wl,-rpath,{temp}"], check=True)

            artifact = temp / "artifact.zip"
            env = os.environ.copy()
            completed = subprocess.run(
                [
                    "python", str(RUNNER),
                    "--dosbox", str(dosbox),
                    "--game-dir", str(game),
                    "--expected-exe-sha256", expected_sha,
                    "--key-events", "40:space",
                    "--captures-ms", "80",
                    "--timeout", "2",
                    "--expect-mode", "640x480",
                    "--artifact", str(artifact),
                ],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            with zipfile.ZipFile(artifact) as zf:
                names = zf.namelist()
                self.assertIn("metadata.json", names)
                self.assertNotIn("ASCEND.EXE", names)
                self.assertTrue(any(item.startswith("captures/frame-") for item in names))
                metadata = json.loads(zf.read("metadata.json"))
            serialized = json.dumps(metadata)
            self.assertNotIn(str(game), serialized)
            self.assertNotIn(str(dosbox.parent), serialized)
            self.assertEqual(metadata["executable"]["sha256"], expected_sha)
            self.assertEqual(metadata["dosbox"]["name"], "dosbox")
            self.assertEqual(metadata["command"][2], "mount c <TEMP_MOUNT>")
            self.assertTrue(metadata["expected_mode_observed"])


if __name__ == "__main__":
    unittest.main()
