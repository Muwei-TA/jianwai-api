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

## NAS 内网预览验收（2026-10-07）

| 项目 | 当前状态 |
|---|---|
| PostgreSQL | NAS 预览库已执行迁移 `01cb45f9a35a`；PR 的 SQLite/PostgreSQL 检查通过 |
| Docker / Compose | NAS 预览的数据库、API、Web 容器均 healthy；内网页面与同源 API 返回 200 |
| Resend 与真实邮箱 | 域名和四条 DNS 记录均为 `verified`。通过预览 API 注册受控转发邮箱返回 201，Resend 报告 `delivered`，目标 Gmail 实际收到验证信，但归入垃圾邮件；提交邮件中的一次性 token 验证返回 200 |
| 邀请码 | 团主创建绑定该邮箱的邀请码返回 201；匿名预览返回 200 且不消耗；已验证账号兑换返回 200、`already_member=false`。只读回查为 2 个已验证用户、2 个成员、1 个已使用邀请码；浏览器社团页显示 2 位同好及邀请码“已使用”，console 无错误 |
| 生产部署 | 当前仍为 NAS 内网 HTTP 预览；公网 HTTPS、手机实机、生产备份与恢复演练尚未验收 |

审查另记录一个非阻断 PostgreSQL 并发改进：评论请求读取资格和帖子状态后，可能与另一事务的离团/撤回交错。尚未在真实 PostgreSQL 上复现；不会让帖子重新公开，也不改变后续读取 ACL。若要求严格阻止所有此类在途评论，应补统一锁内状态复查及 PostgreSQL 双连接回归。

## GitHub 同步状态

两个公开仓库 `Muwei-TA/jianwai-api` 与 `Muwei-TA/jianwai-web` 已存在。Resend 代码位于后端草稿 PR #1 的 `codex/resend-email` 分支；CI 已通过，尚未合并到 `main`。NAS 内网预览使用该分支代码，不等于正式发布。

## 复跑入口

在 API 已安装依赖的 Python 环境运行 `python -m pytest -q`。PostgreSQL 测试只能显式指向可丢弃的 `jianwai_test` 数据库，各例会重建该库业务表；不要指向应用数据。

跨仓浏览器验证的依赖、环境变量和运行命令见相邻前端仓库的 README 与 `docs/verification.md`。部署准备见 [deployment.md](deployment.md)，接口与安全边界见 [api-implementation.md](api-implementation.md)。
