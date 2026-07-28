# Agent 四周学习计划

- 基础：Python 初学者
- 每周投入：6 小时
- 目标：学习 Agent，四周后完成一个可演示的小项目
- 主项目：`datawhalechina/easy-langent`
- 前置项目：`datawhalechina/llm-universe`
- 快速验证：`datawhalechina/coze-ai-assistant`

---

## Week 1：LLM 开发基础

| 时间 | 学习内容 | 具体任务 | 产出 | 学习链接 |
|------|----------|----------|------|----------|
| 第 1 天（1.5h） | 大模型基础概念 | 阅读 `llm-universe` 第一章：什么是 LLM、Token、Prompt | 整理 3 条核心概念笔记 | https://github.com/datawhalechina/llm-universe |
| 第 2 天（1.5h） | API 调用入门 | 学习 OpenAI 兼容 API 调用；配置 API Key | 成功调用一次文本生成接口 | https://docs.python.org/zh-cn/dev/whatsnew/3.13.html |
| 第 3 天（1.5h） | Prompt 工程基础 | 学习 System Prompt、Few-shot、温度参数 | 写出 3 个不同风格的 Prompt | https://blog.axiaoxin.com/post/whats-new-in-python-3.13/ |
| 第 4 天（1.5h） | 环境搭建与调试 | 安装 Python 依赖、配置 `.env`、跑通第一个示例 | 本地可运行基础调用脚本 | https://www.cnblogs.com/nanyu/p/19356064 |

**检查点**
- [ ] 能独立调用 LLM API
- [ ] 理解 Prompt 基本写法
- [ ] 本地环境可运行示例代码

---

## Week 2：LangChain 基础

| 时间 | 学习内容 | 具体任务 | 产出 | 学习链接 |
|------|----------|----------|------|----------|
| 第 1 天（1.5h） | LangChain 核心概念 | 阅读 `llm-universe` LangChain 章节：LLM、Chain、PromptTemplate | 画出 LangChain 基本组件关系图 | https://github.com/datawhalechina/llm-universe |
| 第 2 天（1.5h） | 链式调用实践 | 实现 `PromptTemplate -> LLM -> OutputParser` 链 | 完成一个简单问答链 | https://github.com/datawhalechina/easy-langent |
| 第 3 天（1.5h） | 记忆与上下文 | 学习 ConversationBufferMemory、消息历史管理 | 实现带记忆的多轮对话 | https://github.com/datawhalechina/llm-universe |
| 第 4 天（1.5h） | 文档加载与检索 | 学习 Document Loader、Text Splitter、VectorStore | 实现本地文档问答基础版 | https://github.com/datawhalechina/easy-langent |

**检查点**
- [ ] 理解 Chain 和 Memory 的作用
- [ ] 能实现多轮对话
- [ ] 能基于本地文档做简单问答

---

## Week 3：Agent 与工具调用

| 时间 | 学习内容 | 具体任务 | 产出 | 学习链接 |
|------|----------|----------|------|----------|
| 第 1 天（1.5h） | Agent 核心概念 | 阅读 `easy-langent` Agent 章节：ReAct、工具定义、推理循环 | 总结 Agent 工作流程 | https://github.com/datawhalechina/easy-langent |
| 第 2 天（1.5h） | 工具调用实践 | 定义 2-3 个自定义工具（如计算器、天气查询） | 实现带工具的简单 Agent | https://github.com/datawhalechina/coze-ai-assistant |
| 第 3 天（1.5h） | LangGraph 入门 | 学习 State、Node、Edge、Conditional Edge | 用 LangGraph 重构简单 Agent | https://github.com/datawhalechina/easy-langent |
| 第 4 天（1.5h） | 调试与优化 | 观察 Agent 推理轨迹、处理工具调用失败 | 优化 Agent 的鲁棒性 | https://github.com/datawhalechina/llm-universe |

**检查点**
- [ ] 理解 Agent 的 ReAct 推理模式
- [ ] 能定义并调用自定义工具
- [ ] 能用 LangGraph 构建状态化 Agent

---

## Week 4：项目整合与演示

| 时间 | 学习内容 | 具体任务 | 产出 | 学习链接 |
|------|----------|----------|------|----------|
| 第 1 天（1.5h） | 项目选题与设计 | 确定最终 Demo 方向（推荐：个人知识库问答 Agent） | 写出项目需求与功能清单 | https://github.com/datawhalechina/easy-langent |
| 第 2 天（1.5h） | 核心功能开发 | 实现文档加载、向量检索、Agent 问答主流程 | 可运行的核心代码 | https://github.com/datawhalechina/llm-universe |
| 第 3 天（1.5h） | 界面与交互 | 可选：Streamlit/Gradio 简单界面；或命令行交互 | 可交互的演示入口 | https://github.com/datawhalechina/coze-ai-assistant |
| 第 4 天（1.5h） | 测试与演示准备 | 准备演示脚本、录制 Demo 视频或截图 | 完整可演示项目 | https://github.com/datawhalechina/easy-langent |

**检查点**
- [ ] 项目可正常运行
- [ ] 至少 1 个工具调用链路可演示
- [ ] 有 README 说明项目功能

---

## 推荐项目方向

| 项目 | 难度 | 核心能力 |
|------|------|----------|
| 个人知识库问答 Agent | ⭐⭐ | 文档加载 + 检索 + Agent 问答 |
| 工具调用 Agent | ⭐⭐ | 多工具编排 + 推理展示 |
| 简单工作流 Agent | ⭐⭐⭐ | LangGraph 状态机 + 多步任务 |
| Coze 快速原型 | ⭐ | 低代码验证 Agent 思路 |

---

## 学习建议

1. 每天固定时间学习，哪怕只有 30-45 分钟
2. 边学边敲代码，不要只看教程
3. 每周日做 15 分钟复盘
4. 遇到报错先读错误信息，再搜索，最后提问
