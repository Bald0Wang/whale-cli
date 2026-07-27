import { defineConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'

export default withMermaid(defineConfig({
  title: 'Whale CLI 教程',
  description: '从零搞懂 CLI Coding Agent 的设计与实现',
  lang: 'zh-CN',
  // 正文里有指向 ../../code 源码文件的相对链接（站点目录外），
  // 公网部署时不作为页面链接解析，忽略死链检查让 build 通过。
  ignoreDeadLinks: true,
  srcExclude: [
    '_archive/**',
    'ch06.md', 'ch07.md', 'ch08.md', 'ch09.md',
    'ch10.md', 'ch11.md', 'ch12.md',
    'engineering-details-todo.md',
    'ai-flavor-todo.md',
    'viz-flat-review.md',
    'viz-polish-tracker.md',
    'human-habit-insights.md',
    'ch00-context-animation-vision.md',
  ],
  themeConfig: {
    nav: [{ text: '开始阅读', link: '/ch00' }],
    sidebar: [
      {
        text: '入门篇',
        items: [
          { text: '第 0 章 · 开篇', link: '/ch00' },
          { text: '第 1 章 · 最小 Agent Loop', link: '/ch01' },
          { text: '第 2 章 · 工具的统一管理', link: '/ch02' },
          { text: '第 3 章 · 读文件：Read', link: '/ch03' },
          { text: '第 4 章 · 写文件：Write 与 Edit', link: '/ch04' },
          { text: '第 5 章 · 搜文件：Glob 与 Grep', link: '/ch05' },
        ]
      },
      {
        text: '即将上线',
        items: [
          { text: '第 6 章 · 运行与验证：Bash' },
          { text: '第 7 章 · 任务拆解：TodoWrite' },
          { text: '第 8 章 · 项目规则与环境感知' },
          { text: '第 9 章 · 上下文组装' },
          { text: '第 10 章 · 会话持久化' },
          { text: '第 11 章 · 上下文压缩' },
          { text: '第 12 章 · 操作审批' },
        ]
      },
      {
        text: '进阶篇（开发中）',
        items: []
      },
    ],
    outline: { level: [2, 3], label: '目录' },
    search: { provider: 'local' },
  },
  mermaid: {
    theme: 'base',
    look: 'handDrawn',
    themeVariables: {
      primaryColor: '#fff7ed',
      primaryBorderColor: '#d97757',
      primaryTextColor: '#29261f',
      lineColor: '#c4b5a4',
      secondaryColor: '#f5f0e8',
      tertiaryColor: '#faf9f5',
      fontFamily: '-apple-system, Inter, system-ui, sans-serif',
      fontSize: '14px',
    },
  },
}))
