#!/system/bin/sh
# ==============================================================================
#  RKP CN Bypass - service
#
#  作用：确保 DeviceConfig 里的
#        remote_key_provisioning_native/enable_rkpd = true
#
#  原因：实测发现该值会在开机后被 ROM 内的某个系统服务重置回 false。
#        它为 false 时 RemoteProvisioningService 不会为密钥续期，
#        现有 RKP 证书链约 30 天到期后 attestation 会再次失效。
#
#  做法：开机后 5 分钟内每 10 秒检查一次，发现被改回去就重新写 true。
#        这次没被改回去就不会产生任何写入。
# ==============================================================================
MODDIR=${0%/*}
LOG=/data/local/tmp/rkp_cn_bypass.log

RP=/data/adb/ksu/bin/resetprop
[ -x "$RP" ] || RP=$(command -v resetprop 2>/dev/null)
[ -n "$RP" ] || RP=resetprop

DEVCFG=/system/bin/device_config
[ -x "$DEVCFG" ] || DEVCFG=$(command -v device_config 2>/dev/null)

(
    i=0
    while [ $i -lt 30 ]; do
        CUR=$($DEVCFG get remote_key_provisioning_native enable_rkpd 2>/dev/null)
        if [ "$CUR" != "true" ]; then
            $RP persist.device_config.remote_key_provisioning_native.enable_rkpd true 2>/dev/null
            $DEVCFG put remote_key_provisioning_native enable_rkpd true 2>/dev/null
            echo "[RKP-CN-Bypass] $(date '+%F %T') enable_rkpd: ${CUR:-null} -> true" >> "$LOG"
        fi
        i=$((i + 1))
        sleep 10
    done
) &

exit 0
