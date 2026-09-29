#!/system/bin/sh
# Synthetic files ONLY. Invoked by test_meta_repair_android.py in a private ns.
set -eu
BB=/data/adb/ksu/bin/busybox
mount() { "$BB" mount "$@"; }
umount() { "$BB" umount "$@"; }
case "$LAB" in /data/local/tmp/dolby-mount-lab-*) ;; *) exit 80;; esac
[ -d "$LAB" ] && [ ! -L "$LAB" ] || exit 81
[ "$(readlink /proc/self/ns/mnt)" != "$(readlink /proc/1/ns/mnt)" ] || exit 82
mount --make-rprivate /
mount -t tmpfs -o mode=0700,nodev KSU "$LAB"
M="$LAB/module"
ROOT="$LAB/vendor/lib64"
S="$LAB/snapshot"
W="$LAB/repair-work"
mkdir -p "$M/.runtime" "$M/system/vendor/lib64" "$ROOT/opex" "$LAB/live" "$LAB/meta/opex"
cp "$SOURCE/mount-engine.sh" "$M/mount-engine.sh"
cp "$SOURCE/preserve.sh" "$M/preserve.sh"
cp "$SOURCE/repair-mounts.sh" "$M/repair-mounts.sh"
echo updated-oem > "$LAB/live/oem.so"
echo base-oem > "$ROOT/opex/oem.so"
echo hidden-base > "$LAB/meta/opex/oem.so"
echo dolby-one > "$M/system/vendor/lib64/one.so"
echo dolby-two > "$M/system/vendor/lib64/two.so"
echo stock-one > "$ROOT/one.so"
echo stock-two > "$ROOT/two.so"
cp "$M/system/vendor/lib64/one.so" "$LAB/meta/one.so"
echo conflicting-module > "$LAB/meta/two.so"
printf '%s\n' "$ROOT" > "$M/mount-roots.txt"
for name in one.so two.so; do
    printf 'system/vendor/lib64/%s\t%s/%s\tunused\n' "$name" "$ROOT" "$name" >> "$M/mounts.tsv"
    printf 'system/vendor/lib64/%s\t0644\tu:object_r:vendor_file:s0\n' "$name" >> "$M/labels.tsv"
    chmod 0644 "$M/system/vendor/lib64/$name" "$LAB/meta/$name"
    chcon u:object_r:vendor_file:s0 "$M/system/vendor/lib64/$name" "$LAB/meta/$name"
done
case "$CASE" in
    all) cp "$M/system/vendor/lib64/two.so" "$LAB/meta/two.so";;
    wrong-mode) cp "$M/system/vendor/lib64/two.so" "$LAB/meta/two.so"; chmod 0600 "$LAB/meta/two.so";;
    wrong-label) cp "$M/system/vendor/lib64/two.so" "$LAB/meta/two.so"; chcon u:object_r:system_file:s0 "$LAB/meta/two.so";;
    partial|late|none|empty) ;;
    missing-directory)
        mkdir "$M/system/vendor/lib64/newdir"
        mv "$M/system/vendor/lib64/two.so" "$M/system/vendor/lib64/newdir/two.so"
        "$BB" sed -i 's|lib64/two.so|lib64/newdir/two.so|g' "$M/mounts.tsv" "$M/labels.tsv"
        ;;
    *) exit 83;;
esac
mount --bind "$LAB/live" "$ROOT/opex"
sh "$M/preserve.sh" save
if [ "$CASE" != none ]; then
    if [ "$CASE" = empty ]; then echo stock-one > "$LAB/meta/one.so"; fi
    mount --bind "$LAB/meta" "$ROOT"
fi
cp /proc/self/mountinfo "$M/.runtime/meta-before-restore.mountinfo"
sh "$M/preserve.sh" restore
if sh "$M/repair-mounts.sh" run; then result=0; else result=$?; fi
case "$CASE" in
    late|none|empty) [ "$result" != 0 ] && [ ! -e "$M/.runtime/repair-ok" ];;
    *)
        [ "$result" = 0 ]
        cmp "$M/.runtime/repair-ok" /proc/sys/kernel/random/boot_id
        while IFS="$(printf '\t')" read -r file target; do
            cmp "$file" "$target"
            [ "$(stat -c %u:%g:%a "$file")" = "$(stat -c %u:%g:%a "$target")" ]
            [ "$(ls -Zd "$file" | awk '{print $1}')" = "$(ls -Zd "$target" | awk '{print $1}')" ]
        done < "$M/.runtime/repair-sources.tsv"
        ;;
esac
[ "$(cat "$ROOT/opex/oem.so")" = updated-oem ]
echo "ANDROID_LAB_PASS $CASE $(getenforce)"
