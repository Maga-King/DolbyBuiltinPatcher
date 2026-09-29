#!/system/bin/sh
# Add-on to the original metamodule pipeline, NOT an autonomous mounting mode.
M=${0%/*}
R="$M/.runtime"
BB=/data/adb/ksu/bin/busybox
S=/dev/mio-preserve-mio_dolby_c17_generated
mkdir -p "$R" || exit 1
if [ "${1:-}" != run ]; then
    "$BB" timeout -s TERM -k 2 20 /system/bin/sh "$M/repair-mounts.sh" run > "$R/repair.log" 2>&1
    exit $?
fi
mount() { "$BB" mount "$@"; }
umount() { "$BB" umount "$@"; }
. "$M/mount-engine.sh" || exit 1
W=/dev/mio-dolby-meta-repair4
DOLBY_SELINUX=1
work_id=
pending=
success=0
tab=$(printf '\t')
cleanup() {
    trap - EXIT TERM INT HUP
    if [ "$success" != 1 ]; then
        if [ -n "$work_id" ]; then
            [ -z "$pending" ] || record_publication "$pending"
            [ ! -f "$W/published" ] || rollback_publications
        fi
        rm -f "$R/repair-ok"
        [ -z "$work_id" ] || [ "$(mount_id "$W")" != "$work_id" ] || umount -l "$W"
        echo 'REPAIR_FAILED：不提交杜比音效；不会卸载元模块共享目录层。'
    fi
}
trap cleanup EXIT
trap 'exit 1' TERM INT HUP
fail() { echo "失败：$*"; exit 1; }
echo "REPAIR_BEGIN $(cat /proc/uptime)"
rm -f "$R/repair-ok"
[ ! -f "$M/disable" ] && [ ! -f "$M/remove" ] || fail '模块已禁用'
[ "$(readlink /proc/self/ns/mnt)" = "$(readlink /proc/1/ns/mnt)" ] || fail '非 init 挂载命名空间'
[ "$(getprop init.svc.vendor.audio-hal-aidl)" != running ] && [ "$(getprop init.svc.audioserver)" != running ] || fail '音频已启动，拒绝迟到接入'
cmp -s "$S/boot" /proc/sys/kernel/random/boot_id && [ -f "$S/restored" ] || fail '原版保存/恢复流程未完成'
[ -f "$R/meta-before-restore.mountinfo" ] || fail '缺少元模块挂载阶段记录'
# If no external mount appeared in our affected roots, do not silently replace
# a missing metamodule with a full self-mount implementation.
awk 'FILENAME==ARGV[1] {old[$1]=1; next}
     FILENAME==ARGV[2] {roots[$0]=1; next}
     !old[$1] {for(p in roots) if($5==p || index($5,p"/")==1) found=1}
     END {exit !found}' "$S/before" "$M/mount-roots.txt" "$R/meta-before-restore.mountinfo" || fail '未发现元模块在受影响目录内发布挂载，不进行整包自挂载'

# The only source is the original standard system/ payload. Some installers move
# partition branches to module root: resolve their alias without duplicating data.
: > "$R/repair-pending.tsv"
: > "$R/repair-sources.tsv"
matched=0
missing=0
while IFS="$tab" read -r source target expected; do
    case "$source" in system/*) ;; *) fail '非标准载荷路径';; esac
    safe_path "$target" && safe_path "$M/$source" || fail '非法载荷路径'
    file="$M/$source"
    if [ ! -f "$file" ]; then
        case "$source" in system/vendor/*|system/system_ext/*|system/product/*|system/odm/*) file="$M/${source#system/}";; esac
    fi
    file=$(readlink -f "$file") || fail "来源不可解析：$source"
    module_real=$(readlink -f "$M")
    case "$file" in "$module_real"/*) ;; *) fail '来源逃逸模块目录';; esac
    [ -f "$file" ] && [ ! -L "$file" ] || fail "来源缺失：$source"
    attrs=$(awk -F '\t' -v p="$source" '$1==p {print $2" "$3; n++} END {if(n!=1) exit 1}' "$M/labels.tsv") || fail "来源标签不唯一：$source"
    mode=${attrs%% *}; label=${attrs#* }
    chmod "$mode" "$file" && chcon "$label" "$file" || fail "来源权限恢复失败：$source"
    printf '%s\t%s\n' "$file" "$target" >> "$R/repair-sources.tsv"
    if payload_matches "$file" "$target" && cmp -s "$file" "/proc/1/root$target"; then
        matched=$((matched+1))
    else
        missing=$((missing+1))
        printf '%s\t%s\n' "$file" "$target" >> "$R/repair-pending.tsv"
    fi
done < "$M/mounts.tsv"
echo "META_CHECK matched=$matched repair=$missing"
[ "$matched" -gt 0 ] || fail '元模块未提供任何正确载荷，不自动切换为整包自挂载'
if [ "$missing" -gt 0 ]; then
    [ ! -e "$W" ] || fail '补挂暂存目录已存在'
    mkdir "$W" && mount -t tmpfs -o mode=0700,nodev KSU "$W" || fail '无法创建补挂区'
    work_id=$(mount_id "$W")
    [ -n "$work_id" ] && mount --make-rprivate "$W" || fail '无法隔离补挂区'
    : > "$W/published"
    : > "$W/targets"
    mkdir "$W/payload" "$W/tree" || fail '无法建立补挂计划'
    while IFS="$tab" read -r file target; do
        mkdir -p "$W/payload${target%/*}" || fail '补挂路径准备失败'
        stage_payload "$file" "$W/payload$target" || fail "补挂来源准备失败：$target"
    done < "$R/repair-pending.tsv"
    while read -r root; do
        [ -d "$W/payload$root" ] || continue
        [ "$(readlink -f "$root")" = "$root" ] || fail "补挂根目录是别名，需另行适配：$root"
        plan_tree "$root" "$W/payload$root" || fail "补挂规划失败：$root"
    done < "$M/mount-roots.txt"
    cp "$W/targets" "$R/repair-plan.tsv"
    count=0
    : > "$W/plan"
    while IFS="$tab" read -r kind target payload; do
        count=$((count+1))
        case "$kind" in
            F) stage_payload "$payload" "$W/tree/$count" || fail '单文件准备失败';;
            D) merge_tree "$target" "$payload" "$W/tree/$count" "$target" || fail '缺失路径的最小目录准备失败';;
            *) fail '未知补挂类型';;
        esac
        printf '%s\t%s\t%s\n' "$kind" "$target" "$W/tree/$count" >> "$W/plan"
    done < "$W/targets"
    while IFS="$tab" read -r kind target payload; do
        cp /proc/self/mountinfo "$W/before" || fail '无法记录补挂前状态'
        pending="$target"
        case "$kind" in
            F) mount -o bind "$payload" "$target" || fail '单文件发布失败';;
            D) mount --rbind "$payload" "$target" || fail '目录补挂失败';;
        esac
        record_publication "$target"
        pending=
        mount -o remount,bind,ro "$payload" "$target" || fail '补挂只读处理失败'
    done < "$W/plan"
    cp "$W/published" "$R/repair-owned-mounts.tsv"
fi
while IFS="$tab" read -r file target; do
    payload_matches "$file" "$target" && cmp -s "$file" "/proc/1/root$target" || fail "最终文件不符：$target"
done < "$R/repair-sources.tsv"
# Check the original child mounts AFTER repair too; no VINTF-only success.
while IFS="$tab" read -r saved target; do
    first=$(stat -c '%d:%i' "$saved") && second=$(stat -c '%d:%i' "$target") || fail "子挂载无法检查：$target"
    [ "$first" = "$second" ] || fail "原系统子挂载被改变：$target"
done < "$S/journal"
cat /proc/sys/kernel/random/boot_id > "$R/repair-ok" || fail '无法记录成功'
success=1
echo "REPAIR_OK matched=$matched repaired=$missing（补挂不是实际解码验证）"
