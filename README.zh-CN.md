# code2skill

[![PyPI version](https://img.shields.io/pypi/v/code2skill)](https://pypi.org/project/code2skill/)
[![Python versions](https://img.shields.io/pypi/pyversions/code2skill)](https://pypi.org/project/code2skill/)
[![License](https://img.shields.io/pypi/l/code2skill)](https://github.com/oceanusXXD/code2skill/blob/main/LICENSE)

中文文档。英文说明见 [README.md](./README.md)。

补充文档：

- [CLI Guide](./docs/cli.md)
- [CI Guide](./docs/ci.md)
- [Python API](./docs/python-api.md)
- [Output Layout](./docs/output-layout.md)
- [Release Guide](./docs/release.md)
- [Changelog](./CHANGELOG.md)

`code2skill` 是一个面向真实 Python 仓库的 CLI，用来把源代码转换为结构化项目知识、可供 AI 编程助手直接消费的 Skill 文档，以及适配 Cursor、Claude Code、Codex、GitHub Copilot、Windsurf 等工具的规则文件。

它覆盖从仓库扫描、结构分析、Skill 规划、Skill 生成到规则适配的完整链路，并支持基于 diff 和历史 state 的增量更新。生成结果会直接写入磁盘，便于审阅、提交、复用，并持续集成到本地开发和 CI 流程中。

## 为什么需要 Skill

在传统软件开发里，`README` 是项目的标准入口文档。它面向人类开发者，通常承担项目介绍、安装方式、开发约定和使用示例等职责。

进入 AI IDE 时代后，AI 也会读取 README、文档和源码来理解项目。此时，仓库需要一种更适合 AI 直接消费的知识载体。README 仍然重要，但它往往混合了用户说明、开发说明、背景信息、历史上下文、示例片段和展示性内容。对人类读者来说这很自然；对 AI 来说，更有价值的是被统一整理过的项目约定、关键模式和执行边界。

Skill 就是这种面向 AI 的项目文档形式。

在工程实践里，Skill 可以看作供 AI 阅读的工程化 README。它把与实现直接相关的知识组织成稳定、清晰、可持续维护的文档，让 AI 在不同工具、不同会话和不同阶段都能读取到一致的项目上下文。

Skill 可以表达例如以下信息：

- 项目的核心结构和模块职责边界
- 代码里的关键角色、调用关系和行为约束
- 已有模式、约定和推荐扩展路径
- 特定任务应采用的实现路径和修改方式
- 下游工具规则文件所需的统一信息源

这些信息一旦沉淀为 Skill，就能被 AI IDE、Agent 和自动化流程直接消费。开发者也可以围绕 Skill 迭代协作方式，把“这个仓库应该如何被修改和扩展”沉淀成可审阅、可提交、可演进的工程资产。

## code2skill 提供什么

`code2skill` 围绕真实 Python 仓库构建项目知识，并生成一套可落盘、可追踪、可集成进常规工程流程的产物。

它覆盖从仓库扫描、结构分析、Skill 规划、文档生成到工具规则适配的完整链路，也支持增量重建，让 Skill 能随着仓库演进保持同步。

对于一次性的本地分析，`code2skill` 可以扫描整个仓库并生成完整结果。对于持续开发场景，它可以结合历史 state 和代码 diff，只重建受影响的 Skill，降低重复生成成本，让 CI 内自动更新成为可行方案。

## 它保证什么

- Python 优先分析，核心基于 `ast`、import graph、文件角色推断和模式检测
- Prompt 约束明确：内置 prompt 使用英文、禁止 emoji、避免无证据结论
- 输出可落盘：仓库知识写入文件，而不是留在聊天上下文里
- 执行可度量：每次 `scan`、`estimate` 或 `ci` 都会写出 `report.json`
- 支持增量执行：CI 可以复用历史 state，只重建受影响的 skill

## 命令模型

| 命令 | 是否调用 LLM | 是否写输出 | 主要用途 |
|---|---|---|---|
| `scan` | 会，除非加 `--structure-only` | 会 | 本地全量生成 |
| `estimate` | 不会 | 只写 `report.json` | 预览成本和影响范围 |
| `ci` | 会，除非加 `--structure-only` | 会 | 自动执行 full 或 incremental |
| `adapt` | 不会 | 会 | 把生成后的 skills 复制或合并到目标工具格式 |

## 会生成什么

针对一个 Python 仓库，`code2skill` 可以产出：

- `project-summary.md`：面向人的仓库概览
- `skill-blueprint.json`：Phase 1 的结构蓝图
- `skill-plan.json`：LLM 规划出的 Skill 列表
- `skills/index.md` 和 `skills/*.md`：供 AI 直接消费的 Skill 文档
- 通过 `adapt` 生成 `AGENTS.md`、`CLAUDE.md`、`.cursor/rules/*`、`.github/copilot-instructions.md`、`.windsurfrules`
- `report.json`：执行指标、token 估算和影响摘要
- `state/analysis-state.json`：供增量 CI 复用的状态快照

## Skill 在仓库中的角色

Skill 是仓库知识面向 AI 的标准化表达层。

它连接仓库结构、实现细节、团队约定和工具规则，让 AI 进入项目时可以读取一份统一上下文，而不是每次都从 README、零散文档、历史实现和聊天记录里重新拼装信息。

在工程实践里，这带来几个直接价值：

- 为 AI IDE 提供统一、稳定、低噪声的项目入口
- 让开发者把已有实现模式沉淀为可复用指导
- 让后续变更沿用仓库里已经存在的边界和扩展路径
- 为规则文件生成提供一致的数据来源
- 让仓库知识随着代码变更做增量维护，而不是周期性手工重写

这也是 `code2skill` 的核心价值：组织、传递并持续更新 AI 协作所需的仓库知识。

## 增量更新与持续维护

仓库知识需要跟着代码一起演进。

`code2skill` 支持基于历史分析状态和当前变更范围的增量重建。代码发生修改后，工具可以识别受影响区域，重建相关 Skill，并保留仍然有效的结果。这种机制适合本地开发循环、Pull Request 检查和持续 CI 自动化。

这套工作流的实际收益包括：

- 降低大仓库反复全量生成的成本
- 保持 Skill 与当前代码状态同步
- 把知识维护纳入常规开发流程
- 让生成产物更容易审阅、比较和提交

因此，Skill 不是一次性 prompt 产物，而是一类长期维护的工程资产。

## 适配多种 AI 工具

不同 AI 编程工具使用不同规则文件格式，但它们对高质量项目上下文的需求是相通的。

`code2skill` 会先生成以 Skill 为中心的统一知识层，然后通过 `adapt` 把它复制或合并为目标工具需要的格式，包括：

- `AGENTS.md`
- `CLAUDE.md`
- `.cursor/rules/*`
- `.github/copilot-instructions.md`
- `.windsurfrules`

这样，仓库只需要维护一套核心知识表达，就能向多个 AI 工具分发一致的上下文和约束，避免重复维护。

## 适用场景

`code2skill` 适合以下场景：

- 希望为 AI IDE 提供稳定项目上下文的 Python 仓库
- 希望把仓库知识沉淀成可提交文件而不是聊天内容的团队
- 需要在 CI 里持续更新 AI 规则文件的工程流程
- 需要基于 diff 控制更新范围和成本的项目
- 需要一套知识源同时适配多个 AI 编程工具的仓库

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

1. 发现并过滤文件。
2. 进行粗粒度打分与预算裁剪。
3. 用 `ast` 提取 Python 结构。
4. 构建仓库内 import graph。
5. 修正文件优先级和角色推断。
6. 检测模式并抽象出规则。
7. 组装最终的 `SkillBlueprint`。

### Phase 2：Skill 规划

输入：

- `skill-blueprint.json`

输出：

- `skill-plan.json`

主要步骤：

1. 压缩项目画像、目录、依赖簇、核心模块、规则和流程。
2. 调用一次 LLM。
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
4. 逐个生成 grounded Markdown Skill。
5. 证据不足时显式写出 `[Needs confirmation]`。

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

内置 Prompt 是固定且有约束的：

- Planner 输出必须使用英文、kebab-case 名称、禁止 emoji，并坚持证据优先
- Skill 生成只能使用提供的文件和规则，不允许臆造模块、流程、架构目标或未来计划
- Skill 文档结构固定为五段，便于下游 AI 工具稳定消费
- 证据不足时必须显式写 `[Needs confirmation]`，而不是伪造确定性

这让生成结果更适合进入 Git，也更适合被多个 AI 工具重复消费。

## 当前仓库上的实测数据

下面这组数字采集于 `2026-03-17`，面向本仓库当时的提交 `3714510`，运行环境为 Windows + Python `3.10.6`，使用当前默认限制和启发式定价。

| 指标 | 结果 |
|---|---|
| `scan --structure-only` 耗时 | `1.33s` |
| `estimate` 耗时 | `1.30s` |
| 候选文件 / 最终选中文件 | `51 / 31` |
| 完整结构扫描读取字节数 | `314,585` |
| 保留上下文字符量 | `119,984 chars` |
| 启发式推荐 Skill 数量 | `2` |
| 首次生成估算 | `6,138` 输入 token，`1,610` 输出 token |
| 单 Skill 估算 | `project-overview: 450 in / 850 out`，`backend-architecture: 5,688 in / 760 out` |
| 复用 state 后第二次 `ci --mode auto` | `incremental` |
| 无 diff 的增量读取量 | `20,939 bytes` |
| 无 diff 的增量受影响 Skill | `0` |

补充说明：

- 默认 pricing 模式是 heuristic。它会估算 chars 和 tokens，但在没有真实价格配置时 `estimated_usd` 默认仍为 `0.0`。
- `estimate` 不会真正调用 LLM。它只根据扫描结构预测首次生成、增量重写和增量 patch 的成本。
- `ci --mode auto` 的模式切换不是文案描述，而是已经在本仓库上验证过的真实行为。第一次因为没有历史 state 回退到 `full`，第二次复用 state 后进入 `incremental`。

## 安装

发布版：

```bash
pip install code2skill
```

开发安装：

```bash
pip install -e .[dev]
```

按场景安装的 extras：

```bash
pip install -e .[test]
pip install -e .[release]
```

CLI 入口：

```bash
code2skill --help
python -m code2skill --help
```

顶层 Python 包快捷入口：

```python
from code2skill import adapt_repository, create_scan_config, estimate, run_ci, scan
```

这些高层辅助函数定义在 `code2skill.api` 中，并从包根重新导出，作为当前推荐的 Python API 入口。

## 作为 CLI 使用

先设置模型凭据，再把仓库路径显式传给命令。

Bash：

```bash
export QWEN_API_KEY=...
export CODE2SKILL_LLM=qwen
export CODE2SKILL_MODEL=qwen-plus-latest

code2skill scan /path/to/repo
```

PowerShell：

```powershell
$env:QWEN_API_KEY="..."
$env:CODE2SKILL_LLM="qwen"
$env:CODE2SKILL_MODEL="qwen-plus-latest"

code2skill scan D:\path\to\repo
```

只做结构扫描：

```bash
code2skill scan /path/to/repo --structure-only
```

只预览成本和影响范围：

```bash
code2skill estimate /path/to/repo
```

自动增量模式：

```bash
code2skill ci /path/to/repo --mode auto --base-ref origin/main
```

把生成结果适配为 Codex 的 `AGENTS.md`：

```bash
code2skill adapt /path/to/repo --target codex
```

`adapt` 会把目标文件写到 `repo_path` 下，且相对 `--source-dir` 会按仓库根目录解析。相对 `--output-dir`、`--report-json`、`--diff-file`、`--pricing-file` 也会按 `repo_path` 解析。如果源 skills 目录不存在，命令会直接报错，不会静默跳过。

## 作为 Python 包使用

在简单自动化场景里，优先使用 `code2skill.api` 提供的快捷函数，或者包根导出的同名入口，而不是手动拼装多层 dataclass。

```python
from pathlib import Path

from code2skill import adapt_repository, estimate, scan

repo = Path("/path/to/repo")

preview = estimate(repo)
result = scan(
    repo,
    output_dir=".code2skill",
    llm_provider="qwen",
    llm_model="qwen-plus-latest",
    max_skills=6,
)
written = adapt_repository(repo, target="codex")

print(preview.report_path)
print(result.generated_skills)
print(written)
```

如果需要更细粒度控制，可以组合 `create_scan_config` 与 `scan_repository`、`estimate_repository`、`run_ci_repository`。

Python API 的路径语义：

- `repo_path` 会先解析成绝对路径，并作为仓库根目录
- 相对 `output_dir` 会从 `repo_path` 解析
- 相对 `report_path`、`diff_file`、`pricing_file` 也会从 `repo_path` 解析
- 传给 `adapt_repository(...)` 的相对 `source_dir` 会从 `repo_path` 解析
- 如果没有显式传 `report_path`，默认写到 `output_dir/report.json`
- 只有当历史 state 属于同一个仓库根目录时，增量状态才会被复用

## LLM 后端

支持的 provider：

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

- `qwen` 默认使用 DashScope international compatible endpoint
- `qwen` 会读取 `QWEN_API_KEY`，也兼容 `DASHSCOPE_API_KEY`
- 缺少对应凭据时会直接失败，不会静默降级

## 成本估算与 `report.json`

`estimate` 用于预检和 CI 规划。它不会生成完整产物，只会写出 `report.json`。

报告里包含：

- 选中文件数和保留字符量
- 扫描时读取的字节数
- changed files、affected files、affected skills
- `first_generation_cost`
- `incremental_rewrite_cost`
- `incremental_patch_cost`
- pricing 元数据和运行备注

如果希望得到真实 USD 估算，而不是只看 token 量级，可以传入 pricing 文件：

```bash
code2skill estimate --pricing-file pricing.json
```

`pricing.json` 格式如下：

```json
{
  "model": "qwen-plus-latest",
  "input_per_1m": 0.0,
  "output_per_1m": 0.0,
  "chars_per_token": 4.0
}
```

把其中的 `0.0` 替换成当前模型的真实价格后，再用于预算估算。

## CI/CD 集成

`code2skill ci --mode auto` 是自动化场景的主入口。

它会：

- 从 Git 历史或显式 diff 文件中识别变更文件
- 通过反向依赖扩展影响范围
- 把变更映射到受影响的 Skill
- 只重建必要的 Skill 产物
- 当 Skill 集合变化时清理过期文件

常见回退到 full 的原因：

- 没有 `.code2skill/state/analysis-state.json`
- 没有历史 `skill-plan.json`
- 关键配置发生变化，例如 `pyproject.toml`
- 改动文件过多，不适合安全增量
- 缓存 state 记录的 `repo_root` 与当前仓库根目录不一致

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

- `fetch-depth: 0` 很重要，否则 base ref 可能不在本地历史里
- 缓存 `.code2skill` 是增量提速的关键
- 一个分支上的第一次 CI 通常接近 `full`，因为还没有历史 state
- 如果只想做不调用 LLM 的 CI 健康检查，可以运行 `code2skill ci --mode auto --structure-only`
- 当前仓库已经提供 `.github/workflows/` 下的 CI 和 release workflow

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
- 从真实代码生成 Cursor rules，而不是维护手写说明
- 在大改动前先给 Claude Code 一套仓库专属 Skill
- 在 CI 里持续维护 AI 面向仓库知识

## 当前边界

- 当前重点优化对象是 Python 仓库
- 非 Python 代码不是一等分析目标
- 输出质量仍受仓库清晰度和所选模型影响
- 当前仍处于 `0.1.x` 阶段，后续还会持续演进

## License

Apache-2.0。见 [LICENSE](./LICENSE)。
