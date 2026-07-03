# 国际贸易工程云平台 — 全局架构白皮书 v12

**版本：v12.0.0**
**仓库：batuchek68-ux/global-intelligence-v11-final**
**日期：2026-07-03**
**状态：强化重设计版**

---

## 目录

1. [系统定位与愿景](#一系统定位与愿景)
2. [五层全域架构](#二五层全域架构)
3. [智能编排引擎（强化）](#三智能编排引擎强化)
4. [业务能力矩阵（16个服务模块）](#四业务能力矩阵)
5. [新增核心模块详解](#五新增核心模块详解)
6. [数据架构与存储](#六数据架构与存储)
7. [安全与合规体系](#七安全与合规体系)
8. [通信与集成层](#八通信与集成层)
9. [前端应用矩阵](#九前端应用矩阵)
10. [API 接口全景（50+ 端点）](#十api-接口全景)
11. [全球市场定位与商业模式](#十一全球市场定位与商业模式)
12. [部署架构](#十二部署架构)
13. [架构决策记录 (ADR)](#十三架构决策记录)
14. [演进路线图](#十四演进路线图)
15. [附录](#十五附录)

---

## 一、系统定位与愿景

### 1.1 平台定位

**Global Intelligence v12（国际贸易工程云操作系统）** 是面向跨境 B2B 工程贸易的 **全链路智能运营平台**。

从 v11 的"智能决策平台"升级，v12 覆盖 **商机发现 → 智能撮合 → 交易执行 → 交付管理 → 金融服务 → 持续优化** 六大环节，形成完整的商业闭环。

### 1.2 核心设计原则

| 原则 | v11 | v12 强化 |
|------|-----|---------|
| 智能体驱动 | Planner→Executor→Judge→Decision | + Learning（持续学习闭环） |
| 事件驱动 | 服务间异步解耦 | + Kafka 升级、消息队列持久化 |
| 安全边界 | 高风险人工审批门控 | + 分级审批、审计不可篡改 |
| 多租户隔离 | 企业级数据隔离 | + 资源配额、用量计量 |
| 可扩展 | 紧耦合模块 | + 插件系统、开放 API |
| 全链路 | 情报→决策 | + 撮合→交易→交付→金融 |

### 1.3 平台指标目标

| 指标 | 目标值 |
|------|--------|
| 系统可用性 | 99.9% |
| API 响应 P99 | < 500ms |
| 撮合准确率 | > 85% |
| 信用评估准确率 | > 80% |
| 同时在线租户 | 500+ |
| 日处理交易 | 10,000+ |

---

## 二、五层全域架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          🖥️  接入层 (Access Layer)                        │
│                                                                         │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌─────────────┐ │
│  │Decision Hub│ │Desktop OS│ │Trade Portal│ │Mobile App│ │API Portal   │ │
│  │ 本地决策台 │ │Windows桌面│ │ 客户门户   │ │ React    │ │开发者门户    │ │
│  │ Electron  │ │ Electron │ │ Web App   │ │ Native   │ │Swagger/Docs  │ │
│  └─────┬────┘ └────┬─────┘ └─────┬─────┘ └────┬─────┘ └──────┬──────┘ │
├────────┼───────────┼─────────────┼─────────────┼───────────┼──────────┤
│        │            统一 API 网关 (Kong)                                 │
│        │    认证(JWT/OAuth2) · 限流 · 路由 · 日志 · WebSocket · 版本管理   │
├────────┼───────────┼─────────────┼─────────────┼───────────┼──────────┤
│        │          🧠 智能编排层 (Orchestration Layer)                     │
│                                                                         │
│  ┌─────┴──────┬─────────┬──────────┬──────────┬────────────────────┐   │
│  │ Planner    │Executor │ Judge    │ Decision │ Learning [新]      │   │
│  │ 任务规划    │并行执行  │ 质量评估  │ 行动决策  │ 持续学习闭环        │   │
│  │ ·意图解析  │·Agent调度│ ·结果校验 │ ·审批门控 │ ·反馈收集          │   │
│  │ ·任务拆解  │·工具调用 │ ·合规审查 │ ·自动执行 │ ·模式提取          │   │
│  │ ·依赖分析  │·并行编排 │ ·置信评分 │ ·人工升级 │ ·知识更新          │   │
│  └─────┬──────┴────┬────┴────┬─────┴─────┬────┴──────────┬─────────┘   │
├────────┼───────────┼─────────┼───────────┼───────────────┼─────────────┤
│        │         🏢 业务能力层 (Business Capability — 16 Services)       │
│                                                                         │
│  ┌─────┴─────────────────────────────────────────────────────────────┐ │
│  │                                                                     │ │
│  │  v11 继承 (8)                    v12 新增 (8)                        │ │
│  │  ┌────────────┬──────────────┐  ┌────────────┬──────────────────┐  │ │
│  │  │ 情报中心    │ 任务控制      │  │ 交易撮合[N]│ 供应链追踪[N]     │  │ │
│  │  │ 行业作战室  │ 知识标杆      │  │ 金融服务[N]│ 知识图谱[N]       │  │ │
│  │  │ 证据核查    │ 授权管理      │  │ BI分析[N]  │ 实时协作[N]       │  │ │
│  │  │ 社交营销    │ 内容引擎      │  │ 持续学习[N]│ 插件管理[N]       │  │ │
│  │  └────────────┴──────────────┘  └────────────┴──────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────┤
│                    🔌 集成与基础设施层 (Infrastructure)                    │
│                                                                         │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌─────────┐ ┌──────────────┐ │
│  │Event Bus │ │n8n       │ │GitHub     │ │Message  │ │Plugin System │ │
│  │Kafka [N] │ │工作流自动化│ │Actions    │ │Queue    │ │插件系统 [N]   │ │
│  │持久化消息 │ │低代码编排 │ │云工作流    │ │RabbitMQ │ │entry_points  │ │
│  └──────────┘ └──────────┘ └───────────┘ └─────────┘ └──────────────┘ │
├─────────────────────────────────────────────────────────────────────────┤
│                    💾 数据与存储层 (Data & Storage)                       │
│                                                                         │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌─────────────┐ │
│  │PostgreSQL│ │Redis     │ │ChromaDB   │ │MinIO     │ │Neo4j [N]    │ │
│  │业务数据   │ │缓存/队列  │ │向量存储    │ │对象存储   │ │知识图谱      │ │
│  │SQLAlchemy│ │速率限制   │ │语义搜索   │ │S3兼容    │ │图推理引擎    │ │
│  └──────────┘ └──────────┘ └───────────┘ └──────────┘ └─────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 三、智能编排引擎（强化）

### 3.1 五阶段决策流程（v12 升级）

```
用户意图 → Planner(任务拆解) → Executor(并行执行) → Judge(结果评估)
                │                                        │
                │              Decision(行动决策) ←────────┘
                │                    │
                └── Learning(持续优化) ←── 反馈收集 ←──┘
```

### 3.2 各阶段详解

| 阶段 | 文件 | 核心能力 |
|------|------|---------|
| **Planner** | `core/planner.py` | NLP 意图解析、领域分类、子任务拆解、依赖图构建 |
| **Executor** | `core/executor.py` | 智能体调度、并行任务执行、工具链调用、结果收集 |
| **Judge** | `core/judge.py` | 质量评分、合规验证、置信度计算、异常检测 |
| **Decision** | `core/decision.py` | 风险分级、人类审批门控、自动/手动决策路由 |
| **Learning** | `core/learning.py` [新] | 执行反馈、模式提取、知识更新、性能趋势 |

### 3.3 安全边界

```
自动化区域 (低风险)              人工审批门控 (高风险)
──────────────────────────     ──────────────────────────
· 情报采集与分析                 · 签署合同
· 供应商匹配推荐                 · 批准付款 (>$10K)
· 报告与简报生成                 · 最终报价定价
· 内容草稿与翻译                 · 承诺交期
· 市场趋势分析                   · 公开发布媒体内容
· 信用初筛评估                   · 发送正式客户承诺
· AI 辅助合同模板                · 大宗交易确认 (>$100K)
```

---

## 四、业务能力矩阵

### 4.1 全量服务模块（16个）

| # | 模块 | 类型 | 文件 | 状态 |
|---|------|------|------|------|
| 1 | 情报中心 | v11 | `services/intelligence_center_service.py` | ✅ |
| 2 | 任务控制 | v11 | `services/mission_control_service.py` | ✅ |
| 3 | 行业作战室 | v11 | `services/industry_war_room_service.py` | ✅ |
| 4 | 知识标杆 | v11 | `services/knowledge_benchmark_service.py` | ✅ |
| 5 | 证据核查 | v11 | `services/evidence_verification_service.py` | ✅ |
| 6 | 授权管理 | v11 | `services/license_service.py` | ✅ |
| 7 | 社交营销 | v11 | `services/social_communication_service.py` | ✅ |
| 8 | 内容引擎 | v11 | `content/video_script.py` | ✅ |
| 9 | **交易撮合** | **v12 新** | `services/matching_engine_service.py` | 🆕 |
| 10 | **供应链追踪** | **v12 新** | `services/supply_chain_service.py` | 🆕 |
| 11 | **金融服务** | **v12 新** | `services/financial_service.py` | 🆕 |
| 12 | **知识图谱** | **v12 新** | `services/knowledge_graph_service.py` | 🆕 |
| 13 | **BI 分析** | **v12 新** | `services/bi_analytics_service.py` | 🆕 |
| 14 | **实时协作** | **v12 新** | `services/realtime_collab_service.py` | 🆕 |
| 15 | **持续学习** | **v12 新** | `core/learning.py` | 🆕 |
| 16 | **插件管理** | **v12 新** | `core/plugin_manager.py` | 🆕 |

---

## 五、新增核心模块详解

### 5.1 交易撮合引擎 (Matching Engine)

**职责**：智能匹配买家需求与供应商能力，辅助报价与合同生成。

```
┌─────────────────────────────────────────────────────────┐
│                 交易撮合引擎 (Matching Engine)             │
├──────────────┬──────────────┬──────────────┬────────────┤
│ 需求解析      │ 供应商匹配    │ 报价建议      │ 合同生成    │
│ ·NLP意图提取  │ ·五维评分模型 │ ·历史价格参考 │ ·模板管理   │
│ ·需求结构化   │ ·智能排序    │ ·市场行情比对  │ ·条款推荐   │
│ ·HS编码匹配   │ ·相似度计算  │ ·利润测算     │ ·风险标注   │
├──────────────┴──────────────┴──────────────┴────────────┤
│ 五维评分模型：价格(25%) + 质量(25%) + 认证(20%)           │
│              + 产能(15%) + 物流(15%)                     │
├─────────────────────────────────────────────────────────┤
│ API: /v1/matching/search · /v1/matching/quotes/generate  │
│      /v1/matching/quotes/compare · /v1/matching/contracts│
└─────────────────────────────────────────────────────────┘
```

**关键算法**：
- 五维加权综合评分：`score = Σ(维度得分 × 权重)`
- 维度得分：列表匹配用 Jaccard 相似度，数值匹配用 min/max ratio
- 排序：按 composite score 降序，top-K 返回

### 5.2 供应链追踪 (Supply Chain Tracker)

**职责**：端到端物流可视化、质量检验管理、交付里程碑跟踪、智能预警。

```
┌─────────────────────────────────────────────────────────┐
│              供应链追踪 (Supply Chain Tracker)             │
├──────────────┬──────────────┬──────────────┬────────────┤
│ 物流追踪      │ 质量检验      │ 交付里程碑    │ 智能预警    │
│ ·多承运商API  │ ·AQL 标准管理 │ ·甘特图可视化 │ ·延迟检测   │
│ ·实时位置更新 │ ·检验报告生成 │ ·进度百分比   │ ·风险评分   │
│ ·轨迹回放     │ ·合规审核     │ ·自动通知     │ ·预案推荐   │
├──────────────┴──────────────┴──────────────┴────────────┤
│ API: /v1/supply-chain/shipments · /v1/supply-chain/     │
│      quality/inspections · /v1/supply-chain/milestones   │
│      /v1/supply-chain/contracts/{id}/progress            │
│      /v1/supply-chain/contracts/{id}/alerts              │
└─────────────────────────────────────────────────────────┘
```

**预警机制**：
- 超过 ETA → CRITICAL：通知运营商和买家
- 里程碑逾期 → WARNING：检查依赖项和资源
- 质量不合格 → CRITICAL：触发重检流程

### 5.3 金融服务 (Financial Services)

**职责**：跨境支付路由、汇率风险管理、信用评估、贸易融资推荐。

```
┌─────────────────────────────────────────────────────────┐
│               金融服务 (Financial Services)               │
├──────────────┬──────────────┬──────────────┬────────────┤
│ 跨境支付      │ 汇率管理      │ 信用评估      │ 融资建议    │
│ ·多币种路由   │ ·实时汇率     │ ·多维评分模型 │ ·保理方案   │
│ ·费率比对     │ ·远期锁汇建议 │ ·交易历史分析 │ ·信用证    │
│ ·合规检查     │ ·风险敞口计算 │ ·行业评级     │ ·供应链金融 │
├──────────────┴──────────────┴──────────────┴────────────┤
│ API: /v1/finance/payment/routes                          │
│      /v1/finance/payment/create                          │
│      /v1/finance/fx/{base}/{quote}                       │
│      /v1/finance/fx/hedge                                │
│      /v1/finance/credit/assess                           │
│      /v1/finance/financing/recommend                     │
└─────────────────────────────────────────────────────────┘
```

**信用评分模型**：
- 交易量得分（30%）：按 $1M 归一化
- 准时交付率（25%）：历史交付准时比例
- 争议记录（15%）：每争议扣 5 分
- 经营年限（15%）：每年 +3 分
- 财务健康（15%）：基于财务报表指标

### 5.4 知识图谱 (Knowledge Graph)

**职责**：实体关系网络构建、图推理、替代供应商发现、风险传播分析。

```
┌─────────────────────────────────────────────────────────┐
│              知识图谱 (Knowledge Graph)                    │
├─────────────────────────────────────────────────────────┤
│ 节点类型 (9种):                                            │
│ Company · Product · Industry · Country · Port            │
│ Certification · Project · Person · Event                 │
│                                                         │
│ 关系类型 (10种):                                           │
│ SUPPLIES · PURCHASES · COMPETES_WITH · PARTNERS_WITH     │
│ LOCATED_IN · CERTIFIED_BY · OWNS · REGULATES             │
│ AFFECTS · PARTICIPATES_IN                               │
├─────────────────────────────────────────────────────────┤
│ 推理场景:                                                 │
│ · 替代供应商发现 → (A)-[SUPPLIES]→(X)←[SUPPLIES]-(B)     │
│ · 供应链风险传导 → (灾害)→[AFFECTS]→(港口)←[途经]-(订单)     │
│ · 市场机会发现 → (政策)→[利好]→(行业)←[属于]-(产品)         │
├─────────────────────────────────────────────────────────┤
│ 存储: Neo4j + 文件级 Fallback                             │
│ API: /v1/kg/entities · /v1/kg/relations                  │
│      /v1/kg/suppliers/alternatives                       │
│      /v1/kg/risk/trace · /v1/kg/opportunities            │
└─────────────────────────────────────────────────────────┘
```

### 5.5 BI 分析大屏 (BI Analytics)

**职责**：实时经营仪表盘，多维度数据可视化。

```
API: /v1/bi/dashboard · /v1/bi/dashboard/* (细分端点)
     /v1/bi/reports/generate (JSON/CSV 导出)

仪表盘面板:
· 概览：活跃合同、总交易额、供应商/买家数、覆盖国家
· 交易量：月度/季度趋势、按区域/行业分布
· Pipeline：各阶段机会数、转化率、平均成交周期
· 风险：综合评分、活跃告警、高风险合同
· 财务：YTD 收入、毛利率、应收款、汇率敞口
· 趋势：12 月趋势线、同比增长、下季预测
```

### 5.6 实时协作 (Realtime Collaboration)

**职责**：多方消息、文件共享、审批流转、版本管理。

```
API: /v1/collab/conversations · /v1/collab/messages
     /v1/collab/approvals · /v1/collab/files

功能:
· 对话管理：创建项目对话、多参与方消息
· 审批流：创建→审批→拒绝→修改 四态流转
· 文件共享：上传、版本、下载
· 系统消息：自动通知审批状态变更
```

---

## 六、数据架构与存储

### 6.1 五层存储矩阵

| 存储引擎 | 用途 | 数据特征 | v12 状态 |
|---------|------|---------|---------|
| **PostgreSQL** | 业务核心数据 | 结构化、事务性 | 新增 |
| **Redis** | 缓存、限流、会话 | 键值、高并发 | 新增 |
| **ChromaDB** | 语义搜索、向量索引 | 高维嵌入 | 新增 |
| **Neo4j** | 知识图谱 | 图结构 | 🆕 新增 |
| **MinIO** | 文件、报告、媒体 | 非结构化 | 新增 |
| **文件系统** | 项目、记忆、报告 | 半结构化 JSON | v11 继承 |

### 6.2 数据流向

```
外部数据源 → 情报采集 → NLP/ETL加工 → 知识图谱构建 → 决策支持
                    ↓                    ↓
              ChromaDB(向量)        Neo4j(图推理)
                    ↓                    ↓
              语义检索结果 ──────→ 实体关系洞察
                                        ↓
                              PostgreSQL(业务数据)
                                        ↓
                              BI 大屏 · API · 报告
```

---

## 七、安全与合规体系

### 7.1 多层安全架构

```
┌─────────────────────────────────────────┐
│ 网络层: Kong API Gateway (JWT/OAuth2)    │
├─────────────────────────────────────────┤
│ 应用层: Tenant Isolation + RBAC          │
├─────────────────────────────────────────┤
│ 数据层: AES-256 加密 + 脱敏              │
├─────────────────────────────────────────┤
│ 审计层: 全量操作日志 + 不可篡改链         │
├─────────────────────────────────────────┤
│ 合规层: GDPR / 中国数据安全法 / 跨境合规  │
└─────────────────────────────────────────┘
```

### 7.2 风险分级审批

| 等级 | 操作示例 | 审批要求 |
|------|---------|---------|
| LOW | 情报查询、报告生成 | 自动执行 |
| MEDIUM | 报价建议、内容草稿 | 事后通知 |
| HIGH | 发送报价、批准合同 | 1 人审批 |
| CRITICAL | 大额付款(>$100K)、承诺交期 | 2 人审批 |

---

## 八、通信与集成层

### 8.1 通信网关

| 通道 | 文件 | 协议 |
|------|------|------|
| 统一聊天网关 | `comm/chat_gateway.py` | REST + Webhook |
| GitHub Issue | `comm/github_issue.py` | GitHub API |
| 微信通知 | `comm/wechat.py` | Webhook |
| 邮件通知 | `comm/notification.py` | SMTP |

### 8.2 集成总线

| 组件 | 文件 | 用途 | v12 变化 |
|------|------|------|---------|
| Kafka Event Bus | `integrations/kafka_connector.py` | 服务间异步通信 | 🆕 新增 |
| n8n Connector | `integrations/n8n_connector.py` | 工作流自动化 | ✅ |
| Neo4j Connector | `integrations/neo4j_connector.py` | 图数据库 | 🆕 新增 |

### 8.3 云工作流 (GitHub Actions)

| 工作流 | 文件 | 职责 |
|--------|------|------|
| 国际贸易运营 | `international_trade_ops.yml` | 日常运营自动化 |
| 云验收 | `cloud_acceptance.yml` | 部署质量验收 |
| 自主修复 | `codex_autonomous_repair.yml` | 代码问题自动修复 |
| 看门狗 | `watchdog.yml` | 系统健康巡检 |
| 业主决策 | `owner_decision.yml` | 高风险决策审批流 |

---

## 九、前端应用矩阵

| 应用 | 技术栈 | 用途 | 状态 |
|------|--------|------|------|
| Decision Hub | Electron + React | 本地决策控制台 | ✅ |
| Desktop Cloud OS | Electron + JS | Windows 桌面端 | ✅ |
| Trade Platform | React + MUI | 客户自助门户 | ✅ |
| Mobile App | React Native | 移动审批 + 看板 | 🆕 规划 |
| BI Dashboard | React + ECharts | 数据大屏 | 🆕 规划 |
| API Developer Portal | Swagger UI + Docs | 开发者门户 | 🆕 规划 |
| Kong Admin | Kong Dashboard | API 网关管理 | 🆕 规划 |

---

## 十、API 接口全景（50+ 端点）

### 10.1 核心 API (v11 继承 — 18 端点)

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/v1/health` | 健康检查 |
| POST | `/v1/query` | 智能问答 |
| POST | `/v1/search` | 多源搜索 |
| POST | `/v1/intelligence/search-system` | 情报检索系统 |
| POST | `/v1/intelligence/brief` | 情报简报生成 |
| GET | `/v1/intelligence/keywords` | 关键词库 |
| POST | `/v1/war-room/build` | 作战室构建 |
| GET | `/v1/war-room/execution-queue` | 执行队列 |
| POST | `/v1/knowledge/build` | 知识库构建 |
| POST | `/v1/benchmark/build` | 基准构建 |
| POST | `/v1/answers/score` | 答案评分 |
| POST | `/v1/benchmark/compare` | 基准对比 |
| POST | `/v1/video/center` | 视频中心 |
| POST | `/v1/projects/intake` | 项目录入 |
| POST | `/v1/projects/analyze` | 项目分析 |
| POST | `/v1/projects/discover` | 项目发现 |
| POST | `/v1/projects/pipeline` | 项目管线 |
| POST | `/v1/evidence/verify` | 证据核查 |

### 10.2 管理 API (v11 — 12 端点)

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/v1/reports/headquarters` | 总部报告 |
| GET | `/v1/reports/owner-inbox` | 业主收件箱 |
| POST | `/v1/reports/feasibility` | 可行性报告 |
| GET | `/v1/dashboard` | 仪表盘 |
| GET | `/v1/mission-control` | 任务控制 |
| GET | `/v1/cloud/status` | 云端状态 |
| POST | `/v1/cloud/check` | 云端检查 |
| POST | `/v1/cloud/run` | 云端运行 |
| GET | `/v1/license/status` | 授权状态 |
| POST | `/v1/license/refresh` | 刷新授权 |
| POST | `/v1/approvals/decision` | 审批决策 |
| POST | `/v1/system/integrity` | 系统完整性 |

### 10.3 通信 API (v11 — 4 端点)

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/v1/notifications/test` | 通知测试 |
| POST | `/v1/chat/reply-draft` | 聊天草稿 |
| POST | `/v1/chat/send-approved` | 发送已审批 |
| POST | `/v1/integrations/n8n/trigger/{id}` | n8n 触发 |

### 10.4 社交 API (v11 — 2 端点)

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/v1/social/analyze` | 社交媒体分析 |
| POST | `/v1/social/reply-draft` | 社交回复草稿 |

### 10.5 v12 新增 API — 交易撮合 (5 端点)

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/v1/matching/suppliers/register` | 注册供应商 |
| POST | `/v1/matching/search` | 供应商匹配搜索 |
| POST | `/v1/matching/quotes/generate` | 生成报价 |
| POST | `/v1/matching/quotes/compare` | 报价对比 |
| POST | `/v1/matching/contracts/generate` | 合同生成 |

### 10.6 v12 新增 API — 供应链 (8 端点)

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/v1/supply-chain/shipments` | 创建货运 |
| GET | `/v1/supply-chain/shipments/{id}` | 查询货运 |
| POST | `/v1/supply-chain/shipments/{id}/status` | 更新状态 |
| POST | `/v1/supply-chain/quality/inspections` | 创建质检 |
| POST | `/v1/supply-chain/quality/inspections/{id}/result` | 记录结果 |
| POST | `/v1/supply-chain/milestones` | 创建里程碑 |
| POST | `/v1/supply-chain/milestones/{id}` | 更新里程碑 |
| GET | `/v1/supply-chain/contracts/{id}/progress` | 合同进度 |
| GET | `/v1/supply-chain/contracts/{id}/alerts` | 预警 |

### 10.7 v12 新增 API — 金融服务 (6 端点)

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/v1/finance/payment/routes` | 支付路由查询 |
| POST | `/v1/finance/payment/create` | 创建支付 |
| GET | `/v1/finance/fx/{base}/{quote}` | 汇率查询 |
| POST | `/v1/finance/fx/hedge` | 汇率对冲建议 |
| POST | `/v1/finance/credit/assess` | 信用评估 |
| POST | `/v1/finance/financing/recommend` | 融资推荐 |

### 10.8 v12 新增 API — 知识图谱 (6 端点)

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/v1/kg/entities` | 创建实体 |
| GET | `/v1/kg/entities/search` | 搜索实体 |
| POST | `/v1/kg/relations` | 创建关系 |
| GET | `/v1/kg/suppliers/alternatives` | 替代供应商 |
| GET | `/v1/kg/risk/trace` | 风险传导 |
| GET | `/v1/kg/opportunities` | 市场机会 |

### 10.9 v12 新增 API — BI 分析 (8 端点)

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/v1/bi/dashboard` | 完整仪表盘 |
| GET | `/v1/bi/dashboard/overview` | 概览 |
| GET | `/v1/bi/dashboard/trade-volume` | 交易量 |
| GET | `/v1/bi/dashboard/pipeline` | 管线 |
| GET | `/v1/bi/dashboard/risk` | 风险 |
| GET | `/v1/bi/dashboard/financial` | 财务 |
| GET | `/v1/bi/dashboard/trends` | 趋势 |
| POST | `/v1/bi/reports/generate` | 生成报告 |

---

## 十一、全球市场定位与商业模式

### 11.1 市场空间

全球 B2B 电商市场 2025 年达 18.5 万亿美元，预计 2030 年增长至 28 万亿美元（CAGR 8.7%）。其中：

- **亚太区**：42%（中国-中亚-东南亚贸易走廊增速 15%+）
- **中东非洲**：18%（基建需求推动）
- **欧洲**：22%
- **北美**：12%
- **拉美**：6%

### 11.2 四层客户结构

| 层级 | 客户类型 | 年交易规模 | 核心需求 | 定价策略 |
|------|---------|-----------|---------|---------|
| L1 入门 | 中小贸易商 | $50K-$2M | 快速找单、降本 | SaaS $299/月 |
| L2 专业 | 中型工程商 | $2M-$20M | 全流程管理 | 专业版 $999/月 |
| L3 企业 | 大型集团 | $20M-$200M | 定制+私有部署 | 企业版定制 |
| L4 战略 | 政府/园区 | — | 产业招商 | 项目制 |

### 11.3 收入模型（3年目标）

| 收入来源 | 占比 | 说明 |
|---------|------|------|
| SaaS 订阅 | 60% | 按月/年订阅，分层定价 |
| 交易佣金 | 20% | 撮合成功后收取 0.5-2% |
| 金融增值 | 15% | 支付路由、保理、信用报告 |
| API/数据 | 5% | 开放 API 调用、数据订阅 |

### 11.4 差异化竞争

| 维度 | Global Intelligence v12 | 传统 B2B 平台 |
|------|------------------------|-------------|
| AI 能力 | 多智能体编排 + 全链路 AI | 基础搜索/推荐 |
| 覆盖环节 | 商机→撮合→交易→交付→金融 | 仅信息展示/匹配 |
| 知识沉淀 | 图推理 + 持续学习 | 无 |
| 社交获客 | 6 大平台 AI 驱动 | 被动等待 |
| 信任 | 证据链 + 区块链 + 审计 | 用户自评 |
| 金融服务 | 嵌入式全流程 | 无/第三方跳转 |

---

## 十二、部署架构

### 12.1 本地开发

```powershell
cd "C:\Users\Surface\Documents\New project\global-intelligence-v11"
python -m pip install -r requirements.txt
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```

### 12.2 Docker 全栈部署

```bash
docker-compose -f docker-compose-full.yml up -d
```

服务清单：API (8000) + Kong (8001) + PostgreSQL (5432) + Redis (6379) + Neo4j (7687) + MinIO (9000) + n8n (5678)

### 12.3 环境变量

```powershell
# 核心
$env:GITHUB_TOKEN = "runtime-token"
$env:BING_SEARCH_KEY = "optional-key"

# 企业授权
$env:CLOUD_OS_REQUIRE_LICENSE = "1"
$env:CLOUD_OS_ENTERPRISE_ID = "enterprise-code"

# v12 新增
$env:NEO4J_URI = "bolt://localhost:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "password"
$env:KAFKA_BOOTSTRAP = "localhost:9092"
$env:REDIS_URL = "redis://localhost:6379"
```

---

## 十三、架构决策记录 (ADR)

| # | 决策 | 上下文 | 理由 | 替代方案 |
|---|------|--------|------|---------|
| ADR-1 | Neo4j 做知识图谱 | 需要实体关系推理 | 原生图遍历、Cypher 查询 | PostgreSQL 递归 CTE (性能差) |
| ADR-2 | Kafka 升级事件总线 | 需要持久化、多消费者 | 高吞吐、消息回溯 | RabbitMQ (管理简单但持久化弱) |
| ADR-3 | ChromaDB 向量存储 | 语义搜索 | Python 原生、轻量嵌入 | Pinecone (贵) / Weaviate (重) |
| ADR-4 | MinIO 对象存储 | 文件/报告/媒体 | S3 兼容、私有部署、零成本 | AWS S3 (需联网) |
| ADR-5 | Python entry_points 插件 | 第三方扩展 | 标准机制、低耦合 | 微服务注册中心 (运维重) |
| ADR-6 | Kong API Gateway | 统一入口管理 | 插件丰富、声明式、高性能 | Nginx+Lua (手写多) |
| ADR-7 | React Native 移动端 | 跨平台移动 | 代码复用、热更新 | Flutter (团队不熟) |
| ADR-8 | 文件级 Fallback 模式 | 开发/离线环境 | 零依赖快速启动 | 强制数据库 (开发体验差) |
| ADR-9 | 五阶段编排 → Learning | 持续改进 | 闭环反馈比开环更智能 | 四阶段 (无反馈) |

---

## 十四、演进路线图

| 阶段 | 时间 | 里程碑 | 交付物 |
|------|------|--------|--------|
| **Phase 1: 核心稳固** | ✅ 完成 | 多智能体编排稳定、8 个 v11 服务运营 | v11 API + 工作流 |
| **Phase 2: 平台扩展** | Q3 2026 | 8 个 v12 新模块上线、Kafka+Neo4j 集成 | v12 API (50+ 端点) |
| **Phase 3: 智能深化** | Q4 2026 | 知识图谱推理引擎、自动定价、AI 合同审核 | KG v2 + AI 增强 |
| **Phase 4: 移动+大屏** | Q1 2027 | React Native 移动端、BI 大屏、实时协作 | Mobile App + Dashboard |
| **Phase 5: 生态开放** | Q2-Q3 2027 | API 开放平台、插件市场、第三方服务商 | Developer Portal |
| **Phase 6: 全球化** | 2027-2028 | 多区域部署、本地化、多语言 | Global SaaS |

---

## 十五、附录

### A. 技术栈总览

| 层级 | v11 | v12 升级 |
|------|-----|---------|
| 后端框架 | Python / FastAPI | ✅ 不变 |
| 编排引擎 | Planner-Executor-Judge-Decision | + Learning 五阶段 |
| 消息队列 | — | 🆕 Kafka |
| 自动化 | n8n + GitHub Actions | ✅ 不变 |
| 容器化 | Docker + Compose | + Kong / Neo4j / Kafka |
| AI/LLM | GPT-4 / Claude (可插拔) | ✅ 不变 |
| 知识图谱 | — | 🆕 Neo4j |
| 向量数据库 | — | 🆕 ChromaDB |
| 缓存/队列 | — | 🆕 Redis |
| 对象存储 | 文件系统 | 🆕 MinIO |
| 业务数据库 | 文件系统 JSON | 🆕 PostgreSQL |
| 插件系统 | — | 🆕 entry_points |
| 移动端 | — | 🆕 React Native |
| BI | — | 🆕 React + ECharts |

### B. 目录结构速查

```
global-intelligence-v12/
├── backend/
│   ├── api/
│   │   ├── main.py                    # FastAPI 主入口 (v12)
│   │   ├── integration_routes.py
│   │   ├── matching_routes.py         # 🆕 交易撮合
│   │   ├── supply_chain_routes.py     # 🆕 供应链
│   │   ├── financial_routes.py        # 🆕 金融服务
│   │   ├── kg_routes.py              # 🆕 知识图谱
│   │   └── bi_routes.py              # 🆕 BI 分析
│   ├── core/
│   │   ├── agents.py                  # 智能体池
│   │   ├── orchestration.py           # 编排引擎
│   │   ├── planner.py / executor.py
│   │   ├── judge.py / decision.py
│   │   ├── learning.py               # 🆕 持续学习
│   │   ├── plugin_manager.py         # 🆕 插件管理
│   │   ├── project_loader.py
│   │   └── models.py / storage.py
│   ├── services/
│   │   ├── matching_engine_service.py # 🆕
│   │   ├── supply_chain_service.py    # 🆕
│   │   ├── financial_service.py       # 🆕
│   │   ├── knowledge_graph_service.py # 🆕
│   │   ├── bi_analytics_service.py    # 🆕
│   │   ├── realtime_collab_service.py # 🆕
│   │   ├── [8 个 v11 服务].py
│   │   └── ...
│   ├── models/
│   │   ├── matching.py                # 🆕
│   │   ├── supply_chain.py            # 🆕
│   │   ├── finance.py                 # 🆕
│   │   └── knowledge_graph.py         # 🆕
│   ├── integrations/
│   │   ├── n8n_connector.py
│   │   ├── kafka_connector.py         # 🆕
│   │   └── neo4j_connector.py         # 🆕
│   ├── plugins/                       # 🆕
│   │   ├── __init__.py
│   │   └── examples/
│   ├── comm/ / content/ / security/
│   ├── workflows/ / research/
│   ├── memory/ / projects/ / reports/
│   └── intelligence/
├── apps/
│   ├── decision-hub/ / desktop-cloud-os/
│   └── trade-platform/
├── infrastructure/                    # 🆕
│   ├── kong/
│   ├── neo4j/
│   └── docker-compose-full.yml
├── ARCHITECTURE.md                    # 本文件
├── README.md
├── Dockerfile
└── requirements.txt
```

### C. 全局技术指标汇总

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 可用性 | 99.9% | 年停机 < 8.76 小时 |
| API 延迟 P50 | < 100ms | 健康检查/简单查询 |
| API 延迟 P99 | < 500ms | 复杂编排/搜索 |
| 供应商匹配准确率 | > 85% | 五维评分模型 |
| 信用评估准确率 | > 80% | 多维评分 + 图推理 |
| 同时在线租户 | 500+ | 多租户隔离 |
| 日处理交易 | 10,000+ | 撮合/支付/物流 |
| 知识图谱节点 | 1M+ | 爬取 + 人工录入 |
| 支持语种 | 30+ | AI 多语种翻译 |
| 插件生态 | 50+ | 第三方扩展 |
| 代码覆盖率 | > 80% | pytest + CI |
| 安全合规 | SOC2 + GDPR + 中国数据安全法 | 审计追踪 |

---

> **版本历史**
> - v11.0 (2025): 初始架构 — 多智能体编排 + 8 服务 + 安全边界
> - v11.1 (2026-07-01): 新增社交营销、内容引擎、市场定位
> - v12.0 (2026-07-03): **本次强化重设计** — 新增 8 模块、五层架构、Kafka/Neo4j、50+ API 端点、ADR 体系、BI 大屏、插件系统
>
> **维护者**: batuchek68-ux / Global Intelligence Team
