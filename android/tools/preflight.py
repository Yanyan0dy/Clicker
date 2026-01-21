from __future__ import annotations

import importlib
import os
import platform
import sys


def _fail(message: str, code: int = 2) -> None:
    print(f"[preflight] {message}", file=sys.stderr)
    raise SystemExit(code)


def _warn(message: str) -> None:
    print(f"[preflight] WARNING: {message}")


def _ok(message: str) -> None:
    print(f"[preflight] OK: {message}")


def main() -> int:
    py = sys.version_info
    _ok(f"Python {py.major}.{py.minor}.{py.micro}")

    if (py.major, py.minor) < (3, 10):
        _fail("Python 版本过低，请使用 Python 3.10–3.12")
    if (py.major, py.minor) >= (3, 14):
        _fail("检测到 Python 3.14+：urllib.request 已移除 FancyURLOpener，buildozer 可能无法启动。请改用 Python 3.10–3.12")

    sys_name = platform.system().lower()
    if "windows" in sys_name:
        _warn("检测到 Windows：建议在 WSL2/Linux 或 CI 构建 APK（Windows 工具链兼容性较差）")
    else:
        _ok(f"平台：{platform.system()}")

    try:
        importlib.import_module("buildozer")
        _ok("buildozer 可导入")
    except Exception as exc:  # noqa: BLE001
        _fail(f"buildozer 不可用：{exc}. 先执行：python -m pip install buildozer cython")

    spec = os.path.join(os.path.dirname(__file__), "..", "buildozer.spec")
    if not os.path.exists(spec):
        _warn("未找到 buildozer.spec（请确认当前在 android/ 目录内执行）")
    else:
        _ok("已找到 buildozer.spec")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

