#!/system/bin/sh
set -eu
M=${0%/*}
S=/dev/mio-preserve-mio_dolby_c17_generated
BB=/data/adb/ksu/bin/busybox
case "$1" in
save)
    # Failure closes metamodule mounting; do not leave a partial snapshot active.
    trap 'touch "$M/skip_mount" "$M/skip_mountify"' 0
    [ ! -e "$S" ] || exit 1
    mkdir -m 0700 "$S"
    $BB mount -t tmpfs -o mode=0700,nodev KSU "$S"
    $BB mount --make-rprivate "$S"
    exec > "$M/preserve.log" 2>&1
    echo "SAVE $(cat /proc/uptime)"
    cat /proc/sys/kernel/random/boot_id > "$S/boot"
    cp /proc/self/mountinfo "$S/before"
    : > "$S/children"
    while read -r root; do
        case "$root" in /system/*|/system_ext/*|/vendor/*|/product/*|/odm/*) ;; *) exit 2;; esac
        awk -v p="$root/" 'index($5,p)==1 {print $5}' "$S/before" >> "$S/children"
    done < "$M/mount-roots.txt"
    sort -u "$S/children" > "$S/sorted"
    : > "$S/journal"
    n=0
    while read -r target; do
        case "$target" in *\\*|*' '*|*'..'*) exit 3;; esac
        n=$((n+1)); [ "$n" -le 64 ] || exit 4
        saved="$S/$n"
        if [ -d "$target" ]; then mkdir "$saved"; else touch "$saved"; fi
        $BB mount -o bind "$target" "$saved"
        $BB mount --make-rprivate "$saved"
        printf '%s\t%s\n' "$saved" "$target" >> "$S/journal"
        echo "SAVED $target"
    done < "$S/sorted"
    touch "$S/ready"
    trap - 0
    ;;
restore)
    exec >> "$M/preserve.log" 2>&1
    echo "RESTORE $(cat /proc/uptime)"
    [ -f "$S/ready" ] || exit 5
    cmp -s "$S/boot" /proc/sys/kernel/random/boot_id || exit 6
    tab=$(printf '\t')
    while IFS="$tab" read -r saved target; do
        if ! $BB mount -o bind "$saved" "$target"; then
            echo "RESTORE_FAILED $target"
            echo "不卸载元模块共享父目录；恢复失败需保留日志并禁用杜比。"
            touch "$M/disable"
            exit 7
        fi
        echo "RESTORED $target"
    done < "$S/journal"
    touch "$S/restored"
    echo "DONE $(cat /proc/uptime)"
    ;;
*) exit 8;;
esac
