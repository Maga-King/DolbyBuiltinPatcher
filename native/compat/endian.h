#pragma once
#define __LITTLE_ENDIAN 1234
#define __BIG_ENDIAN 4321
#define __BYTE_ORDER __LITTLE_ENDIAN
#define le32toh(x) (x)
#define htole32(x) (x)
#define le64toh(x) (x)
#define htole64(x) (x)
