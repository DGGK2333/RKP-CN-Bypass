# RKP CN Bypass

[![Release](https://img.shields.io/github/v/release/DGGK2333/RKP-CN-Bypass?style=flat-square&label=release)](https://github.com/DGGK2333/RKP-CN-Bypass/releases/latest)
[![License](https://img.shields.io/github/license/DGGK2333/RKP-CN-Bypass?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Magisk%20%7C%20KernelSU%20%7C%20APatch-4B8BBE?style=flat-square)](#安装)
[![Android](https://img.shields.io/badge/Android-12%2B-3DDC84?style=flat-square&logo=android&logoColor=white)](#适用范围)

> 修复小米国行（CN）ROM 上 **`rkp_only` 机型的 Key Attestation 永久失效**问题
> —— 在作者单机环境中让 Play Integrity 从「全红 / UNEVALUATED」恢复为 **3 绿**。
> 该结果受机型、ROM、启动状态与 Google 策略影响，**不是普遍承诺**。

**不写分区 · 不烧 keybox · 不伪造设备身份 · 不改变 Bootloader 状态。**

> [!IMPORTANT]
> **证据边界**：本模块的根因分析来自**单台设备的实机排查**（logcat、`keystore2` 二进制字符串与运行行为），
> 尚未与小米官方源码或多机型交叉验证；文中「为什么」的解释属于**有证据支撑的推断**，不是上游源码结论。
> 因此本模块**不承诺**在任何机型 / ROM 上恢复 Key Attestation，也**不是**通用的 Play Integrity
> 修复或绕过工具。「恢复 RKP 流程」不等于「证书链有效」，更不等于「Play Integrity 判定通过」。

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

- Not a universal Play Integrity fix: on unlocked or "fake-relocked" devices, on devices with an
  abnormal DICE / verified-boot state, or with keybox-injection setups, it is not expected to help.
- Evidence is single-device and observational; see [`TESTING.md`](TESTING.md) for the test matrix.
- Tested for research and personal device restoration only; use at your own risk.
- Certificates are genuinely signed by Google's RKP servers for your device's real DICE
  chain — no keybox, no spoofed hardware identity.
- Not affiliated with Xiaomi or Google.

</details>

---

## 目录

- [症状](#症状)
- [适用范围](#适用范围)
- [已知限制](#已知限制)
- [根因](#根因)
- [工作原理](#工作原理)
- [安装](#安装)
- [更新](#更新)
- [验证](#验证)
- [排障速查](#排障速查)
- [卸载与回滚](#卸载与回滚)
- [风险与免责](#风险与免责)
- [文件说明](#文件说明)
- [测试矩阵](#测试矩阵)
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

> 上表条件来自作者单机实测与公开资料整理，**未在所有机型上验证**；测试记录见 [TESTING.md](TESTING.md)。
> 若你的设备不满足上述条件，本模块没有意义。

---

## 已知限制

以下情况本模块**无效，或不应期待其生效**：

- **非小米 / 红米设备**：其它厂商的 `keystore2` 没有这个 CN-skip 补丁
- **TEE 真的损坏**（TZ/QSEE 崩溃、TA 加载失败、硬件密钥生成失败）——本模块不修复 TEE
- **解锁 / 伪回锁设备**：`resetprop` 只改 userspace 属性，改变不了 TEE 基于真实启动过程产出的 DICE 链；
  Play Integrity 的 `DEVICE` / `STRONG` 判定依赖 TEE 证明，本模块**不用于、也不能实现**
  「让伪回锁设备通过完整性校验」这一目的
- **KeyMint / TA 协议层异常**：如 `invalid_ta_response`、`unsupported EEK curve: 0`，
  发生在 CN-skip 之前的环节，本模块无法修复
- **修改过 `boot.img` / 启动链**（GKI 模式 KSU、改签内核等）导致 DICE 非 `normal`：Google 会拒签
- **已注入第三方 keybox**（Tricky Store 等）：走的是 `keystore2` 拦截 / keybox 路径而非 RKP，
  本模块不会修复它，还可能改变现有行为
- **跨区 / 混刷固件**，或 TA 与 boot 版本不匹配：应优先恢复与原厂一致的固件组合，而不是更换属性

---

## 根因

这个问题由**四层因素叠加**造成，缺一层都不会触发。先说明每一层结论的证据等级：

| 结论 | 证据来源 | 证据等级 |
|---|---|---|
| 小米 `keystore2` 在国行 ROM 上跳过 RKP | logcat 中的 `remote_provisioning.rs:88` 告警 + 二进制字符串 | 运行时观察（未核验小米源码） |
| `ro.boot.hwc` 是该判断的输入 | 修改该属性后告警消失、行为改变 | 间接证据（单机） |
| `rkp_only` 机型 attestation 只能依赖 RKP | 属性定义 + 跳过 RKP 后报 `ATTESTATION_KEYS_NOT_PROVISIONED` | 单机实证 |
| 该补丁是**唯一 / 主要**原因 | — | **推断**，未排除其它因素 |

以下「层」是作者在该故障案例中观察到的因果链，不是对任意机型的普适结论。

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

日志中的 `remote_provisioning.rs:88` 行号来自 Rust `warn!` 宏自带的源码位置，
**并非已核验的小米源码**；作者也没有在仓库中附带对应 ROM 版本的源码或反编译证据。
因此这一层应理解为：**基于运行时日志与二进制字符串的推断**。逻辑推断为：

```rust
if getprop("ro.boot.hwc") == "CN" && security_level == TEE {
    // 国行 ROM 访问 Google RKP 服务器要绕小米代理，首次开机可能长时间阻塞
    // 小米的解法：干脆不打 attestation 证书
    warn!("CN device with TEE level, skipping RKP to avoid timeout blocking.");
    return;   // 直接跳过 RKP
}
```

**在该案例中，即使证书链已经签好放在数据库里，`keystore2` 也拒绝去取。**

运行时日志里每个 attestation 请求旁边都会伴随这一行：

```
W keystore2: .../remote_provisioning.rs:88 - CN device with TEE level, skipping RKP to avoid timeout blocking.
E keystore2: Error::Km(r#ATTESTATION_KEYS_NOT_PROVISIONED)
```

### 第 4 层：结果

TEE 里永远没有 attestation 密钥 → 所有需要证书链的操作全部失败。

### 为什么"回锁 Bootloader"没用

**在作者观察到的这个故障模型里，这四层都与 BL 锁定状态无关。**

- 回锁只改变 `verifiedbootstate`（orange → green）
- 而 `ATTESTATION_KEYS_NOT_PROVISIONED` 是 TEE **内部密钥缺失**，回锁无法凭空造出证书链
- 所以在该模型下，「真回锁后依然报错」是预期结果，不是操作失误

> 这不等于「所有 attestation 失败都与 BL 无关」。如果失败发生在 DICE / 启动状态层
> （如 `403 DICE mode must be normal`），问题就在启动链，需要恢复原厂 boot 镜像。

### 为什么别的国行小米用户体验不到这个问题

| 机型类型 | CN-skip 的影响 |
|---|---|
| **有内置 keybox** | 无感。跳过 RKP 后 `keystore2` 直接用内置 keybox 出证书 |
| **`rkp_only = true`** | **致命**。attestation 密钥只能来自 RKP，跳过就永远没有证书 |

根据公开讨论与作者观察，多数小米机型属于前者，只有 `rkp_only` 机型会受这条补丁严重影响；
该分布**未做全量统计**。

---

## 工作原理

模块做两件事。修改范围需要说清楚：

| 范围 | 说明 |
|---|---|
| **不修改** | boot / vbmeta / persist / super 等系统或启动分区镜像 |
| **会写入** | `/data` 下的持久化配置：`persist.device_config.*` 属性与 DeviceConfig 存储 |
| **卸载后** | 上述持久化配置**不会自动回滚**，需要按[卸载与回滚](#卸载与回滚)手动清理 |

### 1. `post-fs-data.sh` —— 绕过 CN-skip 判断

```sh
resetprop ro.boot.hwc GL
```

`ro.boot.hwc` 是内核 cmdline 带出来的只读属性（`androidboot.hwc=CN`）。
`resetprop` 只在**属性服务**层面覆盖它，不改任何分区镜像、不改 boot image；
但这一覆盖本身是运行时的，重启后由本脚本再次设置。
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

> [!WARNING]
> `pm clear com.android.rkpdapp` 是**有副作用的操作**：它会清空该应用的全部数据
> （包括密钥池元数据与配置），且重新申领需要设备能访问 Google 的 RKP 服务。
> 执行前建议先记录当前状态并备份 `rkpdapp` 数据库，确认可以接受清空后再操作。
> `am broadcast ... BOOT_COMPLETED` 只是模拟一次开机广播，**不等同于一次真实系统启动**。

如果之前 attestation 一直是坏的，可尝试让 `rkpdapp` 重新申领一次：

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

验证分 6 层。**不要**把「脚本执行成功」或「属性改成功」当成「TEE 修复成功」：
本仓库目前只有作者单机证据，未验证的部分会明确标注。

| 层级 | 检查内容 | 证据状态 |
|---|---|---|
| 1. KeyMint / TEE | 能否生成硬件密钥 | 作者单机实测通过 |
| 2. keystore2 | CN-skip 是否被绕过 | 作者单机实测通过 |
| 3. RKPD | 密钥申领与续期 | 作者单机实测（部分） |
| 4. RKP HAL | `dumpsys remote_provisioning` | 作者单机实测 |
| 5. 证书链 | 完整性 / 签名 / 是否绑定本机 | **未完成严谨验证**（见下） |
| 6. Play Integrity | 三项判定 | 仅作者单机观察，**不构成普遍结论** |

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

### 4. 证书链是否存在

```sh
strings /data/data/com.android.rkpdapp/databases/rkpd_database-wal \
  | grep -i -E 'Google LLC|privateca-content|Key Attestation CA1'
```

> [!NOTE]
> `strings` 只能证明「数据库里出现过相关字符串」，**不能**证明：证书链完整、
> 签名有效、证书绑定本机、或 TEE 能正常使用它。
> 更严谨的做法是从 keystore 导出证书，用 `openssl` / `keytool` 校验证书链签名与有效期，
> 并核对证书中的 device ID 是否与本机匹配。这一项在本仓库中仍属**未完成验证**。

### 5. 最终确认（条件性）

在设备**真实锁定**、DICE 链为 `normal`、且 Play Integrity 其它前置条件满足时，
**可能**看到：

- `MEETS_BASIC_INTEGRITY`
- `MEETS_DEVICE_INTEGRITY`
- `MEETS_STRONG_INTEGRITY`

> 本模块**不承诺**这一结果。若设备处于解锁 / 伪回锁状态、启动链被修改，
> 或证书链本身无效，`DEVICE` / `STRONG` 仍会失败，且这不是本模块能修复的。

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

**先按层次定位异常**（`ATTESTATION_KEYS_NOT_PROVISIONED` 只是最终表现，不能单独归因）：

| 层次 | 典型信号 |
|---|---|
| KeyMint / TA | `invalid_ta_response`、`unsupported EEK curve: 0`、`Failed to generate key pair` |
| keystore2 | `CN device with TEE level`、`ATTESTATION_KEYS_NOT_PROVISIONED` |
| RKPD | `PoolStats`、`Error provisioning`、`403` |
| RKP HAL | `dumpsys remote_provisioning` 无应答或异常 |
| 网络 | 超时、403、代理阻断 |
| DICE / 启动状态 | `403 DICE mode must be normal` |

**常见故障对照：**

| 现象 | 原因 | 处理 |
|---|---|---|
| `ro.boot.hwc` 还是 `CN` | 模块没加载 | 确认 `/data/adb/modules/rkp_cn_bypass/` 下无 `disable` 文件，重启一次 |
| 出现 `without a provided` | 密钥池空了 / 又被打回 false | `pm clear com.android.rkpdapp` + 重新广播 BOOT_COMPLETED（注意副作用） |
| `403 DICE mode must be normal`（**仅 avf**） | AVF 组件的 DICE 链不可用 | 无害，忽略 |
| `403 DICE mode must be normal`（**default**） | boot 镜像被改过，DICE 非 normal | 需要原厂 boot 镜像；本模块无效 |
| `invalid_ta_response` / `unsupported EEK curve: 0` | KeyMint / TA 协议层异常 | 本模块无法修复，需排查固件 / TA 版本匹配 |
| 日志里重新出现 `CN device with TEE level` | 模块被禁用或属性被别的模块抢改 | 检查模块顺序与冲突 |

---

## 卸载与回滚

### 卸载模块

```sh
su -c "rm -rf /data/adb/modules/rkp_cn_bypass"
```

重启后 `ro.boot.hwc` 自动恢复为 `CN`，attestation 回到修复前状态。

### 完整回滚（含配置项）

> `uninstall.sh` 只写卸载日志，**不会自动回滚** DeviceConfig / persist 配置。
> 需要完整回滚时，手动执行下面的命令。

```sh
su -c "rm -rf /data/adb/modules/rkp_cn_bypass"
su -c "device_config put remote_key_provisioning_native enable_rkpd false"
su -c "setprop persist.device_config.remote_key_provisioning_native.enable_rkpd false"
# ro.boot.hwc 重启后自动恢复为 CN
```

> 已签发的 RKP 证书链会留在 TEE 与数据库中。Google 签发的证书本身是真实有效的，
> 不属于伪造；但「保留它没有任何风险」的说法过于绝对——ROM 升级、Google 策略变化后
> 证书链可能失效，应用侧也可能因整体环境异常而拒绝服务。是否保留由你自行判断。

---

## 风险与免责

### 本模块做了什么 / 没做什么

| 做了 | 没做 |
|---|---|
| 修改运行时属性 `ro.boot.hwc` | ❌ 不写入 boot / vbmeta 等启动分区镜像 |
| 修改 DeviceConfig 开关与对应 persist 属性 | ❌ 不烧录任何 keybox 或私钥 |
| — | ❌ 不伪造品牌/型号/序列号/IMEI |
| — | ❌ 不改变 Bootloader 锁状态 |
| — | ❌ 不修改 DICE 链或启动度量 |

> 注意：上表「不写分区」指的是不修改系统 / 启动分区镜像；`/data` 下的持久化配置
> 仍会被写入，且卸载后不会自动回滚，见[工作原理](#工作原理)与[卸载与回滚](#卸载与回滚)。

证书链是 **Google 的 RKP 服务器基于本机真实 DICE 链签发的**，不伪造品牌 / 型号 / 序列号，
也不注入别人的 keybox。但「证书内容真实」不等于「所有服务都会接受」：

- Google 的策略、Play Integrity 判定规则、ROM 版本都可能变化，证书链可能在更新后失效
- 应用侧风控不只看证书链，也看整体设备环境，结果无法保证
- 在解锁 / 伪回锁设备上使用本模块，属于掩盖真实的启动状态，可能违反相关服务条款，
  本仓库不为此背书

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
├── TESTING.md               测试矩阵、证据采集清单与失败案例模板
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

## 测试矩阵

目前只有作者单机记录，兼容性结论**仍待更多样本验证**。完整的测试矩阵、分层证据采集命令
与失败案例模板见 [TESTING.md](TESTING.md)，欢迎按模板提交记录（请先去掉 IMEI / 序列号 /
账号 / token 等敏感信息）。

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

### 未发布（文档修订，无模块行为变更）

- 补充证据边界声明、已知限制、分层验证状态、持久化范围与风险说明
- 把「Play Integrity 三绿」等结论条件化，不再作为普遍承诺
- 新增 [TESTING.md](TESTING.md)：测试矩阵、分层证据采集与失败案例模板
- 修正 `pm clear com.android.rkpdapp` 的副作用说明

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

以下证据来自**作者单台设备**的一次实机排查，未与小米源码或多机型交叉对照，
仅作为诊断思路与线索记录，**不作为普适结论**：

| 证据 | 含义 |
|---|---|
| `QSEE - Image Loaded, Delta - (4225484 Bytes)`（blackbox 分区） | TEE 镜像加载完整 |
| `LoadSecureApps: ... Status = 0x0, AppId = 4294967297` | keymaster TA 加载成功 |
| `keystore_cli_v2 generate` 输出 `Hardware:` 段 | TEE 能正常生成硬件密钥 |
| `dumpsys remote_provisioning` 返回 `hwVersion=3 uniqueId=...` | RKP HAL 正常应答 |
| Google 为 `default` 组件签发 12 把密钥 | 在该案例中 Google 侧 DICE 校验通过 |
| `remote_provisioning.rs:88 - CN device with TEE level, skipping RKP` | 作者判断的病根（运行时证据，未核验源码） |

即：在该案例中，**TEE 本身工作正常，失效的是软件允许它工作的那条路径**。
但这不能反推「所有 `ATTESTATION_KEYS_NOT_PROVISIONED` 都是同一个原因」——见[已知限制](#已知限制)。

---

## License

[MIT](LICENSE)
