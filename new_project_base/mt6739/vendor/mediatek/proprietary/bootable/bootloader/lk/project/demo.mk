#
LOCAL_DIR := $(GET_LOCAL_DIR)
TARGET := Test
MODULES += app/mt_boot \
           dev/lcm
PMIC_CHIP := MT6357
ifeq ($(findstring PMIC_CHIP, $(strip $(DEFINES))),)
DEFINES += PMIC_CHIP_$(shell echo $(PMIC_CHIP) | tr '[a-z]' '[A-Z]')
endif
MTK_UFS_BOOTING = no
MTK_EMMC_SUPPORT = yes
MTK_KERNEL_POWER_OFF_CHARGING = yes
MTK_SMI_SUPPORT = yes
DEFINES += MTK_NEW_COMBO_EMMC_SUPPORT
DEFINES += MTK_GPT_SCHEME_SUPPORT
MTK_PUMP_EXPRESS_PLUS_SUPPORT := no
MTK_RT9458_SUPPORT := yes
MTK_CHARGER_INTERFACE := yes
MTK_LCM_PHYSICAL_ROTATION = 0
CUSTOM_LK_LCM="nt35521_hd_dsi_vdo_truly_nt50358"
#nt35595_fhd_dsi_cmd_truly_nt50358 = yes
#FASTBOOT_USE_G_ORIGINAL_PROTOCOL = yes
MTK_SECURITY_SW_SUPPORT = yes
MTK_VERIFIED_BOOT_SUPPORT = no
MTK_SEC_FASTBOOT_UNLOCK_SUPPORT = yes
SPM_FW_USE_PARTITION = yes
BOOT_LOGO := hd720
DEFINES += MTK_LCM_PHYSICAL_ROTATION_HW
DEBUG := 2
#DEFINES += WITH_DEBUG_DCC=1
DEFINES += WITH_DEBUG_UART=1
#DEFINES += WITH_DEBUG_FBCON=1
CUSTOM_LK_USB_UNIQUE_SERIAL=no
MTK_TINYSYS_SCP_SUPPORT = no
MTK_TINYSYS_SSPM_SUPPORT = no
#DEFINES += NO_POWER_OFF=y
#DEFINES += FPGA_BOOT_FROM_LK=y
MTK_PROTOCOL1_RAT_CONFIG=C/Lf/Lt/W/T/G
MTK_GOOGLE_TRUSTY_SUPPORT = no
MCUPM_FW_USE_PARTITION = yes
# Vanzo:linmaobin on: Tue, 11 Nov 2014 10:11:08 +0800
# support the aosp management
project_name:=$(shell echo $(VANZO_INNER_PROJECT_NAME))
-include ../../../../../../zprojects/$(project_name)/$(project_name).mk
ifeq ($(strip $(project_name)),)
BOOT_LOGO := hd720
else
BOOT_LOGO := $(BOOT_LOGO)
endif
-include ../../../../../../zprojects/$(project_name)/$(project_name).mk
project_defines:=$(shell echo \
             $(CONFIG_CUSTOM_KERNEL_FLASHLIGHT) \
             $(CONFIG_CUSTOM_KERNEL_LCM) \
             $(CONFIG_CUSTOM_KERNEL_IMGSENSOR) | tr a-z A-Z)

DEFINES += $(project_defines)
ifneq ($(strip $(project_name)),)
MTK_INTERNAL_CDEFS := $(foreach t,$(AUTO_ADD_GLOBAL_DEFINE_BY_NAME),$(if $(filter-out no NO none NONE false FALSE,$($(t))),$(t)))
MTK_INTERNAL_CDEFS += $(foreach t,$(AUTO_ADD_GLOBAL_DEFINE_BY_VALUE),$(if $(filter-out no NO none NONE false FALSE,$($(t))),$(foreach v,$(shell echo $($(t)) | tr '[a-z]' '[A-Z]'),$(v))))
DEFINES += $(MTK_INTERNAL_CDEFS)
VANZO_INTERNAL_CDEFS := $(foreach t,$(VANZO_DEFINE_BY_NAME),$(if $(filter-out no NO none NONE false FALSE,$($(t))),$(t)))
VANZO_INTERNAL_CDEFS += $(foreach t,$(VANZO_DEFINE_BY_VALUE),$(if $(filter-out no NO none NONE false FALSE,$($(t))),$(foreach v,$(shell echo $($(t)) | tr '[a-z]' '[A-Z]'),$(v))))
VANZO_INTERNAL_CDEFS += $(foreach t,$(VANZO_DEFINE_BY_NAME_VALUE),$(if $(filter-out no NO none NONE false FALSE,$($(t))),$(t)=\"$($(t))\"))
DEFINES += $(VANZO_INTERNAL_CDEFS)
endif
# End of Vanzo:linmaobin
