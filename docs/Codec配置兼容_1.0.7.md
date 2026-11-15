# Codec 配置新旧兼容（电脑 1.0.7 / 手机 0.2.8）

## 问题与证据

旧生成器 `discovery.py` 以现存厂商 `c2.*` 音频 Decoder 定位共享叶节点。
2026-11 ACE6 输入已经移除 `vendor/etc/media_codecs_c2_audio.xml`，但 7 个视频入口仍 Include 它，
因此报“没有找到包含厂商 Codec2 音频解码器的配置引用链”。这不是二进制 patch 偏移变化。

本次只读输入：`E:\MIO\ACE6`（system incremental 1793843639766，安全补丁 2026-11-01）
和 `E:\MIO\OnePlus13-ColorOS17`（1791342572728，2026-09-01）。
源码基于公开 main `92ac0f96c01cd5775631124b4fe11bed1df22616`，没有回退挂载方案。

新包的 `media_codecs.xml`、`media_codecs_sun.xml`、`media_codecs_sun_vendor.xml`、
`media_codecs_kera_v0.xml`、`media_codecs_kera_v1.xml`、`media_codecs_tuna_v0.xml`、
`media_codecs_tuna_v1.xml` 均保留该 Include；已有 Google 软件音频节点和 QTI 视频节点。
解包文件清单中也没有旧版 QTI c2audio 服务、RC、default2 VINTF 与 libqc2audio_*。
未解开所有 APEX，不能据文件清单断言所有可能加载路径的运行状态。

参考 [AOSP MediaCodecsXmlParser.cpp](https://android.googlesource.com/platform/frameworks/av/+/refs/heads/main/media/libstagefright/xmlparser/MediaCodecsXmlParser.cpp)：
Include 相对当前 XML 目录解析；`combineStatus` 忽略父状态正常时的 `NAME_NOT_FOUND`。
因此不能把“缺 Include 文件”直接说成 Android 必然卡开机；本次已确认的是生成器定位失败。

## 修改方法

- `discovery.py`：保留原有厂商音频候选，并按每条链识别新布局。仅对明确被引用、缺失的
  `media_codecs_c2_audio.xml`，在有 QTI 视频和 Google 音频语义证据时计划新建。
  支持不同 SKU 子目录同时存在新旧布局；不按 ACE6、sun、SDK 或 ROM 日期分支。
  该精确音频 Include 只相对当前 XML 解析，避免根目录旧叶掩盖新 SKU 子目录真正缺失的文件。
- `core.py`：新叶从空 `Included/Decoders` 开始，用原有过滤器只加入
  `c2.dolby.eac3.decoder` 和 `c2.dolby.ac4.decoder`；旧叶原有 Decoder/Encoder 均保留。
- 不复制旧包 XML、不加入 QTI default2 服务、不替换厂商 Codec2 或音效 HAL 二进制。
- 新叶仍经过循环、未解决引用、每入口恰好一次和已有杜比重复节点检查。
  其他未知缺件不自动创建；识别不明确时停止并说明。
- 原生内置沿用原 `Build.metadata()` 给新增 XML 写 0644 / `u:object_r:vendor_configs_file:s0`，
  同步 DNA `config/vendor_fs_config` 与 `vendor_file_contexts`。
- 模块按标准路径 `system/vendor/etc/...` 发布新增 XML，沿用当前元模块与有界补挂流程。
- Android Gradle 同步根目录 `discovery.py`、`core.py`；手机 ROM/实时来源和电脑来源不会各自维护补丁。

安装阶段额外修正：之前冻结音效中心的调用位于 `customize.sh` 的裁剪段，生成模块不包含该调用。
现在放入实际执行的 `install-early.sh`；保留原按需禁用/卸载恢复行为，并检查最终导出 ZIP 中的调用链。

## 验证与回退

无私有资产单元测试：`python -m unittest tests test_mobile test_module_export`。
新增覆盖新包 7 入口、旧/新混合、幂等、未知缺件、重复 Include、错误目标、语义证据缺失、
已有其他杜比节点。100 项单元测试通过；两个真实输入均完成模块生成与原生部署、合并、
普通/调试策略编译及打包标签生成。旧包原有 10 个音频 Decoder、3 个 Encoder 及其参数保留；
新包只新增 2 个杜比 Decoder。两包各 7 个入口覆盖检查通过，内置与模块的对应 XML 一致。
电脑成品 EXE 实际生成 ACE6 测试模块，手机 APK 包含同一共享引擎。
真实包结果和构建退出码见本地交付目录的验证记录。

本次未写两份输入 ROM、未安装模块、未操作手机。用户随后授权发布电脑 1.0.7 / 手机 0.2.8。
生成成功仅证明离线识别/合并/打包通过；冷启动、DMS 调参、EAC3/AC4 实际播放待用户测试。
模块不适用时禁用/卸载并完整重启；原生内置继续使用既有事务回退，新增 XML 会随该事务删除。
