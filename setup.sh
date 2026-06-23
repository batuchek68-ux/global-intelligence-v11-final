#!/bin/bash

echo "🚀 启动 Codex AI v11 + n8n 完整栈"
echo "=================================="

# 1. 创建环境变量文件
echo "1️⃣  创建环境变量..."
cat > .env << EOF
# API 配置
SECRET_KEY=your-secret-key-$(openssl rand -hex 16)

# n8n 配置
N8N_USER=admin
N8N_PASSWORD=$(openssl rand -base64 32)
N8N_API_KEY=$(openssl rand -hex 32)
N8N_DB_PASSWORD=$(openssl rand -base64 32)

# Weaviate 配置
WEAVIATE_API_KEY=$(openssl rand -hex 32)

# 数据库配置
POSTGRES_USER=codex
POSTGRES_PASSWORD=$(openssl rand -base64 32)
EOF

echo "✓ 环境变量已创建"

# 2. 创建数据库初始化脚本
echo "2️⃣  创建数据库初始化脚本..."
cat > init-db.sql << 'EOF'
-- 创建 Codex 数据库
CREATE DATABASE codex_v11;
CREATE DATABASE n8n;

-- 创建用户
CREATE USER codex WITH PASSWORD 'codex';
CREATE USER n8n WITH PASSWORD 'n8n';

-- 授予权限
GRANT ALL PRIVILEGES ON DATABASE codex_v11 TO codex;
GRANT ALL PRIVILEGES ON DATABASE n8n TO n8n;

-- 连接到 codex_v11 数据库
\c codex_v11;

-- 创建表
CREATE TABLE IF NOT EXISTS organizations (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS insights (
    id SERIAL PRIMARY KEY,
    org_id VARCHAR(255) REFERENCES organizations(id),
    execution_id VARCHAR(255) UNIQUE,
    query TEXT,
    result JSONB,
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_executions (
    id VARCHAR(255) PRIMARY KEY,
    org_id VARCHAR(255) REFERENCES organizations(id),
    workflow_id VARCHAR(255),
    status VARCHAR(50),
    result JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_insights_org_id ON insights(org_id);
CREATE INDEX idx_insights_created_at ON insights(created_at);
CREATE INDEX idx_executions_org_id ON workflow_executions(org_id);
EOF

echo "✓ 数据库初始化脚本已创建"

# 3. 启动 Docker 容器
echo "3️⃣  启动 Docker 容器..."
docker-compose -f docker-compose-full.yml up -d

# 4. 等待服务启动
echo "4️⃣  等待服务启动..."
sleep 15

# 5. 检查服务健康状态
echo "5️⃣  检查服务健康状态..."
echo ""
echo "🔍 检查 Codex API..."
curl -s http://localhost:8000/v1/health | jq . || echo "⚠️  Codex API 未就绪"

echo ""
echo "🔍 检查 n8n..."
curl -s http://localhost:5678/api/v1/health | jq . || echo "⚠️  n8n 未就绪"

# 6. 显示凭证
echo ""
echo "=================================="
echo "✓ 启动完成！"
echo "=================================="
echo ""
echo "📱 服务地址："
echo "  • Codex AI API: http://localhost:8000"
echo "  • API 文档: http://localhost:8000/docs"
echo "  • n8n: http://localhost:5678"
echo ""
echo "🔐 n8n 凭证："
echo "  • 用户名: $(grep 'N8N_USER' .env | cut -d= -f2)"
echo "  • 密码: $(grep 'N8N_PASSWORD' .env | cut -d= -f2)"
echo ""
echo "💾 数据库："
echo "  • PostgreSQL: localhost:5432"
echo "  • 用户名: codex"
echo ""
echo "🚀 现在您可以："
echo "  1. 访问 http://localhost:8000/docs 测试 Codex API"
echo "  2. 访问 http://localhost:5678 配置 n8n 工作流"
echo "  3. 运行: python -m pytest tests/ (测试)"
echo ""
