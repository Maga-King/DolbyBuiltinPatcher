#!/system/bin/sh
# Sourced by customize.sh, with installer helpers available.
/data/adb/ksud initrc --help >/dev/null 2>&1 || abort '当前 KernelSU 不支持 initrc 注入，无法保证杜比在音频服务前准备完成。'
[ -x /data/adb/ksu/bin/busybox ] || abort '没有找到 KernelSU 的 busybox，无法执行挂载工具。'
M="$MODPATH"
rm -f "$M/skip_mount" "$M/skip_mountify"
. "$MODPATH/runtime-paths.sh" || abort '缺少运行路径脚本，请重新下载模块。'
P="$(dolby_preinit_base)/mio_dolby_c17_generated"
[ -d /metadata ] || abort '没有可用的 metadata 分区；不会改用碰运气的延迟启动。'
[ ! -L "$P" ] || abort '早期文件目录是符号链接，已停止以免写错位置。'
mkdir -p "$P" || abort '无法创建早期启动文件目录。'
cp -a "$MODPATH/early/." "$P/" || abort '复制早期启动文件失败。'
cp "$MODPATH/target.tsv" "$P/target.tsv" || abort '复制模块信息失败。'
printf '%s\n' "$P" > "$MODPATH/preinit-path"
sed -i "s|/metadata/watchdog/ksu/mio_dolby_c17_generated|$P|g" "$MODPATH/initrc/dolby.rc" || abort '调整 initrc 路径失败。'
set_perm_recursive "$P" 0 0 0755 0644 u:object_r:metadata_file:s0
while IFS="$tab" read -r source target expected label; do
    set_perm "$P/$source" 0 0 0644 "$label"
done < "$P/vintf.tsv"
mkdir -p "$MODPATH/.runtime" || abort '无法创建模块运行目录。'
if ! /system/bin/sh "$MODPATH/install-app.sh"; then
    ui_print '杜比 App 安装失败，详见 .runtime/app-install.log。'
fi
if ! /system/bin/sh "$MODPATH/freeze-audioeffectcenter.sh" >"$MODPATH/.runtime/audioeffectcenter-install.log" 2>&1; then
    ui_print 'OPLUS 音效中心停用失败。'
fi
