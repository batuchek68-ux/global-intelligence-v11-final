# -*- coding: utf-8 -*-
"""
v11 计费模型 - 融资级商业系统
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class PlanType(Enum):
    """套餐类型"""
    STARTER = "starter"        # $49/月
    GROWTH = "growth"          # $199/月
    ENTERPRISE = "enterprise"  # $999/月


class BillingModel:
    """计费模型"""
    
    PLANS = {
        PlanType.STARTER: {
            "price": 49,
            "currency": "USD",
            "monthly_queries": 1000,
            "api_requests_limit": 10000,
            "users": 3,
            "support": "email"
        },
        PlanType.GROWTH: {
            "price": 199,
            "currency": "USD",
            "monthly_queries": 10000,
            "api_requests_limit": 100000,
            "users": 20,
            "support": "priority"
        },
        PlanType.ENTERPRISE: {
            "price": 999,
            "currency": "USD",
            "monthly_queries": "unlimited",
            "api_requests_limit": "unlimited",
            "users": "unlimited",
            "support": "dedicated"
        }
    }
    
    # API 使用计费
    API_PRICING = {
        "query": 0.002,           # 每个查询 $0.002
        "insight": 0.02,          # 每个洞察 $0.02
        "alert_stream": 0.1,      # 每个警报流 $0.1/月
        "custom_agent": 0.05      # 自定义Agent $0.05/执行
    }
    
    @staticmethod
    def calculate_monthly_bill(
        org_id: str,
        plan: PlanType,
        overage_charges: float = 0
    ) -> dict:
        """计算月度账单"""
        
        plan_details = BillingModel.PLANS[plan]
        
        return {
            "org_id": org_id,
            "plan": plan.value,
            "base_fee": plan_details["price"],
            "overage_charges": overage_charges,
            "total": plan_details["price"] + overage_charges,
            "currency": "USD"
        }


@dataclass
class UsageRecord:
    """使用记录"""
    org_id: str
    user_id: str
    action_type: str  # "query", "insight", "alert_stream"
    unit_price: float
    quantity: int
    timestamp: str
    
    @property
    def total_cost(self) -> float:
        return self.unit_price * self.quantity
