# 测试矩阵与证据记录

本文件用于记录模块在不同设备 / ROM 上的**实际**测试结果。

> **为什么要单独记录？**
> README 中的根因解释目前只来自作者单台设备的实机排查。在收到足够的第三方记录前，
> 请把 README 的「适用范围」视为**待验证的假设**，而不是对任意机型的保证。
> 特别是：「恢复 RKP 流程」不等于「证书链有效」，更不等于「Play Integrity 判定通过」。

## 如何提交记录

- 按下方模板填写后开 issue（使用 `bug_report` 模板，或在任意 issue 中贴表格）；
- 或直接 PR 在「结果汇总」表格末尾追加一行；
- **请勿提交** IMEI、序列号、账号信息、完整 keybox、私钥或可用于定位个人的信息；
- Play Integrity 原始返回里如含完整性 token，请先去掉 token 字段再贴。

## 记录模板

| 字段 | 说明 |
|---|---|
| 日期 | `YYYY-MM-DD` |
| 机型 / 代号 | 如 Xiaomi 17 Pro Max / popsicle |
| SoC | 如 SM8850 |
| Android / SDK | 如 Android 16 / SDK 36 |
| HyperOS 版本 | 如 OS3.0.1.0 |
| ROM fingerprint | `getprop ro.build.fingerprint`（用于判断是否原厂包） |
| Root 方案 / 版本 | Magisk / KernelSU / APatch + 版本号 |
| `rkp_only` | `getprop odm.xiaomi.security.tee.rkp_only` |
| 安装后 `ro.boot.hwc` | 期望 `GL` |
| KeyMint 基线 | `keystore_cli_v2 generate` 是否输出 `Hardware:` 段 |
| RKP HAL | `dumpsys remote_provisioning` 的关键行 |
| RKPD 申领 | `Requested / Total provisioned keys` 日志行 |
| 证书链 | 是否取得、离线校验结果（见下） |
| Play Integrity | 三项判定结果（或「未测」） |
| 结论 | 生效 / 无效 / 无法判断 + 备注 |

## 结果汇总

| 日期 | 机型 | SoC | Android / HyperOS | Root 方案 | 结果 | 备注 |
|---|---|---|---|---|---|---|
| 2026-11-04 | 作者设备（型号待补） | 待补 | 待补 | 待补 | 作者单机实测生效 | 仓库公开时的原始记录，证据仍在补充 |

> 后续提交的测试记录请直接追加到上表；未测试的字段请写「未测」，不要留空。

## 分层证据采集

每台设备至少记录以下 7 项，便于定位失败到底发生在哪一层：

```sh
# 1. 环境
getprop ro.build.fingerprint
getprop ro.boot.hwc
getprop ro.boot.verifiedbootstate
getprop ro.boot.flash.locked
getprop odm.xiaomi.security.tee.rkp_only

# 2. TEE / KeyMint 基线（这一步失败说明问题在硬件密钥层，本模块无效）
su -c "keystore_cli_v2 generate --name test_key"

# 3. CN-skip 是否被绕过
logcat -d --pid=$(pidof keystore2) | grep -c 'CN device with TEE level'

# 4. RKPD 申领
logcat -d --pid=$(pidof com.android.rkpdapp) | grep -E 'PoolStats|Successfully provisioned|Error provisioning'

# 5. RKP HAL
su -c "dumpsys remote_provisioning"

# 6. 证书链（粗检 + 离线校验）
strings /data/data/com.android.rkpdapp/databases/rkpd_database-wal | grep -i -E 'Google LLC|Key Attestation CA1'
# 更严谨的做法：从 keystore 导出证书后用 openssl / keytool 校验证书链签名与有效期，
# 并核对证书中的 device ID 是否与本机匹配。strings 只能证明「数据库中存在相关字符串」。

# 7. Play Integrity：记录原始判定结果（去 token），不要只写「三绿 / 全红」
```

## 失败案例

| 日期 | 机型 / ROM | 报错 | 定位层次 | 结论 |
|---|---|---|---|---|
| 待补充 | — | `invalid_ta_response` / `unsupported EEK curve: 0` | KeyMint / TA 协议层 | 此类错误通常与 CN-skip 无关，本模块预期无效 |
| 待补充 | — | `403 DICE mode must be normal`（`default` 组件） | DICE / 启动状态层 | boot / 启动链被修改，本模块预期无效 |

## 已知未验证的结论

以下结论**只在作者单机环境成立或尚未验证**，引用时请注明：

- 「小米 `keystore2` 的 CN-skip 补丁是 `rkp_only` 机型 attestation 失效的主要原因」——运行时证据，未核验小米源码；
- 「恢复 RKP 流程后 Play Integrity 三项通过」——单机观察，不构成普遍结论；
- 「已签发的证书链保留在设备上没有风险」——未做风险量化；
- 兼容性（Magisk / KernelSU / APatch 各版本）——未做完整矩阵测试。
