# 公网部署指南（HTTPS）

目标：让任何人通过 `https://你的域名` 访问 Web 审核工作台。

## 前置条件

1. 一台云服务器（Ubuntu 22.04 即可，2C4G 起步），有公网 IP
2. 一个域名，并把一条 A 记录解析到服务器公网 IP（如 `report.example.com -> 1.2.3.4`）
3. 服务器安全组/防火墙：**只放行 80、443**（22 留给自己 SSH；5432 不要开公网）

## 步骤

### 1. 在服务器上装 Docker + Compose

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # 重新登录后生效
```

### 2. 上传代码

把整个 `report_assembly/` 目录传到服务器（git clone 或 scp）。

### 3. 配置环境变量

```bash
cd report_assembly
cp .env.example .env
# 编辑 .env：填 DOMAIN、改 APP_PASSWORD、把 APP_SECRET 换成强随机值
openssl rand -hex 32   # 生成 APP_SECRET
```

### 4. 启动

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

首次启动 Caddy 会自动向 Let's Encrypt 申请并续期 HTTPS 证书（要求域名已解析到本机）。

### 5. 验证

浏览器打开 `https://你的域名`，用 `.env` 里的 `APP_PASSWORD` 登录。

## 生产安全清单（务必逐项确认）

- [ ] `APP_PASSWORD` 已改成强密码，`APP_SECRET` 已改成强随机值
- [ ] 域名 A 记录已解析，HTTPS 证书正常（浏览器无警告）
- [ ] 防火墙只开 80/443；PostgreSQL（5432）未暴露公网
- [ ] `.env` 未提交到 git（加入 `.gitignore`）
- [ ] LLM 已切换到私有化 `openai_compatible`（数据不出域）

## 当前已知限制（诚实的说明）

- **鉴权**是单密码 + HMAC cookie，生产多用户应替换为企业身份源（LDAP/SSO）
- **LLM** 仍是 mock，接真实私有化模型后需配合异步任务队列（Celery）避免请求阻塞
- **报告生成**目前是同步执行；并发上来后应改为「提交任务 → 后台生成 → 查询结果」
- **数据脱敏**尚未实现（见正文架构讨论）

## 常用运维命令

```bash
docker compose -f docker-compose.prod.yml logs -f app     # 看 app 日志
docker compose -f docker-compose.prod.yml restart app      # 重启
docker compose -f docker-compose.prod.yml down             # 停止（保留数据卷）
docker compose -f docker-compose.prod.yml down -v          # 停止并删除数据
```
