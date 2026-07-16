# 15. Skills 进阶：按来源分层发现

本章导航：

- 新增机制：按项目、用户和内置来源发现 Skill，并在重名时保留高优先级版本。
- 正式入口：`src/whale_cli/skill/discovery.py`。
- 验证方式：`./.venv/bin/python -m pytest tests/test_skills_and_agents.py -q`。
- 本章不展开：远程技能市场、签名校验和模型按需读取全文仍是扩展练习。

第 08 章讲过 skills 的基本思想：把一套可复用流程写成 `SKILL.md`，需要时再加载。

这一章补真实实现里最容易被忽略的一点：**skill 不是只来自一个目录。**

成熟 CLI Agent 会同时支持内置技能、用户技能、项目技能、插件技能，而且要有优先级。

## 本章目标（验收标准）

读完这一章，你应该能回答：

- 为什么不能只扫描 `./skills`
- 生产级参考实现的 skill root 优先级是什么
- Whale CLI 如何做一个不复杂但够用的分层发现机制

## 生产级参考实现里的真实结构

![Skills 分层发现与加载](images/skills-layered-discovery.svg)

生产级参考实现的 skill 发现逻辑在 `production_cli/skill/__init__.py`，核心思想是：

```text
Project > User > Extra > Built-in
```

它会看多类目录：

| scope | 示例 |
|---|---|
| project | `<repo>/.whale_cli/skills`, `<repo>/.agents/skills` |
| user | `~/.whale_cli/skills`, `~/.agents/skills` |
| extra | 配置或命令行额外传入的 skills 目录 |
| builtin | 生产级参考实现自带 skills |

如果同名 skill 在多个地方出现，高优先级覆盖低优先级。

这解决了一个现实问题：项目里的 skill 应该比全局 skill 更贴近当前仓库。

## Whale CLI 现在在哪里

Whale CLI 当前第 08 章更偏设计篇，代码层还没有完整 skill loader。

如果下一步要补，不能只写：

```python
for path in Path("skills").glob("*/SKILL.md"):
    ...
```

这样会让 skill 只能服务当前目录，无法复用，也无法被项目覆盖。

## 教学版应该怎么补

Whale CLI v0 可以只实现三层：

```text
Project > User > Built-in
```

目录建议：

```text
src/whale_cli/
├── skill/
│   ├── __init__.py
│   ├── models.py       # Skill / SkillRoot
│   ├── discovery.py    # 找目录、去重、读 frontmatter
│   └── loader.py       # 按名字加载全文
└── skills/
    └── whale-cli-help/
        └── SKILL.md
```

扫描路径：

```text
项目级：
  .whale_cli/skills
  .agents/skills

用户级：
  ~/.whale_cli/skills
  ~/.agents/skills

内置：
  src/whale_cli/skills
```

## Skill 数据结构

最小字段：

```python
@dataclass
class Skill:
    name: str
    description: str
    path: Path
    scope: str  # project/user/builtin
```

`SKILL.md` 顶部可以支持简单 frontmatter：

```markdown
---
name: bug-fix
description: Diagnose a failing test and implement a small fix.
---

# Bug Fix

...
```

如果没有 frontmatter，就用目录名作为 name，用第一段文字作为 description。

## 注入策略

不要把所有 skill 全文塞进 system prompt。

第一层只注入索引：

```text
Available skills:
- bug-fix (project): Diagnose a failing test and implement a small fix.
- code-review (user): Review code for bugs and missing tests.
```

当模型明确要用某个 skill 时，再通过工具或 loader 读取全文。

这就是生产级参考实现和 Claude Code 都在坚持的原则：**先让模型知道有什么，用到时再展开。**

## 本章验收

准备两个同名 skill：

```text
~/.whale_cli/skills/bug-fix/SKILL.md
./.whale_cli/skills/bug-fix/SKILL.md
```

合格表现：

- 项目级 `bug-fix` 覆盖用户级 `bug-fix`
- system prompt 里只出现一条 `bug-fix`
- 模型需要时能读取项目级全文
- 删除项目级后，自动回退到用户级

## 和生产级参考实现的差距

生产级参考实现还支持：

- 更多来源目录和作用域
- plugin 贡献的 extra skills
- flow skill
- scope 分组显示
- symlink / canonical path 去重
- frozen bundle 下的 builtin skill 路径处理

Whale CLI 先抓住主线：**skill 有来源、有优先级、先索引后加载。**

---

## 本章模块化代码

第 08 章看 skill 概念；这一章看真正的分层发现逻辑。

### 1. 默认搜索路径

文件：`src/whale_cli/skill/discovery.py`

```python
def default_skill_roots(work_dir: str | os.PathLike[str] | None = None) -> list[SkillRoot]:
    root = find_project_root(work_dir)
    home = Path.home()
    candidates = [
        SkillRoot(root / ".whale_cli" / "skills", "project"),
        SkillRoot(root / ".agents" / "skills", "project"),
        SkillRoot(home / ".whale_cli" / "skills", "user"),
        SkillRoot(home / ".agents" / "skills", "user"),
        SkillRoot(builtin_skills_dir(), "builtin"),
    ]
    return [r for r in candidates if r.path.is_dir()]
```

顺序就是优先级：project > user > builtin。

### 2. 解析 frontmatter

```python
def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    raw = text[4:end].strip()
    data = {}
    for line in raw.splitlines():
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data, body
```

### 3. 去重：高优先级先赢

```python
def discover_skills(roots: Iterable[SkillRoot] | None = None) -> list[Skill]:
    found: dict[str, Skill] = {}
    for root in roots or default_skill_roots():
        for skill_file in sorted(root.path.glob("*/SKILL.md")):
            skill = _skill_from_file(skill_file, root.scope)
            if skill.name not in found:
                found[skill.name] = skill
    return list(found.values())
```

这个实现很小，但已经把真实 skill 系统最重要的三件事讲清楚：来源、优先级、按需读取。

## 本章测试与边界

```bash
./.venv/bin/python -m pytest tests/test_skills_and_agents.py -q
```

优先级来自 `default_skill_roots()` 返回的根目录顺序，发现同名 Skill 时第一个被发现的版本保留。它不比较修改时间或版本号。frontmatter 解析只支持简单的 `key: value` 行；复杂 YAML 应留给后续替换解析器的练习。

## 本章小结

分层发现让项目可以覆盖用户或内置 Skill，同时保持规则可预测。当前优先级是固定目录顺序，不做版本解析。下一章会把外部 MCP server 和本地插件统一接入 Toolset，但它们的执行边界不同。

下一章：[16-MCP与插件-把外部能力接进工具池.md](16-MCP与插件-把外部能力接进工具池.md)。
