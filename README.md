# RKP CN Bypass

[![Release](https://img.shields.io/github/v/release/DGGK2333/RKP-CN-Bypass?style=flat-square&label=release)](https://github.com/DGGK2333/RKP-CN-Bypass/releases/latest)
[![License](https://img.shields.io/github/license/DGGK2333/RKP-CN-Bypass?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Magisk%20%7C%20KernelSU%20%7C%20APatch-4B8BBE?style=flat-square)](#安装)
[![Android](https://img.shields.io/badge/Android-12%2B-3DDC84?style=flat-square&logo=android&logoColor=white)](#适用范围)

> 修复小米国行（CN）ROM 上 **`rkp_only` 机型的 Key Attestation 永久失效**问题
> —— 让 Play Integrity 从「全红 / UNEVALUATED」恢复为 **3 绿**。

**不写分区 · 不烧 keybox · 不伪造设备身份 · 不改变 Bootloader 状态。**

<details>
<summary><b>English summary / 英文简介</b></summary>

### What is this?

Some Xiaomi China (CN) ROM builds ship a patched `keystore2` that skips Remote Key
Provisioning (RKP) entirely:

```
W keystore2: .../remote_provisioning.rs:88 - CN device with TEE level, skipping RKP to avoid timeout blocking.
```

On devices whose attestation keys come **only** from RKP (`rkp_only=true`, no built-in
keybox), this makes hardware Key Attestation fail permanently with
`ATTESTATION_KEYS_NOT_PROVISIONED` — Play Integrity shows all `UNEVALUATED`, and relocking
the bootloader does not help.

This module restores the normal RKP path **at runtime only**:

| File | What it does |
|---|---|
| `post-fs-data.sh` | Overrides `ro.boot.hwc` from `CN` to `GL` via `resetprop<sup>*</sup>` |
| `service.sh` | Keeps `remote_key_provisioning_native/enable_rkpd` at `true` so keys renew |

<sup>*</sup> `resetprop` is provided by Magisk / KernelSU / APatch. No partition, `boot.img`,
`vbmeta`, or bootloader state is modified.

### Requirements

- Xiaomi / Redmi device on a **China (CN)** ROM
- `getprop odm.xiaomi.security.tee.rkp_only` returns `true`
- Working TEE (`keystore_cli_v2 generate` prints a `Hardware:` section)
- Magisk, KernelSU, or APatch installed

### Install

1. Download the latest `RKP-CN-Bypass-*.zip` from
   [Releases](https://github.com/DGGK2333/RKP-CN-Bypass/releases/latest).
2. Flash it from your root manager (Magisk / KernelSU / APatch), then reboot.
3. Force a fresh key provisioning once:

   ```sh
   su -c "pm clear com.android.rkpdapp"
   su -c "am broadcast -a android.intent.action.BOOT_COMPLETED -n com.android.rkpdapp/.BootReceiver"
   ```

4. Verify with Play Integrity API Checker — it should report
   `MEETS_BASIC_INTEGRITY` / `MEETS_DEVICE_INTEGRITY` / `MEETS_STRONG_INTEGRITY`.

See the Chinese sections below for root-cause analysis, verification, troubleshooting and rollback.

### Notes

- Tested for research and personal device restoration only; use at your own risk.
- Certificates are genuinely signed by Google's RKP servers for your device's real DICE
  chain — no keybox, no spoofed hardware identity.
- Not affiliated with Xiaomi or Google.

</details>

---

## 目录

- [症状](#症状)
- [适用范围](#适用范围)
- [根因](#根因)
- [工作原理](#工作原理)
- [安装](#安装)
- [更新](#更新)
- [验证](#验证)
- [排障速查](#排障速查)
- [卸载与回滚](#卸载与回滚)
- [风险与免责](#风险与免责)
- [文件说明](#文件说明)
- [开发与发布](#开发与发布)
- [更新日志](#更新日志)
- [排查案例记录](#排查案例记录)

---

## 症状

设备表现为：

- **Play Integrity API Checker** 三个字段全是 `UNEVALUATED`
  （`appRecognitionVerdict` / `deviceIntegrity` / `appLicensingVerdict` 全空）
- **春秋 / nativecheck** 报 "TEE 损坏"，堆栈为：

  ```
  java.security.ProviderException: Failed to generate key pair
  Caused by: android.security.KeyStoreException: -74
      0: system/security/keystore2/src/security_level.rs:959:
         While generating WITHOUT a provided attestation key ...
      1: Error::Km(r#ATTESTATION_KEYS_NOT_PROVISIONED)   (KmError 10)
  ```

- 银行 App、部分游戏、DRM 相关的强校验失败
- **重新锁定 Bootloader 后依然报同样的错**（很多人卡在这一步）
- 重启、恢复出厂、重刷官方包都不能解决

---

## 适用范围

本模块**只在同时满足以下条件时有意义**：

| 条件 | 检查命令 | 期望值 |
|---|---|---|
| 小米 / 红米设备，国行 CN ROM | `getprop ro.boot.hwc` | `CN` |
| 该机型是 RKP-only（无内置 keybox） | `getprop odm.xiaomi.security.tee.rkp_only` | `true` |
| TEE 本身是完好的 | 见[验证](#验证)第 1 条 | 能生成硬件密钥 |
| 已 root（KernelSU / Magisk / APatch） | — | `su` 可用 |

> **如果 `rkp_only` 不是 `true`**，说明机型本身就带内置 keybox，`keystore2` 会直接用它出证书，
> 不会受 CN-skip 补丁影响，**装了也没用**。

### 不适用 / 无效的情况

- 非小米设备（其它厂商的 `keystore2` 没有这个 CN-skip 补丁）
- TEE 真的损坏（TZ/QSEE 崩溃、TA 加载失败）—— 本模块治不了
- 使用了修改过 `boot.img` 的 root 方案（GKI 模式 KSU、改签内核）导致
  **DICE 链不再是 `normal`**，Google 会拒签，本模块同样无效
- 已经烧了第三方 keybox 的设备（情况不同，可能已被污染）

---

## 根因

这个问题由**四层因素叠加**造成，缺一层都不会触发：

### 第 1 层：RKP 总开关被关死

```sh
device_config get remote_key_provisioning_native enable_rkpd
# => false
```

`RemoteProvisioningService`（`com.android.rkpdapp`）的所有申领动作都由这个
DeviceConfig 开关把关（AOSP 默认应为 `true`）。为 `false` 时它连 CSR 都不生成：

```sh
ls /data/misc/apexdata/com.android.rkpd
# => 空目录，时间戳停留在 1970-01-01
```

### 第 2 层：被第三方"RKP 修复"工具写入脏数据

市面上一些"一键修复 TEE"工具会向 `rkpdapp` 的数据库写入看似"已签名"的密钥记录，
但并没有真正把证书链装进 TEE。结果系统认为密钥池已就绪，**永远不会再发起申领**，
形成死锁。

```sh
strings /data/data/com.android.rkpdapp/databases/rkpd_database-wal | grep -i 'attest'
```

### 第 3 层（最隐蔽）：小米在 `keystore2` 里的私有补丁

这是真正的"最后一根稻草"。`keystore2` 二进制里可以找到这段字符串：

```
remote_provisioning.strongbox.rkp_only
remote_provisioning.hostname
ro.boot.hwc
CN device with TEE level, skipping RKP to avoid timeout blocking.
```

对应源码位置 `system/security/keystore2/src/remote_provisioning.rs:88`。
逻辑是：

```rust
if getprop("ro.boot.hwc") == "CN" && security_level == TEE {
    // 国行 ROM 访问 Google RKP 服务器要绕小米代理，首次开机可能长时间阻塞
    // 小米的解法：干脆不打 attestation 证书
    warn!("CN device with TEE level, skipping RKP to avoid timeout blocking.");
    return;   // 直接跳过 RKP
}
```

**即使证书链已经签好放在数据库里，`keystore2` 也拒绝去取。**

运行时日志里每个 attestation 请求旁边都会伴随这一行：

```
W keystore2: .../remote_provisioning.rs:88 - CN device with TEE level, skipping RKP to avoid timeout blocking.
E keystore2: Error::Km(r#ATTESTATION_KEYS_NOT_PROVISIONED)
```

### 第 4 层：结果

TEE 里永远没有 attestation 密钥 → 所有需要证书链的操作全部失败。

### 为什么"回锁 Bootloader"没用

**这四层没有一层和 BL 状态有关。**

- 回锁只改变 `verifiedbootstate`（orange → green）
- 而 `ATTESTATION_KEYS_NOT_PROVISIONED` 是 TEE **内部密钥缺失**，回锁无法凭空造出证书链
- 所以「真回锁后依然报错」是必然结果，不是操作失误

### 为什么别的国行小米用户体验不到这个问题

| 机型类型 | CN-skip 的影响 |
|---|---|
| **有内置 keybox** | 无感。跳过 RKP 后 `keystore2` 直接用内置 keybox 出证书 |
| **`rkp_only = true`** | **致命**。attestation 100% 依赖 RKP，跳过就永远没有证书 |

绝大多数小米机型属于前者，只有 `rkp_only` 机型会被这条补丁坑死。

---

## 工作原理

模块做两件事，都不涉及任何持久分区写入：

### 1. `post-fs-data.sh` —— 绕过 CN-skip 判断

```sh
resetprop ro.boot.hwc GL
```

`ro.boot.hwc` 是内核 cmdline 带出来的只读属性（`androidboot.hwc=CN`）。
`resetprop` 只在**属性服务**层面覆盖它，不改任何分区、不改 boot image。
`keystore2` 读到的就不再是 `CN`，于是正常走 RKP 流程。

> 判断条件已加保护：仅当当前值为 `CN` 时才修改。

### 2. `service.sh` —— 保证密钥能续期

```sh
device_config put remote_key_provisioning_native enable_rkpd true
```

实测发现这个值会在开机后被 ROM 内的某个系统服务重置回 `false`。
它为 `false` 时 `RemoteProvisioningService` 不会为密钥续期，
而 RKP 证书链有有效期（约 30 天）——**不处理的话 expiration 后 attestation 会再次失效**。

脚本在开机后 5 分钟内每 10 秒检查一次，发现被改回去就重新写 `true`；
没被改回去则不产生任何写入。

### 首次修复还需要手动清一次密钥池

模块本身**不会**自动清空 `rkpdapp` 的数据库。若你的设备此前被第三方工具污染过，
装完模块后建议执行一次：

```sh
su -c "pm clear com.android.rkpdapp"
su -c "am broadcast -a android.intent.action.BOOT_COMPLETED -n com.android.rkpdapp/.BootReceiver"
```

这会强制 `rkpdapp` 重新生成 CSR 并向 Google 申领证书链。
随后在日志里应能看到：

```
RkpdProvisioner: Requested number of keys for provisioning: 12
RkpdProvisioner: Total provisioned keys: 12
RkpdPeriodicProvisioner: Successfully provisioned ...IRemotelyProvisionedComponent/default
RkpdPeriodicProvisioner: Successfully provisioned ...IRemotelyProvisionedComponent/strongbox
```

> `.../avf` 组件可能报 `403 DICE mode must be normal`，这是 Android 虚拟化框架（pVM）
> 专用的 RKP 组件，**与日常 attestation 无关**，可以忽略。

---

## 安装

### 方式 A：刷入 zip（推荐）

1. 从 [最新 Release](https://github.com/DGGK2333/RKP-CN-Bypass/releases/latest) 下载 `RKP-CN-Bypass-*.zip`
2. 在 KernelSU / Magisk / APatch 管理器里「从本地安装」
3. 重启

### 方式 B：手动放置

```sh
su
mkdir -p /data/adb/modules/rkp_cn_bypass
# 把 module.prop / post-fs-data.sh / service.sh 复制进去
chmod 755 /data/adb/modules/rkp_cn_bypass
chmod 755 /data/adb/modules/rkp_cn_bypass/*.sh
```

然后重启。

### 安装后（关键）

如果之前 attestation 一直是坏的，**必须让 `rkpdapp` 重新申领一次**：

```sh
su -c "pm clear com.android.rkpdapp"
su -c "am broadcast -a android.intent.action.BOOT_COMPLETED -n com.android.rkpdapp/.BootReceiver"
```

等 30 秒左右，然后按下面「验证」逐项确认。

---

## 更新

模块内置更新检查：`module.prop` 的 `updateJson` 指向仓库根目录的
[`update.json`](update.json)，Magisk / KernelSU / APatch 管理器据此读取最新版本、
下载地址与更新日志。

- 有新版本时，管理器会在模块列表里提示，可直接在管理器内升级
- 也可以手动到 [Releases](https://github.com/DGGK2333/RKP-CN-Bypass/releases) 下载新 zip 覆盖安装
- 覆盖安装后无需重复执行 `pm clear com.android.rkpdapp`；重启一次即可

---

## 验证

### 1. TEE 本身是好的（排除硬件问题）

```sh
su -c "keystore_cli_v2 generate --name test_key"
```

期望输出中包含 `Hardware:` 段（`ORIGIN` / `OS_PATCHLEVEL` / `VENDOR_PATCHLEVEL` 等）。
如果这一步就失败，说明 TEE 真有问题，本模块无效。

### 2. CN-skip 绕过成功

```sh
getprop ro.boot.hwc
# 期望：GL

logcat -d --pid=$(pidof keystore2) | grep -c 'CN device with TEE level'
# 期望：0
```

### 3. keystore2 确实在用 RKP 密钥

```sh
logcat -d --pid=$(pidof keystore2) | grep -E 'with remote provisioned|without a provided'
```

| 输出 | 含义 |
|---|---|
| `with remote provisioned attestation key` | ✅ 正常，在用 RKP 签发的密钥 |
| `without a provided attestation key` | ❌ 还是没拿到，见[排障](#排障速查) |

### 4. 证书链是 Google 真签发的

```sh
strings /data/data/com.android.rkpdapp/databases/rkpd_database-wal \
  | grep -i -E 'Google LLC|privateca-content|Key Attestation CA1'
```

期望看到 Google 的 RKP 私有 CA 地址与 `Key Attestation CA1`。

### 5. 最终确认

打开 **Play Integrity API Checker**，应显示 3 绿：

- ✅ `MEETS_BASIC_INTEGRITY`
- ✅ `MEETS_DEVICE_INTEGRITY`
- ✅ `MEETS_STRONG_INTEGRITY`

---

## 排障速查

以后再变红，按顺序查：

```sh
# ① keystore2 的开关（来自 ROM，一般不变）
getprop remote_provisioning.enable_rkpd
# 期望：true

# ② rkpdapp 的续期开关
device_config get remote_key_provisioning_native enable_rkpd
# 期望：true。被改成 false 时手动执行：
#   su -c "device_config put remote_key_provisioning_native enable_rkpd true"

# ③ 模块是否生效
getprop ro.boot.hwc
# 期望：GL

# ④ 是否还在跳过 RKP
logcat -d --pid=$(pidof keystore2) | grep -c 'CN device with TEE level'
# 期望：0

# ⑤ 密钥池是否空了
logcat -d --pid=$(pidof com.android.rkpdapp) | grep -E 'PoolStats|Successfully provisioned|Error provisioning'
```

**常见故障对照：**

| 现象 | 原因 | 处理 |
|---|---|---|
| `ro.boot.hwc` 还是 `CN` | 模块没加载 | 确认 `/data/adb/modules/rkp_cn_bypass/` 下无 `disable` 文件，重启一次 |
| 出现 `without a provided` | 密钥池空了 / 又被打回 false | `pm clear com.android.rkpdapp` + 重新广播 BOOT_COMPLETED |
| `403 DICE mode must be normal`（**仅 avf**） | AVF 组件的 DICE 链不可用 | 无害，忽略 |
| `403 DICE mode must be normal`（**default**） | boot 镜像被改过，DICE 非 normal | 需要原厂 boot 镜像；本模块无效 |
| 日志里重新出现 `CN device with TEE level` | 模块被禁用或属性被别的模块抢改 | 检查模块顺序与冲突 |

---

## 卸载与回滚

### 卸载模块

```sh
su -c "rm -rf /data/adb/modules/rkp_cn_bypass"
```

重启后 `ro.boot.hwc` 自动恢复为 `CN`，attestation 回到修复前状态。

### 完整回滚（含配置项）

```sh
su -c "rm -rf /data/adb/modules/rkp_cn_bypass"
su -c "device_config put remote_key_provisioning_native enable_rkpd false"
su -c "setprop persist.device_config.remote_key_provisioning_native.enable_rkpd false"
# ro.boot.hwc 重启自动恢复 CN
```

> 已有的 RKP 证书链会留在 TEE 与数据库中。Google 签发的证书本身是真实有效的，
> 属于"设备正常运行产生的结果"，不属于伪造，保留它没有任何风险。

---

## 风险与免责

### 本模块做了什么 / 没做什么

| 做了 | 没做 |
|---|---|
| 修改运行时属性 `ro.boot.hwc` | ❌ 不写入 persist / boot / vbmeta 等任何分区 |
| 修改一个 DeviceConfig 开关 | ❌ 不烧录任何 keybox 或私钥 |
| — | ❌ 不伪造品牌/型号/序列号/IMEI |
| — | ❌ 不改变 Bootloader 锁状态 |
| — | ❌ 不修改 DICE 链或启动度量 |

证书链是 **Google 的 RKP 服务器基于本机真实 DICE 链签发的**，
设备身份完全真实，因此：

- 不会被 Google 风控判定为"伪造设备"
- 与网上那些"烧别人 keybox"的服务有本质区别
- 银行 App / 政企类应用的设备身份校验仍然有效

### 已知副作用

`ro.boot.hwc` 被改成 `GL` 后，**少数按区域判断的 MIUI/HyperOS 功能可能表现略有差异**
（如某些地区限定服务的入口）。实测日常使用无感，若发现异常可随时卸载模块。

### 免责声明

- 本模块仅供**在你自己拥有并控制的设备上恢复出厂应有的功能**使用
- 使用前请确保理解上述原理；因误用导致的任何后果（包括但不限于设备异常、
  App 风控、账号受限）由使用者自行承担
- 本模块不提供任何形式的担保
- 请勿用于绕过第三方服务的安全机制或进行欺诈

---

## 文件说明

```
.
├── module.prop              模块元信息（含 updateJson 更新检查地址）
├── post-fs-data.sh          开机早期执行：绕过 CN-skip 判断
├── service.sh               开机后期执行：保证 rkpd 续期开关为 true
├── customize.sh             安装时打印设备信息与权限设置
├── uninstall.sh             卸载提示（不做破坏性操作）
├── update.json              Magisk / KernelSU / APatch 更新检查数据
├── build.py                 打包脚本（生成刷入包与 SHA256SUMS）
├── CHANGELOG.md             完整更新日志
├── README.md                本文档
├── LICENSE                  MIT
├── .gitattributes           统一 LF 换行
├── .gitignore               忽略打包产物
└── .github/
    ├── workflows/
    │   ├── ci.yml           push / PR 时校验源码与刷入包
    │   └── release.yml      推送 v* 标签时自动打包并发布 Release
    └── ISSUE_TEMPLATE/
        └── bug_report.yml   问题反馈模板
```

> `dist/` 为打包输出目录，已被 `.gitignore` 忽略；刷入包统一从
> [Releases](https://github.com/DGGK2333/RKP-CN-Bypass/releases) 获取。

### 运行日志

```
/data/local/tmp/rkp_cn_bypass.log
```

---

## 开发与发布

### 本地打包

需要 Python 3.8+，无需其它依赖：

```sh
python3 build.py            # 生成 dist/RKP-CN-Bypass-<version>.zip 与 dist/SHA256SUMS
python3 build.py --verify   # 打包并校验模块结构、编码、update.json 与 CHANGELOG 一致性
```

打包规则：模块文件位于 zip 根目录、LF 换行、无 BOM、`.sh` 带可执行位、
固定时间戳以复现构建结果。

### 发布新版本

1. 修改 `module.prop`：`version`（如 `v1.2`）与递增的 `versionCode`
2. 同步 `update.json`：`version`、`versionCode`、`zipUrl`（指向新标签的 Release 附件）
3. 在 `CHANGELOG.md` 增加 `## v1.2` 小节
4. 运行 `python3 build.py --verify` 确认全部校验通过
5. 提交并推送标签：

   ```sh
   git commit -am "release: v1.2"
   git tag v1.2
   git push origin main --tags
   ```

6. `.github/workflows/release.yml` 会自动打包、校验并创建 Release，
   上传 `RKP-CN-Bypass-v1.2.zip` 与 `SHA256SUMS`

---

## 更新日志

完整记录见 [CHANGELOG.md](CHANGELOG.md)。

### v1.1

- 新增 `service.sh`：防止 `enable_rkpd` 在开机后被 ROM 重置为 `false`
  （否则约 30 天后密钥过期，attestation 会再次失效）
- `post-fs-data.sh` 增加条件判断，仅当 `ro.boot.hwc == CN` 时才修改
- 增加 `customize.sh` / `uninstall.sh`，改进安装体验
- 完善文档

### v1.0

- 首个版本：通过 `resetprop ro.boot.hwc GL` 绕过
  `keystore2` 的 "CN device with TEE level, skipping RKP" 补丁


---

## 排查案例记录

本模块的原理来自一次完整的实机排查，关键证据如下（供后来者参考）：

| 证据 | 含义 |
|---|---|
| `QSEE - Image Loaded, Delta - (4225484 Bytes)`（blackbox 分区） | TEE 镜像加载完整 |
| `LoadSecureApps: ... Status = 0x0, AppId = 4294967297` | keymaster TA 加载成功 |
| `keystore_cli_v2 generate` 输出 `Hardware:` 段 | TEE 能正常生成硬件密钥 |
| `dumpsys remote_provisioning` 返回 `hwVersion=3 uniqueId=...` | RKP HAL 正常应答 |
| Google 为 `default` 组件签发 12 把密钥 | **Google 侧 DICE 校验通过**，启动链在 TEE 看来是 normal |
| `remote_provisioning.rs:88 - CN device with TEE level, skipping RKP` | 真正的病根 |

即：**TEE 从头到尾都是好的，坏的只是软件允许它工作的那条路径。**

---

## License

[MIT](LICENSE)
