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
mkdir -p /data/vendor/dolby
chown 1013:1013 /data/vendor/dolby
chmod 0770 /data/vendor/dolby
chcon u:object_r:vendor_data_file:s0 /data/vendor/dolby || fail 'Dolby data label'
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
