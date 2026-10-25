#!/system/bin/sh
# Exact owned metadata path only; disabled initrc must be refreshed by KernelSU.
M=${0%/*}
APP=com.oplus.audio.effectcenter
STATE="$M/.runtime/audioeffectcenter-disabled-by-module"
BB=/data/adb/ksu/bin/busybox
if [ -f "$STATE" ] && [ "$(cat "$STATE" 2>/dev/null)" = "$APP" ] && [ -x "$BB" ]; then
    if "$BB" timeout -s TERM -k 2 10 pm enable --user 0 "$APP" >/dev/null 2>&1; then
        rm -f "$STATE"
        echo '已恢复模块安装前启用的 OPLUS 音效中心。'
    else
        echo 'OPLUS 音效中心恢复失败，请手动执行：pm enable --user 0 com.oplus.audio.effectcenter'
    fi
fi
for P in /metadata/watchdog/ksu/mio_dolby_c17_generated /metadata/ksu/mio_dolby_c17_generated; do
    if [ -d "$P" ] && [ ! -L "$P" ]; then
        resolved=$(readlink -f "$P")
        [ "$resolved" = "$P" ] && rm -rf "$P"
    fi
done
echo '杜比模块的自有早期文件已清理。当前挂载会保留到重启，请重启后再安装或更换元模块。'
