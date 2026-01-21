# 顺序连点器（Python / PyQt6）

一个跨平台（Windows/macOS/Linux）的桌面端顺序连点器：按表格顺序逐点点击，支持暂停/继续、停止、循环模式、全局热键与配置文件保存/加载。

## 功能截图

请在运行后自行截图替换：

- `docs/screenshot_main.png`

## 快速入门

### 1) 安装依赖

```bash
python -m pip install -r requirements.txt
```

### 2) 启动

```bash
python run.py
```

或安装后使用命令：

```bash
python -m pip install -e .
sequential-clicker
```

## 使用说明（简版）

- 添加坐标点：输入 X/Y 后点“添加”，或点“获取当前位置”后再添加
- 编辑坐标：双击表格 X/Y 单元格，用数字微调（范围受屏幕大小限制）
- 拖拽排序：按住行拖动调整顺序，序号会自动更新
- 配置文件：文件菜单支持打开/保存/另存为；自动记录最近打开的 3 个配置
- 控制：开始/暂停(继续)/停止；间隔时间 100–5000ms，实时生效
- 后台：最小化/关闭窗口会驻留托盘，从托盘菜单“退出”真正退出

## 常见问题排查

### 1) 触发 FailSafe 自动停止

`pyautogui` 默认启用 FailSafe：鼠标移动到屏幕角落会抛出异常并停止。可在应用运行时避免把鼠标推到角落。

### 2) 热键不可用/报错

`keyboard` 在部分系统上需要更高权限或不支持。遇到报错时应用会自动关闭热键功能。

### 3) 多屏/分辨率变化导致坐标越界

应用会在开始前校验坐标范围，运行中也会检测分辨率变化导致的越界并安全停止。

## 开发结构（MVC）

- Model：[model.py](file:///c:/Users/Yanyan_/Desktop/try/clicker/model.py)
- View：[view.py](file:///c:/Users/Yanyan_/Desktop/try/clicker/view.py)
- Controller：[controller.py](file:///c:/Users/Yanyan_/Desktop/try/clicker/controller.py)
- Worker：[worker.py](file:///c:/Users/Yanyan_/Desktop/try/clicker/worker.py)

