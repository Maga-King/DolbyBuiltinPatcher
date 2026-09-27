#!/system/bin/sh
# Bounded, post-boot only. No audio/HWS changes in post-fs-data.
MODDIR=${0%/*}
R="$MODDIR/.runtime"
mkdir -p "$R"
boot=$(cat /proc/sys/kernel/random/boot_id)
lock="$R/boot-$boot"
mkdir "$lock" 2>/dev/null || exit 0
exec >"$R/startup.log" 2>&1
tab=$(printf '\t')
audio_changed=0
committed=0
status() { printf '%s\n' "$*" > "$R/status"; echo "$*"; }
fail() { status "FAILED: $*"; exit 1; }
file_digest() { sha256sum "$1" 2>/dev/null | cut -d ' ' -f 1; }
same() { [ -f "$1" ] && [ -f "$2" ] && cmp -s "$1" "$2"; }
rollback_audio() {
    [ -s "$R/audio-binds" ] || return 0
    failed=0
    tac "$R/audio-binds" | while IFS= read -r target; do
        umount "$target" || exit 1
    done || failed=1
    [ "$failed" = 0 ] || return 1
    : > "$R/audio-binds"
}
finish() {
    if [ "$committed" != 1 ] && [ "$audio_changed" = 1 ]; then
        if rollback_audio; then
            echo 'Audio XML bindings rolled back. Requesting stock HAL once.'
            setprop ctl.restart vendor.audio-hal-aidl
        else
            status 'RECOVERY REQUIRED: audio bind rollback failed; disable module and reboot manually.'
        fi
    fi
}
trap finish EXIT
status 'WAITING: boot completed (up to 180 seconds)'
n=0
while [ "$(getprop sys.boot_completed)" != 1 ]; do
    [ "$n" -lt 90 ] || fail 'Boot wait expired; no audio configuration was changed.'
    n=$((n+1)); sleep 2
done
[ ! -f "$MODDIR/disable" ] || fail 'Module disabled.'
[ ! -f /system/etc/init/00-dolby-native.rc ] || fail 'Native Dolby detected; do not stack.'
while IFS="$tab" read -r key expected; do
    [ "$(getprop "$key")" = "$expected" ] || fail "ROM changed: $key. Regenerate module."
done < "$MODDIR/target.tsv"
status 'VERIFYING: metamodule file visibility'
n=0
while :; do
    ready=1
    while IFS="$tab" read -r source target expected; do
        [ -f "$target" ] && [ "$(file_digest "$target")" = "$expected" ] || { ready=0; break; }
    done < "$MODDIR/mounts.tsv"
    [ "$ready" = 1 ] && break
    [ "$n" -lt 10 ] || fail "Metamodule incomplete/different: $target. Stock audio retained."
    n=$((n+1)); sleep 2
done
# A metamodule visible only in the script's private namespace cannot serve HALs.
while IFS="$tab" read -r source target expected; do
    [ "$(file_digest "/proc/1/root$target")" = "$expected" ] || fail "Mount not visible to init: $target"
done < "$MODDIR/mounts.tsv"
# All existing late targets must match the ROM used to generate the module.
# No write or mount occurs until the entire preflight succeeds.
while IFS="$tab" read -r phase source target expected; do
    [ -f "$target" ] && [ ! -L "$target" ] || fail "Missing/symlink late target: $target"
    [ "$(file_digest "$target")" = "$expected" ] || fail "Late target changed by ROM/other module: $target"
done < "$MODDIR/late.tsv"
mkdir -p /data/vendor/dolby
chown 1013:1013 /data/vendor/dolby
chmod 0770 /data/vendor/dolby
chcon u:object_r:vendor_data_file:s0 /data/vendor/dolby || fail 'Dolby data label failed.'
# VINTF is late-bound only after boot; no startup critical manager is restarted.
while IFS="$tab" read -r phase source target expected; do
    [ "$phase" != audio ] || continue
    mount -o bind "$MODDIR/$source" "$target" || fail "Late bind failed: $target"
    same "$MODDIR/$source" "/proc/1/root$target" || fail "Late bind not visible to init: $target"
done < "$MODDIR/late.tsv"
# Refresh libvintf's APEX mtime invalidation once, following the earlier module.
# This may not invalidate every future Android cache; registration is verified.
if [ -f /apex/apex-info-list.xml ]; then
    cp -p /apex/apex-info-list.xml "$R/apex-info-list.xml" || fail 'APEX cache marker copy failed.'
    chcon u:object_r:apex_info_file:s0 "$R/apex-info-list.xml" || fail 'APEX cache marker label failed.'
    sleep 1
    touch "$R/apex-info-list.xml"
    mount -o bind "$R/apex-info-list.xml" /apex/apex-info-list.xml || fail 'VINTF cache refresh failed.'
fi
if [ "$(getprop init.svc.hwservicemanager)" = stopped ]; then
    resetprop -n hwservicemanager.disabled false || fail 'Cannot clear disabled HWS property.'
    setprop ctl.start hwservicemanager || fail 'Cannot start stopped HWS.'
fi
n=0
while [ "$(getprop init.svc.hwservicemanager)" != running ] || [ "$(getprop hwservicemanager.ready)" != true ]; do
    [ "$n" -lt 15 ] || fail 'HWS not ready; no kill/restart attempted, stock audio retained.'
    n=$((n+1)); sleep 1
done
start_once() {
    svc=$1;binary=$2
    timeout 8 /system/bin/linker64 --list "$binary" > "$R/$svc-linker.log" 2>&1 || return 1
    # A declared disabled service may not have published init.svc yet. Attempt
    # ctl.start once before deciding that this KSU lacks initrc injection.
    setprop ctl.start "$svc" 2>/dev/null
    sleep 1
    state=$(getprop "init.svc.$svc")
    if [ -n "$state" ]; then
        [ "$state" = running ] || return 1
    else
        # Older KSU does not inject initrc. Use its existing privileged script
        # context once; no custom persistent supervisor or unbounded log files.
        "$binary" > /dev/null 2>&1 &
        echo "$svc direct-pid=$!"
    fi
}
status 'STARTING: HIDL / AIDL / Codec2 (one attempt each)'
start_once mio-dolby-hidl /vendor/bin/hw/vendor.dolby.hardware.dms@2.0-service || fail 'HIDL linker/start failed.'
start_once mio-dolby-dms /system_ext/bin/hw/vendor.dolby.dms.service || fail 'AIDL DMS linker/start failed.'
start_once mio-dolby-codec /system_ext/bin/hw/dolbycodecservice || fail 'Codec2 linker/start failed.'
n=0
while :; do
    timeout 4 lshal > "$R/hidl.txt" 2>/dev/null
    timeout 4 service list > "$R/aidl.txt" 2>/dev/null
    if grep -q 'vendor.dolby.hardware.dms@2.0::IDms/default' "$R/hidl.txt" &&
       grep -q 'vendor.dolby.dms.IDms/default' "$R/aidl.txt" &&
       grep -q 'android.hardware.media.c2.IComponentStore/default9' "$R/aidl.txt"; then break; fi
    [ "$n" -lt 8 ] || fail 'Dolby registration timed out; stock audio retained, no restart of HWS.'
    n=$((n+1)); sleep 1
done
timeout 8 /system/bin/linker64 --list /vendor/lib64/soundfx/libswdapaidl.so > "$R/dap-linker.log" 2>&1 || fail 'DAP linker preflight failed.'
[ "$(getprop init.svc.vendor.audio-hal-aidl)" = running ] || fail 'Original audio HAL not running.'
status 'ACTIVATING: verified services, late audio XML only'
: > "$R/audio-binds"
while IFS="$tab" read -r phase source target expected; do
    [ "$phase" = audio ] || continue
    [ "$(file_digest "$target")" = "$expected" ] || fail "Concurrent audio XML change: $target"
    mount -o bind "$MODDIR/$source" "$target" || fail "Audio bind failed: $target"
    audio_changed=1
    printf '%s\n' "$target" >> "$R/audio-binds"
    same "$MODDIR/$source" "/proc/1/root$target" || fail "Audio bind not visible to init: $target"
done < "$MODDIR/late.tsv"
oldpid=$(pidof audiohalservice.qti)
setprop ctl.restart vendor.audio-hal-aidl || fail 'Audio restart request failed.'
n=0;stable=0;lastpid=''
while [ "$n" -lt 15 ]; do
    sleep 1; n=$((n+1))
    pid=$(pidof audiohalservice.qti)
    if [ -n "$pid" ] && [ "$pid" != "$oldpid" ] && timeout 4 service list | grep -q 'android.hardware.audio.effect.IFactory/default'; then
        if [ "$pid" = "$lastpid" ]; then stable=$((stable+1)); else stable=0; fi
        [ "$stable" -ge 2 ] && break
    else stable=0; fi
    lastpid=$pid
done
[ "$stable" -ge 2 ] || fail 'Audio factory/PID not stable; rolling back audio bindings.'
committed=1
setprop ctl.restart media
status 'ACTIVE: Dolby services registered, audio factory stable. Startup checker has exited; no polling remains.'
exit 0
