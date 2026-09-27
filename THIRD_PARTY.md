# 来源、致谢与分发范围

## LunarisDolby

- 来源仓库：[Pong-Development/hardware_dolby](https://github.com/Pong-Development/hardware_dolby)。
- App 目录：[LunarisDolby](https://github.com/Pong-Development/hardware_dolby/tree/16/LunarisDolby)。
- 本工具采用的 SELinux 规则固定提交：`6300a4e30757d5810d62b2df0cff973ec438a70f`。
- `assets/upstream-lunaris/` 保留原始 TE、contexts、属性、来源信息和本项目宏展开结果；来源详见该目录 `SOURCE.md`。
- 本项目是集成与适配工具，不声称原创 LunarisDolby App 或 Dolby 音效/解码算法。
- 私有开发期间使用过 AlphaDroid/Lunaris 移植材料；这不表示已获得所有二进制的公开分发许可。
  **此公开仓库不分发 Dolby APK、专有 `.so`、HAL 可执行文件或包含它们的 payload ZIP。**

## SELinuxProject 与 Windows 移植

- 上游：[SELinuxProject/selinux](https://github.com/SELinuxProject/selinux)，3.9 基础提交
  `919e9e64cc4b20f5a1e4df1e38cce1bfe15aff09`。
- 仓库保留相关 `libsepol`、`secilc` 源码以及原始 LICENSE/COPYING 和文件版权头。
  各组件许可证不同，以各自声明为准，不用本项目名称覆盖第三方版权。
- 当前源码包含本地 Windows/Android 兼容改动：`polcaps.h`、`polcaps.c`、`write.c`、`secilc.c`，
  以及 `native/` 下 MinGW 兼容头与构建脚本。
- Android netlink 配置位参考 [AOSP external/selinux](https://android.googlesource.com/platform/external/selinux/+/refs/heads/main/libsepol/src/write.c)。
- 本仓库不附带构建出的 Windows EXE、静态库或 MinGW 工具链；如分发自行构建的程序，仍须遵守相关许可证义务。

## 工具与依赖

- KernelSU：使用其模块、initrc 注入和元模块机制；参考 [模块开发文档](https://kernelsu.org/guide/module.html)。
- Android Platform Tools：ADB 由使用者自行安装，本仓库不含二进制；可从 [Android 官方页面](https://developer.android.com/tools/releases/platform-tools) 获取。
- Python、PyInstaller、CustomTkinter、pyelftools：按各自许可证使用，版本见 `requirements.txt`。
  本仓库不包含它们的运行时或安装包。

来源标注、上游公开可见以及本仓库公开，均不意味着取得所有第三方资产的任意再分发许可。
原创工具代码暂未另行选择开源许可证，不对上游文件做统一改授权。
