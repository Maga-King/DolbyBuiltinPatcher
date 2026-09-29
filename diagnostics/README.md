# 一次性手机杜比诊断

运行生成的单文件 SH 需要 Root、Android 8 或更新版本，以及至少 512MB 空闲空间。
不依赖手机 Python、zip 命令或额外 APK。脚本内嵌的 DEX 只使用 Java ZIP API，通过系统 app_process 运行。

1. 先播放音乐，准备好杜比 App。
2. 使用 Root 终端运行 `sh /sdcard/杜比诊断.sh`。
3. 开始后的约 20 秒内切换几次预设/高音，复现问题。脚本本身不切换设置。
4. 成功时只输出“完成”，结果为 `/sdcard/杜比诊断.zip`，再次运行替换上次结果。

诊断一次执行、无后台常驻。临时开启 log.tag.Dolby=DEBUG，随后恢复原值；不清 logcat、不重启服务、
不挂载分区、不改 SELinux、不改音效开关。采集有整体超时、单命令超时、单文件和总量限制。
异常/超时可能得到部分结果，包内 collector.log、completion.txt 和 files-skipped.txt 可区分。
打包失败不会冒称完成：仅提示失败文件路径，原有 ZIP 不会被失败结果替换。

内容包括实际播放链快照、短时调参日志、服务和进程状态、挂载视图、模块文件与 late XML 比对，
当前 ROM 的音频 XML/VINTF/SELinux 源配置、杜比库与实际 APK、杜比自身偏好。
v2 增加服务端 `/data/vendor/dolby` 目录/数据库属主、权限、标签、复制前后元数据，
以及两种 DMS 进程的文件描述符、数据目录视图、映射库和最多 32 个线程的内核等待位置。
数据库文件仅作原始副本读取，不使用 SQLite 打开手机上的数据库，不执行恢复、解锁或权限修复。
同时复制现有 WAL/SHM/journal；运行中的多文件复制不保证事务一致性，不能据此直接断言原库损坏。
读取的是当前系统可见文件，可能含其他模块覆盖，不等于原厂 OTA。不会提取完整系统镜像。
日志可能含设备、应用、音乐信息和自定义预设，分享前请检查；不会主动抓取其他应用数据库或账户文件。

构建：`diagnostics/build-collector.ps1` 使用 JDK 17 和 Android SDK 的 D8，将 DolbyZip.java 编译为
DEX 后嵌入 collect-dolby.sh.in。输出位于 build/diagnostic-helper/dolby-diagnostic.sh。
同时生成 `dolby-database-diagnostic.sh`（交付名：杜比数据库诊断.sh），用于快速补采上述数据库信息。
快速版不等待 22 秒操作、不修改日志属性、不提取 ROM/APK，结果为 `/sdcard/杜比数据库诊断.zip`，
成功仍只输出“完成”；完整诊断也包含同样的数据库采集。

验证：PLK110/Android 17/Enforcing 实测，424 个相关文件、ZIP CRC 检查通过，stdout 仅“完成”，
日志属性恢复，工作目录清理。此验证不等于所有 Root/ROM 组合已验证。

v2 快速数据库版已在主力 PLK110 实测：3.43 秒，27 个 ZIP 条目，CRC 通过，stdout 仅“完成”，
日志属性保持不变，HIDL PID 不变、工作目录已清理。电脑端仅将数据库副本装入内存运行 quick_check，
结果为 ok。该机不是远端 PKR110 故障机，不能以此判定远端问题已修复。
