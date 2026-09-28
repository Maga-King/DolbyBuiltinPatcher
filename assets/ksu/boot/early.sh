#!/system/bin/sh
P=/metadata/watchdog/ksu/mio_dolby_c17_generated
exec > "$P/early.log" 2>&1
tab=$(printf '\t')
while IFS="$tab" read -r source target expected label; do
    [ -f "$target" ] && [ ! -L "$target" ] || exit 0
done < "$P/vintf.tsv"
: > "$P/bound"
while IFS="$tab" read -r source target expected label; do
    if ! mount -o bind "$P/$source" "$target"; then
        while read -r previous; do umount "$previous"; done < "$P/bound"
        exit 0
    fi
    echo "$target" >> "$P/bound"
done < "$P/vintf.tsv"
echo "EARLY_VINTF_READY $(cat /proc/uptime)"
