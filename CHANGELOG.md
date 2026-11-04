# 更新日志

本模块遵循 [语义化版本](https://semver.org/lang/zh-CN/)，`module.prop` 中的
`versionCode` 每次发版递增，供 Magisk / KernelSU / APatch 判断是否需要更新。

## 未发布（文档修订，无模块行为变更）

- README：补充证据边界声明、已知限制、分层验证状态、持久化范围与风险说明
- README：开头改为先说明「模块做了什么 / 可能解决什么问题」，原理与作者案例后置
- README：把「Play Integrity 三绿」等结论条件化，不再作为普遍承诺
- 新增 `TESTING.md`：测试矩阵、分层证据采集清单与失败案例模板
- 修正 `pm clear com.android.rkpdapp` 的副作用说明

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
