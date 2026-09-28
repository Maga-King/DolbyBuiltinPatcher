# 杜比全景 + 解码器 · DolbyBuiltinPatcher

面向 **ColorOS 17 / Android 17 / Qualcomm ARM64** 的 Windows 图形工具：
为已解包 ROM 集成杜比组件，或根据目标系统生成 **KernelSU + 挂载元模块** 专用包。

模块署名：**科比**。推荐组合：**KSU + MOUNTIFY**。

手机版 0.2.1 预览位于 [`android/`](android/README.md)：通过 root 从当前系统或手机解包 ROM
生成 ZIP，也可输入 `/data/DNA/DNA_01` 一类目录，备份后原位内置杜比；无需电脑参与运行。
公开仓库不附带包含专有资产的 APK。

> 这是第三方适配工具，不是 Dolby、OnePlus、OPPO 或 Lunaris 的官方产品。
> 它不是任意手机通刷包；生成成功不代表目标设备一定可以开机或正常播放。
> 本仓库只发布源码、配置模板及构建材料，**不附带专有 Dolby 库、APK、ROM 或可直接刷入的完整 ZIP**。

## 来源与致谢

本项目的杜比 App 与集成方案来源于 **LunarisDolby / AlphaDroid 相关移植材料**。
LunarisDolby 上游位于 [Pong-Development/hardware_dolby](https://github.com/Pong-Development/hardware_dolby)，
App 源码目录为 [LunarisDolby](https://github.com/Pong-Development/hardware_dolby/tree/16/LunarisDolby)。

本工具采用的 LunarisDolby SELinux 规则快照固定在提交
`6300a4e30757d5810d62b2df0cff973ec438a70f`，原始规则、来源说明及宏展开结果位于
[`assets/upstream-lunaris`](assets/upstream-lunaris/SOURCE.md)。
**本项目不声称原创 LunarisDolby App 或 Dolby 算法，也不以来源标注代替第三方授权。**

同时感谢 [KernelSU](https://github.com/tiann/KernelSU)、
[SELinuxProject](https://github.com/SELinuxProject/selinux) 与 Android/AOSP。
详细说明见 [THIRD_PARTY.md](THIRD_PARTY.md)。

## 可以做什么

| 输入模式 | 修改解包 ROM | 生成 KSU 模块 |
| --- | --- | --- |
| 电脑上的 ROM 解包目录 | 支持，先备份后原位修改 | 支持，只读输入 |
| ADB 手机 ROM 解包目录 | 支持，需要 root 与完整目录 | 支持，只读输入 |
| ADB 实时读取当前系统 | **不支持写回运行分区** | 支持，读取当前可见文件 |
| 手机版：输入手机 ROM 解包目录 | 支持，备份 / 事务状态 / 回退 | 支持，只读输入 |
| 手机版：读取当前系统 | **不支持写回运行分区** | 支持，只读输入 |

- 集成目标包括 LunarisDolby App、DAP 音效、HIDL/AIDL DMS 与 Codec2 解码服务；完整构建需要自行准备合法来源的配套资产。
- 按实际 HAL、音效配置和 codec Include 链定位 XML，不只处理某个固定 SKU 目录。
- 支持 DNA 打包元数据中的权限与 SELinux 标签合并，以及有条件的备份/回退。
- 多设备连接时要求选择设备，不自动选第一台；模块生成不自动刷入、重启或写运行分区。
- 模块的 `solidify/` 仅提供固化参考，工具不会自动把它写入分区。

## 原生内置要解包哪些镜像

需要同一套目标 ROM 的 **system、system_ext、vendor、odm、product** 五个镜像，解成文件目录，
并保留 DNA 生成的 `config`（尤其 `*_fs_config`、`*_file_contexts`）。
如果 ROM 只提供 `super.img`，先拆出对应逻辑分区再解包；仅提取出 `.img` 文件还不够。
若来源是 `payload.bin`，同样先提取这五个镜像。此流程无需解包 boot、init_boot、vendor_boot、dtbo、vbmeta 或 my_*。

`product` 即使没有新增杜比文件也需要：工具读取分区信息，并将其中存在的 SELinux 策略纳入编译。
`*_fs_options`、`*_info` 保留原样；不要混用另一台设备/另一版 ROM 的打包标签和策略文件。
本工具修改解包目录，不自动生成镜像或刷机；实际改动以该次记录为准。

**原生内置与模块输出分开：** 内置使用 `Build` 写入分区文件、更新打包标签并编译目标系统策略；
模块使用 `ModuleBuild` 输出 KSU 安装/自挂载脚本与 `sepolicy.rule`。最小范围挂载修复只作用于后者，
不会让原生内置依赖 KSU、元模块、post-mount 或模块 initrc 注入。

## 当前模块机制

本仓库对应 0.6.1 模块修复系列；内置引擎和 GUI 基础版本仍为 0.6.0。
当前模块版本为 **`0.6.1-selfmount-preview5`**，`versionCode=609`；手机生成器为 0.2.1 测试版。
电脑端三种来源、手机版两种来源共用同一模块生成器与运行脚本。

已去掉安装阶段的设备指纹、SDK、架构、原文件哈希及冲突名单限制，开机不再以原 ROM 身份拦截。
必要的工具/挂载操作、启动顺序、失败回退和安全路径处理保留。去限制不等于跨机型通刷。
模块直接生成完整杜比相关 `sepolicy.rule`，**不再调用策略编译器**；原生内置流程不变。

1. 提前准备 HIDL 支持声明，使用 `files/` 独立载荷和同步 post-mount 自挂载，保留原有子挂载。
   按开机时实际目录缩小范围：已有文件单独 bind，新增文件只合并最近已有父目录，不新增 OverlayFS。
   文件 bind 失败可限额复制到私有 tmpfs 暂存区；目录发布失败仍停止接入，不覆盖原厂分区。
2. 文件、依赖与服务就绪检查通过后，才发布 Codec2/default9 声明并提交音频配置。
3. 解码服务不使用 `oneshot`，提供 `default9` 接口启动映射及 `restart_period 3`。
   这是进程退出后的恢复间隔，**不是每三秒检查或重启健康进程**。
4. 启动准备失败时尝试撤回本模块声明/配置；不强杀或重启 HWS、音频 HAL、mediaserver。
5. 开机对 initrc 缓存检查一次，仅不一致时限时刷新一次；没有开机后的常驻轮询。
6. Action 按钮只读检查本次启动状态，不把上次开机的遗留日志当作成功证据。
7. 安装同签名 Dolby App 更新，保留系统底包，不清数据；修复数据目录标签以恢复设置持久化。
   详见[自挂载与兼容说明](docs/元模块与自挂载兼容说明.md)。

`modules.rc` 刷新只影响**下次启动**，不能替换当前 init 已加载的定义。
手工改 RC 后可在重启前执行：

```sh
su -c 'sh /data/adb/modules/mio_dolby_c17_generated/initrc-cache.sh repair'
```

如果自动兜底在开机后才发现旧缓存并刷新，仍需用户再重启一次。
禁用、待卸载或待更新时跳过修复；不会擅自启用模块。

## 使用前必须了解

- 原生内置会修改你选择的**解包目录**，不是只生成一个无副作用的报告；先备份并准备恢复手段。
- 模块需要支持 initrc 注入、同步 post-mount 与正确挂载的 KSU/元模块环境；不支持时拒绝安装或激活。
- 推荐 KSU + MOUNTIFY 不等于所有版本、机型、SELinux 环境都兼容。
- 部分旧 SukiSU 用户空间没有 `ksud initrc` 接口。安装器不会跳过这一启动依赖；
  更新挂载元模块或仅更换管理器 APK，不保证补齐接口。
- 当前参考实测为一加 13、C17 Android 17 DSU、KSU + Mountify 2.0.3，系统原本为 Permissive。
  **没有证明 Enforcing 或其他机型普遍可用**；工具不会主动关闭 SELinux。
- 后续在 PLQ110 / Android 17 / Enforcing 做过隔离挂载、复制兜底、App 更新与标签修复测试；
  用户反馈恢复正常。这不等于各 KSU 分支和手机均完成开机/音频验证。
- 不建议叠加其他杜比实现。安装器允许更新本模块早期 metadata，不再因旧目录存在拒装。
- 模块仍基于输入 ROM 配置生成，虽然取消了身份绑定，换 ROM 或 OTA 后仍应重新生成。实时读取可能读到其他模块的挂载，不保证是纯净底包。
- 不替换原厂 `libaudioeffecthal.qti.so`，不向模块挂入整份 CIL/precompiled_sepolicy。
- 已修复“解码进程退出后接口长期失联”的配置缺陷；**不宣称解码库内部崩溃已经根治**。
  持续崩溃时应停用模块、保留日志，不能把自动重启当作播放正常。
- 官方 AudioEffectCenter 接管、所有机型通用音效切换不在本仓库已完成功能范围内。

更多说明见 [docs/使用与资产.md](docs/使用与资产.md)。

## 从源码运行

本仓库不包含 `assets/payload.zip`、Windows `secilc.exe`、ADB 或第三方运行时。
`secilc.exe` 仅原生内置功能需要，模块生成不需要它。
**仅克隆仓库不能直接生成可用的杜比模块**；先按 [资产说明](assets/README.md) 准备匹配资产。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest tests -v
python app.py
```

开发参考环境为 Windows x64 / Python 3.12。单元测试不需要手机或专有 payload，
测试通过不等于真实 ROM/音频兼容性通过。

生成模块示例（不会安装模块或修改输入 ROM）：

```powershell
python app.py --rom "D:\ROM解包" --module "D:\杜比_KSU.zip"
python app.py --adb "设备序列号" --remote-rom "/data/DNA/ROM" --module "D:\杜比_KSU.zip"
python app.py --adb "设备序列号" --adb-live --module "D:\杜比_KSU.zip"
```

注意：CLI 只给 `--rom` 时，默认执行原位修改；只生成内置补丁而不写回，必须加 `--build-only`。
资产齐备后执行 `build.ps1` 打包 Windows 程序。编译器源码与构建说明位于 `native/`、`third_party/selinux/`。

## 目录

```text
app.py / gui.py          命令行与图形界面
core.py / discovery.py   ROM 布局识别、文件合并和变更记录
adb_mode.py             ADB 快照、事务、回退
ksu_module.py            模块生成入口
ksu_boot.py              模块启动材料导出与 RC 校验
assets/ksu/boot/         当前早期启动模板、门禁和缓存检查
assets/upstream-lunaris/ LunarisDolby SELinux 来源快照
native/                 Windows secilc 移植兼容层和构建脚本
third_party/selinux/     SELinuxProject 相关源码与原许可证
tests.py                自动化单元测试
```

`assets/ksu/service.sh` 为保留的旧模板；当前生成模块使用 `assets/ksu/boot/service.sh`，不要手工替换混用。

## 问题反馈与隐私

请说明机型、系统版本、KSU/元模块版本、SELinux 状态、操作模式与报错阶段。
发日志前遮盖设备序列号、账号、个人路径和其他隐私；不要上传完整 ROM、账号凭据或未经授权的专有资产。

公开源码不改变第三方文件的许可证，不代表获得 Dolby 商标或专有库的再分发授权。
本项目原创部分尚未另行指定开源许可证；第三方部分遵循其原有许可证与权利声明。
