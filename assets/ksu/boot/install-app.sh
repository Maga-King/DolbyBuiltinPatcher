#!/system/bin/sh
# Same-signature update only. No uninstall, downgrade, root grant or hiding changes.
M=${0%/*}
R="$M/.runtime"
BB=/data/adb/ksu/bin/busybox
APP=org.lunaris.dolby
mkdir -p "$R" || exit 1
if [ "${1:-}" != run ]; then
    # cmd package passes stdio FDs to system_server. A module-labelled log FD
    # can be rejected by Binder/SELinux; give cmd pipes, and let tee own the log.
    set -o pipefail
    "$BB" timeout -s TERM -k 2 50 /system/bin/sh "$M/install-app.sh" run </dev/null 2>&1 | "$BB" tee "$R/app-install.log"
    result=$?
    [ "$result" = 0 ] || echo "App 安装未完成（$result）；不卸载旧版、不清数据、不影响音频启动。" >> "$R/app-install.log"
    exit "$result"
fi
[ ! -e "$M/disable" ] && [ ! -e "$M/remove" ] || exit 1
[ "$(getprop sys.boot_completed)" = 1 ] || { echo '系统尚未启动完成，留到本次开机完成后补试一次。'; exit 1; }
repair_app_data_labels() {
    local path
    # First installation can precede the system-base scan: app_data_file must
    # become privapp_data_file when Android promotes the package on next boot.
    # Ask libselinux/PackageManager's package table; never hard-code UID or MCS.
    for path in /data/user_de/0/org.lunaris.dolby /data/user/0/org.lunaris.dolby; do
        [ -d "$path" ] || continue
        [ ! -L "$path" ] && [ "$(readlink -f "$path")" = "$path" ] || {
            echo "数据目录不是预期路径，停止标签修复：$path"; return 1;
        }
        restorecon -RF "$path" || { echo "数据标签修复失败：$path"; return 1; }
        ls -ldZ "$path"
    done
}
APK="$M/system/system_ext/priv-app/LunarisDolby/LunarisDolby.apk"
[ -s "$APK" ] && [ ! -L "$APK" ] || { echo '模块中的杜比 APK 不存在或无效。'; exit 1; }
current=$("$BB" timeout -s TERM -k 1 5 pm path --user 0 "$APP" | sed -n 's/^package://p' | head -n 1)
case "$current" in /data/app/*)
    if cmp -s "$APK" "$current"; then
        repair_app_data_labels || exit 1
        echo '相同 APK 已安装到 data/app，无需重复安装。'
        exit 0
    fi;;
esac
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
echo '安装杜比 App（同签名覆盖，保留数据；签名冲突或版本过旧时停止）。'
"$BB" timeout -s TERM -k 1 35 pm install -r --user 0 "$T/base.apk" || exit 1
current=$("$BB" timeout -s TERM -k 1 5 pm path --user 0 "$APP" | sed -n 's/^package://p' | head -n 1)
case "$current" in /data/app/*) cmp -s "$APK" "$current" || exit 1;; *) exit 1;; esac
repair_app_data_labels || exit 1
echo 'APK 已从 data/app 加载。系统底包保留；系统身份和参数读写仍需开机后诊断确认。'
