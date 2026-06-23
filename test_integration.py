# -*- coding: utf-8 -*-
"""
集成测试 - 测试 Codex 和 n8n 的连接
"""

import requests
import json
import time

# 配置
CODEX_URL = "http://localhost:8000"
N8N_URL = "http://localhost:5678"

def test_codex_health():
    """测试 Codex 健康状态"""
    print("🔍 测试 Codex 健康状态...")
    
    response = requests.get(f"{CODEX_URL}/v1/health")
    print(f"  状态码: {response.status_code}")
    print(f"  响应: {response.json()}")
    
    assert response.status_code == 200
    print("✓ Codex 健康检查通过\n")


def test_codex_query():
    """测试 Codex 查询"""
    print("🔍 测试 Codex 查询...")
    
    payload = {
        "org_id": "org_test_001",
        "user_id": "user_001",
        "query": "找出科技行业增长最快的公司"
    }
    
    response = requests.post(
        f"{CODEX_URL}/v1/query",
        json=payload
    )
    
    print(f"  状态码: {response.status_code}")
    result = response.json()
    print(f"  执行ID: {result.get('execution_id')}")
    print(f"  状态: {result.get('status')}")
    
    assert response.status_code == 200
    assert result['status'] == 'success'
    print("✓ Codex 查询测试通过\n")


def test_n8n_workflows():
    """测试 n8n 工作流列表"""
    print("🔍 测试 n8n 工作流...")
    
    response = requests.get(
        f"{N8N_URL}/api/v1/workflows",
        auth=("admin", "your-password")
    )
    
    print(f"  状态码: {response.status_code}")
    
    if response.status_code == 200:
        workflows = response.json()
        print(f"  工作流数: {len(workflows)}")
        print("✓ n8n 工作流列表获取成功\n")
    else:
        print("⚠️  n8n 响应: ", response.text)


def test_integration_trigger():
    """测试 Codex 触发 n8n 工作流"""
    print("🔍 测试集成触发...")
    
    payload = {
        "org_id": "org_test_001",
        "user_id": "user_001",
        "data": {
            "query": "找出科技行业增长最快的公司",
            "workflow_id": "acquisition"
        }
    }
    
    response = requests.post(
        f"{CODEX_URL}/api/v1/integrations/n8n/trigger/acquisition",
        json=payload
    )
    
    print(f"  状态码: {response.status_code}")
    print(f"  响应: {response.json()}")
    
    assert response.status_code == 200
    print("✓ 集成触发测试通过\n")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("🚀 Codex AI v11 + n8n 集成测试")
    print("=" * 60)
    print()
    
    try:
        test_codex_health()
        test_codex_query()
        test_n8n_workflows()
        test_integration_trigger()
        
        print("=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
    
    except Exception as e:
        print(f"✗ 测试失败: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
