#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

typedef uint8_t Uint8;
typedef uint16_t Uint16;
typedef uint32_t Uint32;
typedef struct SDL_Color { Uint8 r, g, b, unused; } SDL_Color;
typedef struct SDL_Palette { int ncolors; SDL_Color *colors; } SDL_Palette;
typedef struct SDL_PixelFormat {
    SDL_Palette *palette;
    Uint8 BitsPerPixel, BytesPerPixel;
    Uint8 Rloss, Gloss, Bloss, Aloss;
    Uint8 Rshift, Gshift, Bshift, Ashift;
    Uint32 Rmask, Gmask, Bmask, Amask, colorkey;
    Uint8 alpha;
} SDL_PixelFormat;
typedef struct SDL_Surface {
    Uint32 flags;
    SDL_PixelFormat *format;
    int w, h;
    Uint16 pitch;
    void *pixels;
} SDL_Surface;
typedef struct SDL_keysym { Uint8 scancode; int sym; int mod; Uint16 unicode; } SDL_keysym;
typedef struct SDL_KeyboardEvent {
    Uint8 type, which, state, padding;
    SDL_keysym keysym;
} SDL_KeyboardEvent;
typedef union SDL_Event {
    Uint8 type;
    SDL_KeyboardEvent key;
    Uint8 padding[24];
} SDL_Event;

enum { SDL_KEYDOWN = 2, SDL_KEYUP = 3 };
#define MAX_EVENTS 32
#define MAX_CAPTURES 32

typedef struct {
    long due_ms;
    int key;
    int key_up;
} KeyEvent;

static KeyEvent events[MAX_EVENTS];
static int event_count;
static int event_index;
static long captures[MAX_CAPTURES];
static int capture_count;
static int capture_index;
static SDL_Surface *current_surface;
static const char *capture_dir;
static long long start_ms;
static pthread_t capture_thread;

static long long monotonic_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long long)ts.tv_sec * 1000LL + ts.tv_nsec / 1000000;
}

static long elapsed_ms(void) {
    return (long)(monotonic_ms() - start_ms);
}

static void config_error(const char *message) {
    fprintf(stderr, "CF3SDL config error: %s\n", message);
    _exit(86);
}

static long parse_nonnegative(const char *text, const char *what) {
    char *end = NULL;
    errno = 0;
    long value = strtol(text, &end, 10);
    if (errno || !end || *end || value < 0) config_error(what);
    return value;
}

static int key_code(const char *name) {
    if (!strcmp(name, "space")) return 32;
    if (!strcmp(name, "enter")) return 13;
    if (!strcmp(name, "escape")) return 27;
    if (name[0] && !name[1]) return (unsigned char)name[0];
    return 0;
}

static void parse_events(void) {
    const char *spec = getenv("CF3_KEY_EVENTS");
    if (!spec || !*spec) return;
    char *copy = strdup(spec);
    if (!copy) _exit(87);
    char *save = NULL;
    for (char *item = strtok_r(copy, ";", &save); item; item = strtok_r(NULL, ";", &save)) {
        if (event_count + 2 > MAX_EVENTS) config_error("too many key events");
        char *colon = strchr(item, ':');
        if (!colon) config_error("key event must be TIME:KEY");
        *colon++ = '\0';
        long due = parse_nonnegative(item, "bad key event time");
        int key = key_code(colon);
        if (!key) config_error("unsupported key name");
        if (event_count && due < events[event_count - 1].due_ms) config_error("key events must be sorted");
        events[event_count++] = (KeyEvent){due, key, 0};
        events[event_count++] = (KeyEvent){due, key, 1};
    }
    free(copy);
}

static void parse_captures(void) {
    const char *spec = getenv("CF3_CAPTURES_MS");
    if (!spec || !*spec) spec = "5000,8000,12000";
    char *copy = strdup(spec);
    if (!copy) _exit(87);
    char *save = NULL;
    for (char *item = strtok_r(copy, ",", &save); item; item = strtok_r(NULL, ",", &save)) {
        if (capture_count >= MAX_CAPTURES) config_error("too many capture times");
        long due = parse_nonnegative(item, "bad capture time");
        if (capture_count && due < captures[capture_count - 1]) config_error("capture times must be sorted");
        captures[capture_count++] = due;
    }
    free(copy);
}

static unsigned channel_from_mask(uint32_t pixel, uint32_t mask) {
    if (!mask) return 0;
    unsigned shift = 0;
    while (shift < 32 && ((mask >> shift) & 1u) == 0) ++shift;
    if (shift == 32) return 0;
    uint32_t shifted = mask >> shift;
    unsigned bits = 0;
    while (bits < 32 - shift && ((shifted >> bits) & 1u)) ++bits;
    uint32_t value = (pixel & mask) >> shift;
    if (bits >= 8) return (unsigned)(value >> (bits - 8));
    uint32_t max = (1u << bits) - 1u;
    return (unsigned)((value * 255u + max / 2u) / max);
}

