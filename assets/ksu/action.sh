#!/system/bin/sh
MODDIR=${0%/*}
BB=/data/adb/ksu/bin/busybox
R="$MODDIR/.runtime"
if [ "${1:-}" != collect ]; then
    [ -x "$BB" ] || { echo '缺少 KernelSU BusyBox'; exit 1; }
    mkdir -p "$R" || exit 1
    {
        "$BB" timeout -s TERM -k 1 18 /system/bin/sh "$MODDIR/action.sh" collect
        [ "$?" = 0 ] || echo '服务查询中断'
    } | "$BB" tee "$R/diagnostic-last.txt"
    exit $?
fi

bounded() { "$BB" timeout -s TERM -k 1 4 "$@" 2>/dev/null; }
init_status() {
    local state
    state=$(getprop "init.svc.$2")
    printf '%s  %s\n' "$1" "${state:-缺少服务定义}"
}
registration_status() {
    local label="$1" name="$2" listing="$3" status="$4" mode="$5" state
    state=$(printf '%s\n' "$listing" | awk -v name="$name" -v mode="$mode" '
        mode=="hidl" && $1==name {listed=1; if ($2~/^[1-9][0-9]*$/) ready=1}
        mode=="aidl" && $2==name ":" {ready=1}
        END {if (ready) print "已注册"; else if (listed) print "服务不可用"}')
    if [ -z "$state" ]; then
        if [ "$status" = 0 ]; then state=缺少注册; else state=查询失败; fi
    fi
    printf '%s  %s\n' "$label" "$state"
}

hidl=$(bounded lshal list --types=b --neat -i -p); hidl_status=$?
aidl=$(bounded service list); aidl_status=$?

init_status 'HIDL DMS 进程' mio-dolby-hidl
registration_status 'HIDL DMS 接口' 'vendor.dolby.hardware.dms@2.0::IDms/default' "$hidl" "$hidl_status" hidl
init_status 'AIDL DMS 进程' mio-dolby-dms
registration_status 'AIDL DMS 接口' 'vendor.dolby.dms.IDms/default' "$aidl" "$aidl_status" aidl
init_status 'Codec2 进程' mio-dolby-codec
registration_status 'Codec2 default9' 'android.hardware.media.c2.IComponentStore/default9' "$aidl" "$aidl_status" aidl

issues=$(
    if [ -d /proc/1/root/system ]; then
        for executable in /vendor/bin/hw/vendor.dolby.hardware.dms@2.0-service \
                          /system_ext/bin/hw/vendor.dolby.dms.service \
                          /system_ext/bin/hw/dolbycodecservice; do
            [ -f "/proc/1/root$executable" ] || printf '服务文件缺失  %s\n' "$executable"
        done
    else
        printf 'init 文件检查失败\n'
    fi
    bounded logcat -b main -b system -b crash -d -t 1600 -v brief '*:W' |
        awk 'tolower($0) ~ /org[.]lunaris[.]dolby|vendor[.]dolby|mio-dolby|dolbycodecservice|avc: denied.*(hal_dms|swdap)/ {
                 line=substr($0,1,320); if (!seen[line]++) print line
             }' | tail -n 8
)
if [ -n "$issues" ]; then
    printf '\n异常\n%s\n' "$issues"
fi
