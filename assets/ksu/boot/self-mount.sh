#!/system/bin/sh
M=${0%/*}
R="$M/.runtime"
BB=/data/adb/ksu/bin/busybox
mkdir -p "$R" || exit 1
if [ "${1:-}" != run ]; then
    "$BB" timeout -s TERM -k 3 25 /system/bin/sh "$M/self-mount.sh" run > "$R/self-mount.log" 2>&1
    rc=$?
    [ "$rc" = 0 ] || echo "自挂载失败或超时（$rc），本次不接入杜比音频。详见 self-mount.log。" >> "$R/self-mount.log"
    exit "$rc"
fi
# Android toybox mount does not consistently accept util-linux --make-* options.
# Use KSU's bundled applets explicitly, independent of PATH or ASH_STANDALONE.
mount() { "$BB" mount "$@"; }
umount() { "$BB" umount "$@"; }
. "$M/mount-engine.sh" || exit 1
W=/dev/mio-dolby-selfmount
DOLBY_SELINUX=1
success=0
pending=
cleanup() {
    trap - EXIT TERM INT HUP
    if [ "$success" != 1 ]; then
        if [ -n "$work_id" ]; then
            [ -z "$pending" ] || record_publication "$pending"
            [ ! -f "$W/published" ] || rollback_publications
        fi
        rm -f "$R/mounted-boot"
        echo '自挂载没有完成。未提交新的音频配置，不会强杀系统服务。'
        # Only detach the private scratch mount we created. Never recursively delete it.
        [ -z "$work_id" ] || [ "$(mount_id "$W")" != "$work_id" ] || umount -l "$W"
    fi
}
trap cleanup EXIT
trap 'exit 1' TERM INT HUP
fail() { echo "失败：$*"; exit 1; }
[ ! -f "$M/disable" ] && [ ! -f "$M/remove" ] || fail '模块已禁用或待卸载'
[ "$(readlink /proc/self/ns/mnt)" = "$(readlink /proc/1/ns/mnt)" ] || fail '不是 init 的挂载命名空间；不做局部假挂载'
[ "$(getprop init.svc.vendor.audio-hal-aidl)" != running ] && [ "$(getprop init.svc.audioserver)" != running ] || fail '音频服务已启动，拒绝迟到接入'
if cmp -s "$R/mounted-boot" /proc/sys/kernel/random/boot_id; then
    success=1; echo '本次开机已经自挂载，不叠加第二层。'; exit 0
fi
[ ! -e "$W" ] || fail '临时目录已存在；不接管未知或未完成的旧挂载'
mkdir "$W" || fail '无法创建临时目录'
mount -t tmpfs -o mode=0700,nodev KSU "$W" || fail '无法建立私有挂载区'
work_id=$(mount_id "$W")
[ -n "$work_id" ] || fail '无法读取自己的挂载 ID；挂载隐藏环境下不能安全管理归属'
mount --make-rprivate "$W" || fail '无法隔离临时挂载的传播'
awk -v p="$W" '$5==p {for(i=7;i<=NF && $i!="-";i++) if($i~/^(shared|master):/) exit 1}' /proc/self/mountinfo || fail '临时挂载仍有传播关系'
: > "$W/published"
tab=$(printf '\t')
# Reapply exact payload contexts after the manager's restorecon phase.
while IFS="$tab" read -r relative mode label; do
    case "$relative" in files/*)
        [ -f "$M/$relative" ] && [ ! -L "$M/$relative" ] || fail "文件缺失：$relative"
        chmod "$mode" "$M/$relative" && chcon "$label" "$M/$relative" || fail "权限或标签设置失败：$relative"
    esac
done < "$M/labels.tsv"
n=0
# Build all trees before publishing any of them.
while read -r root; do
    safe_path "$root" || fail "非法目录：$root"
    case "$root" in /system/*|/system_ext/*|/vendor/*|/product/*|/odm/*) ;; *) fail "越界目录：$root";; esac
    real=$(readlink -f "$root")
    safe_path "$real" && [ -d "$real" ] || fail "目标目录不存在：$root"
    case "$real" in /system/*|/system_ext/*|/vendor/*|/product/*|/odm/*) ;; *) fail "解析后的目录越界：$real";; esac
    [ ! -f "$W/plan" ] || ! awk -v p="$real" '$2==p {found=1} END {exit !found}' "$W/plan" || fail "重复的目录别名：$root"
    n=$((n+1))
    echo "准备目录：$root"
    merge_tree "$real" "$M/files$root" "$W/tree/$n" "$real" || fail "合并失败：$root"
    printf '%s\t%s\n' "$n" "$real" >> "$W/plan"
done < "$M/mount-roots.txt"
cp "$W/plan" "$R/mount-plan"
while IFS="$tab" read -r n real; do
    cp /proc/self/mountinfo "$W/before"
    pending="$real"
    mount --rbind "$W/tree/$n" "$real" || fail "发布失败：$real"
    record_publication "$real"
    pending=
    mount -o remount,bind,ro "$W/tree/$n" "$real" || fail "无法将目录层设为只读：$real"
done < "$W/plan"
while IFS="$tab" read -r source target expected; do
    cmp -s "$M/$source" "$target" && cmp -s "$M/$source" "/proc/1/root$target" || fail "挂载后不可见：$target"
done < "$M/mounts.tsv"
cp "$W/published" "$R/published-mounts"
cat /proc/sys/kernel/random/boot_id > "$R/mounted-boot"
success=1
echo '自挂载完成：杜比文件在 init 命名空间可见，原有子挂载保留；接下来由启动门控检查服务。'
