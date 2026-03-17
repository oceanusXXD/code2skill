# code2skill

中文优先，后附英文快速说明。
Chinese first, with an English quick reference at the end.

`code2skill` 是一个面向 Python 仓库的 CLI。它会把真实代码仓库编译成一组结构化项目知识和 Skill 文档，供 Cursor、Claude Code、Codex、Copilot、Windsurf 等 AI 编程助手消费。

它的目标不是“总结仓库”，而是生成能直接用于后续编码、审查和增量更新的高密度上下文。

## 适用范围

- 当前只面向 Python 仓库
- Phase 1 不调用 LLM
- Python 源码使用 `ast` 做结构提取
- 支持 `scan`、`estimate`、`ci`、`adapt`
- 支持 `openai`、`claude`、`qwen`
- 默认使用英文 prompt 和英文 Skill 输出，不使用 emoji，证据不足处标记 `[Needs confirmation]`

## 核心特性

- 结构扫描：目录发现、过滤、预算裁剪、Python 骨架提取
- 结构分析：import graph、角色修正、模式检测、抽象规则提炼
- Skill 规划：用 1 次 LLM 调用决定生成哪些 Skill、每个 Skill 读哪些文件
- Skill 生成：按 Skill 聚焦上下文逐个生成高质量 Markdown
- 增量更新：在 CI 中根据 Git diff 只重写受影响的 Skill
- 目标适配：把 `skills/*.md` 复制或合并到 Cursor / Codex / Claude 等约定位置

## 30 秒上手

先设置模型环境变量：

```bash
export QWEN_API_KEY=...
export CODE2SKILL_LLM=qwen
export CODE2SKILL_MODEL=qwen-plus-latest
```

PowerShell:

```powershell
$env:QWEN_API_KEY="..."
$env:CODE2SKILL_LLM="qwen"
$env:CODE2SKILL_MODEL="qwen-plus-latest"
```

进入要分析的仓库目录后直接运行：

```bash
code2skill scan
```

现在 `repo_path` 默认就是当前目录，所以在仓库根目录里不需要再写 `.`。

如果只想先做结构扫描：

```bash
code2skill scan --structure-only
```

如果已经有历史状态，想走自动增量：

```bash
code2skill ci --mode auto
```

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

## 常用环境变量

这些变量是为了让本地和 CI 使用更短的命令。

