#!/system/bin/sh
# One-shot access repair. Never removes settings, follows links or changes app UID/MCS.
dolby_open_storage() {
    local path kind bb links resolved
    path=$1
    kind=$2
    bb=/data/adb/ksu/bin/busybox
    case "$kind:$path" in
        vendor:/data/vendor/dolby) ;;
        app:/data/user/0/org.lunaris.dolby|app:/data/user_de/0/org.lunaris.dolby) ;;
        *) echo "拒绝修改非杜比数据路径：$path"; return 1;;
    esac
    [ ! -L "$path" ] || { echo "杜比数据路径是符号链接：$path"; return 1; }
    [ -d "$path" ] || return 0
    resolved=$(readlink -f "$path") || return 1
    case "$path:$resolved" in
        /data/user/0/org.lunaris.dolby:/data/data/org.lunaris.dolby) ;;
        *) [ "$resolved" = "$path" ] || return 1;;
    esac
    # App lib/cache may contain links. Keep them; never traverse or chmod their targets.
    links=$("$bb" find "$path" -xdev -type f -links +1 -print -quit) || return 1
    [ -z "$links" ] || echo "跳过杜比数据内的硬链接：$path"
    if [ "$kind" = vendor ]; then
        "$bb" find "$path" -xdev -type d -exec chown 1013:1013 '{}' + || return 1
        "$bb" find "$path" -xdev -type f -links 1 -exec chown 1013:1013 '{}' + || return 1
        # Prefer the ROM's dedicated Dolby label; old generic labels remain supported.
        restorecon -RF "$path" || return 1
    else
        restorecon -RF "$path" || return 1
    fi
    "$bb" find "$path" -xdev -type d -exec chmod 0777 '{}' + || return 1
    "$bb" find "$path" -xdev -type f -links 1 -exec chmod 0777 '{}' + || return 1
    echo "杜比数据已开放 777，内容保留：$path"
}
