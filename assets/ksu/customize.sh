#!/system/bin/sh
[ "${KSU:-false}" = true ] || abort 'This generated module requires KernelSU and a mounting metamodule.'
[ "$ARCH" = arm64 ] || abort 'ARM64 only.'
[ "$API" = 37 ] || abort 'This release targets Android 17 / SDK 37.'
tab=$(printf '\t')
while IFS="$tab" read -r key expected; do
    [ "$(getprop "$key")" = "$expected" ] || abort "Target ROM differs: $key. Regenerate for this system."
done < "$MODPATH/target.tsv"
[ ! -f /system/etc/init/00-dolby-native.rc ] || abort 'Native Dolby is already installed. Do not stack this module.'
for prop in /data/adb/modules/*/module.prop; do
    [ -f "$prop" ] || continue
    other=${prop%/*}
    [ "${other##*/}" = mio_dolby_c17_generated ] && continue
    [ -f "$other/disable" ] && continue
    [ -f "$other/remove" ] && continue
    # A metamodule's description lists its mounted modules; that is not an
    # installed Dolby implementation. Only module identity is a name match.
    if grep -qiE '^(id|name)=.*dolby' "$prop"; then
        abort "Another active Dolby module exists: ${other##*/}. Disable it yourself first."
    fi
done
set_perm_recursive "$MODPATH" 0 0 0755 0644
while IFS="$tab" read -r relative mode label; do
    set_perm "$MODPATH/$relative" 0 0 "$mode" "$label"
done < "$MODPATH/labels.tsv"
set_perm_recursive "$MODPATH/system/vendor" 0 0 0755 0644 u:object_r:vendor_file:s0
set_perm_recursive "$MODPATH/system/system_ext/lib64" 0 0 0755 0644 u:object_r:system_lib_file:s0
# Reapply exact executable/config labels after the directory defaults.
while IFS="$tab" read -r relative mode label; do
    set_perm "$MODPATH/$relative" 0 0 "$mode" "$label"
done < "$MODPATH/labels.tsv"
ui_print 'Target-specific KSU module. Mounting metamodule is required.'
ui_print 'No early audio/HWS restart. Bounded post-boot activation; inspect Action status.'
ui_print 'Runtime compatibility is not proven by successful ZIP generation.'
