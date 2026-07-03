# 国际贸易工程云平台 — 全局架构设计

**版本：v11.1**
**仓库：batuchek68-ux/global-intelligence-v11-final**
**日期：2026-07-03**

---

## 一、系统全景

### 1.1 平台定位

Global Intelligence v11（国际贸易工程云操作系统）是一套面向跨境 B2B 工程贸易的智能决策平台。系统以多智能体编排为核心，覆盖情报采集、市场分析、项目撮合、交易决策、社交媒体营销、云工作流自动化六大能力域，为企业提供从商机发现到交付履约的全链路 AI 支撑。

### 1.2 核心设计原则

| 原则 | 说明 |
|------|------|
| 智能体驱动 | 规划→执行→评判→决策的四阶段 AI 协作流程 |
| 事件驱动 | 业务模块通过事件总线异步解耦 |
| 安全边界 | 高风险操作必须经过人类审批门控 |
| 多租户隔离 | 企业级租户数据与运行时隔离 |
| 云端优先 | GitHub Actions 云工作流 + n8n 自动化编排 |

### 1.3 全局架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端应用层                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ Decision Hub  │  │ Desktop OS   │  │ Trade Platform (Web)  │  │
│  │  (本地决策台)  │  │ (Windows桌面) │  │   (客户门户)          │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬───────────┘  │
├─────────┼─────────────────┼───────────────────────┼──────────────┤
│         │         API Gateway (FastAPI)             │              │
│         │     /v1/health · /v1/query · /v1/search   │              │
├─────────┼─────────────────┼───────────────────────┼──────────────┤
│         │         多智能体编排引擎 (Core)              │              │
│  ┌──────┴──────┐ ┌──────┴──────┐ ┌────────────────┴───────────┐ │
│  │ Planner     │ │ Executor   │ │ Judge → Decision            │ │
│  │ (任务规划)   │ │ (执行引擎)  │ │ (评估→决策)                   │ │
│  └──────┬──────┘ └──────┬──────┘ └────────────────┬───────────┘ │
├─────────┼─────────────────┼───────────────────────┼──────────────┤
│         │            业务服务层                      │              │
│  ┌──────┴──────────┬──────────────┬────────────────┴───────────┐ │
│  │ Intelligence    │ Mission Ctrl │ Industry War Room           │ │
│  │ (情报中心)       │ (任务控制)    │ (行业作战室)                  │ │
│  ├─────────────────┼──────────────┼────────────────────────────┤ │
│  │ Knowledge Bench │ Audit        │ Evidence Verification       │ │
│  │ (知识标杆)       │ (审计追踪)    │ (证据核查)                    │ │
│  ├─────────────────┼──────────────┼────────────────────────────┤ │
│  │ License         │ Social Media │ Content Engine              │ │
│  │ (授权管理)       │ (社交营销)[新] │ (内容引擎)[新]               │ │
│  └─────────────────┴──────────────┴────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                     集成与基础设施层                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ Event Bus│ │ n8n      │ │ GitHub   │ │ Cloud Workflows   │  │
│  │ (事件总线) │ │ (自动化)  │ │ Actions  │ │ (云工作流)         │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                     数据与存储层                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ Projects │ │ Memory   │ │ Reports  │ │ Intelligence      │  │
│  │ (项目库)  │ │ (记忆库)  │ │ (报告库)  │ │ (情报库)           │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、多智能体编排引擎

### 2.1 四阶段决策流程

系统核心采用 **Planner → Executor → Judge → Decision** 四阶段智能体协作模型：

```
用户意图 → Planner(任务拆解) → Executor(并行执行) → Judge(结果评估) → Decision(行动决策)
                                                         │
                                              人类审批门控(高风险操作)
```

### 2.2 模块清单

