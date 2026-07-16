# 21. Datawhale 学习规划 Subagent：用知识库做垂直路线

本章导航：

- 新增机制：本地知识库检索、干净上下文子代理和可执行学习路线。
- 正式入口：`subagents/datawhale.py`、`subagents/runner.py`、`tools/agent/agent_tool.py`。
- 验证方式：请求一份 Python 初学者的 Agent 学习路线，检查推荐项目来自本地 JSONL 语料。
- 本章不展开：向量数据库、长期用户画像、课程进度同步和自动报名。

通用 Agent 可以搜索网页、读仓库和修改文件，但它不天然知道 Datawhale 的项目边界，也不应凭模型记忆推荐仓库。本章实现第一个垂直方向的子代理：**Datawhale 学习规划助手**。

它的工作只包含三步：检索项目证据、结合用户条件规划路线、把紧凑结论回传给主 Agent。

## 21.1 输入和输出的边界

用户应提供四类信息：

- 当前基础：Python、算法、PyTorch、后端等。
- 学习目标：Agent、LLM 部署、算法、深度学习或科研绘图。
- 时间预算：例如每周 6 小时、四周完成。
- 目标产出：读懂项目、完成 notebook、做作品或准备面试。

子代理输出必须包含：学习者假设、3 到 5 个有 URL 的项目建议、阶段路线、练习里程碑和一个追问。没有知识库证据时，它必须说清楚，而不能编造项目名或链接。

## 21.2 本地知识库

语料是项目自己的运行数据，默认保存为：

```text
whale_cli/
  .whale_cli/
    datawhale_bm25_documents.jsonl
```

每行是一个 Datawhale 项目文档，含 `title`、`url`、`text`、`tags`、预分词 `tokens` 和 stars 等 metadata。这个路径不依赖某台机器的绝对目录；复制项目或重新启动 WebUI 后仍会优先读取它。

在 WebUI 的“项目概览”底部可以看到文档数量、文件大小与当前算法，并可导入新的 `.jsonl`。导入时系统会逐行检查 JSON、`title`、`text`、`tokens` 与 `tags`，通过后写入临时文件再原子替换旧语料；不合法文件不会破坏原来的知识库。

部署时也可以用环境变量覆盖默认位置：

```bash
export DATAWHALE_KB_PATH=/path/to/datawhale_bm25_documents.jsonl
```

上传接口限制为 `.jsonl`，最大 64 MB。它用于更换项目语料，不是聊天附件；聊天中的 JSON、CSV 仍走普通附件管理。

### 更新项目语料

外部数据项目每次构建会产生一个完整快照：

```text
/Volumes/拓展/workspace/datawhaledata/outputs/
  bm25_runs/
    20260708-151258/
      datawhale_bm25_documents.jsonl
      datawhale_bm25_manifest.json
      datawhale_bm25_search.py
```

Whale 的 `DatawhaleKnowledgeBaseUpdater` 会在 `bm25_runs` 下寻找包含完整 JSONL 的最新时间戳目录。点击 WebUI “项目概览”中的“同步最新运行”后，它会：读取完整语料、逐行校验、原子替换 `.whale_cli/datawhale_bm25_documents.jsonl`、清除 BM25 缓存，并把来源 run、导入条数和时间保存到 `.whale_cli/datawhale_bm25_update.json`。

默认发现目录适配当前开发环境；换机器时设置：

```bash
export DATAWHALE_BM25_RUNS_DIR=/path/to/outputs/bm25_runs
```

注意：`datawhale_bm25_search.py` 是质量验收工具，不会更新语料。同步前可进入具体 run 目录，使用代表性查询检查构建结果：

```bash
cd /Volumes/拓展/workspace/datawhaledata/outputs/bm25_runs/20260708-151258
python3 datawhale_bm25_search.py "目录 推荐系统 多任务学习" --source-type learn_section
python3 datawhale_bm25_search.py "agent rag" --source-type github_repo
```

第一条应出现 FunRec 的“多任务学习”等课程章节，第二条应出现 `happy-llm`、`hello-agents`、`wow-rag` 等 GitHub 项目。两类结果都正常后，再同步最新运行，避免把不完整或错误抓取的快照带进学习规划。

## 21.3 检索先于规划

```text
学习者背景、目标、时间
    -> DatawhaleKnowledgeBase.search()
    -> 命中少量项目证据
    -> 新建干净 child Soul
    -> 生成路线并回传摘要
```

`DatawhaleKnowledgeBase` 复用 JSONL 的预分词 `tokens`，再把标题与标签加入同一个词袋。它使用标准 **Okapi BM25**：

