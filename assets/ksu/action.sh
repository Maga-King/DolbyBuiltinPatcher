#!/system/bin/sh
MODDIR=${0%/*}
BB=/data/adb/ksu/bin/busybox
R="$MODDIR/.runtime"
APP=org.lunaris.dolby
if [ "${1:-}" != collect ]; then
    echo '来查一下杜比哪里没对上。只检查这一次，不开后台、不重启服务，也不改你的设置。'
    [ -x "$BB" ] || { echo '缺少 KSU busybox，无法保证检测超时；已停止。'; exit 1; }
    mkdir -p "$R" || exit 1
    {
        "$BB" timeout -s TERM -k 2 45 /system/bin/sh "$MODDIR/action.sh" collect
        result=$?
        if [ "$result" = 0 ]; then echo '本次检查结束。'; else echo "检查未完整结束（退出码 $result），请保留已经输出的内容。"; fi
    } | "$BB" tee "$R/diagnostic-last.txt"
    echo "日志只保留最近一份：$R/diagnostic-last.txt"
    echo '发给别人前请看一眼：里面有机型、模块名单、包路径及近期相关错误，不采集设备序列号。'
    exit 0
fi
bounded() { "$BB" timeout -s TERM -k 1 3 "$@" 2>&1; }
section() { printf '\n—— %s ——\n' "$*"; }
section '先看环境'
date; id; uname -r; getenforce
for key in ro.product.model ro.build.version.sdk sys.boot_completed; do printf '%s=' "$key"; getprop "$key"; done
[ "$(id -u)" = 0 ] || { echo '当前不是 Root，读不到完整挂载情况；请从管理器的 Action 运行。'; exit 1; }
bounded /data/adb/ksud --version
echo "当前命名空间：$(readlink /proc/self/ns/mnt)；init：$(readlink /proc/1/ns/mnt)"
section '模块和元模块：0 KB 先不要直接判定 APK 坏了'
echo "元模块路径：$(readlink -f /data/adb/metamodule)"
bounded du -sk "$MODDIR"
echo '上面的大小来自文件统计；统计失败不等于模块实际为 0 KB。'
for module in /data/adb/modules/*; do
    [ -f "$module/module.prop" ] || continue
    echo "[${module##*/}]"
    grep -E '^(id|name|version|metamodule)=' "$module/module.prop"
    for flag in disable remove skip_mount skip_mountify; do [ ! -e "$module/$flag" ] || echo "标记：$flag"; done
done
echo '本测试包正常情况下没有 skip_mount/skip_mountify；若存在，可能是前置保护失败留下的拒绝挂载标记。'
echo '切换元模块后：卸载本模块 → 重启 → 重新安装。不要同时启用多套元模块。'
section '常见挂载器设置（只读文本，不执行配置脚本）'
for file in /data/adb/mountify/config.sh /data/adb/hybrid-mount/config.toml /data/adb/magic_mount/config.toml; do
    [ ! -f "$file" ] || { echo "$file"; head -c 6000 "$file"; echo; }
done
section '下次开机的 initrc 缓存（不是本次已经加载的证明）'
/system/bin/sh "$MODDIR/initrc-cache.sh" check || true
section '本次开机的挂载和启动记录'
if cmp -s "$R/repair-ok" /proc/sys/kernel/random/boot_id; then
    echo '元模块后补挂成功记录属于本次开机。'
else
    echo '没有本次开机的元模块后补挂成功记录。先看 preserve.log 和 repair.log，不要只盯着 App。'
fi
tail -35 "$R/repair.log" 2>/dev/null
section '实际挂载范围：F 是单文件，D 是必要的父目录'
echo '这里只列本模块的补挂，不包含元模块自己的挂载范围。以本次成功记录为准。'
if [ -s "$R/repair-plan.tsv" ]; then
    awk -F '\t' '{print $1 "  " $2} END {print "计划目标数：" NR}' "$R/repair-plan.tsv"
else
    echo '没有补挂计划：可能元模块已全部挂好，也可能检查失败；请结合 repair.log。'
fi
if cmp -s "$MODDIR/.runtime/boot" /proc/sys/kernel/random/boot_id; then
    cat "$MODDIR/.runtime/status" 2>/dev/null || true
    for name in gate codec commit recover; do
        echo "$name:"
        tail -20 "$MODDIR/.runtime/$name.log" 2>/dev/null
    done
else
    echo '没有本次开机的启动门控记录；旧日志不能证明杜比已启动。'
fi
section 'GitHub 原版元模块流程＋缺失项补挂'
echo "本包单份 system/ 载荷，需要元模块；未使用 files/ 双份载荷或 self-mount.sh。"
echo "原版子挂载保存/恢复："; tail -50 "$MODDIR/preserve.log" 2>/dev/null
echo "元模块后补挂："; tail -60 "$R/repair.log" 2>/dev/null
echo "仅修复以下项："; cat "$R/repair-pending.tsv" 2>/dev/null
section '服务：running 仅代表进程状态，不等于歌曲正用杜比解码'
for name in mio-dolby-hidl mio-dolby-dms mio-dolby-codec; do
    echo "$name: $(getprop init.svc.$name)"
