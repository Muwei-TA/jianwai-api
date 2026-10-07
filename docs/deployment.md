# 部署与运行

## 两个目录

将 `jianwai-web/` 和 `jianwai-api/` 放在同一父目录。两个仓库各自维护代码，API 仓库的 compose 统一编排。不要把 `.env`、数据库或上传文件加入 Git。

## 本地开发

API 的 Python 虚拟环境安装锁定依赖，复制 `.env.example` 为 `.env` 后执行 `alembic upgrade head`，运行 `uvicorn app.main:app --reload --port 8000 --no-access-log`。前端 `npm ci` 后 `npm run dev`；浏览器只访问 `http://localhost:5173`，API 和图片由 Vite 同源代理。

创建首位运营者需显式运行 `python -m app.cli bootstrap --email 你的运营邮箱 --display-name 团主昵称 --club-slug film --club-name 影像社`，根据提示输入密码。该操作标记运营邮箱为已验证，操作者应确认邮箱归属；没有公开初始化接口。

开发邮件放在 `var/outbox`，只在本机查看，不提供公开读取接口；真实环境配置 Resend。发出的验证 URL 为一次性凭证，勿复制到聊天或提交仓库。

## 容器运行

在 API 根目录准备私有 `.env.compose`：APP_ENV=production、POSTGRES_PASSWORD（使用随机URL安全字符）、PUBLIC_WEB_URL=https://你的域名、ALLOWED_ORIGINS=https://你的域名、COOKIE_SECURE=true。发信配置 `RESEND_API_KEY` 和已验证域名下的 `RESEND_FROM`（例如 `heijz@muwei.xyz`）；密钥只写入私有环境文件，不提交 Git。`docker compose --env-file .env.compose up --build -d` 先等待 PostgreSQL 健康，单独迁移服务执行成功后启动 API 和 Web。数据库、媒体、outbox 使用命名卷。

默认 Web 只绑定 `127.0.0.1:8080`，由你控制的 HTTPS 入口反向代理至该端口；不直接把开发服务或 PostgreSQL 暴露公网。若香港 VPS 连接 NAS，可以经已有安全隧道转发到 Web，前提是隧道与入口配置由你实际验证。这里不自动部署到任何服务器。

`docker compose --env-file .env.compose run --rm api python -m app.cli bootstrap ...` 创建运营者。启动时不会自动创建公共默认用户。

NGINX 覆盖 X-Forwarded-For；Uvicorn 信任容器内代理，API 没有宿主机映射端口。若存在多层反向代理，须按受控代理网段配置真实 IP，否则所有访问可能按同一代理 IP 限流，不要直接信任互联网传入的 X-Forwarded-For。

## 发布前运维

数据库和媒体卷需要同时备份；升级前数据库快照、迁移、回归检查，再切换流量。首版没有自动定时备份和经过验证的恢复演练。恢复应先在隔离目录验证数据与媒体引用，再接入流量。不要用回滚镜像替代数据库回滚计划。

CI 配置会启动 PostgreSQL 17 并运行测试和迁移；配置存在不代表远端已经运行，实际结果见 docs/verification.md。当前只有单个 API 实例，限流与邮件服务的边界以实现说明为准。
