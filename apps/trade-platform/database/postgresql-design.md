# PostgreSQL 数据库设计：跨境工程贸易与产业招商平台

版本：V1 工程落地稿  
目标：支撑网站首页、矿山设备板块、询盘、项目库、AI 预审、审计追踪，并可扩展到易货、现货、招商、情报与加工业务。

## 1. 设计原则

- 业务对象先稳定：公司、联系人、设备、项目、询盘、AI事件、审批、文档。
- 高风险动作可追踪：所有 AI 判断、人工审批、合同/报价相关动作必须留审计记录。
- 对外内容先草稿：数据库字段区分 `draft`、`reviewing`、`approved`、`published`。
- 国际贸易可扩展：国家、币种、贸易术语、合规风险、语言版本独立建模。
- 不把 AI 输出当事实：AI 结果必须保存置信度、风险等级、来源输入和人工确认状态。

## 2. 核心枚举

```sql
CREATE TYPE lead_status AS ENUM ('new', 'ai_reviewed', 'human_reviewing', 'qualified', 'rejected', 'converted');
CREATE TYPE risk_level AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE approval_status AS ENUM ('pending', 'approved', 'rejected', 'revise_required', 'expired');
CREATE TYPE publish_status AS ENUM ('draft', 'reviewing', 'approved', 'published', 'archived');
CREATE TYPE trade_mode AS ENUM ('barter', 'spot', 'investment', 'project', 'processing', 'parts');
CREATE TYPE ai_event_status AS ENUM ('queued', 'processing', 'completed', 'escalated', 'failed');
```

## 3. 用户、组织与权限

```sql
CREATE TABLE organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  country_code CHAR(2),
  organization_type TEXT NOT NULL,
  website TEXT,
  risk_note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE contacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID REFERENCES organizations(id),
  full_name TEXT NOT NULL,
  title TEXT,
  email TEXT,
  phone TEXT,
  preferred_language TEXT DEFAULT 'en',
  source TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app_users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  display_name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  role TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 4. 设备与矿山重工板块

```sql
CREATE TABLE equipment_categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  parent_id UUID REFERENCES equipment_categories(id),
  name_zh TEXT NOT NULL,
  name_en TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  sort_order INT NOT NULL DEFAULT 0
);

CREATE TABLE equipment_products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id UUID NOT NULL REFERENCES equipment_categories(id),
  name_zh TEXT NOT NULL,
  name_en TEXT,
  model_code TEXT,
  summary TEXT NOT NULL,
  applications TEXT[],
  delivery_scope TEXT[],
  status publish_status NOT NULL DEFAULT 'draft',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE equipment_specs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES equipment_products(id) ON DELETE CASCADE,
  spec_key TEXT NOT NULL,
  spec_value TEXT NOT NULL,
  unit TEXT,
  sort_order INT NOT NULL DEFAULT 0
);

