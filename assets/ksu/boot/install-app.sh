#!/system/bin/sh
# Same-signature update only. No uninstall, downgrade, root grant or hiding changes.
M=${0%/*}
R="$M/.runtime"
BB=/data/adb/ksu/bin/busybox
APP=org.lunaris.dolby
mkdir -p "$R" || exit 1
if [ "${1:-}" != run ]; then
    "$BB" timeout -s TERM -k 2 50 /system/bin/sh "$M/install-app.sh" run </dev/null >"$R/app-install.log" 2>&1
    result=$?
    [ "$result" = 0 ] || echo "App 安装失败（$result）。" >> "$R/app-install.log"
    exit "$result"
fi
[ ! -e "$M/disable" ] && [ ! -e "$M/remove" ] || exit 1
[ "$(getprop sys.boot_completed)" = 1 ] || { echo '系统尚未启动完成。' >&2; exit 1; }
repair_app_data_labels() {
    local path
    # First installation can precede the system-base scan: app_data_file must
    # become privapp_data_file when Android promotes the package on next boot.
    # Ask libselinux/PackageManager's package table; never hard-code UID or MCS.
    for path in /data/user_de/0/org.lunaris.dolby /data/user/0/org.lunaris.dolby; do
        [ -d "$path" ] || continue
        [ ! -L "$path" ] || {
            echo "数据目录不是预期路径，停止标签修复：$path"; return 1;
        }
        restorecon -RF "$path" || { echo "数据标签修复失败：$path"; return 1; }
        dolby_open_storage "$path" app || return 1
    done
}
. "$M/storage-access.sh" || exit 1
APK="$M/system/system_ext/priv-app/LunarisDolby/LunarisDolby.apk"
[ -s "$APK" ] && [ ! -L "$APK" ] || { echo '模块中的杜比 APK 不存在或无效。'; exit 1; }
current=$("$BB" timeout -s TERM -k 1 5 pm path --user 0 "$APP" | sed -n 's/^package://p' | head -n 1)
case "$current" in /data/app/*)
    if cmp -s "$APK" "$current"; then
        repair_app_data_labels || exit 1
        exit 0
    fi;;
esac
# Repair existing settings even when installing a newer/older APK is rejected.
# This step keeps the package's existing UID/MCS and retains saved settings.
repair_app_data_labels || exit 1
T=$(mktemp -d /data/local/tmp/dolby-app.XXXXXX) || exit 1
cleanup() {
    trap - EXIT TERM INT HUP
    case "$T" in /data/local/tmp/dolby-app.*)
        [ ! -L "$T" ] && [ "$(readlink -f "$T")" = "$T" ] || return
        rm -f "$T/base.apk"
        rmdir "$T" 2>/dev/null
    esac
}
trap cleanup EXIT
trap 'exit 1' TERM INT HUP
chmod 0755 "$T" && cp "$APK" "$T/base.apk" && chmod 0644 "$T/base.apk" || exit 1
restorecon -RF "$T" || exit 1
"$BB" timeout -s TERM -k 1 35 pm install -r --user 0 "$T/base.apk" || exit 1
current=$("$BB" timeout -s TERM -k 1 5 pm path --user 0 "$APP" | sed -n 's/^package://p' | head -n 1)
case "$current" in /data/app/*) cmp -s "$APK" "$current" || exit 1;; *) exit 1;; esac
repair_app_data_labels || exit 1
