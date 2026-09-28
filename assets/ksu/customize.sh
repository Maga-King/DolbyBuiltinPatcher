#!/system/bin/sh
tab=$(printf '\t')
# No device/SDK/architecture/fingerprint/conflict-list installation restrictions.
# Required operations below may still fail; removing restrictions is not portability.
set_perm_recursive "$MODPATH" 0 0 0755 0644
while IFS="$tab" read -r relative mode label; do
    set_perm "$MODPATH/$relative" 0 0 "$mode" "$label"
done < "$MODPATH/labels.tsv"
set_perm_recursive "$MODPATH/files/vendor" 0 0 0755 0644 u:object_r:vendor_file:s0
set_perm_recursive "$MODPATH/files/system_ext/lib64" 0 0 0755 0644 u:object_r:system_lib_file:s0
# Reapply exact executable/config labels after the directory defaults.
while IFS="$tab" read -r relative mode label; do
    set_perm "$MODPATH/$relative" 0 0 "$mode" "$label"
done < "$MODPATH/labels.tsv"
# RUNTIME_INSTALL
ui_print '杜比全景+解码器：安装提示'
ui_print '切换元模块后，请卸载本模块 → 重启 → 重新安装。'
ui_print '成功刷入不代表所有机型兼容，请保留救砖和禁用模块的方法。'