| 模块 | 文件 | 职责 |
|------|------|------|
| Planner | `core/planner.py` | 解析用户意图，拆解为可执行子任务 |
| Executor | `core/executor.py` | 调度智能体并行执行任务 |
| Judge | `core/judge.py` | 评估执行结果的质量与合规性 |
| Decision | `core/decision.py` | 基于评估结果做出行动决策 |
| Orchestration | `core/orchestration.py` | 全局编排与工作流管理 |
| Agents | `core/agents.py` | 智能体定义与能力注册 |
| Models | `core/models.py` | 业务实体与数据模型 |
| Storage | `core/storage.py` | 持久化与状态管理 |

### 2.3 安全边界

```
自动化区域(低风险)             人工审批门控(高风险)
─────────────────────────    ──────────────────────────
· 情报采集与分析               · 签署合同
· 报告生成                    · 批准付款
· 内容草稿                    · 报价定价
· 项目方案建议                 · 承诺交期
· 搜索与调研                   · 公开发布媒体内容
                              · 发送正式客户承诺
```

---

## 三、业务服务层

### 3.1 情报中心 (Intelligence Center)

**文件**：`services/intelligence_center_service.py`、`intelligence/`

| 能力 | 实现 |
|------|------|
| 行业情报采集 | 多源爬虫 + API 采集（行业门户、海关数据、社交媒体） |
| 情报分析 | AI 实体识别、情感分析、摘要生成 |
| 简报生成 | `intelligence/brief_generator.py` 自动生成日报/周报 |
| 区域监控 | `intelligence/kazakhstan_xinjiang_monitor.py` 重点区域专项 |
| 知识图谱 | 实体关系构建与推理 |

### 3.2 任务控制 (Mission Control)

**文件**：`services/mission_control_service.py`

- 任务创建、分配、追踪
- 里程碑管理与进度监控
- 团队协作与响应协调
- 执行日志与审计追踪

### 3.3 行业作战室 (Industry War Room)

**文件**：`services/industry_war_room_service.py`

- 竞品动态实时监控
- 市场价格变动预警
- 行业突发事件响应
- 决策推演与方案模拟

### 3.4 知识标杆 (Knowledge Benchmark)

**文件**：`services/knowledge_benchmark_service.py`

- 行业最佳实践库
- 项目模板管理
- 决策案例沉淀
- 学习与改进闭环

### 3.5 证据核查 (Evidence Verification)

**文件**：`services/evidence_verification_service.py`

- 供应商资质验证
- 产品质量证据链
- 交易合规审查
- 审计追踪记录

### 3.6 社交媒体引擎 [新增模块]

**设计原则**：平台抽象 + AI 原生 + 数据闭环

```
┌────────────────────────────────────────────────────┐
│              社交营销模块 (Social Media Module)       │
├──────────────┬──────────────┬──────────────────────┤
│  内容引擎     │  发布引擎     │  分析引擎              │
│  · AI文案生成 │  · 定时发布  │  · 跨平台数据聚合       │
│  · AI图片设计 │  · 智能调度  │  · ROI 分析            │
│  · 短视频生成 │  · 批量操作  │  · 受众画像             │
├──────────────┴──────────────┴──────────────────────┤
│              平台适配层                              │
│  Facebook │ Instagram │ TikTok │ LinkedIn │ X │ YT │
└────────────────────────────────────────────────────┘
```

**核心能力**：
- 六大平台统一接入（FB/IG/TikTok/LinkedIn/X/YouTube）
- AI 驱动的多语种内容生成（30+ 语种）
- 智能发布时间优化
- 内容合规自动审核
- 全链路效果追踪与归因

**集成点**：
- 商品服务 → 获取商品信息生成营销素材
- 情报中心 → 市场热点驱动内容策略
- 任务控制 → 营销活动项目管理
- 事件总线 → 发布结果回调与数据分析

### 3.7 内容引擎 [新增模块]

- AI 辅助视频脚本生成（`content/video_script.py`）
- 多模态内容生产（图文/短视频/文档）
- 内容模板库与品牌风格管理
- A/B 测试与内容效果优化

---

## 四、通信与集成层

### 4.1 通信网关

