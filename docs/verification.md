# 验证记录与交付边界

记录日期：2026-10-06。

**本地 API 与前后端闭环验证已通过：API 21 项测试，真实浏览器 9 组检查。独立代码审查提出的三组问题均已修复并复审关闭。当前尚未正式上线。**

## 已完成的验证

| 项目 | 已记录结果 | 实际范围与证据 |
|---|---|---|
| API 全套测试 | `python -m pytest -q`：20 passed | 根代理最终重新执行；各例使用独立临时 SQLite，经真实 HTTP 接口验证。测试源码在 `tests/` |
| Python 编译检查 | `python -m compileall -q app migrations`：exit 0 | 实施阶段已执行，覆盖应用和迁移模块 |
| 数据库迁移 | Alembic upgrade → downgrade → upgrade 与 `alembic check` 通过 | 使用可丢弃 SQLite；模型与迁移无新增差异。独立审查另执行干净迁移往返：升级 13 张表，降至 base 后仅保留版本表，再次升级恢复 13 张表 |
| API 依赖扫描 | pip-audit 扫描 38 个依赖，0 项已知漏洞 | 本次原始结果为交付工作目录 `work/development/api-audit.json`；结论仅表示扫描时未报告已知依赖漏洞 |
| 配套前端最终验证 | 类型检查、6 文件/19 项测试、生产构建、npm audit 均 exit 0 | 根代理最终重新执行；依赖扫描 232 项、0 已知漏洞。详情见相邻前端仓库 `docs/verification.md` |
| 真实前后端浏览器闭环 | 9 组检查全部 passed | 隔离 SQLite + FastAPI + Vite + Chromium；详见下节 |
| 独立代码审查 | 三组问题全部关闭，结论 Ready to merge — Yes | 已审代码与修复提交；不代表 PostgreSQL、Docker 或生产环境验收完成 |

API 测试覆盖账号与邮箱验证、会话轮换、Origin/CSRF、邀请码绑定与撤销、并发一码一人、离团和旧码重试、邀请配额和限流、草稿 revision 冲突、不可变投稿、审核与撤回、私密帖子/评论/媒体访问、素材所有权、富文本及媒体安全校验。SQLite 的并发结果不能直接视为 PostgreSQL 行锁行为已验证。

## 真实浏览器闭环

运行入口位于相邻前端仓库：`npm run test:e2e`，脚本为 `jianwai-web/e2e/core-flow.mjs`。脚本为每次运行创建独立数据库、邮件 outbox 与媒体目录，使用专用 loopback 端口 8015 / 5175；端口被占用时会拒绝运行。

本次原始结果位于 `jianwai-web/test-results/core-flow/result.json`，状态为 `passed`，记录以下 9 组检查。该结果和截图由脚本生成，位于被 Git 忽略的测试输出目录。

| 序号 | 已通过的实际检查 |
|---|---|
| 1 | 团主在界面创建限定社团、绑定邮箱的邀请码，并一次性显示原文 |
| 2 | 用户真实注册，通过一次性邮箱验证链接验证；token 从地址栏移除 |
| 3 | 预览邀请不消耗邀请码，已验证账号接受邀请后入团 |
| 4 | 真实 Tiptap 文字链接、带格式软换行、图片和图注，经云保存与页面刷新后保留 |
| 5 | 公开投稿在审核前对游客不可见 |
| 6 | 团主阅读完整固定快照并通过；游客读取正文与获准媒体，390px 浏览器视口无横向溢出 |
| 7 | 成员可以发表评论，游客评论被拒绝 |
| 8 | 首页退出后立即清除私密文章，服务端继续拒绝该账号匿名读取原私帖 |
| 9 | 上述实际流程没有未捕获的浏览器错误 |

邮箱步骤使用开发 outbox 中的验证链接，未连接真实 Resend 投递服务。390px 结果是桌面 Chromium 的视口验证，不代表手机输入法、软键盘或无障碍实机验证完成。

## 审查修复记录

| 问题 | 修复及关闭证据 |
|---|---|
| 旧 revision 幂等发布未重查原帖 ACL | API `6539186`：返回历史快照前调用统一 `readable`。A 社团发布→离团→草稿改投 B→重试旧 revision 的实际 HTTP 回归要求 404；独立 ACL 定向测试 3 passed |
| 正常 Tiptap Link `title:null` 与 hardBreak marks 被拒绝 | API `7b86ef7`：可选 title 接受 null 或不超过 160 字的字符串，hardBreak 复用安全 marks 白名单。定向 HTTP 测试 2 passed；实际 Tiptap Editor 生成的完整 JSON 直接 PUT 返回 200，GET 与原 JSON 完全一致 |
| 首页退出后保留旧身份私帖 | Web `04c475f`：资源绑定身份和资格，立即屏蔽旧数据、取消旧请求，logout 成功先清身份；5 项定向回归通过，最终真实浏览器流程也通过 |

独立审查报告保存在交付工作目录 `work/development/code-review.md`。原缺陷和复现记录被保留，避免把初次失败结果与修复后的通过结果混淆。

## 尚未验证的环境与操作

| 项目 | 当前状态 |
|---|---|
| 真实 PostgreSQL | 当前环境未运行 PostgreSQL 测试或迁移。SQL 与锁策略已实施，CI 已配置同套测试；必须以之后实际执行结果为准 |
| Docker / Compose | 文件和启动依赖已静态检查，尚未实际构建镜像或启动整套容器 |
| Resend 实际投递 | NAS 内网预览使用限制到 `muwei.xyz` 的发信 Key；Resend 域名及四条 DNS 记录均为 `verified`，从 API 容器向用户指定的邮箱发送测试邮件返回 200，Resend 邮件状态为 `delivered`。收件箱展示、注册后验证邮件与邀请码业务闭环尚未验收 |
| 远端 GitHub Actions | SQLite/PostgreSQL 矩阵、迁移与镜像检查已配置，工作流尚未在远端执行 |
| 生产部署 | 未在目标服务器上线，未验证生产域名、HTTPS 入口、网络隧道、持久卷运行与恢复演练 |

审查另记录一个非阻断 PostgreSQL 并发改进：评论请求读取资格和帖子状态后，可能与另一事务的离团/撤回交错。尚未在真实 PostgreSQL 上复现；不会让帖子重新公开，也不改变后续读取 ACL。若要求严格阻止所有此类在途评论，应补统一锁内状态复查及 PostgreSQL 双连接回归。

## GitHub 同步状态

目标私有仓库为 `Muwei-TA/jianwai-api` 和 `Muwei-TA/jianwai-web`。现有 GitHub 连接器缺少建仓接口，用户已允许通过 GitHub 网页补足该能力。当前安全登录认证尚未通过，需在安全登录界面完成交接；两个远端仓库尚未创建，推送和 CI 执行仍未完成，不能写成已经同步或上线。

## 复跑入口

在 API 已安装依赖的 Python 环境运行 `python -m pytest -q`。PostgreSQL 测试只能显式指向可丢弃的 `jianwai_test` 数据库，各例会重建该库业务表；不要指向应用数据。

跨仓浏览器验证的依赖、环境变量和运行命令见相邻前端仓库的 README 与 `docs/verification.md`。部署准备见 [deployment.md](deployment.md)，接口与安全边界见 [api-implementation.md](api-implementation.md)。
