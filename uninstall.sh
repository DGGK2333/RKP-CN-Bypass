#!/system/bin/sh
# ==============================================================================
#  RKP CN Bypass - 卸载
#
#  本脚本不做任何破坏性操作。
#  卸载后 ro.boot.hwc 会在下次重启时自动恢复为 CN，
#  attestation 会回到未修复状态（如果确实需要回滚，这是预期行为）。
#
#  可选：把 rkpdapp 的续期开关也恢复成关闭状态
#    device_config put remote_key_provisioning_native enable_rkpd false
# ==============================================================================
LOG=/data/local/tmp/rkp_cn_bypass.log
echo "[RKP-CN-Bypass] $(date '+%F %T') 模块已卸载，重启后 ro.boot.hwc 恢复为 CN" >> "$LOG"
exit 0
