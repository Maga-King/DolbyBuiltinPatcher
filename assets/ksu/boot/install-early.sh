#!/system/bin/sh
# Sourced by customize.sh, with installer helpers available.
/data/adb/ksud initrc --help >/dev/null 2>&1 || abort 'KernelSU initrc injection is required; this KSU build is unsupported.'
[ -x /data/adb/ksu/bin/busybox ] || abort 'KernelSU busybox is required.'
[ -d /metadata/watchdog/ksu ] || abort 'Early metadata path is unavailable; refusing a timing-race fallback.'
P=/metadata/watchdog/ksu/mio_dolby_c17_generated
[ ! -e "$P" ] || abort 'Existing early metadata: uninstall the previous generated module and reboot before reinstalling.'
while IFS="$tab" read -r source target expected label; do
    actual=$(sha256sum "$target")
    [ "${actual%% *}" = "$expected" ] || abort "Original VINTF differs: $target"
done < "$MODPATH/early/vintf.tsv"
mkdir -p "$P" || abort 'Cannot stage early metadata'
cp -a "$MODPATH/early/." "$P/" || abort 'Cannot stage early files'
cp "$MODPATH/target.tsv" "$P/target.tsv" || abort 'Cannot stage target identity'
set_perm_recursive "$P" 0 0 0755 0644 u:object_r:metadata_file:s0
while IFS="$tab" read -r source target expected label; do
    set_perm "$P/$source" 0 0 0644 "$label"
done < "$P/vintf.tsv"
ui_print 'Early HIDL support + synchronous readiness gate; no HWS/audio restart.'
ui_print 'Existing child mounts are preserved. Codec2 is declared only after payload validation.'
ui_print 'Runtime compatibility still requires testing on the target ROM.'