done
echo "解码服务 PID：$(pidof dolbycodecservice)"
echo 'HWS 状态及就绪标记：'
getprop init.svc.hwservicemanager
getprop hwservicemanager.ready
echo 'AIDL 接口：'
bounded service list | grep -E 'vendor.dolby.dms|IComponentStore/default9|audio.effect.IFactory' || true
echo 'HIDL 接口：'
bounded lshal | grep 'vendor.dolby.hardware.dms@2.0::IDms/default' || true
section '杜比 App：文件、注册、用户状态分开查'
bounded pm path "$APP"
bounded dumpsys package "$APP" | grep -E 'userId=|codePath=|resourcePath=|versionCode=|versionName=|pkgFlags=|privateFlags=|usesNonSdkApi=|installed=|hidden=|suspended=|enabled=|enabledComponents|disabledComponents'
echo '安装记录（data/app 更新不等于失去系统身份，看上面的 SYSTEM / PRIVILEGED 标记）：'
tail -12 "$R/app-install.log" 2>/dev/null
echo '持久化数据目录（系统特权 App 不应遗留普通 app_data_file 标签）：'
for dir in /data/user_de/0/org.lunaris.dolby /data/user/0/org.lunaris.dolby; do
    ls -ldZ "$dir" "$dir/shared_prefs" 2>/dev/null
done
active_apk=$(bounded pm path "$APP" | sed -n 's/^package://p' | head -n 1)
apk_source=$(awk -F '\t' '$2 ~ /\.apk$/ {print $1; exit}' "$MODDIR/mounts.tsv")
apk_target=$(awk -F '\t' '$2 ~ /\.apk$/ {print $2; exit}' "$MODDIR/mounts.tsv")
if [ -n "$apk_source" ] && [ -n "$apk_target" ]; then
    for path in "$MODDIR/$apk_source" "$apk_target" "/proc/1/root$apk_target"; do
        echo "文件：$path"
        if [ -f "$path" ]; then
            stat -c '字节数=%s 权限=%a UID=%u GID=%g' "$path"
            ls -lZ "$path"
            [ -s "$path" ] || echo '发现实际的空 APK！这和管理器显示 0 KB 不是一回事。'
        else
            echo '这里看不到 APK：可能未挂载、路径改变或权限阻止，不能当作已正常安装。'
        fi
    done
fi
pids=$(pidof "$APP" 2>/dev/null)
if [ -z "$pids" ]; then
    echo '杜比 App 当前没有主进程。本次无法检查它自己的挂载视图；可以尝试打开 App 后再点一次诊断。'
else
    for pid in $pids; do
        echo "App PID=$pid 命名空间=$(readlink /proc/$pid/ns/mnt)"
        if [ -n "$active_apk" ] && [ -f "/proc/$pid/root$active_apk" ]; then
            echo '从该进程根目录能看到 APK；这仍不代表其 SELinux 域有读取权限。'
        else
            echo 'App 视图中实际加载的 APK 缺失：请同时检查 app-install.log、卸载模块及 VFS UID 隔离。'
        fi
        grep -E 'KSU|overlay| /system_ext| /vendor|opex' "/proc/$pid/mountinfo" | head -n 30
    done
fi
section '应用卸载模块策略（能力不同，查询失败不改任何东西）'
bounded /data/adb/ksud profile get "$APP"
echo '如果管理器支持应用级“卸载模块”，仅为 org.lunaris.dolby 关闭它；无需给该 App Root。'
echo '还需查看 Zygisk / SUSFS / Hybrid VFS / NoMount 的应用排除；本诊断不会替你关闭全局隐藏。'
section '杜比文件在 init 视图里是否齐全'
tab=$(printf '\t')
good=0; bad=0
while IFS="$tab" read -r source target expected; do
    if [ -r "$MODDIR/$source" ] && cmp -s "$MODDIR/$source" "/proc/1/root$target"; then
        good=$((good+1))
    else
        bad=$((bad+1)); echo "缺失、不可读或内容不同：$target"
    fi
done < "$MODDIR/mounts.tsv"
echo "一致=$good；异常=$bad。内容一致不代表 SELinux、链接依赖和实际播放一定正常。"
section '最近相关错误（有限截取，不持续抓取）'
bounded logcat -b all -d -t 1600 | grep -E -i 'org.lunaris.dolby|dolbycodecservice|mio-dolby|vendor.dolby|Failed to open APK|ClassLoader.*unknown path|avc: denied.*(dolby|dms|swdap)' | tail -n 90
section '怎么看结果'
echo '1. 源 APK 都没有/为零：先重新生成和安装，不必先折腾音效参数。'
echo '2. 源文件正常、init 看不到：查元模块后补挂日志和元模块组合。'
echo '3. init 看得到、App 看不到：查应用级卸载模块或 VFS 隔离。'
echo '4. 文件都在但 App 未注册/崩溃：查包扫描、Android 版本要求、SELinux 和上面的错误。'
echo '5. App 能开但无法调参/播放：继续看 HIDL、AIDL、Codec2 和实际播放日志。'
echo '这不是播放测试，也不会自动判定音质、解码能力或所有机型兼容。'
