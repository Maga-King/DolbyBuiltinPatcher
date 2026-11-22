# 杜比全景 + 解码器 · DolbyBuiltinPatcher

面向 **ColorOS 17 / Android 17 / Qualcomm ARM64** 的 Windows 图形工具：
为已解包 ROM 集成杜比组件，或根据目标系统生成 **KernelSU + 挂载元模块** 专用包。

模块署名：**科比**。推荐组合：**KSU + MOUNTIFY**。

手机版 0.2.13 预览位于 [`android/`](android/README.md)：通过 root 从当前系统或手机解包 ROM
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
模块使用 `ModuleBuild` 输出 KSU 安装/元模块补挂脚本与 `sepolicy.rule`。最小范围挂载修复只作用于后者，
不会让原生内置依赖 KSU、元模块、post-mount 或模块 initrc 注入。

## 当前模块机制

最新电脑生成器为 1.0.10。手机版 0.2.13 和当前源码生成的模块版本为
**`0.6.8-install-state`**，`versionCode=620`。
电脑端三种来源、手机版两种来源共用同一模块生成器与运行脚本。
本版新增按引用链识别新旧 Codec 音频布局，内置与模块共用同一发现/合并实现。
旧包保留原厂音频节点；新版仅在确认高通视频入口、Google 音频及缺失 C2 音频 Include 后，
补齐仅包含杜比解码器的叶节点，不从旧包移入不存在的 QTI 音频组件。
本版变更详见[新旧 Codec 配置兼容说明](docs/Codec配置兼容_1.0.7.md)；
启动/挂载沿用[标准路径配置说明](docs/标准路径配置_1.0.6.md)。

已去掉安装阶段的设备指纹、SDK、架构、原文件哈希及冲突名单限制，开机不再以原 ROM 身份拦截。
本版进一步移除运行时启动门控，保留必要的早期 VINTF 加载和安全路径处理。去限制不等于跨机型通刷。
模块直接生成完整杜比相关 `sepolicy.rule`，**不再调用策略编译器**；原生内置流程不变。

1. 恢复首个公开版本 `e09bb23` 的标准 `system/` 单份载荷、挂载前保存/挂载后恢复子挂载流程。
   不生成 `files/` 或 `self-mount.sh`，正常安装不设置 `skip_mount` / `skip_mountify`。
   同步 post-mount 先恢复 VINTF/OPEX 子挂载，再核对并补挂缺失或内容/权限/标签不符的项。
   已有文件单独 bind，新增文件只合并必要父目录；补挂不新增 OverlayFS 文件系统层。
   OPEX 覆盖 `/vendor/bin/hw` 时可对该目录发布只读合并层。
   没有相关元模块挂载或零项正确载荷时停止，不接管整包；复制兜底有内存限额。
2. 音效 XML、Codec2 XML 与 ODM 配置全部放回标准 `system/` 分区目录，由元模块正常加载。
   例如 `system/odm/etc/audio_effects_config.xml` 对应 `/odm/etc/audio_effects_config.xml`，
   `system/vendor/etc/media_codecs_c2_audio.xml` 对应 `/vendor/etc/media_codecs_c2_audio.xml`。
   不再生成 `late/`、`late.tsv` 或 gate/commit/recover/codec 脚本。
   early-init 一次性加载完整 VINTF（含 Codec2/default9）；early-boot 准备数据库权限后直接启动三个杜比服务。
   `repair-ok`、linker 检查、服务注册轮询和指定音频 HAL 名称均不再作为启动条件；数据库准备失败也不拦截启动。
3. 解码服务不使用 `oneshot`，提供 `default9` 接口启动映射及 `restart_period 3`。
   这是进程退出后的恢复间隔，**不是每三秒检查或重启健康进程**。
4. 不再自动撤回声明或音频配置；不强杀或重启 HWS、音频 HAL、mediaserver。
   NoMount 的 VFS 重定向可能没有传统挂载记录，补挂检查失败不会阻止杜比服务启动。
5. 开机对 initrc 缓存检查一次，仅不一致时限时刷新一次；没有开机后的常驻轮询。
6. Action 按钮只读检查本次启动状态，不把上次开机的遗留日志当作成功证据。
7. 安装同签名 Dolby App 更新，保留系统底包，不清数据；修复数据目录标签以恢复设置持久化。
   旧版挂载方案与验证记录见[元模块补挂验证](docs/元模块补挂验证_20260929.md)和[历史兼容说明](docs/元模块与自挂载兼容说明.md)。
8. 刷入时停用 `com.oplus.audio.effectcenter`，仅在确认该用户下原本启用后执行；状态无法确认或包不存在时不改动。卸载模块时只恢复本模块确实停用的实例。

