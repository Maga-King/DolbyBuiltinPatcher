#include "compat/compat.h"
char *stpcpy(char *dest, const char *src) {
    size_t n = strlen(src);
    memcpy(dest, src, n + 1);
    return dest + n;
}
char *strndup(const char *s, size_t n) {
    size_t len = 0;
    while (len < n && s[len]) ++len;
    char *p = malloc(len + 1);
    if (p) { memcpy(p, s, len); p[len] = 0; }
    return p;
}
