# 间外 API 实现说明

## 启动与配置

Python 3.12，安装 `pip install -r requirements.lock`，复制 `.env.example` 为 `.env` 并填写，运行 `alembic upgrade head`，然后 `uvicorn app.main:app --host 127.0.0.1 --port 8000`。`.env` 自动加载，已导出的环境变量优先。应用启动不创建业务表，迁移是必需步骤。API 前缀 `/api/v1`，健康检查 `/api/v1/health`。

配置名：`APP_ENV`、`DATABASE_URL`、`ALLOWED_ORIGINS`（逗号分隔）、`COOKIE_SECURE`、`MEDIA_DIR`、`OUTBOX_DIR`、`PUBLIC_WEB_URL`、`SMTP_HOST`、`SMTP_PORT`、`SMTP_USERNAME`、`SMTP_PASSWORD`、`SMTP_FROM`、`SMTP_STARTTLS`。生产 `APP_ENV=production` 必须配置 PostgreSQL、SMTP_HOST/FROM、HTTPS ALLOWED_ORIGINS 和 PUBLIC_WEB_URL、COOKIE_SECURE=true；缺少时启动失败。SMTP 适配使用可配置 STARTTLS，不支持将465端口当作隐式TLS。默认开发库 `var/jianwai.db`、媒体 `var/media`、邮件 `var/outbox`；全部位于忽略目录。

开发无 SMTP 时邮件写入本地 JSON outbox（权限0600）。文件包含验证链接，供本地集成读取；API响应和正常日志不返回验证token。生产不允许outbox替代SMTP。验证邮件24小时有效，重发撤销旧链接，成功验证只能一次。SMTP出错返回503，业务事务回滚；本版同步邮件发送与数据库提交不是分布式原子事务，极端数据库提交失败时邮件中的链接会无效，用户可重新注册/重发。

运营创建须显式执行：

```bash
python -m app.cli bootstrap --email 'operator@example.com' --display-name '运营' --club-slug 'books' --club-name '读书团' --club-description '关于阅读的讨论'
```

密码由getpass交互读取；自动化可显式设置 `BOOTSTRAP_PASSWORD`，应避免写入命令行或受版本控制的文件。无默认密码；bootstrap拒绝既有邮箱和slug，不提升既有用户。它创建邮箱已验证、具有全站成员资格的团主和一个社团，打印两个ID。无HTTP提权或演示权限接口。

## 事务和安全

密码Argon2，10–128字符，保留空白。昵称2–30字符。邮箱trim+lowercase。会话cookie `jw_session` 为高熵随机token，数据库只有SHA256摘要；HttpOnly、SameSite=Lax，生产Secure；30天有效。匿名GET `/auth/session` 建立CSRF会话；登录/注册/退出轮换会话，退出后需重新GET session刷新CSRF。全部变更要求显式允许的Origin与匹配CSRF。响应默认private,no-store及nosniff。

SQLite每个API数据库事务先BEGIN IMMEDIATE，因此数据库写入串行；SQLite仅供开发。PostgreSQL邀请码创建、兑换、撤销、成员退出、邀请权修改先锁同一个club行，随后邀请码CAS消费与membership写入同事务；重复使用或权限撤销不会绕过锁。发布锁草稿行，再校验在团与已保存revision，唯一索引保证同draft/revision只有一份快照；幂等重试返回旧快照前仍校验旧帖自身的当前ACL，不能借草稿转团读回已离团的私文。保存CAS revision+1，旧版本409；空标题/空社团的未完成草稿和离团后的本人草稿仍可保存，发布才验证资格和内容完整性。审核和撤回共用club锁，审核CAS仅pending，可撤回已离团的本人文章；响应只给id/status。

Tiptap link 的可选title允许null或至多160字字符串；hardBreak允许和text相同的安全marks白名单（支持跨换行加粗），block节点仍禁止marks。其余未知属性及危险链接继续拒绝。正文JSON在保存和发布均严格校验节点白名单、结构、attrs、marks、URL、20层深度、5000节点、150kB JSON、20000字与9张正文图。标题最大80、摘要160、标签5个且每个20字；发布要求标题至少2字、有效社团及非空正文。figure/gallery只接受当前作者当前草稿assetId，封面独立且同样受所有权检查。无任意HTML、iframe、SVG/GIF或远端图片导入。

JPEG/PNG/WebP上传校验宣告MIME与实际解码格式、10MiB、2500万像素、单帧，再重新编码移除EXIF等元数据。媒体目录只能由API访问。本人现存草稿可读取其素材；其他访问必须有某一可读稿件固定快照的真实asset关联。同草稿未引用素材不因其中一篇公开而公开。删草稿只移除草稿访问，已发表快照引用素材保留。附件响应不允许公开缓存。

公开发布创建pending的独立post，审核固定完整快照，不复制旧文章的评论。编辑草稿不更改提交稿；审批通过或退回写一次审核记录。第一版允许团主审核本人稿件。review_note只出现在作者及该团主有权读的DTO；游客不会收到。撤回后仅作者及团主可读，私密scope仍要求相应资格。所有帖子详情、列表、文字搜索、个人稿件、评论、媒体共用ACL，未授权具体资源404，无站点管理员旁路。

限流按直接peer IP及操作类别，敏感账户/邀请码操作10次/分钟，评论30次/分钟，其余变更120次/分钟；资源ID不创建独立桶，桶数量受限。运行单实例/单worker时有效；多个实例需换共享限流存储。代理部署必须准确配置可信代理，不能信任任意客户端X-Forwarded-For。默认uvicorn只信任本地proxy，请由部署根据真实Nginx网络指定信任范围。

## 测试与已验证范围

`python -m pytest -q` 当前20项通过，涵盖真实HTTP、持久化、SQLite双线程一码两人、会话轮换/CSRF/单次验证、绑定邮箱、邀请配额、撤权与离团撤码、成员不消费码、旧码不重新入团、草稿409、重复发布幂等、固定审核快照、越权帖子/列表/评论/媒体、独占媒体撤回、跨作者/跨稿素材、未知JSON/危险URL/正文长度与深度、错误MIME/像素限制/EXIF去除、审核撤回并发、review_note及成员邮箱不泄漏、离团继续保存和资源ID限流绕过、草稿转团后旧版本幂等重试重新校验原帖ACL、真实Tiptap可空link标题及跨hardBreak格式标记兼容性。

默认每例独立tmp SQLite。显式 `TEST_DATABASE_URL=postgresql+psycopg://.../jianwai_test` 时每例开始在这个专用测试库重建业务表；只接受库名jianwai_test，拒绝其他外部库，测试结束释放连接。不使用应用默认DB。PostgreSQL服务器在当前环境不可用，PostgreSQL兼容SQL和锁策略已实现，实际PostgreSQL测试由CI执行，不声称本地已验证。

已实际运行SQLite Alembic upgrade→downgrade→upgrade及alembic check，迁移和模型无差异。`docs/openapi.json` 由当前FastAPI生成。HTTP真实浏览器闭环、Docker与PostgreSQL部署验证由交付阶段另记。

边界：云对象存储/全站上传配额/孤立媒体清理、分布式限流、邮件重试队列、重置密码、跨设备session管理、所有权转移、举报后台、备份恢复演练尚未实现。正文搜索先SQL ACL后在授权结果中做文字匹配，列表计数/分页正确，但大规模社区需改数据库全文索引并按SQL分页优化。
