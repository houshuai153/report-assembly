# 报告初稿自动组装 —— 容器化
# 基础镜像用 3.12（稳定）；代码要求 Python >= 3.10（使用了 `X | None` 语法）

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 先装依赖（利用 Docker 层缓存，源码改动不重装依赖）
# 国内服务器用阿里云 PyPI 镜像加速；境外部署可去掉 -i 参数
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

# 拷贝源码与数据
COPY app ./app
COPY data ./data
COPY tests ./tests
COPY demo_run.py .

# 默认跑 Web 审核工作台（PostgreSQL 持久化 + 鉴权）；
# 跑命令行 demo 时覆盖 command：
#   docker compose run --rm app python demo_run.py
CMD ["python", "-m", "uvicorn", "app.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
