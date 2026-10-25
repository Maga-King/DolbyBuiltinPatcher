#!/system/bin/sh
# Disable only the enabled OPLUS audio effect selector; remember ownership for uninstall.
M=${0%/*}
APP=com.oplus.audio.effectcenter
R="$M/.runtime"
STATE="$R/audioeffectcenter-disabled-by-module"
BB=/data/adb/ksu/bin/busybox
mkdir -p "$R" || exit 1
[ -e "$STATE" ] && exit 0
[ -x "$BB" ] || exit 1
run_pm() { "$BB" timeout -s TERM -k 2 10 pm "$@"; }
installed=$(run_pm list packages --user 0 "$APP" 2>/dev/null) || exit 1
printf '%s\n' "$installed" | grep -Fx "package:$APP" >/dev/null || {
    echo '未找到 OPLUS 音效中心，稍后可由开机服务重试。'
    exit 1
}
disabled=$(run_pm list packages -d --user 0 "$APP" 2>/dev/null) || exit 1
if printf '%s\n' "$disabled" | grep -Fx "package:$APP" >/dev/null; then
    echo 'OPLUS 音效中心原本已停用，保持原状态。'
    exit 0
fi
enabled=$(run_pm disable-user --user 0 "$APP" 2>&1) || {
    echo "$enabled"
    exit 1
}
disabled=$(run_pm list packages -d --user 0 "$APP" 2>/dev/null) || exit 1
printf '%s\n' "$disabled" | grep -Fx "package:$APP" >/dev/null || {
    echo '停用命令未能确认包状态，未记录由模块接管。'
    exit 1
}
tmp="$STATE.tmp"
printf '%s\n' "$APP" > "$tmp" && mv -f "$tmp" "$STATE" || exit 1
echo '已停用 OPLUS 音效中心；卸载模块时会恢复。'
