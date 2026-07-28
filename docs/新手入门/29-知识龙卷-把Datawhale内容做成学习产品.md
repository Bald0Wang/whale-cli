# 29. 知识龙卷：把全部 Datawhale 内容做成可浏览的学习产品

前面的学习路线、复习表和学习档案都属于**学习者自己的数据**。它们应当跟随项目空间隔离，并且需要学习者明确确认。

这一章换一个视角：有一类内容不该由每个用户从零生成，那就是已经导入本地的 Datawhale 课程、章节和 GitHub 项目。它们应该像产品目录一样，打开就能浏览、检索和进入原始资料。

Whale 把这一层叫做 **Datawhale 知识龙卷**。

它不是：

- 用对话临时生成的一张学习计划；
- 对学习者掌握度的判断；
- 模型凭常识编造的前置依赖图。

它是：

- 当前项目 Datawhale BM25 JSONL 的完整索引；
- 有来源链接、标签、课程名和章节路径的资料目录；
- 由领域总览、筛选器、资料列表和详情面板组成的可视化产品。

---

## 1. 先分清两种“图”

| 视图 | 内容从哪里来 | 解决什么问题 | 能否表示掌握度 |
|---|---|---|---|
| 学习图谱（第 23 章） | 学习者记录、Obsidian Wiki | 我正在理解哪些概念，它们怎样关联 | 不直接表示 |
| Datawhale 知识龙卷 | 导入的 Datawhale 语料 | 有哪些真实课程、章节、项目可供选择 | 不能表示 |

这一区分很重要。资料库只证明“有这份资料”，不能证明“我已经学会”。掌握情况仍由复习反馈、练习证据和学习档案记录。

---

## 2. 数据怎样自动进入龙卷

第 21 章的 BM25 语料每行至少包含：

```json
{
  "id": "learn:chapter:100:3201",
  "source_type": "learn_chapter",
  "title": "AI 编程学习 / 配置 Python 环境",
  "url": "https://www.datawhale.cn/learn/content/100/3201",
  "tags": ["Python", "环境配置", "初级"],
  "text": "...",
  "metadata": {
    "courseTitle": "10分钟快速手搓一个小应用-AI编程学习",
    "sectionPath": ["基础篇"]
  }
}
```

`DatawhaleKnowledgeTornado` 会读取当前项目的 JSONL，按**标题、标签和课程名**归入稳定领域，例如：

- 大模型与智能体
- 机器学习与深度学习
- 数据分析与挖掘
- 自然语言处理、计算机视觉、推荐系统
- 编程与开发基础、工程化与部署、竞赛与案例项目
- 无法可靠归类的社区与其他资源

每条资料只会有一个产品浏览领域，避免总览中的同一内容反复出现；但详情页仍保留全部标签和原始链接。

```text
Datawhale BM25 JSONL
        |
        v
DatawhaleKnowledgeTornado.snapshot()
        |
        +-- 领域总览（只展示少量领域节点）
        |       |
        |       +-- 课程或项目（来自 courseId；仓库保持为独立项目）
        |               |
        |               +-- 章节或资料（真实 title、sectionPath、url）
        +-- 右侧上下文面板（当前节点的来源、标签和可进入内容）
```

### 为什么不把 3409 条资料全画成节点？

节点数量到几千时，图会变成一团无法阅读的点。知识龙卷采用两层表达：

1. **图**负责回答“这个库覆盖哪些领域”；
2. **目录和筛选**负责回答“我要找的那一条资料在哪里”。

这让图保持可读，也保证所有内容仍然能被搜索和打开。

### 为什么使用三维空间，而不是卡片气泡？

WebUI 使用 Three.js 把当前层级的节点放进可旋转、可缩放的三维空间：领域总览中的点代表领域，进入领域后代表课程或项目，再进入后才代表具体资料。线只表示目录中的真实包含关系，**不冒充“前置知识”或“推荐顺序”**。

这样做的目的不是把资料做得花哨，而是让学习者能先从整体分布感受资料覆盖面，再自然靠近一个主题查看细节。它的操作也保持简单：

- 拖拽画布：旋转视角；
- 滚轮或双指缩放：靠近或拉远知识空间；
- 点击一个点：进入下一层，或在最后一层打开资料详情；
- 点击“返回”：回到上一级目录。