static void dump_ppm(SDL_Surface *surface, long due, long actual) {
    if (!capture_dir || !surface || !surface->format || !surface->pixels || surface->w <= 0 || surface->h <= 0) return;
    char path[1024];
    snprintf(path, sizeof(path), "%s/frame-%06ldms.ppm", capture_dir, due);
    FILE *out = fopen(path, "wb");
    if (!out) {
        fprintf(stderr, "CF3SDL capture open failed %s: %s\n", path, strerror(errno));
        return;
    }
    fprintf(out, "P6\n%d %d\n255\n", surface->w, surface->h);
    SDL_PixelFormat *format = surface->format;
    unsigned char rgb[3];
    for (int y = 0; y < surface->h; ++y) {
        unsigned char *row = (unsigned char *)surface->pixels + (size_t)y * surface->pitch;
        for (int x = 0; x < surface->w; ++x) {
            if (format->BitsPerPixel == 8 && format->palette && format->palette->colors) {
                SDL_Color color = format->palette->colors[row[x]];
                rgb[0] = color.r; rgb[1] = color.g; rgb[2] = color.b;
            } else {
                uint32_t pixel = 0;
                int bytes = format->BytesPerPixel;
                if (bytes == 4) memcpy(&pixel, row + x * 4, 4);
                else if (bytes == 3) {
                    unsigned char *p = row + x * 3;
                    pixel = p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16);
                } else if (bytes == 2) {
                    uint16_t p;
                    memcpy(&p, row + x * 2, 2);
                    pixel = p;
                } else pixel = row[x];
                rgb[0] = (unsigned char)channel_from_mask(pixel, format->Rmask);
                rgb[1] = (unsigned char)channel_from_mask(pixel, format->Gmask);
                rgb[2] = (unsigned char)channel_from_mask(pixel, format->Bmask);
            }
            fwrite(rgb, 1, sizeof(rgb), out);
        }
    }
    fclose(out);
    fprintf(stderr, "CF3SDL capture due=%ld actual=%ld path=%s\n", due, actual, path);
    fflush(stderr);
}

static void *capture_worker(void *unused) {
    (void)unused;
    while (capture_index < capture_count) {
        long now = elapsed_ms();
        if (current_surface && now >= captures[capture_index]) {
            dump_ppm(current_surface, captures[capture_index], now);
            ++capture_index;
            continue;
        }
        struct timespec delay = {0, 20 * 1000 * 1000};
        nanosleep(&delay, NULL);
    }
    return NULL;
}

__attribute__((constructor)) static void init_probe(void) {
    start_ms = monotonic_ms();
    capture_dir = getenv("CF3_CAPTURE_DIR");
    parse_events();
    parse_captures();
    if (pthread_create(&capture_thread, NULL, capture_worker, NULL) != 0) config_error("capture thread creation failed");
    fprintf(stderr, "CF3SDL init pid=%d key_events=%d captures=%d\n", getpid(), event_count / 2, capture_count);
    fflush(stderr);
}

int SDL_PollEvent(SDL_Event *event) {
    static int (*real_poll)(SDL_Event *);
    if (!real_poll) real_poll = dlsym(RTLD_NEXT, "SDL_PollEvent");
    if (event && event_index < event_count && elapsed_ms() >= events[event_index].due_ms) {
        KeyEvent *source = &events[event_index++];
        memset(event, 0, sizeof(*event));
        event->key.type = source->key_up ? SDL_KEYUP : SDL_KEYDOWN;
        event->key.state = source->key_up ? 0 : 1;
        event->key.keysym.sym = source->key;
        fprintf(stderr, "CF3SDL inject t=%ld %s key=%d\n", elapsed_ms(), source->key_up ? "keyup" : "keydown", source->key);
        fflush(stderr);
        return 1;
    }
    return real_poll(event);
}

SDL_Surface *SDL_SetVideoMode(int w, int h, int bpp, Uint32 flags) {
    static SDL_Surface *(*real_set_mode)(int, int, int, Uint32);
    if (!real_set_mode) real_set_mode = dlsym(RTLD_NEXT, "SDL_SetVideoMode");
    current_surface = real_set_mode(w, h, bpp, flags);
    fprintf(stderr, "CF3SDL mode %dx%d bpp=%d result=%p\n", w, h, bpp, (void *)current_surface);
    fflush(stderr);
    return current_surface;
}
