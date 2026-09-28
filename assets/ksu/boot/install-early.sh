#!/system/bin/sh
# Sourced by customize.sh, with installer helpers available.
/data/adb/ksud initrc --help >/dev/null 2>&1 || abort '当前 KernelSU 不支持 initrc 注入，无法保证杜比在音频服务前准备完成。'
[ -x /data/adb/ksu/bin/busybox ] || abort '没有找到 KernelSU 的 busybox，无法执行挂载工具。'
M="$MODPATH"
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
ui_print '杜比全景+解码器：自挂载测试版'
ui_print '杜比文件由本模块挂载，不占用元模块名额；不强杀 HWS，不重启音频服务。'
ui_print '切换元模块后，请卸载本模块 → 重启 → 重新安装。'
ui_print 'skip_mount 是有意保留的：防止其他挂载器重复处理，并非安装失败。'
ui_print '重启后可点 Action 运行一次中文诊断；不会启动常驻检测。'
ui_print '正在安装杜比 App 更新：不清数据、不降级、不修改隐藏设置。'
if /system/bin/sh "$MODPATH/install-app.sh"; then
    ui_print '杜比 App 已安装；系统底包仍保留在模块中。'
else
    ui_print 'App 暂未安装成功；开机完成后仅补试一次，详见 .runtime/app-install.log。'
fi
ui_print '无需给杜比 App 授予 Root；不要为了修它关闭全局安全或隐藏设置。'
ui_print '本包不按设备指纹或 SDK 拒装，但刷入成功不等于机型兼容。'
