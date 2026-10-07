# 黑匣子 · API

邀请制兴趣社团社区的服务端，V0.1。与相邻的 `jianwai-web` React 前端配套。

当前已实现真实账号、邮箱验证与密码重置、社团邀请码、结构化富文本云草稿、图片与私密访问、不可变投稿及团主审核、阅读与评论。V2 产品设计落为模块化单体；这是首轮工程实现，尚未部署到生产服务器。

## 快速开始

需要 Python 3.12。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

另开终端激活同一虚拟环境，用交互密码创建团主及首个社团：

```bash
python -m app.cli bootstrap --email 'operator@example.com' --display-name '团主' --club-slug 'film' --club-name '影像漫游'
```

请将示例邮箱改为你控制的邮箱。bootstrap 是显式运营操作，会将该运营邮箱标记为已验证；拒绝对既有账号自动提权。没有默认密码或生产演示登录。普通用户从前端注册后，通过邮箱验证链接，再兑换团主创建的邀请码。开发验证邮件位于被Git忽略的 `var/outbox`，仅在本地读取；生产必须配置 Resend。

前端在 `http://localhost:5173` 运行，Vite同源代理 `/api`。后端交互式文档是 `http://127.0.0.1:8000/docs`，正式契约见 [docs/api-contract.md](docs/api-contract.md)。

## 验证

```bash
python -m pytest -q
alembic check
```

测试默认使用每例独立临时SQLite，绝不使用应用数据库。PostgreSQL测试需显式设置 `TEST_DATABASE_URL` 且库名必须是 `jianwai_test`；该测试库的业务表会在各例重建，只能用于可丢弃测试数据。GitHub Actions配置同时跑SQLite与PostgreSQL，远端执行状态以实际工作流为准。

完整跨仓浏览器验证在前端执行 `npm run test:e2e`；会为该次运行创建独立SQLite、邮件和媒体目录，使用临时测试账号，不连接既有部署。详情见 [docs/verification.md](docs/verification.md)。

## 关键规则

- 账号不等同于社团成员；验证邮箱后兑换单社团、单次、7天邀请码。邀请权限独立授予，离团和撤权使未使用码失效。
- Session token仅在HttpOnly Cookie中，数据库存散列；所有写入检查Origin与CSRF；密码Argon2。
- 草稿按revision乐观锁保存，409明确拒绝旧版本；空草稿可以保存，完整性与资格在发布检查。
- 投稿快照不随草稿继续修改；public经团主审核，club/members按权限直接发表。公开快照不复制内部评论。
- 列表、详情、搜索、评论和附件统一权限；私密附件不能直接通过静态目录访问。
- 团主可以审核自己投稿，行为写入审计；这是首版明确选择，不是双人审核系统。

## 目录与文档

`app/`为按业务模块拆分的API；`tests/`为真实HTTP、事务与访问测试；`migrations/`管理数据库结构。

- [架构和范围](docs/architecture.md)
- [接口契约](docs/api-contract.md)；服务启动后可在 `/openapi.json` 查看动态 OpenAPI
- [实现和安全边界](docs/api-implementation.md)
- [本地与容器部署](docs/deployment.md)
- [实施计划](docs/superpowers/plans/2026-10-06-core-community.md)
- [验证记录及未完成项](docs/verification.md)

## 后续迭代

成员所有权转移、举报工作台、云对象存储、分布式限流、媒体总配额与垃圾回收、邮件重试队列、数据库全文搜索、备份恢复演练尚未完成。API默认单进程，SQLite只供开发；生产使用PostgreSQL、HTTPS和 Resend。详见部署文档。
