# =====================================================================
# AI智能体安全网关 - 多阶段构建镜像
#   阶段一：构建 Vue 前端
#   阶段二：Python 后端 + 内置已构建前端（单镜像部署）
# =====================================================================

# ---- 阶段一：前端构建 ----
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- 阶段二：后端运行时 ----
FROM python:3.11-slim AS runtime
WORKDIR /app

# 系统依赖（psycopg2 运行时需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝后端代码
COPY backend/ ./

# 拷贝前端构建产物，供后端托管为静态站点
COPY --from=frontend-build /build/dist ./static

# 服务端口（与 .env 中 GATEWAY_PORT 对应）
EXPOSE 8000

# 通过 shell 形式启动以便读取环境变量中的主机与端口
CMD ["sh", "-c", "uvicorn app.main:app --host ${GATEWAY_HOST:-0.0.0.0} --port ${GATEWAY_PORT:-8000}"]
