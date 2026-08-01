# SDF Translator

[![CI](https://github.com/GoKo-Son626/sdf/actions/workflows/ci.yml/badge.svg)](https://github.com/GoKo-Son626/sdf/actions/workflows/ci.yml)

SDF Translator 是一个面向 Linux 的轻量级全局 AI 翻译工具。它可以在终端中交互使用，也可以在 PDF 阅读器、WPS、浏览器、Vim/Neovim 等程序里选中文字后按全局快捷键翻译。输入语言会自动识别，输出统一为简体中文。

核心行为很克制：单词和短术语返回 2～3 个最常用的中文意思，并显示为右上角紧凑通知；句子、段落和文章只返回一份完整、连贯并贴合所设专业领域的译文，使用较大的结果窗口。两种结果都只在译文下面标出所用模型，失败或降级时才发出额外通知。

## 适用平台

- 当前正式支持：Arch Linux、Wayland、niri。
- 终端命令本身采用纯 Python 3 标准库，源码和 XDG 目录布局已经与发行版解耦。
- Ubuntu、Debian、Fedora、CentOS 等发行版的依赖安装脚本和桌面快捷键适配尚未发布。
- X11 和 niri 之外的 Wayland 合成器尚未提供自动快捷键配置。

全局选择依赖 Wayland 主选区，因此需要 `wl-clipboard`。结果窗口使用 Zenity，异常通知使用 `notify-send`。

## 从 Git 仓库安装（Arch Linux）

```bash
git clone https://github.com/GoKo-Son626/sdf.git
cd sdf
./install.sh
```

安装器会检查并按需安装 `python`、`wl-clipboard`、`zenity` 和 `libnotify`，然后：

- 将应用安装到 `~/.local/share/sdf-translator/app`；
- 将 `sdf` 和 `sdf-global` 安装到 `~/.local/bin`；
- 检测到 niri 时配置 `Super+Shift+T`；
- 检测到 Vim/Neovim 时安装可视选择同步插件；
- 将配置放在 `~/.config/sdf-translator`。

无人值守安装：

```bash
./install.sh --yes
```

可选参数：

```text
--skip-deps     不安装缺失的 Arch 依赖
--skip-hotkey   不修改 niri 快捷键配置
--skip-editor   不安装 Vim/Neovim 选择同步插件
```

如果终端找不到 `sdf`，请确认 `~/.local/bin` 已加入 `PATH`。安装后不需要保留克隆目录；后续可重新克隆并运行同一个安装脚本覆盖升级。

仓库也包含遵循 VCS 包规范的 `packaging/arch/PKGBUILD` 和发布说明，供以后发布 `sdf-translator-git` AUR 包使用。当前还没有发布到 AUR，因此不能直接执行 `yay -S sdf-translator-git`；建立独立 AUR 仓库并填写维护者信息后才能发布。

## 快速使用

首次选择大模型：

```bash
sdf --setup
```

进入交互模式：

```bash
sdf
```

单次翻译：

```bash
sdf "race condition"
sdf "Esta es una oración completa."
```

在图形程序中使用时，先用鼠标选中文字，再按 `Super+Shift+T`。如果没有主选区，程序不会静默翻译旧剪贴板，而是显示普通剪贴板内容并请求确认。单词和短语成功时只出现一个紧凑通知，句子和长文成功时只出现一个翻译结果窗口。

## Vim 和 Neovim

终端 Vim/Neovim 的可视选择原本只存在于编辑器内部，Wayland 无法直接读取，这会造成全局快捷键拿到其他程序遗留的旧选区。安装器附带的插件会在 Visual 模式中同步当前选择，并在离开选择后安全清理自己写入的主选区。

不需要配置按键：进入 Visual 模式选中文字，然后按全局快捷键即可。若不需要该行为，可以在编辑器配置中设置：

```vim
let g:sdf_selection_sync = 0
```

Neovim Lua 配置写法：

```lua
vim.g.sdf_selection_sync = 0
```

## 翻译规则

- 自动识别英语、日语、西班牙语等任意输入语言，并输出简体中文。
- 单词或不超过五个词的短术语：返回按可能性排序的 2～3 个常用中文意思。
- 句子、段落或文章：只返回一份完整译文，不解释、不总结、不遗漏最后一行。
- `:domain` 设置专业领域后，句子和术语优先采用该领域的通行译法。
- 最多处理 12000 个字符；免密备用服务会自动分块处理较长输入。

终端直接粘贴多行通常会作为一次输入读取。如果终端仍将内容拆成多次提交，可使用可靠粘贴模式：

```text
Text> :paste
请粘贴多行文本；完成后另起一行输入 :end
... 第一行
... 第二行
... :end
```

## 模型与免费 API

内置提供商包括：

- 智谱 GLM-4.7-Flash（免费模型）；
- Groq Free；
- OpenRouter Free Router；
- GitHub Models；
- Google Gemini；
- 硅基流动免费模型；
- DeepSeek（低成本付费）；
- 任意 OpenAI Chat Completions 兼容接口。

免费额度、速率限制、可用模型和地区政策会变化。随时运行下面的命令查看各平台 API Key 获取入口和当前内置说明：

```bash
sdf --free-api-help
```

交互模式中对应命令是 `:free-api`。推荐先尝试智谱、Groq 或 OpenRouter；已有 DeepSeek 余额时也可继续使用 DeepSeek。配置的模型调用失败后，会明确显示“服务名翻译失败：原因”，再使用免密机器翻译完成降级。

免密降级服务不需要 API Key，主要用于保持翻译可用；术语释义的完整性和专业领域理解通常不如大模型。

## 生词本与保存策略

新安装默认不保存任何翻译，也不会擅自创建生词本。先设置 Markdown 文件路径，再选择保存模式：

```bash
sdf --set-save-path ~/Documents/vocabulary.md
sdf --set-save-mode terms
```

支持四种模式：

- `off`：关闭保存，也是新安装默认值；
- `all`：保存全部翻译；
- `terms`：只保存单词和短术语；
- `texts`：只保存句子、段落和文章。

也可以运行 `sdf --settings` 交互配置，或在 `sdf` 中使用：

```text
:save
:save off|all|terms|texts
:save-path <Markdown 文件路径>
:settings
:file
```

Markdown 每条记录只有粗体原文一行和中文翻译一行；不会写入内部键、来源、时间或解释。相同原文不会重复保存。

## 常用交互命令

```text
:paste                    多行粘贴，以单独一行 :end 结束
:domain <领域>            设置当前专业领域
:domain                   查看当前领域
:provider                 查看当前提供商和模型
:free-api                 查看免费 API 获取方法
:setup                    配置或切换大模型
:save                     查看保存设置
:save off|all|terms|texts 设置保存类型
:save-path <路径>         设置 Markdown 生词本路径
:settings                 交互配置生词本
:file                     查看生词本路径
:help                     查看帮助
:quit                     退出
```

## 配置和隐私

安装版的私密配置文件是 `~/.config/sdf-translator/config.env`，程序会将权限设为 `600`。仓库中的 `config.example` 只展示格式，不含真实凭据。源码目录中的 `config.env`、`.history`、`vocabulary.md`、`learn/`、缓存和构建产物均被 Git 忽略。

模型翻译会把选中的原文发送给所配置的第三方 API；免密降级会发送给机器翻译服务。程序会在外发前拦截高置信度的 API Key、Bearer Token、私钥和密码形式内容，但它不能代替人工保密判断，请勿选择包含隐私或机密的数据。

手工配置示例：

```text
PROVIDER=deepseek
PROVIDER_NAME=DeepSeek
API_KEY=你的_API_Key
BASE_URL=https://api.deepseek.com
MODEL=deepseek-v4-flash
TRANSLATION_DOMAIN=computer science
SAVE_MODE=terms
VOCABULARY_FILE=/home/your-name/Documents/vocabulary.md
```

通常优先使用 `sdf --setup` 和 `sdf --settings`，无需手改文件。

## PDF、Word 和 OCR

DOC/DOCX 并不保证总能直接选中文字，PDF 也一样：文件可能只有扫描图片、字体编码异常、加密或由查看器限制复制。判断方法很简单——如果能选中并复制出正常文字，就能直接翻译；只能框出一块图片或复制后为空/乱码，就需要 OCR。

OCR（光学字符识别）是把图片中的文字识别为可复制文本。SDF Translator 当前不内置 OCR；扫描版文档需先使用阅读器、WPS 或系统工具的 OCR 功能，再选择识别结果翻译。

## 卸载

保留配置和生词本：

```bash
./uninstall.sh
```

同时清除 SDF 的 XDG 配置和状态目录：

```bash
./uninstall.sh --purge
```

自定义到其他路径的生词本不会被卸载器删除。卸载器也不会还原 niri 中的快捷键行，避免误删用户后来修改过的配置；如不再需要，请手工删除 `Mod+Shift+T` 对应绑定。

## 开发

项目采用 `src` 包布局：

```text
src/sdf_translate/    翻译核心、终端、桌面入口、提供商和存储
editor/               Vim/Neovim Wayland 选择适配
packaging/arch/       Arch PKGBUILD
packaging/bin/        安装后的命令启动器
scripts/              桌面环境配置脚本
tests/                标准库 unittest 测试
```

运行测试：

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python scripts/check_repository.py
```

GitHub Actions 会在 Python 3.11 和 3.13 上执行语法检查、单元测试和仓库隐私检查。

参与开发前请阅读 [贡献指南](CONTRIBUTING.md)；安全问题请按照 [安全策略](SECURITY.md) 私密报告。

## 许可证

本项目采用 [MIT License](LICENSE)。
