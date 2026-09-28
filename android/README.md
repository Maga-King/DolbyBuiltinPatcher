# 手机版（开发预览）

独立 Android App：root 只读快照 → 复用根目录 ModuleBuild → 保存 ZIP。
不包含原位修改 ROM、自动刷模块、系统重启、开机广播、后台服务或网络权限。
策略只导出 sepolicy.rule，不需要 Windows/Android 策略编译器。

使用 Java + Chaquopy 运行共享 Python 生成器，APK 支持 ARM64，界面最低 Android 8；
实际生成器当前仍面向 C17/Android 17 的已支持音频结构，不等于支持所有系统。

## 构建

参考：JDK 17、Gradle 8.13、Android SDK 35、Python 3.12。

```powershell
gradle :app:assembleDebug
# 本地有权使用的私有资产目录，可选。该目录需要 payload.zip：
gradle :app:assembleDebug -PdolbyPrivateAssets="D:/我的私有杜比资产"
```

公开仓库不附带 payload.zip；不指定配套资产时仍可构建/检测 root，但不能生成完整模块。
不要把私有资产、生成的 APK/模块、设备日志或 local.properties 加入 Git。

任务仅在用户操作时执行，建议保持前台。系统回收进程会中断任务，不会自动刷入半成品。
生成记录暂存在 App 私有 history 目录，卸载 App 会清除；先将需要的 ZIP 保存到自己选择的位置。
ROOT 授权由设备管理器决定，App 不尝试替用户授权自身。

## 当前验证范围

- 已构建本地预览 APK，并在 Android 17 ARM64 备用机验证安装、界面、root 授权、
  Python/共享生成器导入、RC 恢复模板及配套资产清单读取。
- 手机 Python 入口在电脑上通过纯净 C17 快照的离线打包回放；读取传输在该测试中模拟。
- 尚未在无杜比目标机完成手机端“实时读取 → 生成 → 保存”的全流程实测，也未验证它生成包的刷入效果。
- 没有在自带杜比的备用机上生成、安装模块或修改其原生杜比。

这是开发预览，不应依据 root 检查通过就声称全流程、长期稳定性或所有机型兼容。
