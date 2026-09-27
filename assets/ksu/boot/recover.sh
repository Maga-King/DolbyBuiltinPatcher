#!/system/bin/sh
M=/data/adb/modules/mio_dolby_c17_generated
R="$M/.runtime"
exec > "$R/recover.log" 2>&1
/system/bin/sh "$M/codec.sh" recover
cmp -s "$R/committed" /proc/sys/kernel/random/boot_id && exit 0
[ -f "$R/audio-targets" ] || exit 0
while read -r target; do
    # Unmount only an exact private bind source owned by this module.
    if cmp -s "$M/late$target" "$target"; then
        umount "$target" || echo "RECOVERY_FAILED: $target"
    fi
done < "$R/audio-targets"
echo "STOCK_AUDIO_RELEASE $(cat /proc/uptime)"
exit 0
