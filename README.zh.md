<div align="center">

# ⚡ prompt2jev

**把 LLM 提示词变成代码可以直接分支的 TypeSafe Jev 决策。**

[![Skill](https://img.shields.io/badge/skill-prompt2jev-7c3aed?style=flat-square)](#install) [![Archetypes](https://img.shields.io/badge/archetypes-5-0d9488?style=flat-square)](#catalog) [![Tests](https://github.com/sumleo/prompt2jev/actions/workflows/test.yml/badge.svg)](https://github.com/sumleo/prompt2jev/actions/workflows/test.yml) [![MIT](https://img.shields.io/badge/license-MIT-ea580c?style=flat-square)](LICENSE)

[English](README.md) · 简体中文

[概览](#overview) · [目录](#contents) · [安装](#install)

</div>

<a id="overview"></a>
## 概览

Jev 负责判断，你的代码负责决策。这个 Skill 教编码 Agent 把一段输出标签、分数、布尔值
或 JSON 字段的提示词，重建为类型化的 [TypeSafe Jev](https://docs.typesafe.ai) 问题，
外加围绕它们的代码：

- **转换：** system prompt、提示词模板或一句自然语言需求，变成 `state`、原子化的
  `choice` / `score` / `noul` 问题，以及一个常量块。
- **校验：** 自带的零依赖命令行工具按 API 契约校验请求，并按 TypeSafe 文档的最佳
  实践做 lint，然后才把请求展示给你。
- **改造：** 五个原型请求覆盖路由、护栏、评分、抽取和引证核对；复制一个再改。

**第一次用？** [把安装提示词交给你的 Agent](#install)，然后
[粘贴一条使用提示词](#usage)。你不需要自己写 JSON。

<a id="contents"></a>
## 目录

| 上手 | 探索 | 深入 |
|---|---|---|
| [📦 安装](#install) | [🧪 输入什么，得到什么](#io) | [🧯 Skill 防住的坑](#pitfalls) |
| [🚀 怎么用](#usage) | [🗂 选一个原型](#catalog) | [⚡ 让 Jev 好用的两个习惯](#habits) |
| [⌨️ 命令行](#cli) | [📐 转换包](#package) | [🔗 来源与致谢](#credits) |

支持 Claude Code、Codex、OpenCode、Cursor、Gemini CLI，以及任何能读取 `SKILL.md`
的 Agent。

<a id="install"></a>
## 📦 安装：把这段交给你的 Agent

粘贴到 **Claude Code、Codex、OpenCode、Cursor 或 Gemini CLI**：

```text
请从 https://raw.githubusercontent.com/sumleo/prompt2jev/main/docs/install.md
把 prompt2jev skill 安装到当前项目。检查我的环境，安装到项目内目录，
用 dry run 离线验证，不要发起任何付费调用。
```

英文版：

```text
Install the prompt2jev skill from
https://raw.githubusercontent.com/sumleo/prompt2jev/main/docs/install.md
into this project. Check my environment, install project-local, verify offline
with a dry run, and do not make a paid call.
```

Agent 会把自包含的 `skills/prompt2jev/` 目录复制到正确位置，跑一次离线 dry run，
然后告诉你还差什么（通常只差一个 API 密钥）。[Agent 安装指南](docs/install.md)

<details>
<summary>想自己装？</summary>

**Claude Code 插件**

```bash
claude plugin marketplace add sumleo/prompt2jev
claude plugin install prompt2jev@prompt2jev
```

用 `/prompt2jev:prompt2jev` 调用，或直接说"使用 prompt2jev skill"。

**其他 Agent，通过 skills.sh**

```bash
npx skills add sumleo/prompt2jev --skill prompt2jev
```

按提示选择你的 Agent。加 `-g` 安装到用户级目录。

**手动复制** 整个 `skills/prompt2jev/` 目录：

| Agent | 项目内目标路径 |
|---|---|
| Claude Code | `.claude/skills/prompt2jev/` |
| Codex | `.agents/skills/prompt2jev/` |
| OpenCode | `.opencode/skills/prompt2jev/` |
| Cursor | `.cursor/skills/prompt2jev/` |
| Gemini CLI | `.gemini/skills/prompt2jev/` |

**可选：把命令加到 PATH**（脚本本身只需要 Python 3.10+）：

```bash
uv tool install git+https://github.com/sumleo/prompt2jev
# 或：pipx install git+https://github.com/sumleo/prompt2jev
```

</details>

<a id="usage"></a>
## 🚀 装好了？这样用

**把下面任意一条发给你的 Agent。** 点名 Skill，指出提示词或需求在哪，剩下的
挖掘工作由 Agent 完成。

### 转换代码里已有的提示词

```text
使用 prompt2jev skill，把 src/triage.py 里的 system prompt 转换成 Jev 决策。
保持下游行为不变。展示请求前先校验，暂时不要发起真实调用。
```

### 转换你粘贴进来的提示词

把引号里的内容换成你自己的：

```text
使用 prompt2jev skill，把这段 LLM 提示词转换成 Jev 决策：
"Classify the support ticket into billing, shipping, or account. Set urgent=true
if the customer cannot use the product or has a deadline today. If they ask for a
refund, add refund=true. Output JSON only."
```

### 从需求而不是提示词开始

```text
使用 prompt2jev skill。我需要把收到的邮件路由到 sales、support 或 spam，
并标记所有提到合同续约的邮件。请设计这个 Jev 决策和消费它的代码。
```

Agent 会先收集上下文（占位符、解析器、依赖各输出字段的代码、已有枚举），只在某个
缺口会改变问题形态时才提问，其余一律写成假设。

<a id="package"></a>
### 📐 你会拿到什么

每次转换都是一个五部分的包，顺序固定：

1. **决策契约**：要做的决策、证据单元、每个答案的消费者、未知路径、成功标准。
2. **拆分表**：提示词里的每条指令分别归入 `choice`、`noul`、`score`、`code`、`keep-llm` 或 `drop`。
3. **请求 JSON**：原生 `{model, state, questions}` 结构，先经 `prompt2jev validate --strict` 校验。
4. **组合代码**：用你项目的语言编写，所有阈值和权重集中在一个常量块里。
5. **假设与测试用例**：自动化之前要确认和验证的事项。

以上面的工单提示词为例：类别变成带 `other` 兜底的 Choice，"urgent" 和 "refund" 变成
Noul 并把提示词自己的定义搬进 `criteria`，截止日期判断留给模型，而 JSON 输出格式
的规则被丢弃。[操作手册](skills/prompt2jev/references/playbook.md) 完整演示了一个
例子，包括算术和日期规则如何搬进代码。

<a id="catalog"></a>
### 🗂 选一个原型

| 你的提示词在做… | 从这个开始 | 它展示的是 |
|---|---|---|
| 归入固定类别并标记几个属性 | `classify-route` | 带兜底的意图 Choice、投机性 Noul、每个分支都读的 Score |
| 按一组规则筛查消息 | `checklist-guardrail` | 每个风险一个 Noul 加一个严重度 Score；优先级在代码里 |
| 按评分表或 1 到 10 打分 | `rubric-composite` | 每个维度一个 Score，权重在代码里，外加一个硬规则 Noul |
| 从文本里抽取值 | `extract-select` | 正则找候选项，Choice 从中选择并带 `not_stated` |
| 核对断言是否有来源支持 | `verify-claim` | 支持度 Choice 加语境 Noul；逐字匹配留在代码里 |

`prompt2jev template <名称>` 可以打印任意一个；文件在
[`skills/prompt2jev/assets/`](skills/prompt2jev/assets/)。它们都是通过校验的请求
模板，不是记录下来的模型输出。

<a id="cli"></a>
### ⌨️ 更喜欢命令行？（可选）

这些命令 Agent 会替你运行，你也可以自己运行。

```bash
prompt2jev setup                                   # 检查哪些密钥存在；不打印任何值
prompt2jev template classify-route > request.json  # 从一个原型开始
prompt2jev validate request.json --strict          # 契约校验 + 最佳实践 lint
prompt2jev run request.json --dry-run              # 打印将要发送的内容
prompt2jev run request.json                        # 真实调用 TypeSafe（TYPESAFE_API_KEY）
prompt2jev run request.json --provider openrouter  # 或经由 OpenRouter（OPENROUTER_API_KEY）
```

没装命令时，把 `prompt2jev` 换成 `python3 skills/prompt2jev/scripts/prompt2jev.py`。

退出码：`0` 成功；`1` 请求无效、`--strict` 下有 lint 警告、缺少密钥或服务端错误。
`run` 会打印请求、原始响应和每个问题的报告，报告里的置信度分档是示例默认值，需要你
自己调优。响应不符合文档契约时仍会先完整打印再报错，付费调用的结果不会丢失。
`--allow CODE` 可以压制某次请求里你判定为误报的 lint 项。

**密钥。** 官方 API 用 `TYPESAFE_API_KEY`（https://console.typesafe.ai/keys 获取，模型
`jev-latest`），或者用 `OPENROUTER_API_KEY`（https://openrouter.ai/settings/keys 获取，
模型 `typesafe/jev-1.13`）。放在启动 Agent 或命令行的环境变量里；不要粘进聊天、
请求文件或代码仓库。校验和 dry run 不需要密钥。真实调用会花钱，并把 state 发给服务方。

<a id="io"></a>
## 🧪 输入什么，得到什么

下面的请求就是每次转换产出的形态。答案取自
[TypeSafe 快速开始](docs/introduction/quickstart.md) 文档中记录的示例；本仓库自身
没有发起过真实调用。

| 📥 输入摘录 | 📤 文档记录的输出 |
|---|---|
| State："Hi, I've been trying to connect my Stripe account for 3 days and the integration keeps failing. I'm losing sales. Please help ASAP."<br />问题：该由哪个团队处理（`billing` / `technical` / `sales`）、客户有多沮丧（三个描述性等级）、是否紧急（Noul）。 | `department = technical`，概率 `0.85`，置信度 `0.78`<br />`frustration = 1.0 / 2`（"Frustrated but civil"），置信度 `1.0`<br />`is_urgent = 1.0` |

<details>
<summary>Skill 会写出的请求</summary>

```json
{
  "model": "jev-latest",
  "state": {
    "ticket": {
      "text": "Hi, I've been trying to connect my Stripe account for 3 days and the integration keeps failing. I'm losing sales. Please help ASAP."
    }
  },
  "questions": {
    "department": {
      "type": "choice",
      "instructions": "Which team should handle `ticket.text`?",
      "criteria": {
        "billing": "Payment or subscription issues",
        "technical": "Bugs or integration problems",
        "sales": "Pricing or account questions",
        "other": "None of the listed teams fits."
      }
    },
    "frustration": {
      "type": "score",
      "instructions": "How frustrated does the customer appear in `ticket.text`?",
      "criteria": ["Calm, just stating facts", "Frustrated but civil", "Very angry, strong language"]
    },
    "is_urgent": {
      "type": "noul",
      "instructions": "Does `ticket.text` convey urgency or time-sensitivity?"
    }
  }
}
```

`prompt2jev run` 会把原始答案包装成报告：选中的选项、它的概率、与第二名的差距、
置信度分档、最接近的 Score 等级及其文字，以及每个 Noul 的 是 / 不确定 / 否 分档。
`noul` 的值是 P(是)，即使分档显示为"否"；`1.0 / 2` 这样的 Score 是在你定义的等级上的
位置，不是概率。

</details>

<a id="habits"></a>
## ⚡ 让 Jev 好用的两个习惯

- **先拆分提示词，再一次问完。** 一个问题只做一个判断；所有相互独立的问题放进同一个
  请求，包括投机性的问题。问题并行执行，彼此看不到答案；只有当 state 依赖上一个答案时
  才发第二个请求。
- **规则留在代码里。** 算术、日期、计数、阈值和精确匹配从不交给模型。抽取变成在代码
  找到的候选项里做选择。阈值集中在一个常量块里，并按错误动作的代价来定。

<a id="pitfalls"></a>
## 🧯 Skill 防住的坑

每一行是 TypeSafe 文档中的一条规则、它防止的失败，以及本仓库如何强制执行。

| 规则 | 防止的失败 | 强制手段 |
|---|---|---|
| 列全选项并加 `other` 之类的兜底 | 模型被迫选一个错误标签 | lint `choice-no-fallback` |
| Score 等级描述具体情形，2 到 10 个 | 纯数字让模型无从匹配 | lint `score-numeric-levels`、`score-degree-only` |
| 一个 Noul 一个命题，高值表示"是" | 复合或否定的问题在代码里被读反 | lint `noul-compound`、`noul-negated` |
| 数字、日期、计数留在代码里 | Jev 不是计算器 | lint `math-in-question`、手册中的拆分表 |
| 完整问题写在 `instructions` 里；id 不会发给模型 | 靠 id 传达问题 | lint `instructions-too-short` |
| state 只放问题用到的内容，用反引号路径引用 | 无关内容降低准确率 | lint `state-field-unreferenced`、`state-too-large` |
| 阈值调好后固定到带版本号的模型 | `jev-latest` 会随版本漂移 | lint `model-alias`（info） |
| 置信度分档按风险定；Noul 阈值单独设 | 所有动作共用一个数字 | SKILL.md 第 5 步、`references/composition.md` |

每条 lint 规则都是启发式的，并有文档化的 `--allow` 逃生口。带出处的完整规则集见
[question-design.md](skills/prompt2jev/references/question-design.md)。

<a id="layout"></a>
## 🧭 文件在哪

```
skills/prompt2jev/
  SKILL.md              skill 本体（交付物、六个步骤、红旗）
  references/           操作手册、问题设计、API 契约、组合模式、示例
  assets/               五个通过校验的原型请求
  scripts/prompt2jev.py 校验器、lint 器、调用器（仅 Python 标准库）
docs/                   编写参考资料所依据的 TypeSafe 文档镜像
docs/install.md         由 Agent 执行的安装指南
tests/                  unittest 测试套件：python3 -m unittest discover -s tests -v
```

<a id="credits"></a>
## 🔗 来源与致谢

- [TypeSafe 文档](https://docs.typesafe.ai)：API 契约、原语、置信度、模式，以及规则所
  依据的 jev-1.13 jaggedness 页面。`docs/` 里有一份镜像。
- [typesafe-ai/skills](https://github.com/typesafe-ai/skills)：TypeSafe 官方 Agent Skill；
  从零构建新集成时可与本 Skill 配合使用。
- [wuyoscar/jev-skill](https://github.com/wuyoscar/jev-skill)：本项目的仓库结构、安装
  流程和 README 形态所参照的集合。

[MIT](LICENSE)。
