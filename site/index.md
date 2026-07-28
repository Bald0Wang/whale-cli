---
layout: page
title: Whale CLI 教程
sidebar: false
---

<style>
/* 首页：隐藏所有 VitePress chrome,只留导航栏 + iframe 全屏 */
html.is-home .VPSidebar,
html.is-home .VPLocalNav,
html.is-home .VPFooter,
html.is-home .VPDocAside,
html.is-home .VPDoc h1 { display: none !important; }

html.is-home .VPContent { padding: 0 !important; margin: 0 !important; max-width: 100% !important; }
html.is-home .VPContent.has-sidebar { padding-left: 0 !important; }
html.is-home .VPPage { padding: 0 !important; }
html.is-home .VPPage > div { max-width: 100% !important; }

/* 导航栏米白——用 CSS 变量覆盖 VitePress 的默认值 */
html.is-home { --vp-c-bg: #faf9f5; --vp-c-bg-alt: #f4f2ea; --vp-c-bg-elv: #f4f2ea; --vp-c-bg-soft: #f4f2ea; --vp-nav-bg-color: #faf9f5; --vp-c-divider: #e8e4d8; }
html.is-home .VPNavBar { background: var(--vp-nav-bg-color) !important; border-bottom: 1px solid #e8e4d8 !important; }
html.is-home .VPNavBar .container { background: transparent !important; }
html.is-home .VPNavBarTitle .title { font-size: 1.05rem !important; font-weight: 600 !important; color: #29261f !important; }
html.is-home #local-search .DocSearch-Button { background: #f4f2ea !important; border: 1px solid #e8e4d8 !important; color: #7d766a !important; box-shadow: none !important; }
html.is-home #local-search .DocSearch-Button:hover { border-color: #d9d3c2 !important; }
html.is-home .DocSearch-Button-Placeholder { color: #b3ac9d !important; }
html.is-home .DocSearch-Button-Keys kbd { background: #ece9e0 !important; border-color: #d9d3c2 !important; color: #7d766a !important; box-shadow: none !important; }
html.is-home .VPSwitchAppearance,
html.is-home .VPNavBarAppearance,
html.is-home .appearance { display: none !important; }
</style>

<iframe src="/viz/all-chapters-hero-journey.html" style="width:100%;height:calc(100vh - 64px);border:none;display:block;" loading="lazy"></iframe>
