# 间外 API 核心闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 可运行且有真实鉴权、事务、持久化的社区 API。

**Architecture:** 模块化单体，SQLAlchemy 数据库事务统一控制邀请码、稿件版本与审核。Cookie 会话加 CSRF；所有内容入口共用可见性策略。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2、Alembic、Argon2、PostgreSQL/SQLite。

**Spec:** docs/architecture.md, docs/api-contract.md

## Global Constraints
- 遵守 docs/architecture.md 与 docs/api-contract.md，接口字段与 Tiptap JSON 完全一致。
- 用户授权开发与创建新仓库；沿用 V2 设计。范围外功能记录 backlog，不扩张首版。
- 私有仓库拟定 Muwei-TA/jianwai-web 与 Muwei-TA/jianwai-api。现有 GitHub 连接器缺少建仓接口，用户已允许通过 GitHub 网页补足；当前远端创建和同步的实际阻塞是安全登录流程尚未完成，本地实施持续进行。
- 不触碰旧 jianwai-prototype 的源码与远端；分离工作目录和提交。禁止生产演示登录、默认密码、私密内容静态打包。

## Review Focus
- 两账号同时兑换一次性邀请码，不得产生两个有效兑换；绑定、撤销和离团重试一致。
- 草稿快速编辑/保存失败/旧版本冲突不丢用户输入，审核绑定不可变快照。
- 知道帖子/媒体 ID 的未授权账号也不能看到私密数据；列表、详情与评论一致。
- 手工伪造富文本 JSON、URL、媒体类型和他人 assetId 时服务端拒绝，前端不注入任意 HTML。
- 中文标题、窄屏与长文本不溢出；未登录/未验证/无社团状态可清晰继续流程。

---

### Task 1: 账号、社团与邀请
**Files:** app/main.py, app/config.py, app/db.py, app/models.py, app/auth.py, app/clubs.py, app/invites.py, app/cli.py, tests/test_auth_invites.py, pyproject.toml, migrations/
**Interfaces:** create_app(settings) -> FastAPI; 文档规定的 /auth、/clubs、/invites 路由。bootstrap CLI 只显式创建运营账号和社团。
- [x] 编写并运行契约 HTTP 测试：密码登录、会话轮换、未验证不可兑、CSRF失败、一码并发只一成功、成员不消费、离团旧码不可重用、邮箱绑定、邀请权撤销。实际执行数据库为 SQLite。
- [x] 实现数据库、迁移、配置、散列会话、邮件 outbox/SMTP、角色与事务邀请码；依赖精确锁定。SMTP 实际投递尚未验证。
- [x] 跑完整当前 pytest 并提交实现；最终 API suite 为 20 passed。

### Task 2: 草稿、媒体、发布与审核
**Files:** app/documents.py, app/media.py, app/posts.py, app/policy.py, tests/test_documents.py, tests/test_acl.py
**Interfaces:** 契约 /drafts、/media、/posts、/reviews；私密资源同一 ACL。
- [x] 写并运行测试：草稿 revision 409、重复 publish 幂等、编辑不影响已提交稿、私密列表/详情/媒体/评论越权、伪造 JSON 与跨作者 assetId 拒绝、审批状态原子更新。
- [x] 实现严格 rich JSON 验证、图片解码重编码与私有响应、immutable post snapshot、团主审核、回应。
- [x] 跑完整 pytest，生成 OpenAPI JSON并提交实现；已报告实际验证数据库为 SQLite。
- [x] 修复并复审旧稿幂等 ACL 与真实 Tiptap Link/格式化 hardBreak 保存兼容性，相关回归通过。

### Task 3: 运维与交付（根代理负责）
**Files:** Dockerfile, compose.yaml, .env.example, .github/workflows/ci.yml, README.md, docs/verification.md
**Interfaces:** 环境变量由配置模块定义；本地与容器启动用同样迁移命令。
- [x] 写部署和验证说明；实际 SQLite 迁移 upgrade→downgrade→upgrade 与模型检查通过；配置 PostgreSQL CI 服务，尚未实际运行 PostgreSQL 或远端 CI。
- [x] 和 web 完成真实 HTTP/浏览器 9 组闭环检查；配置敏感文件忽略规则；三组审查问题均修复并复审关闭。
- [x] 记录 API 20 项测试、38 个依赖零已知漏洞及 PostgreSQL/Docker/SMTP 投递/远端 CI 的未验证边界，见 docs/verification.md。
- [x] 根代理统一提交最终部署、CI、README 与验证材料（随本次本地交付提交保存）。
- [ ] 完成安全登录后创建两个私有 GitHub 仓库并推送；网页补足已获允许，当前阻塞为登录流程，尚未完成远端同步。
