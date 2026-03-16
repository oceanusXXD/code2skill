# code2skill

中文优先，英文补充。
Chinese first, with an English quick reference later in this document.

`code2skill` 是一个 Python CLI，用来把真实代码仓库编译成一组可供 AI 编程助手消费的结构化项目知识与 Skill 文档。
它的目标不是“总结仓库”，而是产出可以直接用于后续编码、审查、增量更新的上下文。

`code2skill` is a Python CLI that turns a real repository into structured project knowledge and Skill documents for downstream AI coding agents.

## 当前状态

当前版本可以用于首次全量生成，也可以用于后续增量 CI/CD。

已验证的两条路径：
- 首次运行：`scan` 可以在没有历史状态时完成完整 Phase 1/2/3，生成 `skill-blueprint.json`、`skill-plan.json`、`skills/*.md`。
- 后续运行：在保留上一轮 `.code2skill/state/analysis-state.json` 和 `skill-plan.json` 的前提下，`ci --mode auto` 可以根据 diff 进入 `incremental` 模式，只重写受影响的 Skill。

要让增量模式在 CI runner 上稳定工作，需要满足这几个前提：
- 仓库是 Git 仓库，或者你显式传入 `--diff-file`
- 能获取有效 diff：推荐 `fetch-depth: 0`，或者显式传入 `--base-ref`
- 恢复上一轮输出目录中的状态文件：至少是 `.code2skill/state/analysis-state.json`
- 如果希望增量修订现有 Skill，而不是重新规划，最好同时恢复 `.code2skill/skill-plan.json` 和 `.code2skill/skills/`

如果这些条件不满足，当前实现会自动回退到全量模式，而不是静默失败。

## 特性概览

