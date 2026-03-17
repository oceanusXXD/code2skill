# code2skill

[![PyPI version](https://img.shields.io/pypi/v/code2skill)](https://pypi.org/project/code2skill/)
[![Python versions](https://img.shields.io/pypi/pyversions/code2skill)](https://pypi.org/project/code2skill/)
[![License](https://img.shields.io/pypi/l/code2skill)](https://github.com/oceanusXXD/code2skill/blob/main/LICENSE)

中文文档。英文主页请看 [README.md](./README.md)。

`code2skill` 是一个面向 Python 仓库的 CLI。它会把真实代码仓库转换成结构化项目知识、可复用的 Skill 文档，以及可直接适配到 Cursor、Claude Code、Codex、GitHub Copilot、Windsurf 的规则文件。

它不是一次性“总结仓库”的工具，而是把仓库知识沉淀成稳定文件，方便后续编码、审查、补丁生成和增量更新。

## 它会产出什么

对一个真实 Python 仓库，`code2skill` 可以产出：

- `project-summary.md`：给人快速浏览的项目概览
- `skill-blueprint.json`：Phase 1 的结构化仓库蓝图
- `skill-plan.json`：LLM 规划出的 Skill 列表和阅读文件
- `skills/index.md` 和 `skills/*.md`：真正给 AI 编程助手消费的 Skill 文档
- `AGENTS.md`、`CLAUDE.md`、`.cursor/rules/*` 等目标格式文件

## 为什么要做成这样

很多 AI 编程工作流依然依赖：

- 很长的一次性 prompt
- 聊天历史
- 手工维护但很快过期的项目说明

这在真实仓库里很难长期保持一致。

`code2skill` 的设计重点是：

- 先做结构扫描，再让 LLM 规划和生成
- 让仓库知识落成文件，而不是留在聊天窗口里
- 让 AI 上下文可以提交、审核、复用、增量更新
- 尽量把规则建立在代码、依赖、模式和证据之上

## 当前适用范围

- 目前只面向 Python 仓库
- Python 源码结构提取使用 `ast`
- Phase 1 不依赖 LLM
- 支持 `scan`、`estimate`、`ci`、`adapt`
- 支持 `openai`、`claude`、`qwen`
- 默认 prompt 和生成的 Skill 文档使用英文

## 安装

发布版：

```bash
pip install code2skill
```

开发版：

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

如果你只想先做结构分析，不调用 LLM：

```bash
code2skill scan --structure-only
```

如果已经有历史状态，想自动走增量：

```bash
code2skill ci --mode auto
```

## 常用命令

完整扫描并生成 Skill：

```bash
code2skill scan --llm qwen --model qwen-plus-latest
```

只做结构扫描：

```bash
code2skill scan --structure-only
```

只做影响范围和成本估算：

```bash
code2skill estimate
```

CI 自动增量：

```bash
code2skill ci --mode auto --base-ref origin/main
```

把 Skill 适配成 Codex 的 `AGENTS.md`：

```bash
code2skill adapt --target codex --source-dir .code2skill/skills
```

把 Skill 适配到所有支持的目标：

```bash
code2skill adapt --target all --source-dir .code2skill/skills
```

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

1. 发现文件并过滤低价值文件
2. 做粗评分和预算裁剪
3. 用 Python AST 提取结构骨架
4. 构建 import graph
5. 基于结构信号修正文件优先级和角色
6. 检测模式并提炼抽象规则
7. 组装 `SkillBlueprint`

### Phase 2：Skill 规划

输入：

- `skill-blueprint.json`

输出：

- `skill-plan.json`

主要步骤：

1. 压缩项目画像、目录摘要、依赖簇、核心模块、规则和流程
2. 调用 1 次 LLM
3. 决定应该生成哪些 Skill
4. 为每个 Skill 选出最值得阅读的文件

### Phase 3：Skill 生成

输入：

- `skill-plan.json`
- 每个 Skill 对应的文件正文或骨架

输出：

- `skills/index.md`
- `skills/*.md`

主要步骤：

1. 为每个 Skill 收集精确的文件上下文
2. 小文件直接内联，大文件使用骨架摘要
3. 过滤与该 Skill 相关的仓库规则
4. 生成 grounded 的 Skill Markdown
5. 清洗并校验输出内容

### Adapt：目标格式适配

输入：

- `skills/*.md`

输出：

- Cursor 规则
- `CLAUDE.md`
- `AGENTS.md`
- `.github/copilot-instructions.md`
- `.windsurfrules`

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

## LLM 后端

支持的提供商：

- `openai`
- `claude`
- `qwen`

环境变量：

Bash：

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export QWEN_API_KEY=...
```

PowerShell：

```powershell
$env:OPENAI_API_KEY="..."
$env:ANTHROPIC_API_KEY="..."
$env:QWEN_API_KEY="..."
```

常见默认值：

```bash
export CODE2SKILL_LLM=qwen
export CODE2SKILL_MODEL=qwen-plus-latest
export CODE2SKILL_OUTPUT_DIR=.code2skill
export CODE2SKILL_MAX_SKILLS=6
export CODE2SKILL_BASE_REF=origin/main
```

说明：

- `qwen` 默认走阿里 DashScope 国际站兼容接口
- `qwen` 会读取 `QWEN_API_KEY`，也兼容 `DASHSCOPE_API_KEY`
- 缺少凭据时会直接报错，不会静默降级

## 增量 CI

`code2skill ci --mode auto` 主要用于自动化和 CI 场景。

它会：

- 从 git 状态或 diff 文件识别变更文件
- 通过内部反向依赖扩展影响范围
- 选择受影响的 Skill
- 尽量只重建必要产物
- 在规划结果变化时清理旧的 skill 文件

常见会自动回退到全量重建的情况：

- 还没有历史状态
- 核心配置变化太大
- 改动文件过多
- 仓库结构变化使增量可信度不足

## 适合哪些场景

- 从已有 Python 后端仓库自动生成 Codex `AGENTS.md`
- 给 Cursor 生成来自真实代码的规则，而不是手工写说明
- 给 Claude Code 提供仓库级 Skill 文档后再做大改动
- 在 CI 里随着代码变化持续更新 AI 可消费上下文

## 当前限制

- 目前主要针对 Python 仓库优化
- JavaScript / TypeScript 不是当前主目标
- 输出质量仍然取决于仓库结构清晰度和所选模型
- 当前仍属于 `0.1.x` Alpha 阶段，生成质量还会继续迭代

## 许可证

Apache-2.0，见 [LICENSE](./LICENSE)。
