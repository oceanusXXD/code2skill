# code2skill

[![PyPI version](https://img.shields.io/pypi/v/code2skill)](https://pypi.org/project/code2skill/)
[![Python versions](https://img.shields.io/pypi/pyversions/code2skill)](https://pypi.org/project/code2skill/)
[![License](https://img.shields.io/pypi/l/code2skill)](https://github.com/oceanusXXD/code2skill/blob/main/LICENSE)

中文文档。英文主页见 [README.md](./README.md)。

`code2skill` 是一个面向真实 Python 仓库的 CLI。它会把仓库转换成结构化项目知识、可直接给 AI 编程助手消费的 Skill 文档，以及适配 Cursor、Claude Code、Codex、GitHub Copilot、Windsurf 的规则文件。

它的目标不是一次性“总结仓库”，而是把仓库知识沉淀成可以复用、可审查、可提交、可增量更新的文件产物。

## 它保证什么

- Python 优先分析，核心基于 `ast`、import graph、角色推断和模式检测
- Prompt 内建且有明确约束：英文输出、禁止 emoji、只允许基于证据推断
- 输出落盘，不依赖聊天上下文
- 每次执行都会生成 `report.json`，可追踪文件量、字符量、影响范围和成本估算
- 支持增量执行，CI 可以复用历史 state，只重建受影响的 Skill

## 命令模型

| 命令 | 是否调用 LLM | 是否写输出 | 主要用途 |
|---|---|---|---|
| `scan` | 会，除非加 `--structure-only` | 会 | 本地全量生成 |
| `estimate` | 不会 | 只写 `report.json` | 预估成本与影响范围 |
| `ci` | 会，除非加 `--structure-only` | 会 | CI 中自动选择 full 或 incremental |
| `adapt` | 不会 | 会 | 把 Skill 复制或合并成目标工具需要的规则文件 |

## 会生成什么

针对一个 Python 仓库，`code2skill` 可以产出：

- `project-summary.md`，面向人的项目概览
- `skill-blueprint.json`，Phase 1 的结构蓝图
- `skill-plan.json`，LLM 规划出的 Skill 列表
- `skills/index.md` 和 `skills/*.md`，真正给 AI 助手消费的 Skill 文档
- 通过 `adapt` 生成 `AGENTS.md`、`CLAUDE.md`、`.cursor/rules/*`、`.github/copilot-instructions.md`、`.windsurfrules`
- `report.json`，记录执行指标、token 估算和影响摘要
- `state/analysis-state.json`，用于 CI 增量复用

## 整体流程

### Phase 1：结构扫描

输入：

- 仓库路径

输出：

- `project-summary.md`
- `skill-blueprint.json`
- `references/architecture.md`
- `references/code-style.md`
- `references/workflows.md`
- `references/api-usage.md`
- `report.json`
- `state/analysis-state.json`

主要步骤：

1. 发现文件并过滤低价值文件。
2. 做粗评分和预算裁剪。
3. 用 `ast` 提取 Python 结构。
4. 构建仓库内 import graph。
5. 修正文件优先级和角色。
6. 检测模式并提炼抽象规则。
7. 组装最终 `SkillBlueprint`。

### Phase 2：Skill 规划

输入：

- `skill-blueprint.json`

输出：

- `skill-plan.json`

主要步骤：

1. 压缩项目画像、目录、依赖簇、核心模块、规则和流程。
2. 调用 1 次 LLM。
3. 决定应该生成哪些 Skill。
4. 为每个 Skill 选择最有代表性的阅读文件。

### Phase 3：Skill 生成

输入：

- `skill-plan.json`
- 每个 Skill 对应的源码正文或结构摘要

输出：

- `skills/index.md`
- `skills/*.md`

主要步骤：

1. 为每个 Skill 收集精确上下文。
2. 小文件直接内联，大文件使用结构摘要。
3. 过滤与该 Skill 最相关的仓库规则。
4. 按 Skill 逐个生成 grounded Markdown。
5. 在证据不足的位置明确写 `[Needs confirmation]`。

### Adapt：目标格式适配

输入：

- `skills/*.md`

输出：

- Cursor rules
- `CLAUDE.md`
- `AGENTS.md`
- `.github/copilot-instructions.md`
- `.windsurfrules`

## Prompt 策略

内建 Prompt 是固定且强约束的：

- Planner 输出必须是英文、使用 kebab-case 名称、不能写 emoji、必须基于结构证据。
- Skill 生成只能使用提供的文件和规则，不允许编造模块、流程、架构目标或未来计划。
- Skill 文档结构固定为五段，方便下游 AI 工具稳定消费。
- 证据不足时必须显式写 `[Needs confirmation]`，而不是伪造确定性。

这也是为什么它更适合被提交进 Git 和被多个 AI 工具重复消费。

## 当前仓库上的实测数据

下面这组数字是在 `2026-03-17`，对本仓库当前提交 `3714510`，在 Windows + Python `3.10.6` 环境下，使用默认限制和默认 heuristic pricing 实测得到的。

| 指标 | 结果 |
|---|---|
| `scan --structure-only` 耗时 | `1.33s` |
| `estimate` 耗时 | `1.30s` |
| 候选文件 / 最终选中文件 | `51 / 31` |
| 完整结构扫描读取字节数 | `314,585` |
| 最终保留上下文字符量 | `119,984 chars` |
| 启发式推荐 Skill 数量 | `2` |
| 首次生成估算 | `6,138` 输入 token，`1,610` 输出 token |
| 单 Skill 估算 | `project-overview: 450 in / 850 out`，`backend-architecture: 5,688 in / 760 out` |
| 复用 state 后第二次 `ci --mode auto` | `incremental` |
| 无 diff 的增量读取量 | `20,939 bytes` |
| 无 diff 的增量受影响 Skill | `0` |

补充说明：

- 默认 pricing 是 heuristic，只估算 chars 和 tokens，不会直接给出真实美元价格，所以 `estimated_usd` 默认是 `0.0`。
- `estimate` 不会真的调用 LLM，它是根据当前扫描结果预测首次生成、增量重写、增量 patch 的体量。
- `ci --mode auto` 的模式切换不是文案说明，而是已经在本仓库上验证过的真实行为。第一次因为没有 state 回退到 `full`，第二次在复用 state 时走 `incremental`。

## 安装

发布版：

```bash
pip install code2skill
```

开发安装：

```bash
pip install -e .[dev]
```

命令入口：

```bash
code2skill --help
python -m code2skill --help
```

## 快速开始

Bash：

```bash
export QWEN_API_KEY=...
export CODE2SKILL_LLM=qwen
export CODE2SKILL_MODEL=qwen-plus-latest

cd /path/to/repo
code2skill scan
```

PowerShell：

```powershell
$env:QWEN_API_KEY="..."
$env:CODE2SKILL_LLM="qwen"
$env:CODE2SKILL_MODEL="qwen-plus-latest"

Set-Location D:\path\to\repo
code2skill scan
```

只做结构扫描：

```bash
code2skill scan --structure-only
```

只做成本和影响范围预估：

```bash
code2skill estimate
```

自动增量模式：

```bash
code2skill ci --mode auto --base-ref origin/main
```

把生成结果适配为 Codex 的 `AGENTS.md`：

```bash
code2skill adapt --target codex --source-dir .code2skill/skills
```

## LLM 后端

支持：

- `openai`
- `claude`
- `qwen`

环境变量：

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export QWEN_API_KEY=...
```

常用默认值：

```bash
export CODE2SKILL_LLM=qwen
export CODE2SKILL_MODEL=qwen-plus-latest
export CODE2SKILL_OUTPUT_DIR=.code2skill
export CODE2SKILL_MAX_SKILLS=6
export CODE2SKILL_BASE_REF=origin/main
```

说明：

- `qwen` 默认使用阿里 DashScope 国际兼容端点。
- `qwen` 会读取 `QWEN_API_KEY`，也兼容 `DASHSCOPE_API_KEY`。
- 没有对应凭据时会直接报错，不会静默降级。

## 成本估算与 `report.json`

`estimate` 用于预检和 CI 规划。它不会生成完整产物，只会写出 `report.json`。

报告里会包含：

- 选中文件数和保留字符量
- 扫描时读取的字节数
- changed files、affected files、affected skills
- `first_generation_cost`
- `incremental_rewrite_cost`
- `incremental_patch_cost`
- pricing 元数据和运行备注

如果你希望得到真实 USD 估算，而不是只看 token 量级，需要传入 pricing 文件：

```bash
code2skill estimate --pricing-file pricing.json
```

`pricing.json` 结构如下：

```json
{
  "model": "qwen-plus-latest",
  "input_per_1m": 0.0,
  "output_per_1m": 0.0,
  "chars_per_token": 4.0
}
```

把其中的 `0.0` 替换成你当前使用模型的真实价格即可。

## CI/CD 集成方式

`code2skill ci --mode auto` 是自动化场景的主入口。

它会：

- 从 Git 历史或显式 diff 文件里识别变更文件
- 通过反向依赖扩展影响范围
- 把变更映射到受影响的 Skill
- 只重建必要的 Skill 产物
- 在 Skill 集合变化时清理过期文件

常见回退到 full 的原因：

- 没有 `.code2skill/state/analysis-state.json`
- 没有历史 `skill-plan.json`
- 关键配置变了，例如 `pyproject.toml`
- 改动文件太多，不适合安全增量

推荐的 GitHub Actions 配置：

```yaml
name: code2skill

on:
  pull_request:
  push:
    branches:
      - main

jobs:
  build-skills:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Restore code2skill cache
        uses: actions/cache@v4
        with:
          path: .code2skill
          key: code2skill-${{ runner.os }}-${{ github.ref_name }}-${{ github.sha }}
          restore-keys: |
            code2skill-${{ runner.os }}-${{ github.ref_name }}-
            code2skill-${{ runner.os }}-

      - name: Install
        run: pip install code2skill

      - name: Run code2skill
        env:
          QWEN_API_KEY: ${{ secrets.QWEN_API_KEY }}
          CODE2SKILL_LLM: qwen
          CODE2SKILL_MODEL: qwen-plus-latest
        run: |
          code2skill ci \
            --mode auto \
            --base-ref origin/${{ github.base_ref || 'main' }} \
            --head-ref HEAD

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: code2skill-output
          path: .code2skill
```

说明：

- `fetch-depth: 0` 很重要，否则基线分支可能不在本地历史里。
- 缓存 `.code2skill` 是增量提速的关键。
- 一个分支上的第一次 CI 运行通常会接近 full，因为还没有历史 state。
- 如果你只想做无 LLM 的 CI 健康检查，可以运行 `code2skill ci --mode auto --structure-only`。

## 输出目录

典型输出如下：

```text
.code2skill/
  project-summary.md
  skill-blueprint.json
  skill-plan.json
  report.json
  references/
    architecture.md
    code-style.md
    workflows.md
    api-usage.md
  skills/
    index.md
    *.md
  state/
    analysis-state.json
```

## 典型场景

- 从一个已有 Python 后端仓库直接生成 Codex `AGENTS.md`
- 从真实代码生成 Cursor rules，而不是手写说明文档
- 在大改动前先给 Claude Code 一套仓库专属 Skill
- 在 CI 里持续维护 AI 面向仓库知识

## 当前边界

- 当前重点优化对象是 Python 仓库
- 非 Python 代码不是一等分析目标
- 输出质量仍然受仓库清晰度和所选模型影响
- 当前还处于 `0.1.x` 阶段，后续还会继续打磨

## License

Apache-2.0，见 [LICENSE](./LICENSE)。