旧版曾完成 Python 回归、Linux 隔离挂载和 Android Enforcing 私有命名空间测试，
以及 PLQ110 + Mountify 2.0.3 的启动、服务注册及 82/82 项挂载验证。
这些历史结果不能当作本版 NoMount 开机或实际音频播放验证；本版验证范围以 Release 说明为准。
更新生成器后须重新生成、安装模块并完整重启，已安装的旧模块不会自动改变。
其他模块晚于补挂再次覆盖、元模块完全失效、原厂子挂载无法恢复时，仍不能保证正常接入。

**DSU 注意：** `/metadata` 可能与主系统共享。DSU 没有管理器或模块目录，不代表没有主系统留下的早期注入。
测试已内置杜比的 ROM 前，禁用/卸载主系统旧杜比模块并确认其 initrc 缓存解除，避免重复 VINTF 声明。
本版没有自动清理其他系统的 metadata，也不声称已解决跨 DSU 隔离。

`modules.rc` 刷新只影响**下次启动**，不能替换当前 init 已加载的定义。
手工改 RC 后可在重启前执行：

```sh
su -c 'sh /data/adb/modules/mio_dolby_c17_generated/initrc-cache.sh repair'
```

如果自动兜底在开机后才发现旧缓存并刷新，仍需用户再重启一次。
禁用、待卸载或待更新时跳过修复；不会擅自启用模块。

## 使用前必须了解

- 1.0.10 / APK 0.2.13 修正安装结果判断：PackageManager 返回 Binder transaction 错误后，
  用最多三次有时限的查询核对用户 0 的 `/data/app` 注册 APK 与模块字节一致才确认成功。
  原始命令/查询返回保留在 `.runtime/app-package-command.log` 和 `app-package-query.log`。
  命令失败且结果不能确认时继续报告，系统 APK 挂载不当作用户更新已成功，不重复盲装或清空数据。
  ColorOS 不支持 `cmd user is-user-unlocked` 时优先使用 `cmd activity get-started-user-state 0`，
  恢复首次解锁后的 CE 权限兜底；两种查询均不可用时保留 unknown，不猜已解锁。

- 2026-11-22 权限测试版：保留旧 Lunaris 规则，追加上游最新 `set_prop` 修复；
  两个 DMS 域增加音频/Dolby 属性写入和专属 permissive，普通 App/系统音频域不设 permissive。
  属性与 `/data/vendor/dolby` 的实际标签从当次 ROM contexts 取证，包括通用类型仍存在时的专属标签。
  模块在 DMS 前和首次解锁后各执行一次数据权限修复：Dolby vendor 数据及用户 0 的 CE/DE App
  数据目录、普通文件设 777，保留内容、App UID/MCS，跳过外部链接，不删除/重建数据库。
  777 放开 DAC，不会绕过其他 App 的 SELinux/MCS；新建文件权限仍由创建者决定，无常驻权限轮询。
  当前 APK 使用同签名 `ColorOS17-3.1.6` Miuix 管理器；本轮只修改生成器/模块，Flyme 启动和重启保存待实测。

- 1.0.2 / APK 0.2.3 仅加强模块生成的数据库权限兜底：在 DMS 启动前修正现有
  `dax_sqlite3.db` 及 WAL/SHM/journal 的属主、权限和标签，保留内容，不清预设、不新增轮询。
  此历史版本仅修复数据库；最新权限修订见下面的 2026-11-22 说明。
  原生 ROM 内置逻辑未改。需重新生成并安装模块，单独更新生成器不会修改已安装模块。
  此修复不解决早期 initrc 未生效、免解锁环境或热重启造成的启动兼容问题；不支持 KSU late-load 接入。
- 新增[一次性诊断脚本源码](diagnostics/README.md)，包含数据库权限及 DMS 文件描述符采集；不会上传用户日志或数据库。
- 1.0.1 / APK 0.2.2 修复原生内置修改已有文件时覆盖原厂 SELinux 标签的问题；明确指定的新增服务执行标签仍保留。
  已用旧版修改的解包目录，请先用原记录回退再重新修改，不要直接重复运行；更新工具不会自动修复旧目录。
  此修复不代表已确认解决所有卡一反馈。
- 原生内置会修改你选择的**解包目录**，不是只生成一个无副作用的报告；先备份并准备恢复手段。
- 模块需要支持 initrc 注入、早期 metadata 访问与正确提供文件的 KSU/元模块环境；同步 post-mount 用于独立的子挂载恢复与补挂。
- 推荐 KSU + MOUNTIFY 不等于所有版本、机型、SELinux 环境都兼容。
- 部分旧 SukiSU 用户空间没有 `ksud initrc` 接口。安装器不会跳过这一启动依赖；
  更新挂载元模块或仅更换管理器 APK，不保证补齐接口。
- 历史参考实测包括一加 13 的 C17 DSU；本版新增 PLQ110 主系统、KSU + Mountify 2.0.3、Enforcing 的上述限定验证。
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
python -m unittest tests test_mobile test_module_export -v
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
assets/ksu/boot/         早期启动模板、数据准备和缓存检查
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
