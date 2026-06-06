# code2skill

[![PyPI version](https://img.shields.io/pypi/v/code2skill)](https://pypi.org/project/code2skill/)
[![Python versions](https://img.shields.io/pypi/pyversions/code2skill)](https://pypi.org/project/code2skill/)
[![License](https://img.shields.io/pypi/l/code2skill)](https://github.com/oceanusXXD/code2skill/blob/main/LICENSE)

语言：[English](https://github.com/oceanusXXD/code2skill/blob/main/README.md) | 简体中文

`code2skill` 会把 Python 仓库转换成编码助手可以读取的项目说明文件。

它会扫描源码和配置，写出 `.code2skill/` 产物目录，生成聚焦的 Skill 文档，并发布到 Codex、Claude Code、Cursor、GitHub Copilot 或 Windsurf。产物都是仓库文件，维护者可以审阅、提交、在 CI 中刷新。

当一个 Python 项目希望编码助手遵守当前模块边界、工作流、API 契约和维护规则时，可以使用 `code2skill`。

## 这个仓库可以做什么

- 用 AST、import graph、配置抽取和文件角色推断分析 Python 仓库。
- 写出 `.code2skill/` bundle，包括项目概要、参考文档、Skill plan、生成的 Skills、执行报告和增量 state。
- 在生成前估算模型成本和受影响 Skills。
- 使用 OpenAI Responses API、OpenAI-compatible Responses endpoint、Claude 或 Qwen，从仓库证据生成 Skill Markdown。
- 把生成的 Skills 发布到 `AGENTS.md`、`CLAUDE.md`、`.cursor/rules/*`、`.github/copilot-instructions.md` 和 `.windsurfrules`。
- 在 CI 中用 full 或 incremental 模式刷新产物。
- 用 `doctor` 校验 bundle 和目标工具文件是否可用。

## 适合谁

| 用户 | 需求 | code2skill 提供什么 |
|---|---|---|
| Python 仓库维护者 | 编码助手需要遵守本地架构和命名方式 | 基于源码生成 Skills，并提供 readiness 检查 |
| DevEx 和平台团队 | 多个服务需要统一的助手接入流程 | CLI、Python API、CI 刷新和统一输出结构 |
| 开源维护者 | 贡献者需要公开的项目规则，而不是私有聊天上下文 | 可提交、可审阅的项目说明文件 |
| 工具评估者 | 同一个仓库需要支持多个编码助手 | 一套 Skill 层适配多个目标格式 |

## 常见场景

| 场景 | 什么时候用 | 预期结果 |
|---|---|---|
| 首次接入编码助手 | 仓库开始使用 Codex、Cursor、Claude Code、Copilot 或 Windsurf | `scan`、`adapt`、`doctor` 产出 ready 的目标文件 |
| PR 刷新 | 代码改动可能让旧说明过期 | `ci --mode auto` 报告 changed files、affected files 和 affected Skills |
| 多工具接入 | 团队同时使用多个编码助手 | `adapt --target all` 写出一致的目标文件 |
| 平台自动化 | DevEx 团队跨多个 Python 服务运行同一流程 | Python API 返回结构化结果和 readiness |
| 开源贡献者 onboarding | 新贡献者改代码前需要项目实现规则 | 生成的 Skills 和 docs 说明仓库的工作契约 |

## 安装

需要 Python 3.10 或更高版本。

```bash
python -m pip install code2skill
code2skill --version
code2skill --help
```

预期 CLI 命令包括 `scan`、`estimate`、`ci`、`adapt` 和 `doctor`。

如果 console script 不在 `PATH` 中，可以使用模块入口：

```bash
python -m code2skill --help
```

## 第一次运行

先跑一次不调用模型的结构检查，确认包能读取仓库并写出本地产物：

```bash
code2skill scan . --structure-only
```

预览模型成本和增量影响：

```bash
code2skill estimate .
```

使用模型生成 Skills：

```bash
export QWEN_API_KEY=...
code2skill scan . --llm qwen --model qwen-plus-latest
```

发布到目标工具：

```bash
code2skill adapt . --target codex
```

检查 bundle 和目标文件是否可用：

```bash
code2skill doctor . --target codex
```

建议审阅并提交与你工作流相关的文件：

- `.code2skill/adoption-guide.md`
- `.code2skill/skills/index.md`
- `.code2skill/skills/*.md`
- 适配后的目标文件，例如 `AGENTS.md`、`CLAUDE.md`、`.cursor/rules/*`、`.github/copilot-instructions.md` 或 `.windsurfrules`

`.code2skill/report.json` 可用于查看选中文件、执行模式、变更文件、受影响 Skills、成本估算和写出产物。

## 模型配置

常用环境变量：

```bash
export CODE2SKILL_LLM=qwen
export CODE2SKILL_MODEL=qwen-plus-latest
export CODE2SKILL_OUTPUT_DIR=.code2skill
export CODE2SKILL_MAX_SKILLS=6
export CODE2SKILL_BASE_REF=origin/main
```

Provider key：

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export QWEN_API_KEY=...
```

OpenAI Responses API：

```bash
export CODE2SKILL_LLM=openai
export CODE2SKILL_MODEL=gpt-4o-mini
export CODE2SKILL_OPENAI_API_KEY=...
code2skill scan .
```

OpenAI-compatible Responses endpoint：

```bash
export CODE2SKILL_LLM=openai
export CODE2SKILL_MODEL=<responses-compatible-model>
export CODE2SKILL_OPENAI_API_KEY=...
export CODE2SKILL_OPENAI_BASE_URL=https://example.com/v1
code2skill scan .
```

`CODE2SKILL_OPENAI_BASE_URL` 可以是 `/v1` base URL，也可以直接是 `/responses` endpoint。

## 命令

| 命令 | 调用模型 | 写文件 | 主要用途 |
|---|---:|---:|---|
| `scan` | 是，除非 `--structure-only` | 是 | 本地全量分析和 Skill 生成 |
| `estimate` | 否 | 只写 `report.json` | 成本和影响预览 |
| `ci` | 是，除非 `--structure-only` | 是 | 面向自动化的全量或增量刷新 |
| `adapt` | 否 | 是 | 把 generated Skills 发布到目标工具文件 |
| `doctor` | 否 | 否 | 校验 bundle、Skill plan、state、目标文件和 readiness |

## 输出结构

默认产物目录是 `.code2skill/`。

| 路径 | 用途 |
|---|---|
| `adoption-guide.md` | 仓库级采用 checklist 和下一步工作流 |
| `project-summary.md` | 面向人的仓库概要 |
| `skill-blueprint.json` | 结构化仓库蓝图 |
| `skill-plan.json` | 模型规划出的 Skill 清单 |
| `references/*.md` | 架构、风格、工作流和 API 参考 |
| `skills/index.md` | 生成的 Skill 索引 |
| `skills/*.md` | 生成的编码助手工作说明 |
| `report.json` | 执行指标、成本估算、变更文件、受影响 Skills 和产物列表 |
| `state/analysis-state.json` | 增量 CI 缓存 |

## 目标工具

| Target | 命令 | 输出 |
|---|---|---|
| Codex | `code2skill adapt . --target codex` | `AGENTS.md` |
| Claude Code | `code2skill adapt . --target claude` | `CLAUDE.md` |
| Cursor | `code2skill adapt . --target cursor` | `.cursor/rules/*.md` 和 `.cursor/rules/.code2skill-manifest.json` |
| GitHub Copilot | `code2skill adapt . --target copilot` | `.github/copilot-instructions.md` |
| Windsurf | `code2skill adapt . --target windsurf` | `.windsurfrules` |
| 全部目标 | `code2skill adapt . --target all` | 以上全部 |

合并型 target 使用托管区块：

```text
<!-- code2skill:start -->
...
<!-- code2skill:end -->
```

托管区块外的手写内容会保留。Cursor 使用复制的 Skill 文件和 manifest，后续运行可以删除过期 generated 文件，同时保留团队手写规则。

## CI 增量刷新

首次 bundle 存在后，可以用 `ci --mode auto` 复用 state，并在代码变化时只刷新受影响的 Skill 输出：

```bash
code2skill ci . --mode auto --base-ref origin/main --head-ref HEAD
code2skill adapt . --target codex
code2skill doctor . --target codex
```

第一次 CI 运行通常会回退到 `full`，因为还没有历史 state。后续运行可以复用 `.code2skill/state/analysis-state.json` 和 `skill-plan.json` 判断是否可以安全增量刷新。

## Python API

包根导出推荐的高层 API：

```python
from pathlib import Path

from code2skill import adapt_repository, doctor, estimate, scan

repo = Path(".")

preview = estimate(repo)
result = scan(
    repo,
    llm_provider="qwen",
    llm_model="qwen-plus-latest",
    max_skills=6,
)
written = adapt_repository(repo, target="codex")
readiness = doctor(repo, target="codex")

print(preview.report_path)
print(result.generated_skills)
print(written)
print(readiness.ready, readiness.score)
```

更底层的自动化可以组合 `create_scan_config(...)`、`scan_repository(...)`、`estimate_repository(...)` 或 `run_ci_repository(...)`。

## 文档

- English README: [README.md](https://github.com/oceanusXXD/code2skill/blob/main/README.md)
- 中文 README: [README.zh-CN.md](https://github.com/oceanusXXD/code2skill/blob/main/README.zh-CN.md)
- [Getting Started](https://github.com/oceanusXXD/code2skill/blob/main/docs/getting-started.md)
- [Use Cases](https://github.com/oceanusXXD/code2skill/blob/main/docs/use-cases.md)
- [CLI Guide](https://github.com/oceanusXXD/code2skill/blob/main/docs/cli.md)
- [CI Guide](https://github.com/oceanusXXD/code2skill/blob/main/docs/ci.md)
- [Python API](https://github.com/oceanusXXD/code2skill/blob/main/docs/python-api.md)
- [Output Layout](https://github.com/oceanusXXD/code2skill/blob/main/docs/output-layout.md)
- [Release Guide](https://github.com/oceanusXXD/code2skill/blob/main/docs/release.md)
- [Changelog](https://github.com/oceanusXXD/code2skill/blob/main/CHANGELOG.md)

## 保证

- Python-first 分析：使用 `ast`、import graph、文件角色推断和模式检测。
- Evidence-first prompt：要求源码引用，避免无证据结论，并显式保留不确定性。
- 产物写入文件，而不是留在聊天上下文中。
- 每次运行写出 `report.json`，便于复查。
- 支持 state、diff impact 和受影响 Skill 映射。
- 通过 `doctor` 检查 bundle 与目标文件。

## 限制

- 主要优化对象是 Python 仓库。
- 非 Python 代码只作为辅助上下文扫描，不是一等分析目标。
- 输出质量仍受仓库清晰度和所选模型影响。
- 当前处于 `0.1.x` 阶段，公开行为仍可能继续演进。

## License

Apache-2.0。见 [LICENSE](https://github.com/oceanusXXD/code2skill/blob/main/LICENSE)。
