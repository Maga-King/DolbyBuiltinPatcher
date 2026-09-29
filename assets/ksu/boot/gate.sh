#!/system/bin/sh
M=/data/adb/modules/mio_dolby_c17_generated
R="$M/.runtime"
mkdir -p "$R"
exec > "$R/gate.log" 2>&1
cat /proc/sys/kernel/random/boot_id > "$R/boot"
rm -f "$R/ready" "$R/committed"
: > "$R/audio-targets"
fail() { echo "FAILED: $*" > "$R/status"; echo "FAILED: $*"; exit 0; }
echo "GATE_BEGIN $(cat /proc/uptime)"
echo 'MIO_DOLBY readiness begin' > /dev/kmsg
. "$M/runtime-paths.sh" || fail '缺少运行路径脚本'
P=$(dolby_early_path)
[ ! -f "$M/disable" ] && [ ! -f "$M/remove" ] || fail 'Disabled'
cmp -s "$R/mounted-boot" /proc/sys/kernel/random/boot_id || fail '本次开机自挂载未完成，保留原厂音频'
[ "$(getprop init.svc.vendor.audio-hal-aidl)" != running ] || fail 'Audio already running'
[ "$(getprop init.svc.audioserver)" != running ] || fail 'Audioserver already running'
[ "$(getprop hwservicemanager.ready)" = true ] || fail 'HWS not ready'
tab=$(printf '\t')
while IFS="$tab" read -r source target expected; do
    cmp -s "$M/$source" "$target" && cmp -s "$M/$source" "/proc/1/root$target" || fail "Mount missing: $target"
done < "$M/mounts.tsv"
while IFS="$tab" read -r source target expected label; do
    cmp -s "$P/$source" "$target" || fail "VINTF missing: $target"
done < "$M/early/vintf.tsv"
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
while IFS="$tab" read -r phase source target expected; do
    [ "$phase" = config ] || continue
    mount -o bind "$M/$source" "$target" || fail "Config bind: $target"
done < "$M/late.tsv"
for spec in 'mio-dolby-hidl:/vendor/bin/hw/vendor.dolby.hardware.dms@2.0-service' 'mio-dolby-dms:/system_ext/bin/hw/vendor.dolby.dms.service'; do
    svc=${spec%%:*}; bin=${spec#*:}
    timeout 2 /system/bin/linker64 --list "$bin" > "$R/$svc-linker.txt" 2>&1 || fail "Linker $svc"
    timeout 2 setprop ctl.start "$svc" || fail "Start $svc"
done
n=0
while [ "$n" -lt 10 ]; do
    timeout 1 lshal > "$R/hidl.txt" 2>/dev/null || true
    timeout 1 service list > "$R/aidl.txt" 2>/dev/null || true
    if grep -q 'vendor.dolby.hardware.dms@2.0::IDms/default' "$R/hidl.txt" && grep -q 'vendor.dolby.dms.IDms/default' "$R/aidl.txt"; then
        [ "$(getprop init.svc.vendor.audio-hal-aidl)" != running ] || fail 'Ordering violation'
        timeout 2 /system/bin/linker64 --list /vendor/lib64/soundfx/libswdapaidl.so > "$R/dap-linker.txt" 2>&1 || fail 'DAP linker'
        /system/bin/sh "$M/codec.sh" || fail "Codec preparation failed"
        cp "$R/boot" "$R/ready"
        echo "SERVICES_READY $(cat /proc/uptime)" > "$R/status"
        echo "SERVICES_READY $(cat /proc/uptime)"
        echo 'MIO_DOLBY services registered before audio' > /dev/kmsg
        exit 0
    fi
    n=$((n+1)); sleep 0.25
done
fail 'Registration timeout; stock audio retained'
