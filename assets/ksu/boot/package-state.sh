#!/system/bin/sh
# PackageManager return codes may fail after committing the install transaction.
# Require its registered /data/app path AND exact APK bytes; a system mount alone is insufficient.
dolby_installed_apk_matches() {
    local current attempt
    for attempt in 1 2 3; do
        current=$("$BB" timeout -s TERM -k 1 3 pm path --user 0 "$APP" 2>>"$R/app-package-query.log" |
            sed -n 's/^package://p' | head -n 1)
        case "$current" in
            /data/app/*)
                if [ -f "$current" ] && [ ! -L "$current" ] && cmp -s "$APK" "$current"; then
                    return 0
                fi;;
        esac
        [ "$attempt" = 3 ] || sleep 1
    done
    return 1
}

dolby_install_update() {
    local result
    if "$BB" timeout -s TERM -k 1 35 pm install -r --user 0 "$1" >"$R/app-package-command.log" 2>&1; then
        result=0
    else
        result=$?
    fi
    if dolby_installed_apk_matches; then
        if [ "$result" != 0 ]; then
            echo "安装命令返回异常（$result），但已确认注册的用户安装 APK 与模块一致；按实际安装成功处理。"
            echo '原始返回信息保留在 .runtime/app-package-command.log。'
        else
            echo '杜比 App 已安装并核对通过。'
        fi
        return 0
    fi
    echo "杜比 App 更新尚未确认（命令返回 $result）；下次启动会重试，已有 App 和设置保留。"
    cat "$R/app-package-command.log"
    return 1
}
