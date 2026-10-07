# 前后端接口契约 V0.1

所有路径基于 /api/v1。JSON snake_case；ID 字符串；时间 ISO8601 UTC。响应对象直接返回；列表 {items:[]}; 错误 {error:{code,message,details?}}。分页 limit(1–50,默认20)/offset，列表返回 total。鉴权 Cookie jw_session；GET /auth/session 提供 csrf_token，所有变更（含登录注册）发送 X-CSRF-Token 并校验 Origin。匿名先 GET session，登录后刷新 token。

## 实体
User={id,email,display_name,email_verified,is_member}；Session={user:User|null,csrf_token}
Club={id,slug,name,description,accent,member_count,my_role:null|owner|member,can_invite:boolean}
Document={title,summary,body:JSON,club_id,scope:club|members|public,tags:string[],feedback_intent:string,cover_asset_id:string|null}
Draft=Document+{id,revision,updated_at}；草稿 title 可空、club_id 可 null，其余上限/安全校验保留；发布时才要求 title 最少2字、有效社团和至少文字或图片内容。
Post=Document+{id,author:{id,display_name},club:{id,name,slug},status:pending|published|changes_requested|withdrawn,created_at,published_at?,review_note?,comment_count}
Asset={id,url,mime_type,width,height}
Invitation={id,club_id,code?:string,expires_at,created_at,bound_email:string|null,status:active|used|expired|revoked}

## 账户
密码 10–128 字符；昵称 2–30 字符；邮箱 trim+lowercase。注册失败不可泄露任何 token；重复邮箱返回通用注册提示。
GET /health -> {status:"ok"}
GET /auth/session -> Session (创建匿名 CSRF 会话如无；刷新或登录后再次调用)
POST /auth/register {email,password,display_name} -> Session (自动登录未验证账号；发送邮件；201)
POST /auth/login {email,password} -> Session
POST /auth/logout {} -> {ok:true}
POST /auth/verify-email {token} -> {ok:true}; 无需把 token 留在地址栏，前端 /verify?token=.. 读取后 replaceState 清理，通过按钮 POST
POST /auth/resend-verification {} -> {ok:true}

## 社团与邀请
GET /clubs -> {items:Club[],total}; 仅当前账号已加入且活跃的社团，匿名为空列表
GET /clubs/{id} -> Club; 仅该社团成员可读，其他请求返回 404
GET /clubs/{id}/invites -> {items:Invitation[],total}; 本人邀请权限；仅列本人，owner 可列全团（不返回 code）
POST /clubs/{id}/invites {bound_email?:string} -> Invitation (一次显示 code)
DELETE /clubs/{id}/invites/{invite_id} -> {ok:true}; creator 或 owner
POST /invites/preview {code} -> {club:{id,name,description},expires_at,requires_email:boolean,status:string}; 匿名可预览但限流、不返回绑定邮箱
POST /invites/redeem {code} -> {club:Club,already_member:boolean}
DELETE /clubs/{id}/membership -> {ok:true}; owner 409
GET /clubs/{id}/members -> {items:[{user_id,display_name,role,can_invite,joined_at}],total}; 仅当前owner；不得返回邮箱
PATCH /clubs/{id}/members/{user_id}/invite-permission {can_invite:boolean} -> {ok:true}; owner

## 草稿与媒体
GET /drafts -> {items:Draft[],total}; only own
POST /drafts {club_id?} -> Draft (空稿 revision 1)
GET /drafts/{id} -> Draft
PUT /drafts/{id} {revision,...Document} -> Draft (原子乐观锁 revision+1；409 STALE_DRAFT)
DELETE /drafts/{id} -> {ok:true}; 删除不删除任何已提交 post 固定快照引用的媒体；本轮不做物理垃圾回收
POST /drafts/{id}/media multipart field file -> Asset
GET /media/{id} -> 文件 (动态 ACL, Cache-Control private,no-store, nosniff)；允许本人未删除草稿上传的资产，或某个当前可读 post 的固定快照正文/封面确实引用的资产；同团/同稿其他未引用附件不自动授权
POST /drafts/{id}/publish {revision} -> Post (201; repeated idempotent)

## 内容与审核
GET /posts ?club_id=&scope=&q=&limit=&offset= -> {items:Post[],total}; 仅可读 published；文字搜索先 ACL
GET /posts/{id} -> Post (pending/退回 仅作者及该团 owner)
GET /me/posts -> {items:Post[],total}; 自己稿件，已离团私文不展示
GET /reviews -> {items:Post[],total}; owner所管团 pending 固定完整快照
POST /posts/{id}/review {decision:approve|request_changes,note?:string} -> Post
POST /posts/{id}/withdraw {} -> {id,status:"withdrawn"}；作者即使已离团仍可撤回本人稿；响应不附正文。与审核使用相同锁/条件状态更新，撤回不能被迟到审核复活
GET /posts/{id}/comments -> {items:[{id,body,author:{id,display_name},created_at}],total}
POST /posts/{id}/comments {body:string} -> Comment (1–2000字，纯文本；201)

## 状态规则
review_note 只向作者及有权团主返回；公开列表/阅读给其他读者的 Post DTO 必须省略内部审核意见。
withdrawn 对作者及该团 owner 可读，但私密帖仍要求当前对应社团/社区资格；其他账号详情/评论/该帖子独占附件均404。若同一资产另被当前可读稿件引用，则按另一条合法引用授权。
401 AUTH_REQUIRED,403 EMAIL_UNVERIFIED/CSRF_FAILED/INVITE_PERMISSION_REQUIRED,404 NOT_FOUND（包括无权看具体内容）,409 INVITE_UNAVAILABLE/ALREADY_REDEEMED/STALE_DRAFT/INVALID_STATE,422 VALIDATION_ERROR,429 RATE_LIMITED。前端显示服务端中文 message，不能吞保存错误或把409当成功。

## 富文本内联标记补充
text 和 hardBreak 都可携带安全 marks（跨软换行选区格式会给 hardBreak 加标记），其它块节点禁止 marks。link attrs 允许 href、target、rel、class:null、title:null 或最多160字符文本；URL仍只http/https，不接受onclick等未知属性。

## 本地集成
API 127.0.0.1:8000；web 127.0.0.1:5173，Vite /api 代理 localhost:8000 保留浏览器 Origin。API allowed_origins 显式 http://localhost:5173,http://127.0.0.1:5173。生产 Nginx /api 转后端、其它路径 SPA fallback。不要跨端口直接取媒体，浏览器用 /api/v1/media/id 同源。
