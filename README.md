<p align="center">
  <img src="webui/public/whale-cli-logo.png" width="240" alt="Whale CLI logo" />
</p>

<h1 align="center">Whale CLI</h1>

<p align="center"><strong>从 Agent Loop 到学习陪伴，一套能读、能跑、能改、能验证的学习型 Agent 系统。</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.3.0-285f9e" alt="version 0.3.0" />
  <img src="https://img.shields.io/badge/python-3.10%2B-3572a5" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/tests-174%20passed-397a68" alt="174 tests passed" />
  <img src="https://img.shields.io/badge/license-MIT-f0b43c" alt="MIT License" />
</p>

<p align="center">
  <a href="webui/public/project-intro.html">项目介绍</a> ·
  <a href="docs/新手入门/README.md">28 章教程</a> ·
  <a href="docs/部署与发布.md">部署指南</a> ·
  <a href="docs/测试报告.md">测试报告</a> ·
  <a href="CHANGELOG.md">Changelog</a>
</p>

---

Whale CLI 面向两类人：想亲手理解 coding agent 如何工作的学习者，以及希望用 AI 规划 Datawhale 学习路线、连接知识和完成项目的实践者。

它不是一个只返回答案的聊天壳。模型调用、工具分发、审批、会话、MCP 和学习状态都能在源码、测试和 WebUI 运行轨迹中找到对应位置。

<p align="center">
  <img src="webui/public/whale-cli-system-overview.png" width="100%" alt="Whale CLI 系统功能总览" />
</p>

## 你能用它做什么

| 方向 | 能力 | 你会看到什么 |
|---|---|---|
| Agent Runtime | ReAct loop、Toolset、Todo、Compaction、Approval | 模型为什么调用工具、结果怎样进入下一轮、任务何时结束 |
| Harness | Agents、Hooks、Skills、Subagents、Background、AGENTS.md | 功能如何独立扩展，而不把核心循环改成一组 `if/elif` |
| MCP | stdio、Streamable HTTP、SSE | 外部工具如何进入统一 schema、审批和生命周期 |
| 文件任务 | 代码、图片、PDF、Office、表格和文本 | 附件预览、视觉输入、工作区文件浏览与受控写入 |
| 学习规划 | Datawhale BM25、学习者档案、动态路线 | 推荐依据、路线子任务、手动 checklist 与完成状态 |
| 知识沉淀 | Obsidian Wiki、知识图谱、间隔复习、学习档案 | 学过什么、知识如何关联、何时复习、项目留下了什么证据 |

## 五分钟开始

### 1. 安装

在本 README 所在目录执行。Python 必须为 3.10 或更高版本。

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Windows PowerShell 使用：

```powershell
.venv\Scripts\Activate.ps1
```

### 2. 配置模型

Whale 默认使用 OpenAI 兼容的 Step Plan 接口和 `step-3.7-flash`。推荐通过环境变量配置：

```bash
export STEP_API_KEY="your-step-plan-key"
```

也可以保存到本机配置文件：

```bash
mkdir -p ~/.whale
cp config.example.json ~/.whale/config.json
```

```json
{
  "llm": {
    "api_key": "your-step-plan-key",
    "base_url": "https://api.stepfun.com/step_plan/v1",
    "model": "step-3.7-flash",
    "vision_enabled": true
  }
}
```

真实 Key 不要写入仓库、教程、截图或提交记录。

### 3. 选择入口

终端 REPL：

```bash
whale-doctor
whale-cli
```

React WebUI：

```bash
make web
whale-doctor --web
whale-web
```

打开 <http://127.0.0.1:8765>。WebUI 提供 Markdown 对话、图片和文档输入、历史会话、命令面板、运行轨迹、审批、教程阅读、知识图谱、路线、复习和学习档案。

## 第一次对话

可以从这些任务开始：

```text
请先探索这个仓库，告诉我入口、主要模块和测试命令。
```

```text
请解释 Whale CLI 的 Agent Loop：模型如何选择工具，结果如何回填到下一轮？
```

```text
我是 Python 初学者，每周可以学习 6 小时，目标是四周完成一个 Agent 小项目。请根据 Datawhale 本地知识库先给我预览一条学习路线，不要直接确认生成。
```

```text
请从本地聊天记录生成今天的间隔复习表，并打开 Agent Loop 的复习资料。
```

## 系统如何工作

```text
User / WebUI / CLI
        │
        ▼
Session + Project Context
        │
        ▼
Soul.run() ── LLM Client
        │          │
        │      tool calls
        ▼          │
Toolset ◄──────────┘
  │
  ├── Approval + Workspace Policy
  ├── File / Bash / Web / Todo
  ├── MCP / Skills / Subagents / Background
  └── Profile / Knowledge / Roadmap / Review / Portfolio
        │
        ▼
tool result → messages → next turn or final answer
```

核心原则：

- `Soul` 只负责循环，不直接实现每一种工具。
- 工具通过 `Toolset` 暴露 schema、统一调用和回填结果。
- 写文件与命令默认需要审批，并继续受工作区策略限制。
- 会话、学习状态和运行数据使用 JSON/JSONL，本地可读、可迁移。
- CLI 与 WebUI 共用同一套运行时和学习模块。

## 学习陪伴闭环

Whale 的垂直能力不是一次性生成一份计划，而是一条由用户确认推进的学习循环：

1. `LearnerProfile` 记录基础、目标、时间和偏好。
2. Datawhale BM25 根据项目元数据和 GitHub README 检索证据。
3. `KnowledgeMap` 描述知识点的前置、关联、作用和可以解锁的能力。
4. `LearningRoadmap` 先预览路线，用户确认后才生成，并拆成任务和 checklist。
5. 用户在 CLI 对话或 WebUI 中明确标记完成。
6. `LearningReview` 根据日期生成间隔复习表，由用户自评回忆质量。
7. Obsidian Wiki、项目产出和 `LearningPortfolio` 留下可回看的学习证据。

