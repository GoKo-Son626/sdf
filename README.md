# English 专业翻译助手

在任意终端中运行：

```bash
sdf
```

然后直接输入英文单词、术语、短语或句子。每次成功查询后，结果会自动保存到
`/home/shuqi/repo/AI/translat-tool-goko/vocabulary.md`。

输出规则：

- 单词或短专业术语：只返回 1～4 个最可能的简短中文意思。
- 句子、段落或文章：只返回一份完整中文译文。
- Markdown 每条只记录原文一行、翻译一行，不记录例句、解释、来源或时间。

也可以单次查询：

```bash
sdf "race condition"
```

## 配置或切换大模型

运行：

```bash
sdf --setup
```

可选择：

1. DeepSeek（默认推荐）
2. 智谱 GLM-4.7-Flash（免费）
3. Gemini
4. 任意 OpenAI Chat Completions 兼容接口
5. 不使用大模型，只使用免费备用翻译

DeepSeek API Key 可在这里创建：

https://platform.deepseek.com/api_keys

截至 2026-07-26，默认使用 `deepseek-v4-flash`。旧名称 `deepseek-chat` 已于
2026-07-24 停用，因此不要再填写旧模型名。

粘贴 API Key 时终端不会显示字符，这是正常的安全保护。Key 保存在
`/home/shuqi/repo/AI/translat-tool-goko/config.env`，权限为 600（仅当前用户可读写）。

智谱免费模型的 API Key 可在这里创建：

https://bigmodel.cn/usercenter/proj-mgmt/apikeys

智谱内置配置使用 `glm-4.7-flash` 和通用端点
`https://open.bigmodel.cn/api/paas/v4`。它不会影响 DeepSeek 配置；通过
`sdf --setup` 可以随时来回切换。

## 支持哪些大模型

除了内置的 DeepSeek、智谱和 Gemini，还支持采用 OpenAI Chat Completions 格式的服务。
配置自定义服务时只需要提供：

- 服务名称
- API Base URL
- 模型名称
- API Key

例如 OpenAI、硅基流动、OpenRouter、Moonshot，以及其他提供
`POST /chat/completions` 兼容接口的平台。不同平台的具体 Base URL 和模型名需要以
其官方文档为准。

## 交互命令

- `:paste`：可靠的多行粘贴模式，粘贴完成后单独输入 `:end`
- `:provider`：查看当前大模型
- `:setup`：切换大模型或重新设置 API Key
- `:domain embedded systems`：设置本次会话的专业领域
- `:domain`：查看当前专业领域
- `:save off` / `:save on`：临时关闭或开启自动归档
- `:file`：显示生词本路径
- `:help`：查看帮助
- `:quit`：退出

## 降级顺序

1. 优先调用当前配置的大模型，按照输入类型返回简短词义或完整译文。
2. 大模型请求失败时，终端显示服务名称和具体失败原因。
3. 自动调用 MyMemory 继续翻译；长文本会分块，任何一块失败都不会保存残缺译文。
4. 备用结果成功后照常保存到 Markdown。

## 多行粘贴

现代终端可以直接粘贴多行英文，程序会把整次粘贴作为一个查询，并将换行合并为空格。
如果当前终端仍将粘贴内容拆成多次输入，使用：

```text
English> :paste
请粘贴多行英文；完成后另起一行输入 :end
... 第一行
... 第二行
... :end
```

## 手工配置格式

通常不需要手工修改；如有需要，可编辑 `config.env`：

```text
PROVIDER=deepseek
PROVIDER_NAME=DeepSeek
API_KEY=你的_Key
BASE_URL=https://api.deepseek.com
MODEL=deepseek-v4-flash
TRANSLATION_DOMAIN=computer science
```

自定义 OpenAI 兼容服务：

```text
PROVIDER=openai-compatible
PROVIDER_NAME=服务名称
API_KEY=你的_Key
BASE_URL=https://服务商地址/v1
MODEL=模型名称
```

智谱免费模型：

```text
PROVIDER=zhipu
PROVIDER_NAME=智谱 GLM
API_KEY=你的_Key
BASE_URL=https://open.bigmodel.cn/api/paas/v4
MODEL=glm-4.7-flash
```

如果终端已经设置 `HTTPS_PROXY`，无需在配置文件中重复填写。
