#!/usr/bin/env bash
# =====================================================================
# 本地开发启动脚本：同时启动后端与前端开发服务器
# 后端：uvicorn，默认 8000 端口
# 前端：vite，默认 5173 端口，代理 API 到后端
# =====================================================================
set -e

cd "$(dirname "$0")/.."

# 检查环境变量
if [ ! -f backend/.env ]; then
  echo "⚠️  backend/.env 不存在，从 .env.example 复制..."
  cp backend/.env.example backend/.env
fi
if [ ! -f frontend/.env ]; then
  echo "⚠️  frontend/.env 不存在，从 .env.example 复制..."
  cp frontend/.env.example frontend/.env
fi

echo "===== AI智能体安全网关 - 本地启动 ====="
echo "后端 API：http://127.0.0.1:8000"
echo "API 文档：http://127.0.0.1:8000/docs"
echo "前端界面：http://127.0.0.1:5173"
echo "按 Ctrl+C 停止服务"
echo ""

# 并行启动后端与前端
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd frontend && npm run dev &
FRONTEND_PID=$!

cleanup() {
  echo ""
  echo "正在停止服务..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
  wait $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
  exit 0
}

trap cleanup INT TERM EXIT
wait
