#!/system/bin/sh
# Exact owned metadata path only; disabled initrc must be refreshed by KernelSU.
for P in /metadata/watchdog/ksu/mio_dolby_c17_generated /metadata/ksu/mio_dolby_c17_generated; do
    if [ -d "$P" ] && [ ! -L "$P" ]; then
        resolved=$(readlink -f "$P")
        [ "$resolved" = "$P" ] && rm -rf "$P"
    fi
done
echo '杜比模块的自有早期文件已清理。当前挂载会保留到重启，请重启后再安装或更换元模块。'
