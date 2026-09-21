# prompt2jev

[English](README.md) · 简体中文

一个 Agent Skill，把 LLM 提示词（或一段自然语言需求）转换成
[TypeSafe Jev](https://docs.typesafe.ai) 决策：类型化的 `state`、原子化的
`choice` / `score` / `noul` 问题，以及消费这些答案的代码。它遵循 TypeSafe 文档中的
最佳实践，并自带一个零依赖的校验器、lint 器和调用器。

适用于 Claude Code、Codex、OpenCode、Cursor、Gemini CLI，以及任何能读取 `SKILL.md`
的 Agent。

## 它做什么

给你的 Agent 一段这样的提示词：

```text
You are a support triage assistant. Return JSON with category (billing, shipping,
account, bug, feature_request), urgency 1-5, refund_requested (true/false),
escalate=true if a refund is requested and the amount is over 100 USD and the
purchase is older than 30 days, and a one-sentence summary.
```

装上这个 Skill 后，Agent 会交付一个五部分的**转换包**：

1. **决策契约**：要做的决策、证据单元、每个答案的消费者、未知路径、成功标准。
2. **拆分表**：提示词里的每条指令分别归入 `choice`、`noul`、`score`、`code`、`keep-llm` 或 `drop`。
3. **请求 JSON**：原生 `{model, state, questions}` 结构，展示之前先通过校验。
4. **组合代码**：所有阈值和权重集中在一个常量块里。
5. **假设与测试用例**：自动化之前需要确认和验证的事项。

以上面的提示词为例：`category` 变成带 `other` 兜底选项的 Choice，urgency 变成五个
用具体情形描述的 Score 等级，`refund_requested` 变成 Noul，金额和日期比较留在代码里，
摘要仍交给生成式模型。参见
[完整示例](skills/prompt2jev/references/playbook.md#worked-example-support-triage-prompt)。

## 安装

### Claude Code 插件

```bash
claude plugin marketplace add sumleo/prompt2jev
claude plugin install prompt2jev@prompt2jev
```

用 `/prompt2jev:prompt2jev` 调用，或者直接说"使用 prompt2jev skill"。

### 其他 Agent，通过 skills.sh

```bash
npx skills add sumleo/prompt2jev --skill prompt2jev
```

按提示选择你的 Agent。加 `-g` 可安装到用户级目录。

### 手动复制

把整个 `skills/prompt2jev/` 目录（它是自包含的）复制到 Agent 的 skills 目录：

| Agent | 项目内目标路径 |
|---|---|
| Claude Code | `.claude/skills/prompt2jev/` |
| Codex | `.agents/skills/prompt2jev/` |
| OpenCode | `.opencode/skills/prompt2jev/` |
| Cursor | `.cursor/skills/prompt2jev/` |
| Gemini CLI | `.gemini/skills/prompt2jev/` |

### 让 Agent 自己安装

把下面这段粘贴给你的编码 Agent：

```text
Install the prompt2jev skill from
https://raw.githubusercontent.com/sumleo/prompt2jev/main/docs/install.md
into this project. Check my environment, install project-local, verify offline
with a dry run, and do not make a paid call.
```

中文版：

```text
请从 https://raw.githubusercontent.com/sumleo/prompt2jev/main/docs/install.md
把 prompt2jev skill 安装到当前项目。检查我的环境，安装到项目内目录，
用 dry run 离线验证，不要发起任何付费调用。
```

### 命令行工具（可选）

Skill 自带的脚本只需要 Python 3.10+，没有其他依赖。想把 `prompt2jev` 命令加到 PATH：

```bash
uv tool install git+https://github.com/sumleo/prompt2jev
# 或：pipx install git+https://github.com/sumleo/prompt2jev
```

## 使用

向 Agent 提出请求时点名这个 Skill：

```text
使用 prompt2jev skill，把 src/triage.py 里的 system prompt 转换成 Jev 决策，
保持下游行为不变。
```

```text
使用 prompt2jev skill。我需要把收到的邮件路由到 sales、support 或 spam，
并标记所有提到合同续约的邮件。请设计这个 Jev 决策。
```

```text
使用 prompt2jev skill，把这段评分提示词转成 Jev 问题：
"Grade the essay 1-10 on argument, evidence, and clarity."
```

Agent 会先挖掘上下文（占位符、解析器、依赖输出分支的代码、已有的枚举），只在
某个缺口会改变问题形态时才提问，其余情况直接写明假设。

## 命令行

```bash
prompt2jev setup                                   # 检查哪些密钥存在；不打印任何值
prompt2jev template classify-route > request.json  # 从一个原型模板开始
prompt2jev validate request.json --strict          # 契约校验 + 最佳实践 lint
prompt2jev run request.json --dry-run              # 打印将要发送的请求
prompt2jev run request.json                        # 真实调用 TypeSafe（TYPESAFE_API_KEY）
prompt2jev run request.json --provider openrouter  # 或经由 OpenRouter（OPENROUTER_API_KEY）
```

没有安装命令行工具时，把 `prompt2jev` 换成
`python3 skills/prompt2jev/scripts/prompt2jev.py`。

退出码：`0` 成功；`1` 请求无效、`--strict` 下有 lint 警告、缺少密钥或服务端错误。
`run` 会打印请求、原始响应，以及每个问题的报告，报告里的置信度分档只是示例值，
需要你自己调优。响应不符合文档契约时，仍会先完整打印再报错，付费调用的结果不会丢失。

`template` 可用的原型：`classify-route`、`checklist-guardrail`、
`rubric-composite`、`extract-select`、`verify-claim`。

lint 检查项：Choice 缺少兜底选项、Score 等级只是数字或程度词、Noul 含复合条件或
否定表述、问题里夹带算术或日期逻辑、instructions 短到无法独立成句、state 里有没被
任何问题引用的字段、state 超出模型预算、使用了会漂移的模型别名。这些检查是启发式的；
对某次请求判定为误报的检查项，可以用 `--allow CODE` 压制。

## 密钥

- `TYPESAFE_API_KEY`：官方 API，去 https://console.typesafe.ai/keys 获取
  （端点 `https://api.typesafe.ai/v1/systemone`，模型 `jev-latest`）。
- `OPENROUTER_API_KEY`：备选，去 https://openrouter.ai/settings/keys 获取
  （模型 `typesafe/jev-1.13`）。

密钥放在启动 Agent 或命令行的环境变量里。不要把它粘进聊天、请求文件或代码仓库。
校验和 dry run 不需要密钥；真实调用会花钱，并把 state 发送给服务方。

## Skill 强制执行的最佳实践

- 一个问题只做一个判断；复合规则拆开，再在代码里组合。
- 问题 id 不会发给模型；完整的问题写在 `instructions` 里。
- state 是一个命名字段的 JSON 对象，只放问题需要的内容，用反引号路径引用。
- Choice：每个选项都有描述；输入开放时加 `other` 之类的兜底选项。
- Score：2 到 10 个等级，每个等级描述一个具体情形，一个问题只量一个维度。
- Noul：一个命题，高值表示"是"，不用否定表述。
- 算术、计数、日期、阈值留在代码里；抽取改为在候选项中选择。
- 所有相互独立的问题放进同一个请求；只有当 state 依赖上一个答案时才发第二个请求。
- 置信度分档按每个动作的风险来定；常量集中在一个代码块里。
- 阈值调好后固定到带版本号的模型 id；记录响应里的 `model` 字段。

## 仓库结构

```
skills/prompt2jev/
  SKILL.md              skill 本体
  references/           操作手册、问题设计、API 契约、组合模式、示例
  assets/               五个通过校验的原型请求
  scripts/prompt2jev.py 校验器、lint 器、调用器（仅标准库）
docs/                   编写参考资料时使用的 TypeSafe 文档镜像
docs/install.md         由 Agent 执行的安装指南
tests/                  unittest 测试套件
```

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## 许可证

[MIT](LICENSE)。
