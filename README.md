# 报告初稿自动组装 · Demo

针对 CRO 生物分析报告初稿组装场景的**模块化单体** demo，实现四层架构：

```
源数据治理 → 确定性计算 → 受控生成 → 合规锚定
```

> 核心原则：**初稿组装的本质是"结构化数据的确定性填充"，而不是"让 AI 写报告"。**

## 四层架构

| 层 | 目录 | 职责 | 关键决策 |
|---|---|---|---|
| 源数据治理 | `app/governance/` | 接入 → 校验 → 锁定 | 校验在治理层完成，报告层不再校验 |
| 知识与检索 | `app/retrieval/` | 已批准文本候选召回 | 是"检索 + 选择"，不是"生成" |
| 生成与编排 | `app/generation/` | 确定性计算 + 受控叙述 | 数值不经过 LLM；LLM 只组装润色 |
| 合规锚定 | `app/compliance/` | 哈希链审计 + 状态机 + 审核 | 人工"在环"是硬约束，不可绕过 |

## 运行

依赖 Pydantic v2（企业级强类型契约），先安装：

```bash
pip install -r requirements.txt
```

然后运行：

```bash
python demo_run.py
```

脚本会端到端演示：数据治理锁定 → PK/质控确定性计算 → 候选检索 → mock LLM
受控叙述生成 → 文档组装 → 状态机拦截"AI 直接批准" → 人工审核 → 审计链
完整性校验 + 篡改检测。生成的初稿写入 `data/draft_report.md`。

### 切换到真实 LLM（可选）

设置环境变量指向私有化部署的 OpenAI 兼容接口（内网合规，数据不出域）：

```bash
export LLM_PROVIDER=openai_compatible
export LLM_BASE_URL=http://your-internal-endpoint
export LLM_API_KEY=...
export LLM_MODEL_ID=qwen2.5-14b-instruct
python demo_run.py
```

### Web 审核工作台（生产版：PostgreSQL 持久化 + 登录鉴权）

用 Docker 一键起（含数据库）：

```bash
docker compose up --build
```

浏览器打开 http://localhost:8000（默认密码 `demo`），点「生成演示报告」即可走完完整流程：
提交研究 → 治理锁定 → 确定性计算 → 检索 + 受控生成 → 组装初稿 → 认领审核 →
逐段接受/修改/拒绝 → QA 批准 → 查看/验证审计链。数据全部持久化到 PostgreSQL，
重启不丢。

本地不带 Docker 跑（需先起 PostgreSQL）：

```bash
export DATABASE_URL=postgresql+psycopg://report:report@localhost:5432/report_assembly
uvicorn app.api.app:app --reload
```

公网部署（域名 + HTTPS）见 [DEPLOY.md](DEPLOY.md)。

## 测试

```bash
python -m unittest discover -s tests -t .
```

覆盖：PK 参数计算（纯函数）、审计链完整性/篡改检测、状态机不可绕过 + 批准权限。

## Docker

Web 审核工作台需要 PostgreSQL，Docker 一键起（含数据库）：

```bash
docker compose up --build                          # 起 app + PostgreSQL，打开 http://localhost:8000
docker compose run --rm app python demo_run.py     # 跑命令行 demo（无需数据库）
```

- `app`：Web 审核工作台（FastAPI + 单页前端，默认命令）
- `db`：`pgvector/pgvector:pg17` —— 业务库 + 审计链 + 向量检索同库
- `redis`（`--profile prod`）：为异步任务队列（Celery）预留
- 公网部署（域名 + HTTPS + Caddy）见 [DEPLOY.md](DEPLOY.md)

## 目录结构

```
report_assembly/
├── demo_run.py                  # 端到端 demo（入口）
├── app/
│   ├── config.py                # 配置（模型端点、合规参数）
│   ├── governance/              # 第一层：源数据治理
│   │   ├── adapters.py          #   LIMS/Excel 接入适配器
│   │   ├── validators.py        #   校验规则
│   │   ├── contracts.py         #   强类型数据契约
│   │   └── service.py           #   治理服务入口
│   ├── retrieval/               # 第二层：知识与检索
│   │   ├── corpus.py            #   已批准文本语料库
│   │   ├── embed.py             #   文本向量化（词频 + 余弦）
│   │   └── hybrid_search.py     #   混合检索（向量 + 关键词 + 元数据）
│   ├── generation/              # 第三层：生成与编排
│   │   ├── deterministic/       #   确定性计算（纯函数，零 LLM）
│   │   │   ├── pk_calculator.py #     PK 参数
│   │   │   ├── qc_stats.py      #     质控统计
│   │   │   └── table_builder.py #     表格构建
│   │   ├── narrative/           #   叙述生成
│   │   │   ├── llm.py           #     LLM 客户端（mock / OpenAI 兼容）
│   │   │   ├── prompt_builder.py#     受控 prompt 组装
│   │   │   └── orchestrator.py  #     章节级编排
│   │   ├── assembler.py         #   文档组装
│   │   └── state_machine.py     #   报告状态机
│   ├── compliance/              # 第四层：合规锚定
│   │   ├── audit_chain.py       #   哈希链审计追踪
│   │   ├── rbac.py              #   角色权限
│   │   └── review_workflow.py   #   审核工作流
│   └── api/                     # Web 审核工作台（FastAPI + 单页前端）
├── data/
│   ├── sample_concentrations.csv# 样例浓度数据（模拟 LIMS 导出）
│   └── draft_report.md          # 生成的初稿（运行后产生）
└── tests/
```

## 生产化替换点

数据契约已使用 Pydantic v2；其余 demo 用轻量实现以做到开箱即用，生产环境替换点已用注释标注：

- **配置加载**：`BaseModel.from_env` → `pydantic-settings` 的 `BaseSettings`（绑定 `.env` / 环境变量）
- **向量检索**：词频向量 → embedding 模型 + `pgvector`（业务库 + 审计链同库）
- **LLM**：`MockLLMClient` → 私有化 7B~14B 指令微调模型（OpenAI 兼容接口）
- **表格渲染**：markdown → Jinja2 模板渲染 TFLs
- **审计链存储**：内存 → PostgreSQL（append-only 表）
- **任务队列**：同步 → Celery（报告生成长任务异步化）
