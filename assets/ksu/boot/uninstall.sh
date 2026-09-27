#!/system/bin/sh
# Exact owned metadata path only; disabled initrc must be refreshed by KernelSU.
P=/metadata/watchdog/ksu/mio_dolby_c17_generated
if [ -d "$P" ] && [ ! -L "$P" ]; then
    resolved=$(readlink -f "$P")
    [ "$resolved" = /metadata/watchdog/ksu/mio_dolby_c17_generated ] && rm -rf "$P"
fi
