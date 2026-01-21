## 需求结论与可行性边界
- 桌面端（Windows/macOS/Linux）完全按需求实现：PyQt6 + pyautogui + keyboard。
- 安卓端“Python + pyautogui/keyboard + 系统级点击控制”在技术与权限模型上不现实：pyautogui/keyboard不适配安卓，且安卓对全局点击需无障碍/系统权限。
- 处理方式：先交付桌面端完整版本；安卓作为独立子项目，用“可复用核心逻辑 + 安卓原生/无障碍点击实现（非纯 Python）”或“Kivy/KivyMD + pyjnius 调用无障碍服务”路线（二选一），功能对齐但实现栈不同。

## 项目结构（MVC）
- 新建 Python 工程目录（示例）：
  - app/main.py：启动入口（QApplication/QMainWindow）
  - app/model.py：坐标点数据结构、校验、JSON序列化/反序列化
  - app/view.py：界面（QMainWindow 三栏布局、表格、托盘、对话框）
  - app/controller.py：信号连接、业务流程、文件管理、线程调度
  - app/worker.py：连点工作线程（QThread + QObject）
  - app/settings.py：最近文件/热键/默认参数（QSettings）
  - resources/：托盘图标、提示音
  - requirements.txt、setup.py、README.md、docs/用户手册.md（后续导出PDF）

## 坐标点管理模块（QTableWidget）
- 表格列：序号（自动）、X、Y；序号随执行顺序实时更新。
- 添加：
  - “获取当前位置”使用 pyautogui.position() 填充X/Y；也支持手动输入。
  - 输入校验：整数、范围 0..屏幕最大宽/高（取主屏或当前屏幕几何）。
- 编辑：
  - 双击单元格编辑；用 delegate + QIntValidator 做实时校验；非法输入阻止提交并提示。
- 删除：
  - 单选/多选删除；QMessageBox 二次确认。
- 拖拽排序：
  - QTableWidget InternalMove；drop后重新同步到 Model 并刷新序号列。
- 配置文件：
  - JSON 格式保存/加载（包含点列表与顺序、间隔、循环配置、热键配置）。
  - “打开/另存为”标准文件对话框。
  - 最近打开3个文件：用 QSettings 维护，显示在“文件”菜单里。

## 连点控制模块（多线程 + 可暂停）
- UI 控件：开始/暂停/停止按钮；开始后禁用开始；暂停可继续；停止重置。
- 间隔时间：QSpinBox（100–5000ms，步长100，默认500），修改后对下一次点击立即生效。
- 执行状态：
  - 状态栏：准备/运行/暂停/停止/错误。
  - 进度条：当前点进度（以及可选的循环进度）。
  - 系统托盘：图标/tooltip 反映状态；托盘菜单可开始/暂停/停止/退出。
- Worker 线程：
  - 依次遍历坐标点：pyautogui.moveTo(x,y) + pyautogui.click(x,y)。
  - 暂停：使用 threading.Event 控制 wait；停止：stop flag 并唤醒暂停。
  - 通过 Qt signals 把进度/状态/错误回传主线程更新UI。

## 健壮性与异常处理
- 捕获 pyautogui.FailSafeException：提示用户并立即停止，UI恢复初始状态。
- 屏幕分辨率/DPI 变化：
  - 启动时取 QGuiApplication.screens() 的几何信息校验坐标。
  - 运行前再次校验；越界点给出弹窗选择（中止/跳过）。
- 后台运行：最小化到托盘；连点运行时允许切换窗口（pyautogui 本身是全局输入）。
- 用户反馈：
  - 完成提示音（QSoundEffect；不可用时回退 QApplication.beep）。
  - 错误弹窗 + 托盘通知。
  - 日志：logging 写入应用数据目录，记录打开/保存/开始/暂停/停止/异常。

## 可选扩展（按开关实现）
- 循环模式：次数 1–999 或无限；循环间隔独立；显示当前循环次数。
- 全局快捷键：keyboard 注册开始/暂停/停止；支持组合键；注册失败/冲突时提示并禁用该热键。

## UI规范与适配
- 三栏布局：左侧表格60%（QSplitter 控制比例）；右侧上控制按钮组；右侧下参数区（间隔、循环、热键）。
- DPI：启用 Qt6 的高DPI策略（四舍五入策略/字体缩放），在 125/150/200% 下保持布局不溢出。
- Windows Fluent / 安卓 Material：
  - 桌面端：使用 Qt 内置 Fusion/Windows 样式 + 轻量 QSS 接近 Fluent（不引入额外主题依赖）。
  - 安卓：放入第二阶段单独工程，Material 由 KivyMD 或原生实现。

## 依赖与交付物
- requirements.txt：PyQt6>=6.4.0、pyautogui>=0.9.53、keyboard>=0.13.5。
- setup.py：setuptools 打包安装与入口脚本。
- README.md：截图位、快速入门、常见问题（权限/热键/FailSafe/多屏）。
- 中文用户手册：先以 docs/用户手册.md 交付，提供导出PDF说明；若环境支持再补充自动化导出脚本。

## 验证方案
- 单元测试：model 的校验、JSON读写、最近文件列表逻辑。
- 运行验证：提供“模拟运行（不点击）”模式用于安全自测；再做真实点击手动回归。
- 兼容性：至少在 Windows 10/11 下验证；macOS/Linux 作为可选验证（依赖系统权限与keyboard库限制）。