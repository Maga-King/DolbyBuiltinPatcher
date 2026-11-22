#!/system/bin/sh
MODDIR=${0%/*}
BB=/data/adb/ksu/bin/busybox
R="$MODDIR/.runtime"
if [ "${1:-}" != collect ]; then
    [ -x "$BB" ] || { echo '缺少 KernelSU BusyBox'; exit 1; }
    mkdir -p "$R" || exit 1
    {
        if ! "$BB" timeout -s TERM -k 1 60 /system/bin/sh "$MODDIR/action.sh" collect; then
            echo '部分诊断超时；已保留完成的资料。'
        fi
    } | "$BB" tee "$R/diagnostic-last.txt"
    exit $?
fi

bounded() { "$BB" timeout -s TERM -k 1 4 "$@" 2>/dev/null; }
detail="$R/diagnostic-detail"
mkdir -p "$detail"
printf '杜比诊断 · %s\n' "$(date '+%Y-%m-%d %H:%M:%S')"
printf '系统：%s · SDK %s · DSU %s\n' "$(getprop ro.build.display.id)" "$(getprop ro.build.version.sdk)" "$(getprop ro.gsid.image_running)"
printf 'SELinux：%s · 用户解锁：%s\n' "$(getenforce 2>/dev/null)" "$(cmd user is-user-unlocked 0 2>/dev/null)"
printf '场景属性：persist.vendor.audio.scenario=%s\n' "$(getprop persist.vendor.audio.scenario)"
printf '该属性实际标签：%s\n' "$(getprop -Z persist.vendor.audio.scenario 2>/dev/null)"
printf '声明值类型：%s\n' "$(getprop -T persist.vendor.audio.scenario 2>/dev/null)"
init_status() {
    local state
    state=$(getprop "init.svc.$2")
    printf '%s  %s\n' "$1" "${state:-缺少服务定义}"
}
registration_status() {
    local label="$1" name="$2" listing="$3" status="$4" mode="$5" state
    state=$(printf '%s\n' "$listing" | awk -v name="$name" -v mode="$mode" '
        mode=="hidl" && $1==name {listed=1; if ($2~/^[1-9][0-9]*$/) ready=1}
        mode=="aidl" && $2==name ":" {ready=1}
        END {if (ready) print "已注册"; else if (listed) print "服务不可用"}')
    if [ -z "$state" ]; then
        if [ "$status" = 0 ]; then state=缺少注册; else state=查询失败; fi
    fi
    printf '%s  %s\n' "$label" "$state"
}

hidl=$(bounded lshal list --types=b --neat -i -p); hidl_status=$?
aidl=$(bounded service list); aidl_status=$?

init_status 'HIDL DMS 进程' mio-dolby-hidl
registration_status 'HIDL DMS 接口' 'vendor.dolby.hardware.dms@2.0::IDms/default' "$hidl" "$hidl_status" hidl
init_status 'AIDL DMS 进程' mio-dolby-dms
registration_status 'AIDL DMS 接口' 'vendor.dolby.dms.IDms/default' "$aidl" "$aidl_status" aidl
init_status 'Codec2 进程' mio-dolby-codec
registration_status 'Codec2 default9' 'android.hardware.media.c2.IComponentStore/default9' "$aidl" "$aidl_status" aidl

printf '\n管理器\n'
bounded pm path --user 0 org.lunaris.dolby
bounded dumpsys package org.lunaris.dolby > "$detail/package.txt"
awk '/versionCode=|versionName=|codePath=|dataDir=|userId=|pkgFlags=|privateFlags=|User 0:|stopped=|android.permission.MODIFY_AUDIO_SETTINGS|android.permission.RECEIVE_BOOT_COMPLETED/ {print}' "$detail/package.txt" | head -n 28
bounded ps -AZ > "$detail/processes.txt"
printf '\n实际进程域（不是仅看 sepolicy.rule 声明）\n'
awk 'tolower($0) ~ /dolby|audioserver|audiohalservice|hwservicemanager/ {print}' "$detail/processes.txt" | head -n 16
printf '\n杜比数据权限和标签（不输出设置值）\n'
for path in /data/vendor/dolby /data/user_de/0/org.lunaris.dolby /data/user/0/org.lunaris.dolby; do
    [ -d "$path" ] || { printf '尚不可访问/不存在：%s\n' "$path"; continue; }
    ls -ldZ "$path"
    for sub in "$path/shared_prefs" "$path/databases"; do [ ! -d "$sub" ] || ls -ldZ "$sub"; done
    bounded "$BB" find "$path" -xdev -maxdepth 3 -type f -exec ls -lZ '{}' + | head -n 32
done
printf '\nDMS 打开的数据库/设置文件\n'
for pid in $(pidof vendor.dolby.hardware.dms@2.0-service vendor.dolby.dms.service 2>/dev/null); do
    bounded ls -l "/proc/$pid/fd" | awk '/dolby|dax|sqlite|deleted/ {print}' | head -n 16
done
printf '\n模块实际挂载可见性\n'
tab=$(printf '\t')
count=0;missing=0;different=0
while IFS="$tab" read -r source target _ignored; do
    count=$((count+1))
    if [ ! -f "/proc/1/root$target" ]; then
        missing=$((missing+1)); printf 'init 看不到：%s\n' "$target"
    elif ! cmp -s "$MODDIR/$source" "/proc/1/root$target"; then
        different=$((different+1)); printf 'init 文件内容不同：%s\n' "$target"
    fi
done < "$MODDIR/mounts.tsv"
printf '检查 %s 项；缺失 %s，内容不同 %s。\n' "$count" "$missing" "$different"
cat /proc/1/mountinfo > "$detail/init-mountinfo.txt" 2>/dev/null
printf '\n当前 ROM 的相关属性/数据标签\n'
for file in /vendor/etc/selinux/vendor_property_contexts /system/etc/selinux/plat_property_contexts \
            /odm/etc/selinux/precompiled_property_contexts /vendor/etc/selinux/vendor_file_contexts; do
    [ -f "$file" ] || continue
    printf '%s\n' "$file"
    awk '/persist.vendor.audio|dolby|dax/ {print}' "$file" | head -n 25
done
printf '\n请求的属性权限和 permissive（实际是否生效需看内核）\n'
awk '/^permissive |^allow hal_(aidl_)?dms_default .*property_service|^allow hal_(aidl_)?dms_default property_socket/ {print}' "$MODDIR/sepolicy.rule"
printf '\n近期准备/解锁/安装结果\n'
for file in prepare.log storage-after-unlock.log app-install.log initrc-cache.log; do
    [ ! -f "$R/$file" ] || { printf '%s\n' "$file"; tail -n 8 "$R/$file"; }
done
bounded logcat -b main -b system -b crash -d -t 3500 -v threadtime > "$detail/logcat.txt"
awk 'tolower($0) ~ /dolby|dapcontroller|dscontext|dms|persist.vendor.audio.scenario|avc: denied|sqlite.*(error|readonly|denied)/ {print}' "$detail/logcat.txt" | tail -n 70 > "$detail/dolby-errors.txt"
printf '\n近期预设/存储/拒绝信息\n'
tail -n 24 "$detail/dolby-errors.txt"
bounded dumpsys media.audio_flinger > "$detail/audio-flinger.txt"
bounded dumpsys media.audio_policy > "$detail/audio-policy.txt"
printf '\nDAP 后处理位置\n'
awk 'tolower($0) ~ /dap|dolby|effect chain|session|output thread/ {print}' "$detail/audio-flinger.txt" | head -n 32
printf '\n详细资料：%s\n' "$detail"
printf '导出规则中 permissive 仅代表模块要求；不能据此保证内核已成功注入。\n'

issues=$(
    if [ -d /proc/1/root/system ]; then
        for executable in /vendor/bin/hw/vendor.dolby.hardware.dms@2.0-service \
                          /system_ext/bin/hw/vendor.dolby.dms.service \
                          /system_ext/bin/hw/dolbycodecservice; do
            [ -f "/proc/1/root$executable" ] || printf '服务文件缺失  %s\n' "$executable"
        done
    else
        printf 'init 文件检查失败\n'
    fi
    bounded logcat -b main -b system -b crash -d -t 1600 -v brief '*:W' |
        awk 'tolower($0) ~ /org[.]lunaris[.]dolby|vendor[.]dolby|mio-dolby|dolbycodecservice|avc: denied.*(hal_dms|swdap)/ {
                 line=substr($0,1,320); if (!seen[line]++) print line
             }' | tail -n 8
)
if [ -n "$issues" ]; then
    printf '\n异常\n%s\n' "$issues"
fi
