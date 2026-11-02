#!/system/bin/sh
# Best-effort preparation. Init starts services even if this exits or times out.
M=/data/adb/modules/mio_dolby_c17_generated
R="$M/.runtime"
mkdir -p "$R" || exit 1
exec > "$R/prepare.log" 2>&1
cat /proc/sys/kernel/random/boot_id > "$R/boot"
fail() { echo "DATA_PREPARE_FAILED: $*" > "$R/status"; echo "DATA_PREPARE_FAILED: $*"; exit 1; }
echo "DATA_PREPARE_BEGIN $(cat /proc/uptime)" > "$R/status"
# BEGIN DOLBY DATABASE ACCESS
# Old backups may contain a root:root 0600 DB. DMS runs as media (1013).
# Preserve contents; never recurse into unrelated files or follow symlinks.
[ ! -L /data/vendor/dolby ] || fail 'Dolby 数据目录是符号链接，拒绝修改'
mkdir -p /data/vendor/dolby || fail '无法创建 Dolby 数据目录'
[ "$(readlink -f /data/vendor/dolby)" = /data/vendor/dolby ] || fail 'Dolby 数据目录路径异常'
for db in /data/vendor/dolby/dax_sqlite3.db /data/vendor/dolby/dax_sqlite3.db-wal /data/vendor/dolby/dax_sqlite3.db-shm /data/vendor/dolby/dax_sqlite3.db-journal; do
    [ ! -L "$db" ] || fail "Dolby 数据库是符号链接：$db"
    [ -e "$db" ] || continue
    [ -f "$db" ] && [ "$(stat -c %h "$db")" = 1 ] || fail "Dolby 数据库不是独立普通文件：$db"
done
chown 1013:1013 /data/vendor/dolby || fail 'Dolby 数据目录属主修复失败'
chmod 0770 /data/vendor/dolby || fail 'Dolby 数据目录权限修复失败'
chcon u:object_r:vendor_data_file:s0 /data/vendor/dolby || fail 'Dolby data label'
for db in /data/vendor/dolby/dax_sqlite3.db /data/vendor/dolby/dax_sqlite3.db-wal /data/vendor/dolby/dax_sqlite3.db-shm /data/vendor/dolby/dax_sqlite3.db-journal; do
    [ -f "$db" ] || continue
    chown 1013:1013 "$db" || fail "Dolby 数据库属主修复失败：$db"
    chmod 0600 "$db" || fail "Dolby 数据库权限修复失败：$db"
    chcon u:object_r:vendor_data_file:s0 "$db" || fail "Dolby 数据库标签修复失败：$db"
done
echo 'Dolby 数据目录及现有数据库权限已准备；未删除或重建数据库。'
# END DOLBY DATABASE ACCESS
echo "DATA_PREPARED $(cat /proc/uptime)" > "$R/status"
