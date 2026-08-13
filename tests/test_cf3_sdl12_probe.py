from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE = ROOT / "tools" / "cf3_sdl12_probe.c"

FAKE_SDL = r'''
#include <stdint.h>
#include <stdlib.h>
typedef uint8_t Uint8; typedef uint16_t Uint16; typedef uint32_t Uint32;
typedef struct SDL_Color { Uint8 r,g,b,unused; } SDL_Color;
typedef struct SDL_Palette { int ncolors; SDL_Color *colors; } SDL_Palette;
typedef struct SDL_PixelFormat { SDL_Palette *palette; Uint8 BitsPerPixel,BytesPerPixel,Rloss,Gloss,Bloss,Aloss,Rshift,Gshift,Bshift,Ashift; Uint32 Rmask,Gmask,Bmask,Amask,colorkey; Uint8 alpha; } SDL_PixelFormat;
typedef struct SDL_Surface { Uint32 flags; SDL_PixelFormat *format; int w,h; Uint16 pitch; void *pixels; } SDL_Surface;
typedef union SDL_Event { Uint8 type; Uint8 padding[24]; } SDL_Event;
static SDL_PixelFormat fmt={0,32,4,0,0,0,0,16,8,0,0,0x00ff0000,0x0000ff00,0x000000ff,0,0,255};
static SDL_Surface *current;
static SDL_Surface *make_surface(int w,int h){SDL_Surface *s=calloc(1,sizeof(*s));s->format=&fmt;s->w=w;s->h=h;s->pitch=(Uint16)(w*4);s->pixels=calloc((size_t)w*h,4);uint32_t *p=s->pixels;for(int i=0;i<w*h;i++)p[i]=0x00ffffff;return s;}
SDL_Surface *SDL_SetVideoMode(int w,int h,int bpp,Uint32 flags){(void)bpp;(void)flags;if(current){free(current->pixels);free(current);}current=make_surface(w==640?3:2,h==480?1:2);return current;}
int SDL_PollEvent(SDL_Event *ev){(void)ev;return 0;}
'''

FIXTURE = r'''
#include <stdint.h>
#include <unistd.h>
typedef uint32_t Uint32; typedef struct SDL_Surface SDL_Surface;
typedef struct SDL_keysym { unsigned char scancode; int sym; int mod; unsigned short unicode; } SDL_keysym;
typedef struct SDL_KeyboardEvent { unsigned char type,which,state,padding; SDL_keysym keysym; } SDL_KeyboardEvent;
typedef union SDL_Event { unsigned char type; SDL_KeyboardEvent key; unsigned char padding[24]; } SDL_Event;
extern SDL_Surface *SDL_SetVideoMode(int,int,int,Uint32);
extern int SDL_PollEvent(SDL_Event *);
int main(void){SDL_Event ev;SDL_SetVideoMode(320,200,32,0);for(int i=0;i<10;i++){SDL_PollEvent(&ev);usleep(5000);}usleep(30000);SDL_SetVideoMode(640,480,32,0);for(int i=0;i<100;i++){if(SDL_PollEvent(&ev)&&ev.type==2&&ev.key.keysym.sym==32)return 0;usleep(5000);}return 3;}
'''


class ProbeSmokeTests(unittest.TestCase):
    def test_probe_compiles_in_isolation(self) -> None:
        gcc = shutil.which("gcc")
        self.assertIsNotNone(gcc, "gcc is required by the CF3 cloud harness")
        with tempfile.TemporaryDirectory() as name:
            output = pathlib.Path(name) / "probe.so"
            subprocess.run([gcc, "-shared", "-fPIC", "-O2", "-Wall", "-Wextra", "-Werror", "-o", str(output), str(PROBE), "-ldl"], check=True)
            self.assertTrue(output.is_file())

    def test_surface_switch_capture_and_key_injection_are_same_thread_safe(self) -> None:
        gcc = shutil.which("gcc")
        self.assertIsNotNone(gcc, "gcc is required by the CF3 cloud harness")
        with tempfile.TemporaryDirectory() as name:
            temp = pathlib.Path(name)
            (temp / "fake_sdl.c").write_text(FAKE_SDL)
            (temp / "fixture.c").write_text(FIXTURE)
            probe = temp / "probe.so"
            library = temp / "libfakesdl.so"
            fixture = temp / "fixture"
            subprocess.run([gcc, "-shared", "-fPIC", "-o", str(library), str(temp / "fake_sdl.c")], check=True)
            subprocess.run([gcc, "-o", str(fixture), str(temp / "fixture.c"), "-L", str(temp), "-lfakesdl", f"-Wl,-rpath,{temp}"], check=True)
            subprocess.run([gcc, "-shared", "-fPIC", "-O2", "-Wall", "-Wextra", "-Werror", "-o", str(probe), str(PROBE), "-ldl"], check=True)
            captures = temp / "captures"; captures.mkdir()
            env = os.environ.copy()
            env.update({"LD_PRELOAD": str(probe), "CF3_CAPTURE_DIR": str(captures), "CF3_KEY_EVENTS": "100:space", "CF3_CAPTURES_MS": "60"})
            completed = subprocess.run([str(fixture)], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            frame = captures / "frame-000060ms.ppm"
            self.assertTrue(frame.is_file(), completed.stderr)
            # The fake SDL frees the first 2x2 surface when switching modes.
            # The scheduled capture must use the new 3x1 surface, not a stale pointer.
            self.assertTrue(frame.read_bytes().startswith(b"P6\n3 1\n255\n"))
            self.assertIn("CF3SDL inject", completed.stderr)


if __name__ == "__main__":
    unittest.main()
