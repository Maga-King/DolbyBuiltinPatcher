#!/system/bin/sh
# Cache housekeeping only. This cannot change RC definitions already read by init.
# No service starts/stops, polling, reboot, or writes to modules.rc by this script.
M=${0%/*}
BB=/data/adb/ksu/bin/busybox
KSUD=/data/adb/ksud
CACHE=/metadata/watchdog/ksu/modules.rc
PENDING=/data/adb/modules_update/mio_dolby_c17_generated
case "${1:-check}" in check|repair) ;; *) echo 'Usage: initrc-cache.sh [check|repair]'; exit 2 ;; esac
if [ -f "$M/disable" ] || [ -f "$M/remove" ] || [ -d "$PENDING" ]; then
    echo 'CACHE_CHECK_SKIPPED: disabled, removing or pending update; use KSU Manager.'
    exit 0
fi
[ -x "$BB" ] && [ -r "$M/initrc/dolby.rc" ] || { echo 'CACHE_CHECK_FAILED: missing tools or RC'; exit 1; }
cache_matches() {
    [ -r "$CACHE" ] || return 1
    # Compare the whole owned section, not a token elsewhere in another module.
    # Ignore whitespace/comments. KSU records the module id in each source header.
    "$BB" awk '
    FNR == NR {
        if ($0 ~ /^[ \t]*#/ || $0 ~ /^[ \t]*$/) next
        line=$0; gsub(/^[ \t]+|[ \t\r]+$/, "", line); expected[++count]=line; next
    }
    /^# === from / {
        active=($0 ~ /^# === from mio_dolby_c17_generated:/)
        if (active) sections++
        next
    }
    active && $0 !~ /^[ \t]*#/ && $0 !~ /^[ \t]*$/ {
        line=$0; gsub(/^[ \t]+|[ \t\r]+$/, "", line)
        if (line != expected[++seen]) bad=1
    }
    END { exit !(count > 0 && sections == 1 && seen == count && !bad) }
    ' "$M/initrc/dolby.rc" "$CACHE"
}
if cache_matches; then
    echo 'CACHE_OK: next-boot cache matches module RC; not proof of current init definitions.'
    exit 0
fi
echo 'CACHE_MISMATCH: module RC is not fully present in next-boot cache.'
[ "${1:-check}" = repair ] || exit 1
[ -x "$KSUD" ] || { echo 'CACHE_REFRESH_FAILED: ksud missing'; exit 1; }
# Do not hand-edit the aggregate file; KSU owns module enable/disable/update rules.
"$BB" timeout 8 "$KSUD" initrc refresh || { echo 'CACHE_REFRESH_FAILED: no retry'; exit 1; }
if cache_matches; then
    echo 'CACHE_REFRESHED_NEXT_BOOT_ONLY: reboot manually; current init is unchanged.'
    exit 0
fi
echo 'CACHE_REFRESH_UNVERIFIED: inspect KSU configuration; no service control attempted.'
exit 1
