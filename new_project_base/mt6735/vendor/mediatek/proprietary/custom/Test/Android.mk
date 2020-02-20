LOCAL_PATH:= $(call my-dir)
ifeq ($(MTK_PROJECT), Test)
include $(call all-makefiles-under,$(LOCAL_PATH))
endif
