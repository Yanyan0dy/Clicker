from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from kivy.utils import platform


@dataclass(frozen=True, slots=True)
class AndroidIds:
    package_name: str
    accessibility_service: str


def ids() -> AndroidIds:
    return AndroidIds(
        package_name="org.sequentialclicker.sequentialclicker",
        accessibility_service="org.sequentialclicker.sequentialclicker.ClickerAccessibilityService",
    )


def _jnius():
    if platform != "android":
        return None
    try:
        from jnius import autoclass  # type: ignore

        return autoclass
    except Exception:  # noqa: BLE001
        return None


def get_activity():
    autoclass = _jnius()
    if autoclass is None:
        return None
    try:
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        return PythonActivity.mActivity
    except Exception:  # noqa: BLE001
        return None


def is_accessibility_enabled() -> bool:
    activity = get_activity()
    autoclass = _jnius()
    if activity is None or autoclass is None:
        return False
    try:
        SettingsSecure = autoclass("android.provider.Settings$Secure")
        TextUtils = autoclass("android.text.TextUtils")
        enabled = SettingsSecure.getInt(activity.getContentResolver(), SettingsSecure.ACCESSIBILITY_ENABLED)
        if enabled != 1:
            return False
        enabled_services = SettingsSecure.getString(
            activity.getContentResolver(), SettingsSecure.ENABLED_ACCESSIBILITY_SERVICES
        )
        if TextUtils.isEmpty(enabled_services):
            return False
        full = f"{ids().package_name}/{ids().accessibility_service}"
        return full in str(enabled_services)
    except Exception:  # noqa: BLE001
        return False


def open_accessibility_settings() -> None:
    activity = get_activity()
    autoclass = _jnius()
    if activity is None or autoclass is None:
        return
    try:
        Intent = autoclass("android.content.Intent")
        Settings = autoclass("android.provider.Settings")
        intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
        activity.startActivity(intent)
    except Exception:  # noqa: BLE001
        return


def send_click(x: int, y: int) -> bool:
    activity = get_activity()
    autoclass = _jnius()
    if activity is None or autoclass is None:
        return False
    try:
        Intent = autoclass("android.content.Intent")
        intent = Intent("org.sequentialclicker.ACTION_CLICK")
        intent.putExtra("x", int(x))
        intent.putExtra("y", int(y))
        activity.sendBroadcast(intent)
        return True
    except Exception:  # noqa: BLE001
        return False


def start_foreground_service() -> bool:
    activity = get_activity()
    autoclass = _jnius()
    if activity is None or autoclass is None:
        return False
    try:
        Intent = autoclass("android.content.Intent")
        Build = autoclass("android.os.Build")
        ServiceClass = autoclass("org.sequentialclicker.sequentialclicker.ClickerForegroundService")
        intent = Intent(activity, ServiceClass)
        if int(Build.VERSION.SDK_INT) >= 26:
            activity.startForegroundService(intent)
        else:
            activity.startService(intent)
        return True
    except Exception:  # noqa: BLE001
        return False


def stop_foreground_service() -> bool:
    activity = get_activity()
    autoclass = _jnius()
    if activity is None or autoclass is None:
        return False
    try:
        Intent = autoclass("android.content.Intent")
        ServiceClass = autoclass("org.sequentialclicker.sequentialclicker.ClickerForegroundService")
        intent = Intent(activity, ServiceClass)
        activity.stopService(intent)
        return True
    except Exception:  # noqa: BLE001
        return False
