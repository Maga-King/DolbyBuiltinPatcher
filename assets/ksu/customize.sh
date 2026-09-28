#!/system/bin/sh
tab=$(printf '\t')
# No device/SDK/architecture/fingerprint/conflict-list installation restrictions.
# Required operations below may still fail; removing restrictions is not portability.
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
