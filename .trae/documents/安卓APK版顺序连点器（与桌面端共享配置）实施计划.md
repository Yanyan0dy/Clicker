## 目标与边界

* 目标：在现有桌面端基础上新增“安卓 APK 版本”，尽可能复用配置格式与业务逻辑（点序列、间隔、循环）。

* 关键边界：安卓上无法用 `pyautogui/keyboard` 做系统级点击；必须走 **无障碍（AccessibilityService）+ 前台服务（Foreground Service）** 才能在后台稳定执行点击与状态通知。

* 用户侧前置条件：需要在系统设置里手动开启本应用的无障碍服务权限（这是安卓系统限制，无法绕过）。

## 技术路线（优先方案）

* **Python UI + 安卓原生点击引擎**：

  * UI/业务层：Kivy + KivyMD（Material 风格），用 python-for-android 打包为 APK。

  * 点击执行：通过 `pyjnius` 调用随 APK 一起打包的 Java/Kotlin 代码，实现 AccessibilityService 发起 `dispatchGesture()` 点击。

  * 后台运行：Android Foreground Service + 通知栏控制（开始/暂停/停止）。

## 代码组织（与现有桌面端协同）

* 抽取可复用核心为 `clicker_core`：

  * 迁移/复用现有 [model.py](file:///c:/Users/Yanyan_/Desktop/try/clicker/model.py) 的数据结构与 JSON 序列化逻辑。

  * 明确配置 schema：保留 `version` 字段并添加向后兼容解析。

* 桌面端继续使用现有 MVC（[controller.py](file:///c:/Users/Yanyan_/Desktop/try/clicker/controller.py)、[view.py](file:///c:/Users/Yanyan_/Desktop/try/clicker/view.py)、[worker.py](file:///c:/Users/Yanyan_/Desktop/try/clicker/worker.py)），仅在必要处改为依赖 `clicker_core`。

## 配置格式兼容策略（桌面↔安卓）

* 现有 v1 以“绝对像素坐标”为主，安卓设备分辨率/横竖屏差异会导致不可移植。

* 方案：升级到 v2（仍兼容读取 v1）：

  * 点数据支持两种坐标模式：

    * `abs`: 绝对像素（沿用 v1）

    * `ratio`: 归一化坐标（0.0–1.0，随分辨率自适应）

  * 保存时在安卓端优先写 `ratio`；桌面端打开 v2 仍可正常编辑与执行（执行时换算为当前屏幕像素）。

## 安卓端功能实现拆解

### 1) 坐标点采集与管理（Material 风格）

* 列表：RecyclerView 风格列表（KivyMD List），显示序号、X/Y（或 ratio）。

* 添加：

  * “记录模式”：弹出全屏半透明覆盖层，让用户在屏幕上点一下即记录坐标（推荐）。

  * “手动输入”：可输入 abs 或 ratio（高级选项）。

* 编辑/删除：列表项编辑对话框；多选删除 + 二次确认。

* 拖拽排序：KivyMD 支持拖拽列表重排，实时更新序号。

### 2) 连点控制与后台运行

* 开始/暂停/停止：

  * 前台界面按钮 + 通知栏快捷按钮（等价于桌面托盘）。

* 间隔时间：100–5000ms，实时生效。

* 循环：次数 1–999 或无限；循环间隔独立。

* 状态显示：

  * 顶部状态条/Toast + 通知栏常驻（运行中必须前台服务）。

  * 进度条：当前点进度与循环进度。

### 3) 点击注入（核心难点）

* 新增 Android 原生模块：

  * AccessibilityService：接收“点坐标队列 + 间隔/循环 + 控制指令”。

  * 使用 `dispatchGesture(GestureDescription)` 执行点击。

* Python 与 Service 通信：

  * 方案 A（简单稳定）：BroadcastReceiver + Intent（开始/暂停/停止/更新参数）。

  * 方案 B（更强）：绑定服务（Bound Service）+ AIDL（后续可扩展）。

## 健壮性与异常处理（安卓）

* 权限未开启：启动前检测 AccessibilityService 开启状态，未开启则引导到系统设置页。

* 分辨率/旋转：

  * ratio 模式自动适配；abs 模式检测越界并提示跳过/停止。

* FailSafe：安卓侧提供“紧急停止”通知按钮；同时应用内保留“停止”大按钮。

* 日志：写入应用内部存储（可导出分享）。

## 打包与交付

* 新增 `android/` 子项目：

  * buildozer.spec / python-for-android 配置

  * Kivy/KivyMD Python 入口

  * `src/` 下 Java/Kotlin 无障碍服务与前台服务

* 构建方式：

  * 推荐在 Linux/WSL2 或 CI（GitHub Actions + docker）构建 APK；Windows 本机直接构建受限。

* 输出：debug APK（可安装测试）+ release 构建说明。

## 验证方案

* 单元测试：继续覆盖 `clicker_core` 的 JSON/坐标换算/循环计划逻辑。

* 端到端测试：

  * 安卓：在测试机上启用无障碍权限，跑“记录模式→开始→暂停→继续→停止→循环完成”全链路。

  * 桌面：验证仍可读写 v2 配置并正常执行。

## 本轮落地顺序（实现优先级）

* 第一阶段：抽 core + 安卓端 UI（列表/录点/保存加载）+ Accessibility 点击最小闭环（开始/停止）。

* 第二阶段：暂停/继续、循环、通知栏控制、日志导出。

* 第三阶段：更完善的 Material 细节、配置迁移提示、多机适配与CI构建。

