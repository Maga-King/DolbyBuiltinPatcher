# LunarisDolby 上游 SELinux 规则快照

仓库：https://github.com/Pong-Development/hardware_dolby
分支：16
提交：6300a4e30757d5810d62b2df0cff973ec438a70f
读取日期：2026-09-27
目录：sepolicy/vendor

本目录的原始 attributes、TE 和 contexts 来自上述固定提交，保留用于核查。
expanded.cil 是本工具按 AOSP public/te_macros、public/global_macros 展开的有效授权。
宏依据：https://android.googlesource.com/platform/system/sepolicy/+/refs/heads/main/public/te_macros
权限集依据：https://android.googlesource.com/platform/system/sepolicy/+/refs/heads/main/public/global_macros

type 声明：目标 ROM 已有同名类型时复用，不能重复声明；本工具当前仍要求厂商提供 DMS 域。
hal_server_domain 的属性归属：expanded.cil 显式加入，重复归属不减权限。
init_daemon_domain 的允许、转换、dontaudit：已展开。
add_hwservice 的 neverallow 断言：不影响 -N 模式下的有效权限；原始宏与源文件有记录，不用断言删授权。
file_contexts 的老 Codec2 vendor 路径不套给当前 system_ext 可执行文件；使用本工具已有 mediacodec_exec 标签。
不是把小米专有音效库搬进 C17；这里只引入此仓库的 SELinux 集成规则。

## 2026-11-22 增量刷新

重新读取分支 16，当前提交 `b2963f7c2c7835389e7c16bdb0946ff9311d20e2`。
`latest/` 保留该提交 sepolicy/vendor 的全部原始文件。
当前上游 hal_dms_default.te 明确新增 set_prop(hal_dms_default, vendor_audio_prop)，
用于 libdlbdsservice 在切预设时写 persist.vendor.audio.scenario。
expanded.cil 保留旧提交的全部有效授权，再增量加入该 set_prop 的 property_service set，
并为本工具的 AIDL DMS 补完整 property socket/connectto/read/set。
上游新的 vendor_dolby_data_file 声明与 contexts 保留在 latest 原文，运行时不强加新类型：
policy_sources 按目标实际 Dolby 数据标签为两个 DMS 域追加存取授权，保留已有标签。
不删除旧平台客户端/Binder/存储授权，不把新上游客户端布局整套覆盖当前桥接配置。
