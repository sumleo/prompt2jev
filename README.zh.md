<div align="center">

# ⚡ prompt2jev

**把自然语言变成 Jev：输入一段 LLM 提示词或一句需求，输出类型化的问题和能跑的代码。**

[![Skill](https://img.shields.io/badge/skill-prompt2jev-7c3aed?style=flat-square)](#install) [![Archetypes](https://img.shields.io/badge/archetypes-5-0d9488?style=flat-square)](#catalog) [![Tests](https://github.com/sumleo/prompt2jev/actions/workflows/test.yml/badge.svg)](https://github.com/sumleo/prompt2jev/actions/workflows/test.yml) [![MIT](https://img.shields.io/badge/license-MIT-ea580c?style=flat-square)](LICENSE)

[English](README.md) · 简体中文

[概览](#overview) · [目录](#contents) · [安装](#install)

</div>

<a id="overview"></a>
## 概览

prompt2jev 把自然语言变成一个 Jev 请求，以及围绕它的代码。

**输入：** 一段你已经在跑的 LLM 提示词（system prompt、提示词模板，或一步输出标签、
分数、布尔值或 JSON 字段的"提示后解析"调用），或者一句还没写成提示词的自然语言需求。

**输出：** 同一个决策，改建在 [TypeSafe Jev](https://docs.typesafe.ai) 上。Jev 是
TypeSafe 的 System One 模型：它不生成文本，而是针对一个 `state` 回答类型化的问题
（`choice` 选标签、`score` 按量表打分、`noul` 回答是或否），返回代码可以直接分支的
概率。Jev 负责判断，你的代码负责决策。

```
输入：自然语言                          输出
──────────────────────────────          ─────────────────────────────────────────────
一段 system prompt                      request.json   state + 类型化的 Jev 问题
一个提示词模板                  ──►     decide.py      发送请求并按答案分支的脚本
一句自然语言需求                        假设清单       自动化之前需要你确认的事项
```

这个 Skill 教编码 Agent 完成转换，自带的命令行工具负责检查和生成各个部分：

- **转换：** 提示词里的每个判断变成一个原子化的 `choice` / `score` / `noul` 问题；
  代码能算的规则（算术、日期、精确匹配）搬进常量块和代码；格式化指令直接丢掉。
- **校验：** 零依赖的命令行工具按 API 契约校验请求，并按 TypeSafe 文档的最佳实践做
  lint，然后才把请求展示给你。
- **生成：** 同一个工具能从校验过的请求直接写出可运行的程序：官方 SDK 的 Python、
  官方 SDK 的 JavaScript、零依赖的 Python，或任何语言都能照抄的原始 `curl` 请求。
- **改造：** 五个原型请求覆盖路由、护栏、评分、抽取和引证核对；复制一个再改。

**第一次用？** [把安装提示词交给你的 Agent](#install)，然后
[粘贴一条使用提示词](#usage)。你不需要自己写 JSON。
[看一条提示词如何一路变成能跑的脚本和真实答案](#example)。

<a id="contents"></a>
## 目录

| 上手 | 探索 | 深入 |
|---|---|---|
| [📦 安装](#install) | [🧪 端到端：提示词进，脚本和答案出](#example) | [🧯 Skill 防住的坑](#pitfalls) |
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

### 要一个能直接运行的脚本

```text
使用 prompt2jev skill，把上面的工单提示词变成一个我能直接对工单运行的 Python 脚本。
先校验请求，再生成脚本并编译；如果我设置了 TYPESAFE_API_KEY，就用示例跑一次，
把真实输出给我看。
```

把 "Python" 换成 "TypeScript" 或 "Go"，Skill 会相应切换到官方 JavaScript SDK 或
纯 HTTP 请求；见[端到端示例](#example)。

Agent 会先收集上下文（占位符、解析器、依赖各输出字段的代码、已有枚举），只在某个
缺口会改变问题形态时才提问，其余一律写成假设。

<a id="package"></a>
### 📐 你会拿到什么

每次转换都是一个五部分的包，顺序固定：

1. **决策契约**：要做的决策、证据单元、每个答案的消费者、未知路径、成功标准。
2. **拆分表**：提示词里的每条指令分别归入 `choice`、`noul`、`score`、`code`、`keep-llm` 或 `drop`。
3. **请求 JSON**：原生 `{model, state, questions}` 结构，先经 `prompt2jev validate --strict` 校验。
4. **组合代码，且是一个能运行的文件**：由 `prompt2jev code` 从校验过的请求生成，用你项目的语言编写，所有阈值和权重集中在一个常量块里，分支逻辑已填好。
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
prompt2jev code request.json --lang python --output decide.py   # 可运行的程序（见下文）
prompt2jev run request.json --dry-run              # 打印将要发送的内容
prompt2jev run request.json                        # 真实调用 TypeSafe（TYPESAFE_API_KEY）
prompt2jev run request.json --provider openrouter  # 或经由 OpenRouter（OPENROUTER_API_KEY）
```

`code` 支持 `--lang python`（官方 `typesafe-sdk`）、`javascript`（官方
`@typesafe-ai/sdk`，Node 20+）、`python-stdlib`（零依赖）和 `curl`（任何语言都能照抄的
原始 HTTP 请求）。它会先按 API 契约校验请求并打印 lint 结果，所以不符合契约的请求永远
不会变成代码；想让 lint 警告也拦住生成，先跑 `validate --strict`。JavaScript 输出是 ES
模块，文件名请用 `.mjs`。

没装命令时，把 `prompt2jev` 换成 `python3 skills/prompt2jev/scripts/prompt2jev.py`。

退出码：`0` 成功；`1` 请求无效、`--strict` 下有 lint 警告、缺少密钥或服务端错误。
`run` 会打印请求、原始响应和每个问题的报告，报告里的置信度分档是示例默认值，需要你
自己调优。响应不符合文档契约时仍会先完整打印再报错，付费调用的结果不会丢失。
`--allow CODE` 可以压制某次请求里你判定为误报的 lint 项。

**密钥。** 官方 API 用 `TYPESAFE_API_KEY`（https://console.typesafe.ai/keys 获取，模型
`jev-latest`），或者用 `OPENROUTER_API_KEY`（https://openrouter.ai/settings/keys 获取，
模型 `typesafe/jev-1.13`）。放在启动 Agent 或命令行的环境变量里；不要粘进聊天、
请求文件或代码仓库。校验和 dry run 不需要密钥。真实调用会花钱，并把 state 发给服务方。

<a id="example"></a>
## 🧪 端到端：提示词进，脚本和真实答案出

把[怎么用](#usage)里那条工单提示词从头走到尾。下面的每个文件都在
[`examples/triage/`](examples/triage/) 里，由所示命令生成；答案是 2026-09-21 从
TypeSafe API 记录下来的真实响应（模型 `jev-1.13.0`）。你自己重跑时，概率可能在小数点
后第二位有所浮动。

**1. 你对 Agent 说的话**

```text
Use the prompt2jev skill to turn this prompt into a Python script I can run:
"Classify the support ticket into billing, shipping, or account. Set urgent=true
if the customer cannot use the product or has a deadline today. If they ask for a
refund, add refund=true. Output JSON only."
```

**2. Skill 写出的请求**（[`examples/triage/request.json`](examples/triage/request.json)）

类别变成带 `other` 兜底的 Choice；"urgent" 变成 Noul，提示词自己的定义搬进
`criteria`；"refund" 变成第二个 Noul；"Output JSON only" 被丢弃，因为答案本来就是
类型化的。它通过 `prompt2jev validate --strict`。

```json
{
  "model": "jev-latest",
  "state": {
    "ticket": {
      "text": "Nobody on my team can log in since this morning and payroll closes at 5pm."
    }
  },
  "questions": {
    "team": {
      "type": "choice",
      "instructions": "Which team should handle `ticket.text`?",
      "criteria": {
        "billing": "Charges, invoices, refunds, or subscriptions.",
        "shipping": "Delivery status, delays, lost or damaged packages.",
        "account": "Login, password, profile, permissions, or security.",
        "other": "None of the listed teams fits, or the message is not a support request."
      }
    },
    "urgent": {
      "type": "noul",
      "instructions": "Does `ticket.text` say the customer cannot use the product or has a deadline today?",
      "criteria": {
        "true": "States that the product is unusable for them now, or names a same-day deadline.",
        "false": "Describes a problem they can work around, or sets no deadline."
      }
    },
    "refund_requested": {
      "type": "noul",
      "instructions": "Does the customer in `ticket.text` explicitly ask for money back or a credit?"
    }
  }
}
```

**3. Skill 生成的脚本**（[`examples/triage/triage.py`](examples/triage/triage.py)）

```bash
prompt2jev validate examples/triage/request.json --strict
prompt2jev code examples/triage/request.json --lang python --output examples/triage/triage.py
```

<details>
<summary>triage.py，与生成结果完全一致</summary>

```python
#!/usr/bin/env python3
"""Jev decision generated by prompt2jev from request.json.

One System One request sends every question at once; the code below reads the typed
answers. Every threshold lives in the constants block. The defaults are illustrative:
tune them on labeled data before an answer triggers an action.

Run:
    pip install typesafe-sdk      # the official SDK
    export TYPESAFE_API_KEY=...   # https://console.typesafe.ai/keys
    python3 triage.py             # judges EXAMPLE_STATE
    python3 triage.py state.json  # judges the JSON object in that file; - reads stdin
"""

from __future__ import annotations

import json
import sys

from typesafe_sdk import Choice, Noul, NoulCriteria, TypeSafeClient

MODEL = "jev-latest"  # pin a versioned id such as jev-1.13.0 once thresholds are tuned

# ----- Constants: every threshold in one place -----
CONFIDENCE_FLOOR = 0.5  # a Choice or Score below this is not acted on; a person decides
NOUL_YES = 0.8  # a Noul at or above this counts as yes
NOUL_NO = 0.2  # a Noul at or below this counts as no; in between is uncertain

QUESTIONS = {
    "team": Choice(
        instructions="Which team should handle `ticket.text`?",
        criteria={
            "billing": "Charges, invoices, refunds, or subscriptions.",
            "shipping": "Delivery status, delays, lost or damaged packages.",
            "account": "Login, password, profile, permissions, or security.",
            "other": "None of the listed teams fits, or the message is not a support request.",
        },
    ),
    "urgent": Noul(
        instructions="Does `ticket.text` say the customer cannot use the product or has a deadline today?",
        criteria=NoulCriteria(
            true="States that the product is unusable for them now, or names a same-day deadline.",
            false="Describes a problem they can work around, or sets no deadline.",
        ),
    ),
    "refund_requested": Noul(
        instructions="Does the customer in `ticket.text` explicitly ask for money back or a credit?",
    ),
}

# The state the request was written against. Build the real one from your own data.
EXAMPLE_STATE = {
    "ticket": {
        "text": "Nobody on my team can log in since this morning and payroll closes at 5pm.",
    },
}


def ask(state):
    """Send every question in one request; they run in parallel."""
    with TypeSafeClient() as client:  # reads TYPESAFE_API_KEY; retries 429 and 529 itself
        return client.system_one(state=state, questions=QUESTIONS, model=MODEL)


def read_choice(answer) -> dict:
    """The chosen option, or needs_review when the distribution is too flat to act on."""
    acted = answer.confidence >= CONFIDENCE_FLOOR
    return {"choice": answer.choice if acted else "needs_review", "confidence": answer.confidence,
            "probabilities": answer.probabilities}


def read_score(answer) -> dict:
    """The probability-weighted level and the nearest level's description."""
    level = int(answer.score + 0.5)
    return {"score": answer.score, "level": level, "label": answer.legend[level], "confidence": answer.confidence}


def read_noul(answer) -> dict:
    """P(yes) with a yes / uncertain / no band. A Noul has no separate confidence."""
    value = answer.noul
    band = "yes" if value >= NOUL_YES else "no" if value <= NOUL_NO else "uncertain"
    return {"noul": value, "band": band}


def decide(state) -> dict:
    """Read every answer, then branch. Replace the return with the decision your code needs."""
    response = ask(state)
    answers = response.answers
    team = read_choice(answers["team"])
    urgent = read_noul(answers["urgent"])
    refund_requested = read_noul(answers["refund_requested"])
    # Branch on the values above here; keep every threshold as a constant at the top.
    return {
        "model": response.model,
        "team": team,
        "urgent": urgent,
        "refund_requested": refund_requested,
    }


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        with (sys.stdin if argv[1] == "-" else open(argv[1], encoding="utf-8")) as handle:
            state = json.load(handle)
    else:
        state = EXAMPLE_STATE
    print(json.dumps(decide(state), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

</details>

**4. 运行它**

```bash
pip install typesafe-sdk
export TYPESAFE_API_KEY=...                        # https://console.typesafe.ai/keys
python3 examples/triage/triage.py                  # 判断 EXAMPLE_STATE 里的工单
python3 examples/triage/triage.py my-ticket.json   # 判断文件里的 {"ticket": {"text": "..."}}
```

**5. 得到的结果**（[`examples/triage/output.json`](examples/triage/output.json)）

```json
{
  "model": "jev-1.13.0",
  "team": {
    "choice": "account",
    "confidence": 0.99,
    "probabilities": {
      "billing": 0.0,
      "shipping": 0.0,
      "account": 1.0,
      "other": 0.0
    }
  },
  "urgent": {
    "noul": 0.98,
    "band": "yes"
  },
  "refund_requested": {
    "noul": 0.01,
    "band": "no"
  }
}
```

这样读：工单归 `account`（概率 1.0，置信度 0.99），它是紧急的（P(是) 0.98，分档
`yes`），没有人要求退款（P(是) 0.01，分档 `no`）。同一个脚本跑 "I was charged twice
for order 5521. Please refund the duplicate charge." 得到 `billing`、紧急 `no`、退款
`yes`。Agent 的最后一步是把 `decide()` 里的 `return` 换成你的路由逻辑，比如把
`needs_review`（置信度低于 `CONFIDENCE_FLOOR`）和 `other` 交给人处理；
[组合模式参考](skills/prompt2jev/references/composition.md) 展示了这处改动。

想用别的语言？`--lang javascript` 用官方 Node SDK 写出同样的程序，`--lang python-stdlib`
不需要任何包，`--lang curl` 打印出 Go、Rust、Java 或任何语言都能照抄的原始请求。写这一节
时，四种输出都对真实 API 跑过。

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
| 组合代码是一个编译过、跑过的文件 | 读者还得自己补完的片段或伪代码 | `prompt2jev code`、SKILL.md 第 4 部分 |

每条 lint 规则都是启发式的，并有文档化的 `--allow` 逃生口。带出处的完整规则集见
[question-design.md](skills/prompt2jev/references/question-design.md)。

<a id="layout"></a>
## 🧭 文件在哪

```
skills/prompt2jev/
  SKILL.md              skill 本体（交付物、六个步骤、红旗）
  references/           操作手册、问题设计、API 契约、组合模式、示例
  assets/               五个通过校验的原型请求
  scripts/prompt2jev.py 校验器、lint 器、代码生成器、调用器（仅 Python 标准库）
examples/triage/        上面的端到端示例：请求、生成的脚本、真实输出
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
