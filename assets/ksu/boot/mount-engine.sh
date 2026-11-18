#!/system/bin/sh
# Dolby-only merge engine. No foreign module discovery, VFS controls or service control.
# Sourced by repair-mounts.sh; also exercised in an isolated Linux mount namespace.
visible_mount_id() (
    # An open fd identifies the mount selected by path lookup, even with stacked mounts.
    # A subshell contains both the descriptor and any redirection failure.
    exec 9< "$1" || exit 1
    awk '$1=="mnt_id:" && $2~/^[0-9]+$/ {print $2; found=1} END {exit !found}' /proc/self/fdinfo/9
) 2>/dev/null
mount_id() {
    local id
    id=$(visible_mount_id "$1") || return 0
    awk -v id="$id" -v path="$1" '$1==id && $5==path {print $1}' /proc/self/mountinfo
}
object_id() { stat -c '%d:%i' "$1"; }
mount_is_readonly() {
    awk -v id="$1" '$1==id && $6~/(^|,)ro(,|$)/ {ok=1} END {exit !ok}' /proc/self/mountinfo
}
capture_submounts() {
    local root="$1" output="$2" path id identity attrs
    awk -v prefix="$root/" 'index($5,prefix)==1 {print $5}' /proc/self/mountinfo | sort -u > "$output.paths" || return 1
    : > "$output" || return 1
    while IFS= read -r path; do
        safe_path "$path" || return 1
        id=$(mount_id "$path") || return 1
        [ -n "$id" ] || continue
        identity=$(object_id "$path") || return 1
        attrs=$(awk -v id="$id" '$1==id {print $3":"$4" "$6}' /proc/self/mountinfo) || return 1
        [ -n "$attrs" ] || return 1
        printf '%s\t%s\t%s\n' "$path" "$identity" "$attrs" >> "$output" || return 1
    done < "$output.paths"
}
verify_submounts() {
    local tab path identity attrs id current
    tab=$(printf '\t')
    while IFS="$tab" read -r path identity attrs; do
        id=$(mount_id "$path") && [ -n "$id" ] && [ "$(object_id "$path")" = "$identity" ] || {
            engine_fail "原有子挂载未保留：$path"; return 1;
        }
        current=$(awk -v id="$id" '$1==id {print $3":"$4" "$6}' /proc/self/mountinfo)
        [ "$current" = "$attrs" ] || { engine_fail "原有子挂载来源或属性变化：$path"; return 1; }
    done < "$1"
}
safe_path() {
    # These are quoted filesystem names, NOT shell programs. '[' is a legitimate
    # Android toybox symlink. Reject only forms this mountinfo journal cannot encode.
    case "$1" in /*) ;; *) return 1;; esac
    case "$1" in *[[:space:]]*|*\\*|*/../*|*/./*|*/..|*/.) return 1;; esac
    return 0
}
engine_fail() { echo "合并细节：$*" >&2; return 1; }
payload_matches() {
    local src="$1" dst="$2" source_context target_context
    [ -f "$src" ] && [ ! -L "$src" ] && [ -f "$dst" ] && [ ! -L "$dst" ] || return 1
    cmp -s "$src" "$dst" || return 1
    [ "$(stat -c %u:%g:%a "$src")" = "$(stat -c %u:%g:%a "$dst")" ] || return 1
    if [ "$DOLBY_SELINUX" = 1 ]; then
        source_context=$(ls -Zd "$src" | awk '{print $1}')
        target_context=$(ls -Zd "$dst" | awk '{print $1}')
        case "$source_context" in u:object_r:*:s0*) ;; *) return 1;; esac
        [ "$source_context" = "$target_context" ] || return 1
    fi
}
plan_target() {
    local kind="$1" target="$2" payload="$3"
    safe_path "$target" && safe_path "$payload" || return 1
    # Plans must be disjoint. Never hide an earlier publication under a later
    # ancestor, including different logical roots resolving to the same place.
    if awk -v p="$target" '$2==p || index($2,p"/")==1 || index(p,$2"/")==1 {found=1} END {exit !found}' "$W/targets"; then
        engine_fail "计划目标重复或重叠：$target"; return 1
    fi
    printf '%s\t%s\t%s\n' "$kind" "$target" "$payload" >> "$W/targets"
}
plan_tree() {
    local original="$1" payload="$2" entry base missing=0
    safe_path "$original" && safe_path "$payload" || return 1
    [ ! -L "$original" ] && [ ! -L "$payload" ] || {
        engine_fail "修改分支碰到链接：$original"; return 1;
    }
    if [ -f "$payload" ]; then
        [ -f "$original" ] || { engine_fail "单文件目标缺失或类型不匹配：$original"; return 1; }
        if payload_matches "$payload" "$original"; then
            echo "已就位，不重复挂载：$original"
            return 0
        fi
        plan_target F "$original" "$payload"
        return $?
    fi
    [ -d "$payload" ] && [ -d "$original" ] || {
        engine_fail "规划起点不是已有目录：$original"; return 1;
    }
    # Descend through existing directories. Only a missing immediate child
    # forces merging this directory; siblings above it are never visited.
    for entry in "$payload"/* "$payload"/.[!.]* "$payload"/..?*; do
        [ -e "$entry" ] || [ -L "$entry" ] || continue
        safe_path "$entry" || return 1
        base=${entry##*/}
        [ ! -L "$entry" ] && [ ! -L "$original/$base" ] || {
            engine_fail "杜比资产与已有链接冲突：$original/$base"; return 1;
        }
        [ -e "$original/$base" ] || missing=1
    done
    if [ "$missing" = 1 ]; then
        plan_target D "$original" "$payload"
        return $?
    fi
    for entry in "$payload"/* "$payload"/.[!.]* "$payload"/..?*; do
        [ -e "$entry" ] || [ -L "$entry" ] || continue
        plan_tree "$original/${entry##*/}" "$entry" || return 1
    done
}
dir_attrs() {
    local ref="$1" dest="$2" context
    chmod "$(stat -c %a "$ref")" "$dest" && chown "$(stat -c %u:%g "$ref")" "$dest" || return 1
    if [ "$DOLBY_SELINUX" = 1 ]; then
        context=$(ls -Zd "$ref" | awk '{print $1}')
        case "$context" in u:object_r:*:s0*) chcon "$context" "$dest";; *) return 1;; esac
    fi
}
clone_entry() {
    local src="$1" dst="$2"
    safe_path "$src" && safe_path "$dst" || { engine_fail "路径无法安全记录：$src -> $dst"; return 1; }
    if [ -L "$src" ]; then
        cp -a "$src" "$dst" || { engine_fail "复制链接失败：$src"; return 1; }
    elif [ -d "$src" ]; then
        mkdir "$dst" && mount --rbind "$src" "$dst" && mount --make-rprivate "$dst" || { engine_fail "保留目录挂载失败：$src"; return 1; }
    elif [ -f "$src" ]; then
        : > "$dst" && mount -o bind "$src" "$dst" || { engine_fail "保留文件失败：$src"; return 1; }
    else
        echo "不支持合并的文件类型：$src"; return 1
    fi
}
stage_payload() {
    local src="$1" dst="$2" owned context bytes available
    # Only a newly-created leaf in our PRIVATE staging tree may use this fallback.
    # Never copy through a live bind, and never fall back after publication.
    [ ! -e "$dst" ] && [ ! -L "$dst" ] || return 1
    : > "$dst" || return 1
    if mount -o bind "$src" "$dst"; then
        owned=$(mount_id "$dst")
        [ -n "$owned" ] || return 1
        if mount -o remount,bind,ro "$src" "$dst"; then return 0; fi
        [ "$(mount_id "$dst")" = "$owned" ] && umount "$dst" || return 1
    fi
    [ -z "$(mount_id "$dst")" ] || return 1
    # tmpfs copying is bounded: no more than 128 MiB, with 256 MiB RAM headroom.
    bytes=$(stat -c %s "$src") || return 1
    available=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
    case "$bytes:$available" in *[!0-9:]*|:*|*:) return 1;; esac
    copied_bytes=$((${copied_bytes:-0}+bytes))
    [ "$copied_bytes" -le 134217728 ] && [ "$available" -gt $((bytes/1024+262144)) ] || {
        engine_fail "复制兜底预算不足，停止接入：$src"; return 1;
    }
    cp -p "$src" "$dst" && chown "$(stat -c %u:%g "$src")" "$dst" || return 1
    if [ "$DOLBY_SELINUX" = 1 ]; then
        context=$(ls -Zd "$src" | awk '{print $1}')
        case "$context" in u:object_r:*:s0*) chcon "$context" "$dst" || return 1;; *) return 1;; esac
    fi
    cmp -s "$src" "$dst" || return 1
    echo "已用复制兜底（发布时只读）：$src"
}
merge_tree() {
    local original="$1" payload="$2" dest="$3" ref="$4" entry base
    [ ! -L "$original" ] && [ ! -L "$payload" ] || { engine_fail "修改分支碰到目录链接：$original"; return 1; }
    [ ! -e "$original" ] || [ -d "$original" ] || return 1
    mkdir -p "$dest" || return 1
    [ ! -d "$original" ] || ref="$original"
    dir_attrs "$ref" "$dest" || { engine_fail "继承目录权限/标签失败：$ref -> $dest"; return 1; }
    # Unchanged branches use recursive binds: existing OPEX / other module mounts survive.
    for entry in "$original"/* "$original"/.[!.]* "$original"/..?*; do
        [ -e "$entry" ] || [ -L "$entry" ] || continue
        base=${entry##*/}
        [ -e "$payload/$base" ] || [ -L "$payload/$base" ] || clone_entry "$entry" "$dest/$base" || return 1
    done
    for entry in "$payload"/* "$payload"/.[!.]* "$payload"/..?*; do
        [ -e "$entry" ] || [ -L "$entry" ] || continue
        safe_path "$entry" || { engine_fail "无法记录的资产路径：$entry"; return 1; }
        base=${entry##*/}
        [ ! -L "$entry" ] && [ ! -L "$original/$base" ] || { engine_fail "杜比资产与已有链接冲突：$original/$base"; return 1; }
        if [ -d "$entry" ]; then
            merge_tree "$original/$base" "$entry" "$dest/$base" "$ref" || return 1
        elif [ -f "$entry" ]; then
            [ ! -e "$original/$base" ] || [ -f "$original/$base" ] || return 1
            stage_payload "$entry" "$dest/$base" || { engine_fail "绑定及复制兜底失败：$entry"; return 1; }
        else
            return 1
        fi
    done
}
record_publication() {
    local target="$1" staged="$2" root_id current path source_id
    root_id=$(mount_id "$target")
    [ -n "$root_id" ] && [ "$(object_id "$target")" = "$(object_id "$staged")" ] || return 1
    if awk -v id="$root_id" '$1==id {found=1} END {exit !found}' "$W/before"; then return 1; fi
    printf '%s\t%s\n' "$root_id" "$target" >> "$W/published" || return 1
    awk -v id="$root_id" 'FILENAME==ARGV[1] {old[$1]=1; next}
        {parent[$1]=$2; path[$1]=$5}
        END {for (i in path) if (i!=id && !old[i]) {
            p=i; while (p in parent && p!=id && p!=parent[p]) p=parent[p]
            if (p==id) print i "\t" path[i]
        }}' "$W/before" /proc/self/mountinfo > "$W/candidates" || return 1
    while IFS="$(printf '\t')" read -r current path; do
        case "$path" in "$target"/*) ;; *) continue;; esac
        [ "$(mount_id "$path")" = "$current" ] || continue
        source_id=$(mount_id "$staged${path#"$target"}")
        [ -n "$source_id" ] || continue
        [ "$(object_id "$path")" = "$(object_id "$staged${path#"$target"}")" ] || continue
        printf '%s\t%s\n' "$current" "$path" >> "$W/published" || return 1
    done < "$W/candidates"
}
rollback_publications() {
    local id target current
    # Higher IDs are not assumed to mean deeper mounts. Sort by path depth, then ID.
    awk '!seen[$1]++ {n=split($2,a,"/"); print n"\t"$0}' "$W/published" | sort -k1,1nr -k2,2nr > "$W/undo"
    while read -r depth id target; do
        current=$(mount_id "$target")
        if [ "$current" = "$id" ]; then
            umount "$target" || engine_fail "卸载失败 $target"
        fi
    done < "$W/undo"
}
