#!/system/bin/sh
# One cache housekeeping check, then bounded completion report. No service control.
M=${0%/*}
mkdir -p "$M/.runtime"
/system/bin/sh "$M/initrc-cache.sh" repair > "$M/.runtime/initrc-cache.log" 2>&1
n=0
while [ "$(getprop sys.boot_completed)" != 1 ] && [ "$n" -lt 45 ]; do n=$((n+1)); sleep 2; done
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