- 仅面向 Python 仓库
- Phase 1 不调用 LLM
- Python 源码使用 `ast` 做骨架提取
- 内置 import graph、角色修正、模式检测
- 支持 `scan`、`ci`、`estimate`、`adapt`
- 支持 `openai`、`claude`、`qwen`
- 输出默认中文，不使用 emoji，证据不足的地方标记 `[待确认]`

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
```

## LLM 后端与密钥

OpenAI：

```bash
export OPENAI_API_KEY=...
```

Claude：

```bash
export ANTHROPIC_API_KEY=...
```

Qwen：

```bash
export QWEN_API_KEY=...
```

说明：
- `qwen` 默认走阿里国际站兼容接口
- 当前实现会读取 `QWEN_API_KEY`，也兼容 `DASHSCOPE_API_KEY`
- 如果没有配置对应环境变量，命令会直接报错

## 工作流

### Phase 1：结构扫描

输入：
- 本地 Git 仓库路径

输出：
- `project-summary.md`
- `skill-blueprint.json`
- `references/*.md`
- `report.json`
- `state/analysis-state.json`

主要处理：
1. 文件发现与过滤
2. 粗评分与预算裁剪
3. Python 骨架提取
4. import graph 构建
5. 结合图信号做优先级修正
6. 角色分组与模式检测
7. 组装 `SkillBlueprint`

### Phase 2：Skill 规划

输入：
- `skill-blueprint.json`

输出：
- `skill-plan.json`

主要处理：
- 根据目录摘要、核心模块、配置、依赖簇、工作流、抽象规则，决定要生成哪些 Skill
- 每个 Skill 只选必要文件，不全读整仓

### Phase 3：Skill 生成

输入：
- `skill-plan.json`
- 每个 Skill 对应的源码正文或骨架

输出：
- `skills/index.md`
- `skills/*.md`

主要处理：
- 为每个 Skill 生成可被 AI 编程助手消费的 Markdown 规范文档
- 增量模式下只更新受影响的 Skill

### Adapt：输出适配

输入：
- `skills/*.md`

输出：
- Cursor / Claude / Codex / Copilot / Windsurf 对应位置的规则文件

## 首次使用

推荐先从全量生成开始。

### 方式 1：显式使用 `scan`

```bash
code2skill scan <repo_path> \
  --output-dir .code2skill \
  --llm qwen \
  --model qwen-plus
```

这会执行完整 Phase 1/2/3，并写出：

```text
.code2skill/
  project-summary.md
  skill-blueprint.json
  skill-plan.json
  report.json
  references/
  skills/
  state/
    analysis-state.json
```

### 方式 2：直接使用 `ci --mode auto`

```bash
code2skill ci <repo_path> \
  --output-dir .code2skill \
  --mode auto \
  --llm qwen \
  --model qwen-plus
```

在首次运行时，如果没有历史状态，当前实现会自动回退到全量模式。
所以对 CI 而言，首次运行直接用 `ci --mode auto` 也可以。

## 后续增量使用

### 本地增量

如果你在同一个仓库里已经跑过一次，并且 `.code2skill/state/analysis-state.json` 还在，可以直接：

```bash
code2skill ci <repo_path> \
  --output-dir .code2skill \
  --mode auto \
  --llm qwen \
  --model qwen-plus
```

当前实现会：
1. 读取上一次的 `analysis-state.json`
2. 计算从上次 `head_commit` 到当前工作树的 diff
3. 识别受影响文件
4. 将受影响文件映射到受影响 Skill
5. 只重写这些 Skill

### 显式指定基线

如果你更想显式指定 diff 基线，可以传 `--base-ref`：

```bash
code2skill ci <repo_path> \
  --output-dir .code2skill \
  --mode auto \
  --base-ref origin/main \
  --head-ref HEAD \
  --llm qwen \
  --model qwen-plus
```

这在 PR / merge request 场景下更稳定。

### 使用外部 diff 文件

如果你的 CI 系统已经生成了 unified diff，可以直接传：

```bash
code2skill ci <repo_path> \
  --output-dir .code2skill \
  --mode incremental \
  --diff-file changes.diff \
  --llm qwen \
  --model qwen-plus
```

## 推荐的 CI/CD 使用方式

推荐把 `.code2skill/` 作为 CI cache 或 artifact 保存，而不是提交进仓库。

原因：
- `.code2skill/state/analysis-state.json` 是增量模式的核心状态
- `.code2skill/skill-plan.json` 用于把受影响文件映射到已有 Skill
- `.code2skill/skills/*.md` 用于增量修订已有 Skill 正文

如果这些文件没有恢复，`ci --mode auto` 会自动退回全量。

### GitHub Actions 示例

下面这个例子适用于 PR 增量生成。

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
        run: |
          code2skill ci . \
            --output-dir .code2skill \
            --mode auto \
            --base-ref origin/${{ github.base_ref }} \
            --head-ref HEAD \
            --llm qwen \
            --model qwen-plus

      - name: Upload outputs
        uses: actions/upload-artifact@v4
        with:
          name: code2skill-output
          path: .code2skill
```

说明：
- `fetch-depth: 0` 很重要，否则 `base_ref` 或旧 `head_commit` 可能不在本地历史中
- `restore-keys` 让当前 commit 可以复用同分支上一次缓存
- 第一次没有 cache 时，会自动走全量

## 命令速查

全量生成：

```bash
code2skill scan . --output-dir .code2skill --llm qwen --model qwen-plus
```

只做结构扫描：

```bash
code2skill scan . --output-dir .code2skill --structure-only
```

增量 CI：

```bash
code2skill ci . --output-dir .code2skill --mode auto --llm qwen --model qwen-plus
```

成本估算：

```bash
code2skill estimate . --output-dir .code2skill
```

适配到 Codex：

```bash
code2skill adapt --target codex --source-dir .code2skill/skills
```

适配全部目标：

```bash
code2skill adapt --target all --source-dir .code2skill/skills
```

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

## 回退条件

在 `ci --mode auto` 下，当前实现会在这些情况下自动退回全量：
- 没有历史状态缓存
- 改动了核心配置文件，例如 `pyproject.toml`
- 改动文件数超过 `--max-incremental-changed-files`
- 当前目录不是 Git 仓库，且你也没有传 `--diff-file`

## 已知边界

- 当前只面向 Python 仓库
- 生成的 Skill 质量已经可用于实际消费，但仍然更适合“辅助编码与审查”，不应被当作绝对真理
- `report.json` 中的部分影响摘要仍偏启发式，最终以 `skill-plan.json` 和实际生成的 `skills/*.md` 为准

## English Quick Reference

### What It Does

`code2skill` converts a Python repository into:
- a structural blueprint
- a skill plan
- generated skill markdown files
- cached state for incremental CI/CD updates

### First Run

Use either:

```bash
code2skill scan . --output-dir .code2skill --llm qwen --model qwen-plus
```

or:

```bash
code2skill ci . --output-dir .code2skill --mode auto --llm qwen --model qwen-plus
```

If no previous state exists, `ci --mode auto` automatically falls back to a full build.

### Incremental CI

For incremental updates, restore:
- `.code2skill/state/analysis-state.json`
- `.code2skill/skill-plan.json`
- preferably `.code2skill/skills/`

Then run:

```bash
code2skill ci . --output-dir .code2skill --mode auto --llm qwen --model qwen-plus
```

For pull requests, prefer:

```bash
code2skill ci . \
  --output-dir .code2skill \
  --mode auto \
  --base-ref origin/main \
  --head-ref HEAD \
  --llm qwen \
  --model qwen-plus
```

### When Auto Mode Falls Back to Full

- no previous state
- core config changes
- too many changed files
- not a Git repo and no `--diff-file`

### Supported Backends

- `openai` via `OPENAI_API_KEY`
- `claude` via `ANTHROPIC_API_KEY`
- `qwen` via `QWEN_API_KEY` or `DASHSCOPE_API_KEY`

## License

Apache-2.0
