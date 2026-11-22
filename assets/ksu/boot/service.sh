#!/system/bin/sh
# One cache housekeeping check, then bounded completion report. No service control.
M=${0%/*}
BB=/data/adb/ksu/bin/busybox
. "$M/user-state.sh" || exit 1
mkdir -p "$M/.runtime"
/system/bin/sh "$M/initrc-cache.sh" repair > "$M/.runtime/initrc-cache.log" 2>&1
n=0
while [ "$(getprop sys.boot_completed)" != 1 ] && [ "$n" -lt 45 ]; do n=$((n+1)); sleep 2; done
if [ "$(getprop sys.boot_completed)" = 1 ] && [ ! -e "$M/disable" ] && [ ! -e "$M/remove" ] && [ ! -e "$M/update" ]; then
    /system/bin/sh "$M/freeze-audioeffectcenter.sh" > "$M/.runtime/audioeffectcenter.log" 2>&1
    /system/bin/sh "$M/install-app.sh"
    # CE settings may still be locked when sys.boot_completed becomes 1.
    # Wait only during startup, then repair once; no resident permission watcher.
    n=0
    while [ "$(dolby_user_unlock_state)" != true ] && [ "$n" -lt 60 ]; do
        n=$((n+1)); sleep 2
    done
    if [ "$(dolby_user_unlock_state)" = true ]; then
        (
            . "$M/storage-access.sh" || exit 1
            dolby_open_storage /data/vendor/dolby vendor
            dolby_open_storage /data/user_de/0/org.lunaris.dolby app
            dolby_open_storage /data/user/0/org.lunaris.dolby app
        ) > "$M/.runtime/storage-after-unlock.log" 2>&1
    else
        printf '用户解锁状态=%s；本次未执行 CE 权限准备。\n' "$(dolby_user_unlock_state)" > "$M/.runtime/storage-after-unlock.log"
    fi
fi
mkdir -p "$M/.runtime"
{
    getprop sys.boot_completed
    getprop init.svc.hwservicemanager
    getprop init.svc.mio-dolby-hidl
    getprop init.svc.mio-dolby-dms
    getprop init.svc.mio-dolby-codec
    timeout 4 service list
} > "$M/.runtime/after-boot.txt" 2>&1
exit 0
