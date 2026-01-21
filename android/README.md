# 安卓版顺序连点器（KivyMD + AccessibilityService）

本目录为安卓版 APK 子项目骨架：使用 Kivy/KivyMD 实现 Material 风格 UI，并通过 Android 无障碍服务注入点击。

## 重要说明

- 安卓系统限制：全局点击必须依赖无障碍服务（AccessibilityService）。应用安装后需要用户在系统设置里手动开启权限。
- buildozer 运行环境要求：推荐 **WSL2/Linux 或 CI** 构建；Windows 本机不仅容易缺依赖，还会被 Python 版本差异影响。
- Python 版本要求：请使用 **Python 3.10–3.12**。如果你用的是 **Python 3.14**，会出现 `FancyURLOpener` 导入失败（该类在 3.14 已移除），buildozer 将无法启动。

## 目录结构

- [main.py](file:///c:/Users/Yanyan_/Desktop/try/android/main.py)：KivyMD 应用入口（UI/配置管理/录点）
- [buildozer.spec](file:///c:/Users/Yanyan_/Desktop/try/android/buildozer.spec)：python-for-android 构建配置（示例）
- [android_src](file:///c:/Users/Yanyan_/Desktop/try/android/android_src)：Android 原生代码（AccessibilityService/前台服务骨架）
- tools/preflight.py：构建环境自检（建议每次构建前先跑）

## 构建（推荐：WSL2 / Linux）

```bash
sudo apt update
sudo apt install -y python3 python3-pip git openjdk-17-jdk zip unzip
python3 -m pip install --upgrade pip
python3 -m pip install buildozer cython

cd android
python3 tools/preflight.py
buildozer -v android debug
```

产物通常位于 `android/bin/` 目录。

## CI 构建（推荐：Windows 用户）

- 仓库已包含 GitHub Actions 工作流 [android-build.yml](file:///c:/Users/Yanyan_/Desktop/try/.github/workflows/android-build.yml)，可在 Ubuntu runner 上构建 debug APK 并自动上传 artifact。
- 适合 Windows 本机不方便装 WSL2/Android 工具链的场景。

## 开启无障碍权限

安装后进入：

设置 → 无障碍 → 已下载的应用/已安装服务 → 顺序连点器 → 开启

## 常见错误：FancyURLOpener 导入失败

如果你在 Windows 里运行 `buildozer -v android debug`，看到类似：

`ImportError: cannot import name 'FancyURLOpener' from 'urllib.request'`

说明你正在使用 Python 3.14。处理方式：

1. 改用 WSL2/Ubuntu，并安装 Python 3.10–3.12 再构建；或
2. 使用 CI 工作流构建 APK；或
3. 在 Windows 安装 Python 3.11/3.12 并用该版本的 venv 安装 buildozer（但仍可能遇到 Windows 工具链问题）。
