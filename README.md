# Screen Context Assistant

**Windows 桌面多模态 AI 助手：框选屏幕内容，在悬浮窗口中提取文字、翻译、解释图像和总结信息。**

Free, MIT-licensed source code for a Windows screen-region assistant. Select a task, select a screen region, and read the result in a floating window. Model requests use the user's own ChatGPT sign-in through a local Codex App Server process.

## 功能与产品流程

- **任务先行**：先选择看图解释、翻译、文字提取、总结或练习题解释，再决定输入范围。
- **手动框选**：只在用户触发任务时读取指定区域，悬浮按钮可以拖动。
- **多模态输入**：将实际选区图像交给模型，支持图形与文字混合内容。
- **输入可核对**：“查看本次图片”显示本次发送的完整图像，便于判断选区是否正确。
- **重复读取**：“再看一次”重新读取上一次区域的当前内容。
- **状态与反馈**：显示等待状态、错误说明，分析期间限制重复提交，结果支持复制。
- **高 DPI 处理**：将 Qt 逻辑坐标换算为实际屏幕像素；多屏无法准确匹配时明确报错。

这是一个独立桌面工具。不会替用户点击网页、执行命令或自动操作其他应用。

## 运行要求

1. Windows 10 / 11。
2. Python **3.12**，包含 `py` 启动器和 `venv`。
3. 已安装可运行的 Codex，并在本机使用自己的 ChatGPT 账号登录。建议将 Codex CLI 加入 PATH；程序也会检查常见的本机 Codex 安装目录。
4. 账号具备相应模型访问权限和可用额度，并能联网。

**软件源代码免费开源，不代表模型服务无限免费。** 分析使用运行者自己的账号、模型权限和 Codex 额度，本仓库不提供或共享任何账号、API 密钥或额度。

## 安装与使用

在本页选择 **Code → Download ZIP**，解压到可写目录，或运行：

```powershell
git clone https://github.com/ZHUYIFAN001225/screen-context-assistant.git
cd screen-context-assistant
```

1. 双击 `setup_windows.bat` 安装依赖。
2. 双击 `start.bat` 启动。
3. 点击悬浮按钮，选择任务，再选择“框选区域”。
4. 在结果窗阅读或复制结果。可通过“查看本次图片”核对输入，或“再看一次”读取原区域。
5. 选择“退出程序”结束进程；区域选择时可按 Esc 取消。

如未登录或额度不足，请在 Codex 中检查自己的账号状态。代码不读取 `.env`，此版本不使用 API 密钥模式。

## 隐私与数据流

```text
用户选择任务与屏幕区域
    → 本机截图、坐标换算与输入预览
    → 本机 Codex App Server
    → 使用本人账号向 OpenAI 发送图像与任务
    → 悬浮窗口显示结果
```

- **图片会发送给 OpenAI 分析**；请只选择你愿意发送且有权处理的内容。
- 本程序不把截图写入本地文件，不包含后台录屏或自动采集。
- 使用临时分析会话，并在无法确认临时会话时停止发送图片；本程序不建立自己的聊天历史数据库。
- 账号凭据由本机 Codex 管理。本程序不会直接读取、复制或上传 Codex 凭据文件。
- 本机 `config.json` 仅保存界面偏好，首次修改模式后可自动生成，已列入忽略规则。
- 分析客户端拒绝额外工具和审批请求；屏幕中的文字作为分析材料处理。

“不保存本地截图”不等同于数据从未离开电脑；服务端数据处理以 OpenAI 及账号设置为准。

## 项目结构

| 文件 | 用途 |
|---|---|
| `main.py` | 任务菜单、选区、悬浮结果、状态与输入预览 |
| `screen_capture.py` | 屏幕读取与高 DPI 坐标处理 |
| `account_backend.py` | 本机 Codex App Server 连接、临时会话、结果与错误处理 |
| `setup_windows.bat` / `start.bat` | 安装依赖与启动 |
| `tests/` | 使用合成图片及模拟连接的离线回归检查 |

## 验证与当前边界

在安装依赖后运行：

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

离线检查覆盖高 DPI 坐标、负坐标显示器、边缘截取、临时会话保护、图像输入和异常关闭，不向模型发送请求、不读取真实屏幕。它们不能替代不同机器上的实际安装、显示器兼容性和模型效果验证。

当前发布为 Python 源码版本，未提供独立安装器。由于截图、登录与本机 Codex 安装方式存在差异，不保证所有显示器组合或 Codex 版本均兼容。模型回答也需要用户判断和核对。

## 开源许可与依赖

本项目源代码使用 [MIT License](LICENSE)。PySide6、mss、Pillow 由使用者通过 pip 单独安装，遵循各自许可；仓库不包含 Python、第三方依赖、账号、截图或作者本机运行环境。

参考：[OpenAI Codex App Server](https://learn.chatgpt.com/docs/app-server) · [Codex authentication](https://learn.chatgpt.com/docs/auth)
