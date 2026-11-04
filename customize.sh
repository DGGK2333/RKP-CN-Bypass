#!/system/bin/sh
# ==============================================================================
#  RKP CN Bypass - 安装提示
#  （Magisk 提供 ui_print，KernelSU 可能没有，这里做兼容）
# ==============================================================================
command -v ui_print >/dev/null 2>&1 || ui_print() { echo "$1"; }

ui_print "*******************************************"
ui_print "  RKP CN Bypass v1.1"
ui_print "  绕过小米 keystore2 的 CN-skip-RKP 补丁"
ui_print "*******************************************"
ui_print " "
ui_print "- 机型          : $(getprop ro.product.model)"
ui_print "- 设备代号      : $(getprop ro.product.device)"
ui_print "- Android       : $(getprop ro.build.version.release)"
ui_print "- ro.boot.hwc   : $(getprop ro.boot.hwc)"
ui_print "- rkp_only      : $(getprop odm.xiaomi.security.tee.rkp_only)"
ui_print " "
ui_print "- 本模块不修改任何分区 / 不写入密钥 / 不改变 BL 状态"
ui_print "- 重启后生效"
ui_print "*******************************************"

set_perm_recursive "$MODPATH" 0 0 0755 0644 2>/dev/null
set_perm "$MODPATH/post-fs-data.sh" 0 0 0755 2>/dev/null
set_perm "$MODPATH/service.sh" 0 0 0755 2>/dev/null

exit 0
