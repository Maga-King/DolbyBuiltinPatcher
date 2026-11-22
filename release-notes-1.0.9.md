## 杜比预设与数据权限修订

- 同步最新 LunarisDolby 上游 SELinux 规则，补齐预设切换写入 `persist.vendor.audio.scenario` 的权限。
- HIDL/AIDL 两个杜比 DMS 专属域加入 permissive；音频属性、配置和数据库权限按当次 ROM 标签追加，保留旧规则。
- 模块在启动前及首次解锁后执行一次数据权限准备，杜比数据库和 App CE/DE 数据目录、普通文件设为 777，保留已有内容和 App 属主。无常驻扫描。
- 内含同签名 `ColorOS17-3.1.6` Miuix 管理器（versionCode 8），保留开关/磁贴同步与开机恢复实现，不用 root-test1 管理器。
- 模块“诊断”增加场景属性实际标签、进程域、App 状态、数据权限、文件描述符、挂载可见性、DAP 和近期错误；结果在模块 `.runtime/diagnostic-last.txt` 与 `diagnostic-detail/`。
- 旧/新 Codec XML 和 OPEX/元模块补挂兼容逻辑保留。

电脑 **1.0.9** / 手机 **0.2.12** / 生成模块 **0.6.7-permissions**，署名 **科比**。
更新生成器后需重新生成模块。切换元模块：卸载杜比 → 完整重启 → 重新安装。

106 项测试通过；本地 ColorOS 17.0.202 实际生成模块、普通/调试原生策略离线编译通过，未删旧规则。
Flyme/对方机型的预设听感与重启保存尚待上机验证。777 仅放开文件权限，不绕过其他应用的 SELinux/MCS 隔离；
KSU 隐藏不是策略注入成功保证。本版会降低两个杜比服务域及杜比数据的隔离强度，请自行决定是否安装。

来源：LunarisDolby / Pong-Development hardware_dolby；上游提交 `b2963f7c2c7835389e7c16bdb0946ff9311d20e2`。
