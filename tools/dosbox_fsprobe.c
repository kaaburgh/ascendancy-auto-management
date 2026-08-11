// Host-side LD_PRELOAD filesystem probe for DOSBox runtime experiments.
//
// Build:
//   cc -shared -fPIC -O2 -Wall -Wextra -o dosbox_fsprobe.so \
//      tools/dosbox_fsprobe.c -ldl
//
// Use:
//   DOSBOX_FSPROBE_PREFIX=/path/to/mounted/game \
//   LD_PRELOAD=./dosbox_fsprobe.so dosbox ... 2>fsprobe.log
//
// The probe does not modify guest state.  It records selected host filesystem
// calls made by DOSBox so guest file-open failures can be correlated with the
// mounted directory.  Leave DOSBOX_FSPROBE_PREFIX unset to log all paths.

#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <dirent.h>

static __thread int g_busy;

static int should_log(const char *path) {
    const char *prefix;

    if (path == NULL) {
        return 0;
    }
    prefix = getenv("DOSBOX_FSPROBE_PREFIX");
    return prefix == NULL || *prefix == '\0' || strstr(path, prefix) != NULL;
}

static void log_path(const char *fn, const char *extra, const char *path,
                     long result, int saved_errno) {
    char buffer[2048];
    int length;

    if (g_busy || !should_log(path)) {
        return;
    }

    g_busy = 1;
    length = snprintf(buffer, sizeof(buffer),
                      "FSPROBE|%s%s%s|ret=%ld|errno=%d|%s\n",
                      fn,
                      extra != NULL ? "|" : "",
                      extra != NULL ? extra : "",
                      result,
                      saved_errno,
                      path);
    if (length > 0) {
        size_t bytes = (size_t)length;
        if (bytes > sizeof(buffer)) {
            bytes = sizeof(buffer);
        }
        (void)write(STDERR_FILENO, buffer, bytes);
    }
    g_busy = 0;
}

int open(const char *path, int flags, ...) {
    static int (*real_open)(const char *, int, ...);
    mode_t mode = 0;
    int result;
    int saved_errno;

    if (real_open == NULL) {
        real_open = dlsym(RTLD_NEXT, "open");
    }
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode = (mode_t)va_arg(args, int);
        va_end(args);
        result = real_open(path, flags, mode);
    } else {
        result = real_open(path, flags);
    }
    saved_errno = errno;
    log_path("open", NULL, path, result, saved_errno);
    errno = saved_errno;
    return result;
}

int open64(const char *path, int flags, ...) {
    static int (*real_open64)(const char *, int, ...);
    mode_t mode = 0;
    int result;
    int saved_errno;

    if (real_open64 == NULL) {
        real_open64 = dlsym(RTLD_NEXT, "open64");
    }
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode = (mode_t)va_arg(args, int);
        va_end(args);
        result = real_open64(path, flags, mode);
    } else {
        result = real_open64(path, flags);
    }
    saved_errno = errno;
    log_path("open64", NULL, path, result, saved_errno);
    errno = saved_errno;
    return result;
}

int openat(int dirfd, const char *path, int flags, ...) {
    static int (*real_openat)(int, const char *, int, ...);
    mode_t mode = 0;
    int result;
    int saved_errno;

    if (real_openat == NULL) {
        real_openat = dlsym(RTLD_NEXT, "openat");
    }
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode = (mode_t)va_arg(args, int);
        va_end(args);
        result = real_openat(dirfd, path, flags, mode);
    } else {
        result = real_openat(dirfd, path, flags);
    }
    saved_errno = errno;
    log_path("openat", NULL, path, result, saved_errno);
    errno = saved_errno;
    return result;
}

FILE *fopen(const char *path, const char *mode) {
    static FILE *(*real_fopen)(const char *, const char *);
    FILE *result;
    int saved_errno;
    char extra[128];

    if (real_fopen == NULL) {
        real_fopen = dlsym(RTLD_NEXT, "fopen");
    }
    result = real_fopen(path, mode);
    saved_errno = errno;
    snprintf(extra, sizeof(extra), "mode=%s", mode != NULL ? mode : "(null)");
    log_path("fopen", extra, path, (long)result, saved_errno);
    errno = saved_errno;
    return result;
}

FILE *fopen64(const char *path, const char *mode) {
    static FILE *(*real_fopen64)(const char *, const char *);
    FILE *result;
    int saved_errno;
    char extra[128];

    if (real_fopen64 == NULL) {
        real_fopen64 = dlsym(RTLD_NEXT, "fopen64");
    }
    result = real_fopen64(path, mode);
    saved_errno = errno;
    snprintf(extra, sizeof(extra), "mode=%s", mode != NULL ? mode : "(null)");
    log_path("fopen64", extra, path, (long)result, saved_errno);
    errno = saved_errno;
    return result;
}

int access(const char *path, int mode) {
    static int (*real_access)(const char *, int);
    int result;
    int saved_errno;

    if (real_access == NULL) {
        real_access = dlsym(RTLD_NEXT, "access");
    }
    result = real_access(path, mode);
    saved_errno = errno;
    log_path("access", NULL, path, result, saved_errno);
    errno = saved_errno;
    return result;
}

int stat(const char *path, struct stat *buffer) {
    static int (*real_stat)(const char *, struct stat *);
    int result;
    int saved_errno;

    if (real_stat == NULL) {
        real_stat = dlsym(RTLD_NEXT, "stat");
    }
    result = real_stat(path, buffer);
    saved_errno = errno;
    log_path("stat", NULL, path, result, saved_errno);
    errno = saved_errno;
    return result;
}

int lstat(const char *path, struct stat *buffer) {
    static int (*real_lstat)(const char *, struct stat *);
    int result;
    int saved_errno;

    if (real_lstat == NULL) {
        real_lstat = dlsym(RTLD_NEXT, "lstat");
    }
    result = real_lstat(path, buffer);
    saved_errno = errno;
    log_path("lstat", NULL, path, result, saved_errno);
    errno = saved_errno;
    return result;
}

DIR *opendir(const char *path) {
    static DIR *(*real_opendir)(const char *);
    DIR *result;
    int saved_errno;

    if (real_opendir == NULL) {
        real_opendir = dlsym(RTLD_NEXT, "opendir");
    }
    result = real_opendir(path);
    saved_errno = errno;
    log_path("opendir", NULL, path, (long)result, saved_errno);
    errno = saved_errno;
    return result;
}
