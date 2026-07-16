# Changelog

本项目遵循语义化版本。尚未发布的改动记录在 `Unreleased`。

## Unreleased

- 暂无。

## 0.3.0 - 2026-07-15

### Added

- React WebUI，支持 Markdown、图片与常用文档输入、会话管理、运行轨迹和审批。
- Datawhale BM25 学习规划子代理、学习者档案、知识图谱、动态路线、间隔复习、项目陪学和学习档案。
- Obsidian Learning Wiki 同步与 Web 图谱镜像。
- `whale-web`、`whale-doctor`、健康检查、wheel 静态资源打包和 Docker/Compose/systemd 部署能力。
- Whale CLI 品牌 logo 与独立项目介绍页。

### Changed

- 运行数据与工作区通过 `WHALE_HOME`、`WHALE_WORKSPACE` 分离。
- 教程扩展为 00-27 章，并与每个可运行模块和测试对应。

### Verified

- 174 项离线测试通过，4 项真实模型 E2E 默认跳过。
- wheel 纯净环境安装、React 生产构建、Docker 镜像及容器健康检查通过。
