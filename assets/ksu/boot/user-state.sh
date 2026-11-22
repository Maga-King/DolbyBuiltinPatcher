#!/system/bin/sh
# Use ActivityManager's AOSP shell command; some ColorOS cmd user builds omit unlock queries.
dolby_user_unlock_state() {
    local state bb
    bb=${BB:-/data/adb/ksu/bin/busybox}
    state=$("$bb" timeout -s TERM -k 1 3 cmd activity get-started-user-state 0 2>/dev/null)
    case "$state" in
        RUNNING_UNLOCKED|*'RUNNING_UNLOCKED'*) printf 'true\n'; return;;
        RUNNING_LOCKED|RUNNING_UNLOCKING|BOOTING|STOPPING|SHUTDOWN) printf 'false\n'; return;;
    esac
    state=$("$bb" timeout -s TERM -k 1 3 cmd user is-user-unlocked 0 2>/dev/null)
    case "$state" in true|false) printf '%s\n' "$state";; *) printf 'unknown\n';; esac
}
