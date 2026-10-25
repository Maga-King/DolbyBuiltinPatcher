#!/system/bin/sh
M=${0%/*}
mkdir -p "$M/.runtime"
/data/adb/ksu/bin/busybox timeout -s TERM -k 2 15 /system/bin/sh "$M/preserve.sh" save
rc=$?
exit "$rc"
