#!/system/bin/sh
# ==============================================================================
#  RKP CN Bypass - post-fs-data
#
#  作用：绕过小米 keystore2 的私有补丁
#        keystore2 / remote_provisioning.rs:88
#        "CN device with TEE level, skipping RKP to avoid timeout blocking."
#
#  该补丁的判断依据是 ro.boot.hwc == "CN"。把它改成 "GL" 后，
#  keystore2 就会正常去 rkpdapp 取 RKP 签发的 attestation 密钥。
#
#  注意：resetprop 只改运行时属性，不写入任何分区，重启后由本脚本再次设置。
# ==============================================================================
MODDIR=${0%/*}
LOG=/data/local/tmp/rkp_cn_bypass.log

RP=/data/adb/ksu/bin/resetprop
[ -x "$RP" ] || RP=$(command -v resetprop 2>/dev/null)
[ -n "$RP" ] || RP=resetprop

HWC=$(getprop ro.boot.hwc 2>/dev/null)

if [ "$HWC" = "CN" ]; then
    $RP ro.boot.hwc GL 2>/dev/null
    NOW=$(getprop ro.boot.hwc 2>/dev/null)
    echo "[RKP-CN-Bypass] $(date '+%F %T') ro.boot.hwc: CN -> ${NOW}" >> "$LOG"
else
    echo "[RKP-CN-Bypass] $(date '+%F %T') ro.boot.hwc=${HWC}，无需修改" >> "$LOG"
fi

exit 0
