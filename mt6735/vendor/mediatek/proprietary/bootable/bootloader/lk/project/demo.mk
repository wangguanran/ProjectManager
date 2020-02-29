LOCAL_DIR := $(GET_LOCAL_DIR)
TARGET := demo
MODULES += app/mt_boot \
           dev/lcm
MTK_EMMC_SUPPORT = yes
DEFINES += MTK_NEW_COMBO_EMMC_SUPPORT
MTK_KERNEL_POWER_OFF_CHARGING = yes
MTK_PUMP_EXPRESS_SUPPORT := yes
MTK_LCM_PHYSICAL_ROTATION = 0
# Vanzo:yucheng on: Thu, 05 Mar 2015 18:33:38 +0800
# use new config way
#CUSTOM_LK_LCM="hx8392a_dsi_cmd_qhd"
#hx8392a_dsi_cmd = yes
# End of Vanzo:yucheng
#FASTBOOT_USE_G_ORIGINAL_PROTOCOL = yes
MTK_SECURITY_SW_SUPPORT = yes
MTK_VERIFIED_BOOT_SUPPORT = yes
MTK_SEC_FASTBOOT_UNLOCK_SUPPORT = yes
DEBUG := 0
BOOT_LOGO:=qhd
#DEFINES += WITH_DEBUG_DCC=1
DEFINES += WITH_DEBUG_UART=1
#DEFINES += WITH_DEBUG_FBCON=1
#DEFINES += MACH_FPGA=y
#DEFINES += SB_LK_BRINGUP=y
DEFINES += MTK_GPT_SCHEME_SUPPORT
#DEFINES += MACH_FPGA_NO_DISPLAY=y
#MTK_EFUSE_DOWNGRADE = yes
MTK_GOOGLE_TRUSTY_SUPPORT=no
# Vanzo:yucheng on: Tue, 11 Nov 2014 10:11:08 +0800
project_name:=$(shell echo $(VANZO_INNER_PROJECT_NAME))
#CUSTOM_LK_LCM="hx8392a_dsi_cmd"
ifeq ($(strip $(project_name)),)
CUSTOM_LK_LCM="hx8392a_dsi_cmd"
endif
-include ../../../../../../zprojects/$(project_name)/$(project_name).mk

ifeq ($(strip $(project_name)),)
BOOT_LOGO := cmcc_lte_hd720
else
BOOT_LOGO := $(BOOT_LOGO)
endif
# End of Vanzo:yucheng
# Vanzo:yucheng on: Tue, 11 Nov 2014 18:14:52 +0800
# support the aosp management

-include ../../../../../../zprojects/$(project_name)/$(project_name).mk
project_defines:=$(shell echo \
             $(CONFIG_CUSTOM_KERNEL_FLASHLIGHT) \
             $(CONFIG_CUSTOM_KERNEL_LCM) \
             $(CONFIG_CUSTOM_KERNEL_IMGSENSOR) | tr a-z A-Z)


DEFINES += $(project_defines)

ifneq ($(strip $(project_name)),)
MTK_INTERNAL_CDEFS := $(foreach t,$(AUTO_ADD_GLOBAL_DEFINE_BY_NAME),$(if $(filter-out no NO none NONE false FALSE,$($(t))),$(t))) 
MTK_INTERNAL_CDEFS += $(foreach t,$(AUTO_ADD_GLOBAL_DEFINE_BY_VALUE),$(if $(filter-out no NO none NONE false FALSE,$($(t))),$(foreach v,$(shell echo $($(t)) | tr '[a-z]' '[A-Z]'),$(v)))) 
#MTK_INTERNAL_CDEFS += $(foreach t,$(AUTO_ADD_GLOBAL_DEFINE_BY_NAME_VALUE),$(if $(filter-out no NO none NONE false FALSE,$($(t))),$(t)=\"$($(t))\")) 
DEFINES += $(MTK_INTERNAL_CDEFS)

VANZO_INTERNAL_CDEFS := $(foreach t,$(VANZO_DEFINE_BY_NAME),$(if $(filter-out no NO none NONE false FALSE,$($(t))),$(t))) 
VANZO_INTERNAL_CDEFS += $(foreach t,$(VANZO_DEFINE_BY_VALUE),$(if $(filter-out no NO none NONE false FALSE,$($(t))),$(foreach v,$(shell echo $($(t)) | tr '[a-z]' '[A-Z]'),$(v)))) 
VANZO_INTERNAL_CDEFS += $(foreach t,$(VANZO_DEFINE_BY_NAME_VALUE),$(if $(filter-out no NO none NONE false FALSE,$($(t))),$(t)=\"$($(t))\")) 

DEFINES += $(VANZO_INTERNAL_CDEFS)
endif

# End of Vanzo:yucheng
