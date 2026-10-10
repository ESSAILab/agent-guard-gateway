#!/usr/bin/env bash
# =====================================================================
# Docker 一键部署脚本：构建镜像并启动容器（PostgreSQL + 护栏网关）
# =====================================================================
set -e

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "⚠️  根目录 .env 不存在，从 .env.example 复制..."
  cp .env.example .env
  echo "请检查 .env 配置（数据库密码、SECRET_KEY 等），然后重新运行本脚本。"
  exit 1
fi

echo "===== AI智能体安全网关 - Docker 部署 ====="
echo "1/2 构建 Docker 镜像（包含前端 + 后端）..."
docker build -t ai-guardrail:latest .

echo "2/2 启动服务（Docker Compose）..."
docker compose up -d

echo ""
echo "✅ 部署完成！"
echo "   - 护栏网关：http://localhost:8000"
echo "   - API 文档：http://localhost:8000/docs"
echo "   - 数据大屏：http://localhost:8000/#/dashboard"
echo ""
echo "管理命令："
echo "   查看日志：docker compose logs -f gateway"
echo "   停止服务：docker compose down"
echo "   重启服务：docker compose restart gateway"