CREATE TABLE equipment_media (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES equipment_products(id) ON DELETE CASCADE,
  media_type TEXT NOT NULL,
  url TEXT NOT NULL,
  caption TEXT,
  status publish_status NOT NULL DEFAULT 'draft',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 5. 询盘与线索

```sql
CREATE TABLE trade_leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  trade_mode trade_mode NOT NULL,
  status lead_status NOT NULL DEFAULT 'new',
  contact_id UUID REFERENCES contacts(id),
  target_country_code CHAR(2),
  subject TEXT NOT NULL,
  requirement TEXT NOT NULL,
  budget_amount NUMERIC(18, 2),
  budget_currency CHAR(3),
  expected_delivery_date DATE,
  source_channel TEXT NOT NULL DEFAULT 'website',
  assigned_user_id UUID REFERENCES app_users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE lead_products (
  lead_id UUID NOT NULL REFERENCES trade_leads(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES equipment_products(id),
  quantity NUMERIC(18, 3),
  note TEXT,
  PRIMARY KEY (lead_id, product_id)
);
```

## 6. 项目库与招商

```sql
CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  country_code CHAR(2),
  sector TEXT NOT NULL,
  project_type TEXT NOT NULL,
  estimated_value NUMERIC(18, 2),
  currency CHAR(3),
  owner_org_id UUID REFERENCES organizations(id),
  stage TEXT NOT NULL DEFAULT 'intake',
  risk_level risk_level NOT NULL DEFAULT 'medium',
  summary TEXT NOT NULL,
  status publish_status NOT NULL DEFAULT 'draft',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE project_partners (
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id),
  partner_role TEXT NOT NULL,
  qualification_note TEXT,
  PRIMARY KEY (project_id, organization_id, partner_role)
);

CREATE TABLE investment_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  incentives TEXT[],
  land_policy TEXT,
  tax_policy TEXT,
  labor_condition TEXT,
  infrastructure TEXT,
  status publish_status NOT NULL DEFAULT 'draft'
);
```

## 7. 易货、现货与加工扩展

```sql
CREATE TABLE barter_offers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id UUID REFERENCES trade_leads(id),
  offered_asset TEXT NOT NULL,
  requested_asset TEXT NOT NULL,
  offered_estimated_value NUMERIC(18, 2),
  requested_estimated_value NUMERIC(18, 2),
  currency CHAR(3),
  cash_difference NUMERIC(18, 2),
  valuation_note TEXT,
  risk_level risk_level NOT NULL DEFAULT 'medium',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE spot_inventory (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID REFERENCES equipment_products(id),
  warehouse_country_code CHAR(2),
  quantity NUMERIC(18, 3) NOT NULL,
  unit TEXT NOT NULL,
  available_from DATE,
  indicative_price NUMERIC(18, 2),
  currency CHAR(3),
  status publish_status NOT NULL DEFAULT 'draft',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE processing_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id UUID NOT NULL REFERENCES trade_leads(id),
  drawing_document_id UUID,
  material TEXT,
  tolerance_note TEXT,
  quantity NUMERIC(18, 3),
  required_delivery_date DATE,
  ai_review_note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 8. 文档、合同与内容发布

```sql
CREATE TABLE documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_type TEXT NOT NULL,
  owner_id UUID NOT NULL,
  document_type TEXT NOT NULL,
  file_name TEXT NOT NULL,
  storage_url TEXT NOT NULL,
  version INT NOT NULL DEFAULT 1,
  checksum TEXT,
  status publish_status NOT NULL DEFAULT 'draft',
  created_by UUID REFERENCES app_users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE contract_drafts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id UUID REFERENCES trade_leads(id),
  project_id UUID REFERENCES projects(id),
  document_id UUID REFERENCES documents(id),
  contract_type TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'en',
  ai_generated BOOLEAN NOT NULL DEFAULT false,
  risk_level risk_level NOT NULL DEFAULT 'high',
  approval_status approval_status NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 9. AI 事件、请示与审计

```sql
CREATE TABLE ai_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_id UUID NOT NULL,
  status ai_event_status NOT NULL DEFAULT 'queued',
  input_payload JSONB NOT NULL,
  output_payload JSONB,
  confidence_score INT CHECK (confidence_score BETWEEN 0 AND 100),
  risk_level risk_level,
  escalation_required BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE TABLE approvals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ai_event_id UUID REFERENCES ai_events(id),
  requested_by UUID REFERENCES app_users(id),
  approver_id UUID REFERENCES app_users(id),
  status approval_status NOT NULL DEFAULT 'pending',
  risk_level risk_level NOT NULL,
  context_summary TEXT NOT NULL,
  blocked_action TEXT NOT NULL,
  decision_note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  decided_at TIMESTAMPTZ
);

CREATE TABLE audit_logs (
  id BIGSERIAL PRIMARY KEY,
  actor_type TEXT NOT NULL,
  actor_id TEXT,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id UUID,
  confidence_score INT,
  risk_level risk_level,
  result TEXT NOT NULL,
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 10. 情报与市场数据

```sql
CREATE TABLE intelligence_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  source_name TEXT,
  source_url TEXT,
  source_published_at TIMESTAMPTZ,
  topic TEXT NOT NULL,
  country_code CHAR(2),
  summary TEXT NOT NULL,
  fact_inference_note TEXT,
  risk_level risk_level NOT NULL DEFAULT 'medium',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE market_prices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  commodity TEXT NOT NULL,
  market TEXT,
  price NUMERIC(18, 4) NOT NULL,
  currency CHAR(3) NOT NULL,
  unit TEXT NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  source_name TEXT,
  source_url TEXT
);
```

## 11. 推荐索引

```sql
CREATE INDEX idx_trade_leads_status_created ON trade_leads(status, created_at DESC);
CREATE INDEX idx_trade_leads_country ON trade_leads(target_country_code);
CREATE INDEX idx_projects_country_sector ON projects(country_code, sector);
CREATE INDEX idx_equipment_products_category ON equipment_products(category_id);
CREATE INDEX idx_ai_events_source ON ai_events(source_type, source_id);
CREATE INDEX idx_ai_events_status ON ai_events(status, created_at DESC);
CREATE INDEX idx_approvals_status ON approvals(status, created_at DESC);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id, created_at DESC);
CREATE INDEX idx_intelligence_topic_time ON intelligence_items(topic, source_published_at DESC);
CREATE INDEX idx_market_prices_lookup ON market_prices(commodity, observed_at DESC);
```

## 12. 网站事件到 AI 总部映射

| 网站事件 | 写入表 | AI事件类型 | 默认风险 | 处理结果 |
|---|---|---|---|---|
| 用户提交矿山设备需求 | `trade_leads`, `lead_products` | `lead.pre_review` | medium | 需求补全、风险清单、下一步建议 |
| 用户下载合同草稿 | `documents`, `contract_drafts` | `contract.version_check` | high | 检查版本与审批状态 |
| 用户提交招商项目 | `projects`, `investment_profiles` | `project.investment_match` | high | 投资人匹配、招商报告草稿 |
| 用户上传图纸 | `documents`, `processing_requests` | `drawing.pre_review` | medium | 审图问题、工艺评估、报价前置资料 |
| 全球情报入库 | `intelligence_items` | `intel.briefing` | medium | 简报、项目影响判断 |

## 13. 第一阶段落地范围

第一阶段只需要实现：

- `equipment_categories`
- `equipment_products`
- `equipment_specs`
- `trade_leads`
- `lead_products`
- `projects`
- `ai_events`
- `approvals`
- `audit_logs`

这些表足够支撑首页、矿山设备板块、项目线索、AI 预审和人工请示闭环。