| 通道 | 文件 | 用途 |
|------|------|------|
| 聊天网关 | `comm/chat_gateway.py` | 统一消息收发接口 |
| GitHub Issue | `comm/github_issue.py` | Issue 驱动的任务协作 |
| 微信通知 | `comm/wechat.py` | 审批与告警推送 |
| 通知服务 | `comm/notification.py` | 多渠道消息分发 |

### 4.2 集成总线

| 组件 | 文件 | 用途 |
|------|------|------|
| 事件总线 | `integrations/event_bus.py` | 服务间异步通信 |
| n8n 连接器 | `integrations/n8n_connector.py` | 工作流自动化编排 |

### 4.3 云工作流 (GitHub Actions)

| 工作流 | 文件 | 职责 |
|--------|------|------|
| 国际贸易运营 | `international_trade_ops.yml` | 日常业务运营自动化 |
| 云验收 | `cloud_acceptance.yml` | 部署质量验收 |
| 自主修复 | `codex_autonomous_repair.yml` | 代码问题自动修复 |
| 看门狗 | `watchdog.yml` | 系统健康巡检 |
| 业主决策 | `owner_decision.yml` | 高风险决策审批流 |

---

## 五、数据架构

### 5.1 存储分层

| 层级 | 路径 | 内容 |
|------|------|------|
| 项目库 | `backend/projects/` | 活跃项目、模板库、归档项目 |
| 记忆库 | `backend/memory/` | 决策记录、执行日志、案例知识 |
| 报告库 | `backend/reports/` | 日报、分析报告、简报输出 |
| 情报库 | `backend/memory/intelligence/` | 情报采集与分析结果 |
| 知识库 | `backend/memory/knowledge_base/` | 行业知识与最佳实践 |
| 作战室 | `backend/memory/war_room/` | 实时监控与决策数据 |

### 5.2 数据流

```
外部数据源 → 情报采集 → 分析加工 → 知识沉淀 → 决策支持 → 行动执行 → 效果反馈
    │                                                          │
    └──────────────── 持续学习与改进闭环 ──────────────────────┘
```

---

## 六、安全与合规

### 6.1 多租户隔离

**文件**：`security/tenant_isolation.py`

- 每个企业租户拥有独立数据空间
- 运行时安全沙箱
- API 访问权限控制
- 数据加密与脱敏

### 6.2 授权管理

**文件**：`services/license_service.py`

```
License 验证 → 功能授权 → 用量计量 → 到期提醒 → 自动续期/停用
```

### 6.3 审计追踪

**文件**：`services/audit_service.py`

- 全量操作记录
- 可追溯审计链
- 合规报告生成
- 异常行为告警

---

## 七、前端应用

| 应用 | 路径 | 用途 |
|------|------|------|
| Decision Hub | `apps/decision-hub/` | 本地决策控制台，离线可用 |
| Desktop Cloud OS | `apps/desktop-cloud-os/` | Windows 桌面端完整功能 |
| Trade Platform | `apps/trade-platform/` | 客户自助门户与项目入口 |

---

## 八、部署架构

### 8.1 本地运行

```powershell
cd "C:\Users\Surface\Documents\New project\global-intelligence-v11"
python -m pip install -r requirements.txt
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```

### 8.2 Docker 部署

```bash
docker-compose -f docker-compose-full.yml up -d
```

### 8.3 环境变量

```powershell
$env:GITHUB_TOKEN = "runtime-token"
$env:BING_SEARCH_KEY = "optional-bing-key"
$env:CLOUD_OS_REQUIRE_LICENSE = "1"
$env:CLOUD_OS_ENTERPRISE_ID = "enterprise-code"
```

---

