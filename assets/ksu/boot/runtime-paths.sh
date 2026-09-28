#!/system/bin/sh
dolby_preinit_base() {
    if [ -d /metadata/watchdog ]; then echo /metadata/watchdog/ksu; else echo /metadata/ksu; fi
}
dolby_early_path() {
    local p
    p=$(cat "$M/preinit-path" 2>/dev/null)
    case "$p" in /metadata/watchdog/ksu/mio_dolby_c17_generated|/metadata/ksu/mio_dolby_c17_generated) echo "$p";;
        *) echo "$(dolby_preinit_base)/mio_dolby_c17_generated";; esac
}
