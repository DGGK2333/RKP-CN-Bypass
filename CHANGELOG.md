# 更新日志

本模块遵循 [语义化版本](https://semver.org/lang/zh-CN/)，`module.prop` 中的
`versionCode` 每次发版递增，供 Magisk / KernelSU / APatch 判断是否需要更新。

## v1.1

- 新增 `service.sh`：防止 `remote_key_provisioning_native/enable_rkpd`
  在开机后被 ROM 重置为 `false`（否则约 30 天后 RKP 证书链过期，attestation 会再次失效）
- `post-fs-data.sh` 增加条件判断，仅当 `ro.boot.hwc == CN` 时才修改
- 新增 `customize.sh` / `uninstall.sh`，改进安装与卸载体验
- `customize.sh` 安装时打印机型、系统版本、`ro.boot.hwc`、`rkp_only` 等信息
- 完善文档：补充根因分析、验证步骤与排障速查
- 新增 `update.json` 更新检查与自动打包脚本 `build.py`

## v1.0

- 首个版本：通过 `resetprop ro.boot.hwc GL` 绕过 `keystore2` 的
  `CN device with TEE level, skipping RKP` 补丁
