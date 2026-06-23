# -*- coding: utf-8 -*-
"""
事件总线 - 连接 Codex 和 n8n
"""

import logging
from typing import Dict, Any, Callable, List
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class EventBus:
    """事件总线"""
    
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.event_history = []
        
        logger.info("✓ Event Bus 初始化成功")
    
    def subscribe(self, event_type: str, callback: Callable):
        """订阅事件"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        
        self.subscribers[event_type].append(callback)
        logger.info(f"✓ 订阅事件: {event_type}")
    
    async def publish(self, event_type: str, data: Dict[str, Any]):
        """发布事件"""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        # 记录事件
        self.event_history.append(event)
        
        # 调用所有订阅者
        if event_type in self.subscribers:
            tasks = [
                callback(event)
                for callback in self.subscribers[event_type]
            ]
            await asyncio.gather(*tasks)
            
            logger.info(f"✓ 事件已发布: {event_type}")


class EventTypes:
    """事件类型定义"""
    
    # Codex 事件
    QUERY_STARTED = "codex.query.started"
    QUERY_COMPLETED = "codex.query.completed"
    QUERY_FAILED = "codex.query.failed"
    INSIGHT_GENERATED = "codex.insight.generated"
    
    # n8n 事件
    WORKFLOW_TRIGGERED = "n8n.workflow.triggered"
    WORKFLOW_COMPLETED = "n8n.workflow.completed"
    WORKFLOW_FAILED = "n8n.workflow.failed"
    
    # 系统事件
    ALERT_CREATED = "system.alert.created"
    REPORT_GENERATED = "system.report.generated"


async def setup_event_handlers(event_bus: EventBus, n8n_connector):
    """
    设置事件处理器
    
    连接 Codex 和 n8n 事件
    """
    
    # 当 Codex 完成查询时，触发 n8n 工作流
    async def on_query_completed(event):
        logger.info("📡 Codex 查询完成，触发 n8n 工作流...")
        
        result = n8n_connector.trigger_workflow(
            workflow_id="workflow_acquisition",
            input_data=event["data"],
            org_id=event["data"].get("org_id")
        )
        
        if result["status"] == "success":
            await event_bus.publish(
                EventTypes.WORKFLOW_TRIGGERED,
                {
                    "workflow_id": "workflow_acquisition",
                    "execution_id": result["workflow_execution_id"]
                }
            )
    
    # 当 n8n 工作流完成时，更新 Codex
    async def on_workflow_completed(event):
        logger.info("📡 n8n 工作流完成，更新 Codex...")
        
        # 更新洞察数据库
        # 发送通知
        pass
    
    # 订阅事件
    event_bus.subscribe(EventTypes.QUERY_COMPLETED, on_query_completed)
    event_bus.subscribe(EventTypes.WORKFLOW_COMPLETED, on_workflow_completed)
    
    logger.info("✓ 事件处理器已设置")
