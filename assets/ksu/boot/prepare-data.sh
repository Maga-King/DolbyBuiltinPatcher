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
# User-authorized 777 fallback for all existing Dolby tuning/state files.
[ ! -L /data/vendor/dolby ] || fail 'Dolby 数据目录是符号链接，拒绝修改'
mkdir -p /data/vendor/dolby || fail '无法创建 Dolby 数据目录'
[ "$(readlink -f /data/vendor/dolby)" = /data/vendor/dolby ] || fail 'Dolby 数据目录路径异常'
. "$M/storage-access.sh" || fail '缺少 Dolby 数据权限脚本'
dolby_open_storage /data/vendor/dolby vendor || fail 'Dolby 数据权限修复失败'
dolby_open_storage /data/user_de/0/org.lunaris.dolby app || fail 'Dolby DE 设置权限修复失败'
if [ "$(cmd user is-user-unlocked 0 2>/dev/null)" = true ]; then
    dolby_open_storage /data/user/0/org.lunaris.dolby app || fail 'Dolby CE 设置权限修复失败'
fi
# END DOLBY DATABASE ACCESS
echo "DATA_PREPARED $(cat /proc/uptime)" > "$R/status"
