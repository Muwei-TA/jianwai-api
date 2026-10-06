# 间外 V0.1 工程规格

日期：2026-10-06。根据本轮已经完成的 V2 产品计划书和原型实施。用户已授权创建前后端 GitHub 仓库并开发。

## 目标与范围

交付可以真实联调的第一版：注册、邮箱验证、登录退出、邀请入团、社团浏览、结构化富文本云草稿、多稿管理、图片上传、内部发布、独立公开投稿与团主审核、阅读和评论。不是只搭脚手架。前端延续间外 V2 暖白杂志版式、克制橙色、文化兴趣社团，不复制机核商标或素材。首轮不做 IM、积分、支付、推荐算法或 App。

## 架构

两个独立仓库：jianwai-web（React + TypeScript + Vite + Tiptap 3.31.4）和 jianwai-api（Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic）。生产 PostgreSQL，开发允许 SQLite 文件。API /api/v1，通过前端开发代理或 Nginx 同源访问。部署由 API 仓库 compose 编排两个相邻仓库，私有媒体经 API 鉴权后返回，不能作为公开静态目录。密码使用 Argon2；随机不透明 session token 仅存 HttpOnly Cookie，数据库存散列。无 JWT localStorage。Cookie SameSite=Lax；生产 Secure；状态变更必须校验 Origin 和 CSRF token。前端会话状态仅内存，用户内容不写公共静态 bundle。

## 第一版业务规则

- 账号与成员分开：邮箱验证后可兑换邀请码；成功加入任一社团后持有社区成员资格。离开最后一个社团不删除全站成员资格。
- 社团角色 owner/member，邀请权限 can_invite 独立。团主默认可邀请；普通成员不可默认生成。首位运营账号和社团通过显式 CLI bootstrap 创建，不在生产提供公开提权/演示角色切换接口。
- 邀请码随机高熵，库中只存 hash，响应创建时一次性返回原文。仅绑定一个社团；7 天过期；每邀请人每团最多 20 个有效未用码；可选绑定规范化邮箱。预览不消费；邀请码不进常规日志。
- 兑换验证账号、邮箱、团状态、邀请人仍在团且仍有邀请权、有效期、撤销、绑定邮箱、是否已有资格。事务内条件更新消费码并加入成员。一码两个账号同时兑换仅一人成功。已在团不消费。已成功兑换者重试若仍为成员返回原结果；离团后旧码不得再次加入。撤销邀请权或退出撤销该人在本团所有未使用码，不影响已加入者；团主必须转移后离团（本轮未实现转移 UI，直接阻止团主离团）。
- 范围 public/members/club；默认 club。读 API、列表、搜索、个人帖子、评论与附件应用相同 ACL。非授权资源返回 404。站点管理员没有普通请求的私密内容旁路。公开文章游客可读，仅社区成员可评论；club 仅在团成员可读评；members 仅全站成员可读评。
- 保存草稿与发布不同。未完成草稿可使用空标题和 null club_id；安全与长度上限始终生效，最小标题/正文和社团资格仅在发布校验。草稿归 user_id，多草稿；版本号乐观锁，旧 revision 保存返回 409，客户端保留输入、导出备份并显式重新载入。请求中显式 revision，不允许最后写入静默覆盖。
- 发布读取指定已保存 revision 的不可变快照，server 校验本人仍在团且邮箱验证。club/members 直接发布；public 进入 pending。发布请求幂等：同一 draft_id + revision 唯一，不制造重复稿件。后续编辑草稿不会改写已提交快照。
- 公开稿独立 post，不把内部评论、反应或成员清单复制过去。团主对完整固定快照审批；第一版团主可审核自己的投稿，操作同样记录审计，不虚构双人审核要求。后续可增加双人审核策略。
- 决定通过/退回操作仅 owner 可执行且原状态必须 pending，事务写审核记录。作者在投稿列表看到状态和退回原因；退回后草稿可改新 revision 重投。撤回自己投稿/文章；隐藏不等于删除。
- 邮件真实 SMTP 适配；development 明确使用本地 outbox 文件，响应不得泄露验证码或 token。生产配置缺 SMTP 拒绝启动。验证 token 随机、散列、有效期、一次性；登录/注册/重发/评论等适当限流；本版单实例限流边界明确。

## 富文本契约

canonical body 是 Tiptap JSON doc。允许 paragraph/text/heading(level2,3)/blockquote/bulletList/orderedList/listItem/horizontalRule/hardBreak/figure/gallery/linkCard，marks bold/italic/underline/strike/code/link/spoiler。不接收任意 HTML 或 iframe；link 仅 http/https。后端严格校验节点、attrs、深度与体积，不可信 attrs 不直接渲染。标题 2–80 字，摘要 <=160；正文纯文本 <=20000 字；tags <=5，每个 <=20；正文图片 <=9，每张 <=10 MiB；封面独立。

figure attrs={assetId,caption,alt,layout:normal|wide,spoiler:boolean}；gallery attrs={items:[{assetId,caption,alt}],caption,layout}；linkCard attrs={url,title,description}；spoiler mark 无 attrs。上传 JPEG/PNG/WebP，校验 MIME+真实解码和像素上限，重新编码移除元数据，拒绝 SVG/GIF 与外部图片 URL。媒体 attrs 仅保存 server assetId；上传先拥有草稿，再将媒体关联该草稿。正文/封面只能引用本人可用于该稿的素材，不能通过猜 ID 公开别人的私图。

## 开发约束与验收

仓库没有默认生产密码、真实 token、个人邮箱种子。README 中文；.env.example 仅占位符；依赖锁定；CI 前端类型/构建/测试，后端含 PostgreSQL 服务和测试、迁移。本地至少通过实际 HTTP API 和真实浏览器一条注册→验证→邀请码→写作→保存刷新→投稿→审核→游客阅读闭环。后端覆盖越权、一码并发、重试离团、草稿 409、固定审核版本、恶意 JSON 与媒体鉴权。测试不能把前端模拟权限当服务端权限。

## 已知首轮边界

密码重置、跨设备会话管理、举报后台、管理员转让、内容修改版本串联、云对象存储、分布式限流、邮件投递追踪、备份恢复演练在后续迭代；部署配置可运行并不等于已上线。未连接 PostgreSQL 或 Docker 时必须如实记录验证范围，不能声称已经验证。
