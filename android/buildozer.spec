[app]
title = Sequential Clicker
package.name = sequentialclicker
package.domain = org.sequentialclicker
source.dir = .
source.include_exts = py,kv,json,md,xml,java
version = 0.1
requirements = python3,kivy,kivymd,pyjnius
orientation = portrait
fullscreen = 0

android.permissions = FOREGROUND_SERVICE,POST_NOTIFICATIONS
android.accept_sdk_license = True
android.api = 33
android.minapi = 26
android.ndk_api = 26
android.archs = arm64-v8a,armeabi-v7a
android.allow_backup = True
android.private_storage = True

android.add_src = android_src
android.add_resources = android_res
android.extra_manifest_xml = manifest_extras.xml

[buildozer]
log_level = 2
warn_on_root = 1
