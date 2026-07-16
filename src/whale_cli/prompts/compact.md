# 上下文压缩提示词（Compaction Prompt）

> 本文件由 `soul/compaction.py` 加载，用于在长对话触发压缩时，指导模型生成结构化的会话摘要。
> 使用 XML 标签结构，方便后续恢复当前任务、环境、问题和代码状态。

---

Below is a list of messages from an agent conversation. Compact this conversation
according to the priorities and rules below. Output a structured summary using
the XML tags shown at the end.

**压缩优先级（按顺序）：**
1. **Current Task State（当前任务状态）**：现在正在做什么
2. **Errors & Solutions（错误与解决方案）**：遇到过的所有错误及其解决办法
3. **Code Evolution（代码演变）**：只保留最终可用版本，删除中间尝试
4. **System Context（系统上下文）**：项目结构、依赖、环境配置
5. **Design Decisions（设计决策）**：架构选择及其理由
6. **TODO Items（待办事项）**：未完成的任务和已知问题

**压缩规则：**
- **必须保留**：错误信息、堆栈跟踪、可用的解决方案、当前任务状态
- **合并**：相似的讨论合并成要点
- **删除**：冗余解释、失败尝试（但保留"教训"）
- **浓缩**：长代码块 → 只保留签名 + 关键逻辑

**特殊处理：**
- 代码：< 20 行可全保留，否则只留签名 + 关键逻辑
- 错误：保留完整错误信息 + 最终解决方案
- 讨论：只提取决策和行动项

**输出结构（务必使用这些 XML 标签）：**

<current_focus>
[现在正在做什么]
</current_focus>

<environment>
- [关键环境/配置要点]
- ...
</environment>

<completed_tasks>
- [任务]: [简要结果]
- ...
</completed_tasks>

<active_issues>
- [问题]: [状态/下一步]
- ...
</active_issues>

<code_state>

<file>
[文件名]

**Summary:**
[这个文件做什么]

**Key elements:**
- [重要的函数/类]
- ...

**Latest version:**
[关键的代码片段]
</file>

</code_state>

---

**待压缩的对话内容：**

{conversation}
