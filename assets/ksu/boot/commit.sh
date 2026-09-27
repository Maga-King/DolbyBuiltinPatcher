#!/system/bin/sh
M=/data/adb/modules/mio_dolby_c17_generated
R="$M/.runtime"
exec > "$R/commit.log" 2>&1
[ "$(cat "$M/mode")" = activate ] || { echo 'REGISTER_ONLY: stock audio retained'; exit 0; }
cmp -s "$R/ready" /proc/sys/kernel/random/boot_id || exit 0
[ "$(getprop init.svc.vendor.audio-hal-aidl)" != running ] || exit 0
[ "$(getprop init.svc.audioserver)" != running ] || exit 0
tab=$(printf '\t')
while IFS="$tab" read -r phase source target expected; do
    [ "$phase" = audio ] || continue
    actual=$(sha256sum "$target")
    [ "${actual%% *}" = "$expected" ] || exit 0
done < "$M/late.tsv"
# Journal every intended target BEFORE binding; recovery also handles hard kills.
while IFS="$tab" read -r phase source target expected; do
    [ "$phase" = audio ] || continue
    echo "$target" >> "$R/audio-targets"
    mount -o bind "$M/$source" "$target" || exit 0
    cmp -s "$M/$source" "/proc/1/root$target" || exit 0
done < "$M/late.tsv"
cp "$R/ready" "$R/committed"
echo "AUDIO_CONFIG_COMMITTED $(cat /proc/uptime)" > "$R/status"
echo 'MIO_DOLBY audio config committed before HAL' > /dev/kmsg
exit 0
