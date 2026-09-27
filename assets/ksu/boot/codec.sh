#!/system/bin/sh
# Module runtime: publish Codec2 only after mounted payload and DMS checks succeeded.
set -eu
M=/data/adb/modules/mio_dolby_c17_generated
R=$M/.runtime
TARGET=$(cat "$M/codec-target")
refresh() {
    copy=$(mktemp "$R/apex-refresh.XXXXXX")
    cp -p /apex/apex-info-list.xml "$copy"
    chcon u:object_r:apex_info_file:s0 "$copy"
    # Nanosecond mtime differs from the source without a recurring timer.
    touch "$copy"
    mount -o bind "$copy" /apex/apex-info-list.xml
}
if [ "${1:-start}" = recover ]; then
    cmp -s "$R/codec-ready" /proc/sys/kernel/random/boot_id && exit 0
    if cmp -s "$M/codec-manifest.xml" "$TARGET"; then
        umount "$TARGET"
        refresh
        echo 'CODEC_DECLARATION_ROLLED_BACK'
    fi
    exit 0
fi
exec > "$R/codec.log" 2>&1
rm -f "$R/codec-ready"
# Reject late activation if normal codec-list consumers have already started.
for name in mediaserver cameraserver mediacodeclist_generator media.swcodec; do
    if pidof "$name" >/dev/null 2>&1; then echo "TOO_LATE $name"; exit 1; fi
done
[ "$(getprop init.svc.audioserver)" != running ]
timeout 2 /system/bin/linker64 --list /system_ext/bin/hw/dolbycodecservice > "$R/codec-linker.txt" 2>&1
cmp -s "$M/early/late$TARGET" "$TARGET"
echo "DECLARE $(cat /proc/uptime)"
mount -o bind "$M/codec-manifest.xml" "$TARGET"
refresh
setprop ctl.start mio-dolby-codec
n=0
while [ "$n" -lt 12 ]; do
    if timeout 1 service check android.hardware.media.c2.IComponentStore/default9 | grep -q ': found'; then
        cp /proc/sys/kernel/random/boot_id "$R/codec-ready"
        echo "CODEC_READY $(cat /proc/uptime)"
        exit 0
    fi
    n=$((n+1)); sleep 0.1
done
echo 'CODEC_REGISTRATION_FAILED'
exit 1