LLM API Key：

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export QWEN_API_KEY=...
```

PowerShell:

```powershell
$env:OPENAI_API_KEY="..."
$env:ANTHROPIC_API_KEY="..."
$env:QWEN_API_KEY="..."
```

CLI 默认值：

```bash
export CODE2SKILL_LLM=qwen
export CODE2SKILL_MODEL=qwen-plus-latest
export CODE2SKILL_OUTPUT_DIR=.code2skill
export CODE2SKILL_MAX_SKILLS=6
export CODE2SKILL_BASE_REF=origin/main
```

PowerShell:

```powershell
$env:CODE2SKILL_LLM="qwen"
$env:CODE2SKILL_MODEL="qwen-plus-latest"
$env:CODE2SKILL_OUTPUT_DIR=".code2skill"
$env:CODE2SKILL_MAX_SKILLS="6"
$env:CODE2SKILL_BASE_REF="origin/main"
```

说明：

- `qwen` 默认走阿里国际站兼容接口
- `qwen` 会读取 `QWEN_API_KEY`，也兼容 `DASHSCOPE_API_KEY`
- 如果没有配置对应 API key，命令会直接报错，不会静默降级

## 命令速查

完整扫描并生成 Skill：

```bash
code2skill scan --llm qwen --model qwen-plus-latest
```

只做结构扫描：

```bash
code2skill scan --structure-only
```

自动增量：

```bash
code2skill ci --mode auto --base-ref origin/main
```

只做成本预估：

```bash
code2skill estimate
```

把 Skill 合并到 Codex 规则文件：

```bash
code2skill adapt --target codex --source-dir .code2skill/skills
```

适配所有目标：

```bash
code2skill adapt --target all --source-dir .code2skill/skills
```

## 工作流说明

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

1. 文件发现与过滤
2. 粗评分与预算裁剪
3. Python AST 骨架提取
4. import graph 构建
5. 基于结构信号修正优先级和角色
6. 模式检测与抽象规则提炼
7. 组装 `SkillBlueprint`

### Phase 2：Skill 规划

输入：

- `skill-blueprint.json`

输出：

- `skill-plan.json`

主要步骤：

1. 压缩项目画像、目录摘要、依赖簇、核心模块、规则和流程
2. 调用 1 次 LLM
3. 决定要生成哪些 Skill
4. 为每个 Skill 选出最值得阅读的文件集合

### Phase 3：Skill 生成

输入：

- `skill-plan.json`
- 每个 Skill 对应的文件正文或骨架

输出：

- `skills/index.md`
- `skills/*.md`

主要步骤：

1. 按 Skill 收集上下文文件
2. 筛选与该 Skill 最相关的抽象规则
3. 调用 LLM 生成 Skill 文档
4. 在增量模式下只修订受影响的 section

### Adapt：目标格式适配

输入：

- `skills/*.md`

输出：

- Cursor：复制到 `.cursor/rules/`
- Claude：合并为 `CLAUDE.md`
- Codex：合并为 `AGENTS.md`
- Copilot：合并为 `.github/copilot-instructions.md`
- Windsurf：合并为 `.windsurfrules`

## 输出目录

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

## CI / 增量使用建议

推荐把 `.code2skill/` 当成 CI cache 或 artifact，而不是提交进仓库。

增量模式依赖这些文件：

- `.code2skill/state/analysis-state.json`
- `.code2skill/skill-plan.json`
- 最好同时恢复 `.code2skill/skills/`

如果这些文件缺失，或者 diff 条件不满足，`ci --mode auto` 会自动回退到全量模式。

### 自动回退到全量的常见情况

- 没有历史状态
- 改动了核心配置文件，例如 `pyproject.toml`
- 改动文件数超过 `--max-incremental-changed-files`
- 当前目录不是 Git 仓库，且也没有提供 `--diff-file`

### GitHub Actions 示例

```yaml
name: code2skill

on:
  pull_request:

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

      - name: Install
        run: pip install -e .[dev]

      - name: Run code2skill
        env:
          QWEN_API_KEY: ${{ secrets.QWEN_API_KEY }}
          CODE2SKILL_LLM: qwen
          CODE2SKILL_MODEL: qwen-plus-latest
        run: |
          code2skill ci \
            --mode auto \
            --base-ref origin/${{ github.base_ref }} \
            --head-ref HEAD

      - name: Upload outputs
        uses: actions/upload-artifact@v4
        with:
          name: code2skill-output
          path: .code2skill
```

说明：

- `fetch-depth: 0` 很重要，否则基线提交可能不在本地历史里
- `restore-keys` 能让同一分支上的后续提交复用历史状态
- 第一次没有 cache 时，`ci --mode auto` 会自动走全量

## 生成产物与 Git 管理

默认情况下，仓库根目录下的这些目录已经在 `.gitignore` 中忽略：

- `.code2skill/`
- `.code2skill-*/`
- `.pypi-smoke/`

建议：

- 正式产物统一写到 `.code2skill/`
- 本地试跑、真人验收、不同模型对比时，用 `.code2skill-qwen-live/`、`.code2skill-test/` 这类命名
- 不要把测试生成的 `skills/` 目录提交到 Git
- 如果要在 PR 中查看结果，优先用 artifact，而不是直接提交生成文件

## 这个项目内部是怎么完成的

如果你想理解 `code2skill` 自己是如何工作的，可以从这些模块开始：

- `src/code2skill/scanner/`：文件发现、过滤、预算裁剪、优先级评分
- `src/code2skill/extractors/python_extractor.py`：Python AST 骨架提取
- `src/code2skill/import_graph.py`：仓库内 import graph
- `src/code2skill/pattern_detector.py`：同角色文件模式检测
- `src/code2skill/analyzers/skill_blueprint_builder.py`：把扫描结果组装成 `SkillBlueprint`
- `src/code2skill/skill_planner.py`：生成 `skill-plan.json`
- `src/code2skill/skill_generator.py`：生成和增量修订 `skills/*.md`
- `src/code2skill/core.py`：统一编排 `scan / estimate / ci`

推荐阅读顺序：

1. `cli.py`
2. `core.py`
3. `scanner/` 与 `extractors/`
4. `analyzers/`
5. `skill_planner.py`
6. `skill_generator.py`
7. `adapt.py`

## 发布检查清单

开发与发布前推荐跑：

```bash
pip install -e .[dev]
python -m pytest tests -q
python -m build
python -m twine check dist/code2skill-*.tar.gz dist/code2skill-*.whl
```

## 当前边界

- 目前只面向 Python 仓库
- 生成的 Skill 已适合辅助编码与审查，但不应被当作绝对事实
- 增量更新依赖历史状态文件与可用 diff
- `report.json` 中部分影响摘要仍带启发式成分，最终以 `skill-plan.json` 和生成出来的 `skills/*.md` 为准

## English Quick Reference

### What It Does

`code2skill` turns a Python repository into:

- a structural blueprint
- a skill plan
- generated skill markdown files
- cached state for incremental CI/CD runs

### Quick Start

From the target repo root:

```bash
export QWEN_API_KEY=...
export CODE2SKILL_LLM=qwen
export CODE2SKILL_MODEL=qwen-plus-latest
code2skill scan
```

PowerShell:

```powershell
$env:QWEN_API_KEY="..."
$env:CODE2SKILL_LLM="qwen"
$env:CODE2SKILL_MODEL="qwen-plus-latest"
code2skill scan
```

### Main Commands

```bash
code2skill scan
code2skill scan --structure-only
code2skill ci --mode auto --base-ref origin/main
code2skill estimate
code2skill adapt --target codex --source-dir .code2skill/skills
```

### Incremental CI Requirements

Restore:

- `.code2skill/state/analysis-state.json`
- `.code2skill/skill-plan.json`
- preferably `.code2skill/skills/`

If they are missing, `ci --mode auto` falls back to a full run.

### Release Validation

```bash
pip install -e .[dev]
python -m pytest tests -q
python -m build
python -m twine check dist/code2skill-*.tar.gz dist/code2skill-*.whl
```

## License

Apache-2.0
