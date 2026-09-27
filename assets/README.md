# 资产说明

公开仓库只保留文本配置、规则、模块脚本和资产路径清单，不附带专有 payload 或工具二进制。

## 完整构建需要自行准备

1. `payload.zip`：应包含与 `payload.json` 匹配的组件，以 `canonical` 字段为 ZIP 内路径。
   包含 App、库与服务等私有开发材料；只能使用自己有权使用的来源，并自行确认分发权限。
   清单不是下载器，也不证明随意找一套同名库就能兼容。
2. `native/secilc.exe`：从仓库所附的 SELinuxProject 源码与 `native/build.sh` 构建。
   参考环境为 WSL/Linux + make + MinGW-w64 交叉编译工具链。
3. ADB：将 Android Platform Tools 加到 PATH，或自行将官方文件放到 `assets/adb/`。
   ADB 模式需要已授权设备与 root；电脑 ROM 模式不需要 ADB。

```sh
# 在 WSL/Linux 的仓库根目录，准备好 MinGW-w64 后：
bash native/build.sh
```

`payload.json` 保留原适配方案的路径、权限和标签。改变实际 payload 后必须重新审计清单、
ELF 依赖、init、VINTF、SELinux 与运行兼容性，不能仅改文件名视为适配完成。

## 禁止误传的内容

不要把自己的 payload、ROM、用户数据、凭据、设备日志、构建历史或运行时备份加入提交。
根目录 `.gitignore` 已忽略常见二进制和临时目录；发布前仍需人工检查暂存区。
