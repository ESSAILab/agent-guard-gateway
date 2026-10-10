#!/usr/bin/env bash
# =====================================================================
# 一键构建脚本：编译前端，安装后端依赖
# =====================================================================
set -e

echo "===== AI智能体安全网关 - 一键构建 ====="
cd "$(dirname "$0")/.."

# 前端构建
echo "1/2 构建前端（Vue3 + Vite）..."
cd frontend
if [ ! -d node_modules ]; then
  npm install
fi
npm run build
echo "✓ 前端构建完成 -> frontend/dist/"

# 后端依赖
echo "2/2 安装后端依赖（Python）..."
cd ../backend
pip3 install -r requirements.txt --quiet
echo "✓ 后端依赖已安装"

echo ""
echo "✅ 构建完成！接下来："
echo "   - 本地启动：bash scripts/start.sh"
echo "   - Docker 部署：bash scripts/deploy-docker.sh"
