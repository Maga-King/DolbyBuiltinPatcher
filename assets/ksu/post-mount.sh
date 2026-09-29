#!/system/bin/sh
M=${0%/*}
mkdir -p "$M/.runtime" || exit 1
rm -f "$M/.runtime/repair-ok"
cp /proc/self/mountinfo "$M/.runtime/meta-before-restore.mountinfo" || exit 1
/data/adb/ksu/bin/busybox timeout -s TERM -k 2 15 /system/bin/sh "$M/preserve.sh" restore || exit 1
exec /system/bin/sh "$M/repair-mounts.sh"
