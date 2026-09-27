#pragma once
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
char *strndup(const char *s, size_t n);
char *stpcpy(char *dest, const char *src);
#ifndef S_ISSOCK
#define S_ISSOCK(mode) 0
#endif
#ifndef MIN
#define MIN(a,b) ((a)<(b)?(a):(b))
#endif
#ifndef MAX
#define MAX(a,b) ((a)>(b)?(a):(b))
#endif