```text
score(D, Q) = Σ IDF(q) × TF(q, D) × (k1 + 1) / (TF(q, D) + k1 × (1 - b + b × |D| / avgdl))
```

其中 `IDF` 会降低常见词的影响，`TF` 表示词在文档中的出现次数，`|D| / avgdl` 会对特别长的文档做长度归一化。也就是说，同样命中 `agent` 时，只有一处关键词却很长的汇总页不会天然压过更聚焦的项目说明。当前参数是 `k1=1.5`、`b=0.75`。

GitHub 项目会把仓库描述、topics、README 标题、README 清洗后的正文一起写入同一份项目文档的 `text` 与 `tokens`。README 中的代码块、图片链接和 HTML 标签会被剔除，正文会按仓库截断，避免大文件淹没其它项目。这样检索 “RAG 评测”“Agent 记忆” 这类描述不足以表达的能力时，BM25 也能命中 README 里的真实主题；更新面板中的 “GitHub README N 个” 用于确认新快照的覆盖量。

3408 条文档不会进入模型上下文：运行时先缓存文档频率和平均长度，检索时只计算查询词，再把最相关的 6 条项目证据传给子代理。

这就是垂直 Agent 的第一步：先建立可信、可检查的领域边界，再让模型在边界内做规划。

## 21.4 如何调用

主 Agent 使用统一的 `Agent` 工具：

```json
{
  "description": "规划 Datawhale 路线",
  "agent_type": "datawhale_learning",
  "prompt": "我是 Python 初学者，每周 6 小时，目标是学习 Agent 并完成一个工具调用项目。"
}
```

WebUI 的指令面板提供 `/datawhale` 快捷入口。也可以直接输入：

```text
请调用 Agent 工具，agent_type 使用 datawhale_learning。
我的基础是 Python 初学者；每周可投入 6 小时；目标是学习 Agent；希望四周后完成一个可演示的小项目。
```

子代理默认没有 Bash、WriteFile 或网络搜索工具。它只读取传入的本地项目证据，因此学习规划不会获得无关的系统权限。

## 21.5 输出应如何区分事实和建议

项目标题、URL、标签和描述是**知识库事实**；推荐顺序、每周安排和练习任务是**模型建议**。好的输出会把它们分开：

```markdown
## 优先项目
1. Agent-Learning-Hub
   - URL: ...
   - 证据：知识库描述它是 Agent 学习路线与资料库。

## 四周路线
- 第 1 周：读项目导航，梳理循环、工具和上下文概念。
- 第 2 周：完成一次本地工具调用练习。
- 第 3 周：把工具调用接进小任务。
- 第 4 周：整理可演示 README。
```

## 21.6 实用案例：小陈要在四周内完成第一个 Agent 项目

小陈会写 Python 函数，但没做过 LLM 应用；他每周只有 6 小时，希望四周后拿出一个能演示的工具调用项目。在 WebUI 中点击“规划 Datawhale 路线”，或输入：

```text
请调用 Agent 工具，agent_type 使用 datawhale_learning。
我是 Python 初学者，会函数和 pip；每周 6 小时；目标是四周完成一个 Agent 小项目。
请基于 Datawhale 本地知识库推荐项目，并说明每周做什么。
```

本轮的真实调用链是：

```text
主 Soul
  -> Agent(datawhale_learning)
  -> DatawhaleKnowledgeBase.search(用户目标)
  -> 取最多 6 条项目证据和 URL
  -> 子 Soul 生成路线
  -> 主 Soul 把路线回给小陈
```

小陈应检查输出中的项目 URL 是否来自本地语料，以及“第 1 周”是否只安排了自己能完成的基础任务。这里不会写入学习档案；它先解决“选什么资料和项目”，下一章才开始保存小陈的个人状态。

## 21.7 如何验证

```bash
./.venv/bin/python -m pytest tests/test_datawhale_subagent.py -q
```

测试使用临时 JSONL，验证：

- “LLM 部署”查询优先命中 `llm-deploy`。
- 子代理 prompt 含命中项目和 URL。
- 垂直子代理没有文件写入或 Bash 工具。
- `Agent` schema 暴露 `datawhale_learning`。

## 当前实现的边界

- 当前是词项检索，不是语义向量检索，同义表达可能漏召回。
- 知识库是本地快照，不会自动同步 Datawhale 项目。
- 不保存长期学习画像；每次路线都依赖用户重新提供背景、目标和时间。
- 推荐项目有证据约束，但路线安排仍是模型建议，用户应按实际基础调整。

下一步可以加入反馈闭环：用户完成一个里程碑后，用相同知识库重新规划下一阶段。