## 教程地图

教程位于 [`docs/新手入门/`](docs/新手入门/README.md)，每章都对应代码模块、最小案例和验证命令。

| 章节 | 阶段 | 目标 |
|---|---|---|
| 00-10 | Agent 核心闭环 | REPL、LLM Client、Loop、工具、Todo、Skills、Session 与压缩 |
| 11-20 | Agent Harness | Agents、Hooks、Subagents、Background、MCP、AGENTS、Loop 模式和附件 |
| 21-25 | 学习系统 | BM25 子代理、学习者档案、知识图谱、动态路线和间隔复习 |
| 26-27 | 项目与档案 | 项目陪学、能力证据、学习档案和社区反馈 |

WebUI 左侧“学习地图”可以直接打开这些 Markdown 教程，并在章节之间跳转。

## 目录结构

```text
src/whale_cli/
├── soul/             # Agent Loop、Toolset、Approval、Todo、Compaction
├── llm/              # OpenAI 兼容客户端
├── tools/            # 文件、命令、网页、学习与后台工具
├── storage/          # JSONL 会话持久化
├── loops/            # turn / goal / time / proactive
├── mcp/              # 配置、transport、adapter 与 auth
├── learning/         # 档案、图谱、路线、复习、项目、Wiki 与作品集
├── agents/           # agent.yaml 与 system template
├── skills/           # 内置能力包
├── hooks/            # 生命周期事件
├── subagents/        # 干净上下文与 Datawhale 子代理
├── security/         # 工作区与危险命令策略
├── runtime.py        # 运行目录配置
├── doctor.py         # 安装与部署诊断
└── web/server.py     # 可安装 WebUI 后端

webui/                # React 前端与静态项目介绍页
docs/新手入门/        # 00-27 渐进教程
tests/                # 单元、模块、集成与真实模型 E2E
```

## MCP

项目级 MCP 配置默认保存在 `.whale_cli/mcp.json`：

```bash
mkdir -p .whale_cli
cp mcp.example.json .whale_cli/mcp.json
whale-cli
```

当前支持 `stdio`、Streamable HTTP 和 SSE。外部工具会被转换为 Whale `Tool`，继续经过统一审批、Hooks 和结果回填。OAuth 交互回调尚未完成，不作为当前稳定能力承诺。

## 运行数据

| 位置 | 内容 |
|---|---|
| `~/.whale/` 或 `$WHALE_HOME` | 模型配置、会话、上传文件 |
| 当前目录或 `$WHALE_WORKSPACE` | 项目文件和项目级学习数据 |
| `.whale_cli/learning/` | 档案、图谱、路线、复习与项目状态 |
| `.whale_cli/mcp.json` | 项目 MCP 配置 |
| `learning-wiki/` | 可由 Obsidian 打开的 Markdown Wiki |

## Docker

```bash
export STEP_API_KEY="your-step-plan-key"
export WHALE_WORKSPACE_PATH="$PWD"
docker compose up -d --build
curl http://127.0.0.1:8765/ready
```

Compose 默认只向宿主机 `127.0.0.1` 发布端口。运行数据保存在 `whale-data` volume，工作区通过 bind mount 提供给 Agent。

### 阿里云 ACR 公网镜像

项目的公网镜像仓库为：

```text
crpi-l4ex9om7pwr2is5u.cn-shanghai.personal.cr.aliyuncs.com/while_cli/while_cli
```

仓库是公开的，因此已发布的版本可以直接拉取；但推送仍需使用此 ACR 实例的访问凭证登录。当控制台中出现 `0.3.0` 标签后，可使用：

```bash
docker pull crpi-l4ex9om7pwr2is5u.cn-shanghai.personal.cr.aliyuncs.com/while_cli/while_cli:0.3.0
```

维护者的推送、验证和发布标签流程见 [`docs/部署与发布.md`](docs/部署与发布.md)。

完整的源码、wheel、Docker 和 systemd 部署流程见 [`docs/部署与发布.md`](docs/部署与发布.md)。

## 测试与发布

```bash
# 离线测试，不调用真实模型
python -m pytest

# 真实 step-3.7-flash E2E
RUN_E2E=1 python -m pytest tests/test_e2e.py -v

# Python + React + doctor + wheel 发布门禁
make release
```

0.3.0 当前验证状态：

- 174 项离线测试通过，4 项真实模型 E2E 默认跳过。
- React 生产构建通过。
- wheel 在独立 Python 3.11 环境安装并启动通过。
- Docker 镜像构建、容器 health 和 HTTP API 烟测通过。

详情见 [`docs/测试报告.md`](docs/测试报告.md)。

## 安全边界

- Safe 模式会在写文件和执行命令前询问；YOLO 只跳过询问，不绕过工作区策略。
- 审批不是完整操作系统沙箱。只应向 Whale 提供你愿意让它访问的工作区。
- WebUI 当前定位为单用户本地或可信内网工具，默认监听 `127.0.0.1`。
- 直接公网部署前必须增加 HTTPS、身份认证、限流和多用户隔离。
- MCP server、skills 和 plugins 都属于可执行扩展，只加载可信来源。

## 参与项目

提交改动前请运行：

```bash
make test
git diff --check
```

新增能力时，请同时补充对应测试与教程章节，让代码、示例和解释保持一致。版本变化记录在 [`CHANGELOG.md`](CHANGELOG.md)。

## License

Whale CLI 使用 [MIT License](LICENSE)。