每次进入新层级，右侧仍会保留当前节点的来源、标签、课程路径和下一步可进入的内容，因此三维画布负责发现，详情面板负责确认事实。

---

## 3. 后端：可重建的只读目录

实现位于 `src/whale_cli/learning/tornado.py`：

```python
tornado = DatawhaleKnowledgeTornado(
    DatawhaleKnowledgeBase(project_kb_path)
)

page = tornado.snapshot(
    cluster_id="llm-agent",
    query="RAG",
    source_type="learn_chapter",
    page=1,
)
```

第一次读取时，它会把结果缓存到当前项目的：

```text
.whale_cli/datawhale_knowledge_tornado.json
```

缓存包含语料文件的修改时间与大小指纹。导入新 JSONL 或同步新的 BM25 运行结果后，下一次打开 API 时发现指纹变化，就会自动重建。学习者不需要点击“生成知识龙卷”，也不会产生任何学习者数据写入。

接口分为两类：

| 接口 | 用途 |
|---|---|
| `GET /api/datawhale-tornado` | 返回领域、筛选后的资料分页和总览图数据 |
| `GET /api/datawhale-tornado/document?id=...` | 返回某条资料的来源、标签、课程位置和同领域资料 |

---

## 4. CLI 中的只读工具

Agent 可以帮助学习者找资料，但它没有“create”动作：

```json
{
  "action": "browse",
  "cluster_id": "llm-agent",
  "query": "RAG",
  "source_type": "learn_chapter",
  "page": 1
}
```

工具名是 `DatawhaleTornado`，可用动作：

- `summary`：了解资料总量、领域和来源类型；
- `browse`：按领域、来源类型或关键词浏览；
- `document`：读取一条已选资料的真实链接和元数据。

合适的对话是：

```text
请用 DatawhaleTornado 搜索 RAG 的初级课程和项目。
只根据真实链接给我推荐一个起点，并说明它属于哪个领域。
```

不合适的对话是：

```text
替我生成一张 RAG 知识龙卷，并判断我现在掌握了多少。
```

后者应当转到学习图谱、复习或学习档案，而不是污染资料目录。

---

## 5. WebUI 的浏览路径

在侧栏打开“知识龙卷”：

1. 从领域总览点击一个主题节点；
2. 在地图中继续点击一门课程或一个 GitHub 项目；
3. 再点击一条章节或资料，右侧查看真实来源、标签和课程路径；
4. 用左上角“返回”回到上一级，用拖拽和滚动探索地图；
5. 用右上角搜索和来源筛选快速定位资料；
6. 再回到对话，让 Whale 基于这条真实资料制定适合你的路线或项目练习。

当项目空间还没有导入语料时，页面会清楚提示去“运行架构”的 Datawhale 本地项目语料区导入 JSONL 或同步最新 BM25 运行。不同学习项目各自持有语料与知识龙卷缓存，因此不会串数据。

---

## 6. 测试什么

本章应验证四件事：

1. 语料中的每条记录都会进入目录，资料总数不丢失；
2. 领域统计之和等于资料总数；
3. 更新 JSONL 后，指纹改变会触发自动重建；
4. API 的分页、关键词筛选和单条详情都只返回真实语料字段。

```bash
pytest -q tests/test_learning.py tests/test_webui_settings.py
npm run build --prefix webui
```

## 7. 代码定位

| 文件 | 职责 |
|---|---|
| `src/whale_cli/learning/tornado.py` | 构建、缓存、筛选完整 Datawhale 产品目录 |
| `src/whale_cli/subagents/datawhale.py` | 保留 JSONL 的 id、来源类型和课程元数据 |
| `src/whale_cli/tools/learning/learning_tools.py` | 提供只读 `DatawhaleTornado` 工具 |
| `src/whale_cli/web/server.py` | 为 WebUI 提供目录与资料详情 API |
| `webui/src/App.jsx` | Three.js 三维知识空间、资料筛选与详情面板 |
| `webui/src/styles.css` | 三维画布、导航覆盖层与小屏布局 |

下一步不是让知识龙卷替你做决定，而是从一条真实资料开始：把它加入学习路线、完成一次练习，再把事实沉淀到学习档案里。
