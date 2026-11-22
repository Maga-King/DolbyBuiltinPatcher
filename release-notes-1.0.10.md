## 安装结果与 ColorOS 解锁兼容修订

- 修正杜比 App 安装误报：即使 `pm install` 返回 Binder transaction 错误，只有实际用户 APK 注册且与模块一致才确认成功；真失败仍保留原始记录并报告。
- 修正部分 ColorOS 缺少 `cmd user is-user-unlocked`，导致首次解锁后数据权限兜底不执行的问题；优先读取 ActivityManager 用户状态。
- 模块诊断增加安装命令/查询原始日志，过滤 ColorOS 应用推荐噪声，改善 DAP 上下文展示。
- 保留上一版 DMS 权限、专属 permissive、777 数据准备、新旧 Codec 配置兼容和 3.1.6 Miuix 管理器，不清空旧数据。

电脑 **1.0.10** / 手机 **0.2.13** / 生成模块 **0.6.8-install-state**，署名 **科比**。
106 项主测试和 4 项 WSL 执行测试通过；需要重新生成并安装模块才生效。
这是离线修订验证，预设音效和重启保存仍需目标设备实测。
