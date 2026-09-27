#!/system/bin/sh
# One-shot transaction. No boot service and no persistent polling process.
set -eu
job=$1
root=$(cat "$job/root.txt")
operation=$(cat "$job/operation.txt")
tab=$(printf '\t')
finished=0
locked=0
phase=initialization
relative='(none)'

hash_file() {
    if [ -L "$1" ]; then return 1; fi
    if [ -f "$1" ]; then
        value=$(sha256sum "$1") || return 1
        printf '%s\n' "${value%% *}"
    elif [ -e "$1" ]; then
        return 1
    else
        printf '%s\n' '-'
    fi
}

check_path() (
    # Run in a subshell: validation must not overwrite the caller's journal path.
    relative=$1
    case "$relative" in ''|/*|..|../*|*/../*|*/..|*\\*|*:*|.|./*|*/./*|*/.) return 1;; esac
    [ "$(readlink -f "$root")" = "$root" ] || return 1
    current=$root
    remainder=$relative
    while :; do
        component=${remainder%%/*}
        [ -n "$component" ] || return 1
        current=$current/$component
        [ ! -L "$current" ] || return 1
        case "$remainder" in */*) remainder=${remainder#*/};; *) break;; esac
    done
)

rollback() {
    [ -f "$job/intents.tsv" ] || return 0
    # The intent is journalled before rename, so an interrupted rename is recoverable.
    tac "$job/intents.tsv" | while IFS="$tab" read -r relative before after mode; do
        check_path "$relative" || exit 1
        target=$root/$relative
        temporary=$target.dolby-tmp-$(basename "$job")
        if [ -e "$temporary" ] || [ -L "$temporary" ]; then
            temporary_hash=$(hash_file "$temporary") || exit 1
            [ "$temporary_hash" = "$after" ] || [ "$temporary_hash" = "$before" ] || exit 1
            rm -f "$temporary" || exit 1
        fi
        actual=$(hash_file "$target") || exit 1
        if [ "$actual" = "$before" ]; then continue; fi
        [ "$actual" = "$after" ] || { echo "Rollback refuses concurrent edit: $relative"; exit 1; }
        if [ "$before" = '-' ]; then
            rm -f "$target" || exit 1
        else
            backup=$job/original_files/$relative
            [ "$(hash_file "$backup")" = "$before" ] || exit 1
            temp=$target.dolby-restore-$(basename "$job")
            [ ! -e "$temp" ] && [ ! -L "$temp" ] || exit 1
            cp -p "$backup" "$temp" && mv -f "$temp" "$target" || exit 1
        fi
        [ "$(hash_file "$target")" = "$before" ] || exit 1
    done
}

on_exit() {
    code=$?
    trap - EXIT HUP INT TERM
    if [ "$finished" = 1 ]; then exit "$code"; fi
    set +e
    echo "Transaction failed: phase=$phase path=$relative exit=$code"
    if [ "$locked" = 1 ]; then
        if [ ! -s "$job/intents.tsv" ]; then
            echo 'Preflight failed; no ROM file writes were attempted.'
            echo failed-preflight > "$job/status"
        elif rollback; then
            echo 'Attempted ROM file writes rolled back.'
            echo rolled-back > "$job/status"
        else
            echo 'Rollback incomplete; preserve backups and inspect the journal.'
            echo recovery-required > "$job/status"
        fi
        rmdir "$root/.dolby-patcher-lock" 2>/dev/null
    else
        echo failed-preflight > "$job/status"
    fi
    exit 1
}
trap on_exit EXIT
trap 'exit 1' HUP INT TERM

case "$root" in /data/*/*|/sdcard/*|/storage/*/*/*|/mnt/*/*/*) ;; *) echo 'Unsafe ROM root'; exit 1;; esac
[ -d "$root/config" ] && [ ! -L "$root/config" ] || exit 1
mkdir "$root/.dolby-patcher-lock" || { echo 'Another transaction or stale lock exists'; exit 1; }
locked=1
mkdir "$job/lock-owned"
echo preflight > "$job/status"
mkdir -p "$job/original_files"
# Guard untouched compilation inputs too, not just the files being replaced.
# Otherwise concurrent changes to platform CIL could invalidate the compiled cache.
if [ -f "$job/guards.tsv" ]; then
    phase=input-guards
    while IFS="$tab" read -r relative kind expected; do
        [ -n "$relative" ] || continue
        if [ "$kind" = L ]; then
            check_path "$(dirname "$relative")" || { echo "Unsafe link parent: $relative"; exit 1; }
            [ -L "$root/$relative" ] && [ "$(readlink "$root/$relative")" = "$expected" ] || { echo "Build input symlink changed: $relative"; exit 1; }
        else
            check_path "$relative" || { echo "Unsafe input path: $relative"; exit 1; }
            [ "$(hash_file "$root/$relative")" = "$expected" ] || { echo "Build input changed: $relative"; exit 1; }
        fi
    done < "$job/guards.tsv"
fi
# Full preflight/backup before touching the first target.
phase=target-preflight-backup
while IFS="$tab" read -r relative before after mode; do
    check_path "$relative"
    target=$root/$relative
    [ "$(hash_file "$target")" = "$before" ] || { echo "Target changed: $relative"; exit 1; }
    if [ "$after" != '-' ]; then
        [ "$(hash_file "$job/patch_tree/$relative")" = "$after" ] || { echo "Payload corrupt: $relative"; exit 1; }
    fi
    if [ "$before" != '-' ]; then
        mkdir -p "$(dirname "$job/original_files/$relative")"
        cp -p "$target" "$job/original_files/$relative"
        [ "$(hash_file "$job/original_files/$relative")" = "$before" ]
    fi
done < "$job/manifest.tsv"
echo applying > "$job/status"
phase=apply
while IFS="$tab" read -r relative before after mode; do
    check_path "$relative"
    target=$root/$relative
    [ "$(hash_file "$target")" = "$before" ] || { echo "Concurrent change: $relative"; exit 1; }
    mkdir -p "$(dirname "$target")"
    check_path "$relative"
    printf '%s\t%s\t%s\t%s\n' "$relative" "$before" "$after" "$mode" >> "$job/intents.tsv"
    if [ "$after" = '-' ]; then
        rm -f "$target"
    else
        temp=$target.dolby-tmp-$(basename "$job")
        [ ! -e "$temp" ] && [ ! -L "$temp" ]
        if [ "$before" != '-' ]; then
            cp -p "$target" "$temp"
            cat "$job/patch_tree/$relative" > "$temp"
        else
            cp "$job/patch_tree/$relative" "$temp"
            chmod "$mode" "$temp"
        fi
        [ "$(hash_file "$temp")" = "$after" ]
        # Recheck after preparing the temp, before overwriting anything.
        [ "$(hash_file "$target")" = "$before" ]
        mv -f "$temp" "$target"
    fi
    [ "$(hash_file "$target")" = "$after" ]
    printf '%s\n' "$relative" >> "$job/completed.txt"
done < "$job/manifest.tsv"
phase=finalize
sync
rmdir "$root/.dolby-patcher-lock"
echo complete > "$job/status"
finished=1
exit 0