## 九、API 接口全景

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/v1/health` | 健康检查 |
| POST | `/v1/query` | 智能问答 |
| POST | `/v1/search` | 搜索查询 |
| POST | `/v1/projects/intake` | 项目录入 |
| POST | `/v1/projects/analyze` | 项目分析 |
| GET | `/v1/reports/headquarters` | 总部报告 |
| GET | `/v1/reports/owner-inbox` | 业主收件箱 |
| GET | `/v1/cloud/status` | 云端状态 |
| POST | `/v1/cloud/check` | 云端检查 |
| POST | `/v1/cloud/run` | 云端运行 |
| POST | `/v1/approvals/decision` | 审批决策 |
| POST | `/v1/integrations/n8n/trigger/{id}` | n8n 触发 |
| POST | `/v1/social/publish` | 社交发布 [新] |
| GET | `/v1/social/analytics` | 社交分析 [新] |
| POST | `/v1/intelligence/collect` | 情报采集 [新] |
| GET | `/v1/intelligence/briefs` | 情报简报 [新] |

---

## 十、全球 B2B 市场定位

### 10.1 市场空间

全球 B2B 电商市场 2025 年达 18.5 万亿美元，预计 2030 年增长至 28 万亿美元（CAGR 8.7%）。亚太占 42%，是最大单一市场。

### 10.2 差异化策略

| 维度 | 策略 |
|------|------|
| 行业聚焦 | 新能源、医疗器械、智能硬件 3 个垂直行业深耕 |
| AI 原生 | 多智能体编排 + LLM 驱动的内容与决策 |
| 信任体系 | 证据核查 + 审计追踪 + 区块链溯源 |
| 社交获客 | 六大平台内容矩阵，AI 驱动精准获客 |
| 金融服务 | 嵌入式跨境支付、供应链金融、汇率管理 |

### 10.3 目标客户

- **中小零售商**（年采购 $50K-500K）：小批量多频次，价格敏感
- **品牌商/贴牌商**（年采购 $500K-5M）：定制化长期合作
- **分销商/批发商**（年采购 $1M-10M）：大批量稳定供应链
- **项目采购商**（单项目 $100K-2M）：技术方案驱动

---

## 十一、演进路线图

| 阶段 | 时间 | 里程碑 |
|------|------|--------|
| **Phase 1：核心稳固** | 当前 | 多智能体编排稳定、情报中心运营、作战室上线 |
| **Phase 2：社交扩展** | Q3 2026 | 社交营销模块（FB/IG/TikTok）、AI 内容引擎上线 |
| **Phase 3：智能深化** | Q4 2026 | 知识图谱构建、智能定价、自动发布全平台覆盖 |
| **Phase 4：生态开放** | 2027 | 多区域本地化、开发者 API、第三方服务商接入 |

---

## 十二、附录

### A. 技术栈总览

| 层级 | 技术 |
|------|------|
| 后端框架 | Python / FastAPI |
| 编排引擎 | 自研 Planner-Executor-Judge-Decision |
| 自动化 | n8n + GitHub Actions |
| 容器化 | Docker + Docker Compose |
| 通信 | REST API + Event Bus |
| AI/LLM | GPT-4 / Claude（可插拔模型层） |
| 前端 | Decision Hub (本地) / Desktop OS (Windows) |
| 数据库 | 文件系统存储 + PostgreSQL（可选） |
| 监控 | 内置健康检查 + 看门狗巡检 |

### B. 目录结构速查

```
global-intelligence-v11/
├── backend/
│   ├── api/              # FastAPI 路由
│   ├── core/             # 智能体编排引擎
│   ├── services/         # 业务服务
│   ├── intelligence/     # 情报采集分析
│   ├── integrations/     # 外部集成
│   ├── comm/             # 通信网关
│   ├── security/         # 安全隔离
│   ├── models/           # 数据模型
│   ├── content/          # 内容引擎
│   ├── research/         # 研究工具
│   ├── projects/         # 项目数据
│   ├── memory/           # 记忆与知识
│   ├── reports/          # 报告输出
│   └── workflows/        # 云工作流
├── apps/                 # 前端应用
├── n8n/                  # n8n 自动化
├── data/                 # 数据文件
├── Dockerfile            # 容器构建
├── docker-compose.yml    # 容器编排
└── requirements.txt      # Python 依赖
```
