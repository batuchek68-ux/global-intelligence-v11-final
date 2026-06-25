const state = {
  approvals: [],
  learning: {},
  licenseAllowed: true,
  cloud: null,
  mission: null,
  projectLibrary: null,
};

const sourceLabels = {
  bing: "Bing",
  google: "Google",
  yandex: "Yandex / 中亚",
  social: "抖音 / 字节 / Telegram",
  academic: "学术",
  library: "图书馆",
};

function qs(selector, root = document) {
  return root.querySelector(selector);
}

function qsa(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function setRuntime(text, mode = "ok") {
  const badge = qs("#runtimeBadge");
  badge.textContent = text;
  badge.className = `runtime-badge ${mode}`;
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const text = await res.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { raw: text };
  }
  if (!res.ok) {
    const message = data.error || data.detail || data.reason || "请求失败";
    const error = new Error(typeof message === "string" ? message : JSON.stringify(message));
    error.payload = data;
    error.status = res.status;
    throw error;
  }
  return data;
}

function switchView(name) {
  qsa(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === name));
  qsa(".view").forEach((view) => view.classList.toggle("active", view.id === name));
  const active = qs(`.nav-item[data-view="${name}"]`);
  qs("#viewTitle").textContent = active ? active.textContent : "作战指挥台";
}

function licenseLabel(license = {}) {
  const map = {
    active: "授权有效",
    owner_mode: "本地业主模式",
    grace: "宽限期",
    expired: "授权过期",
    unpaid: "未缴费",
    disabled: "已禁用",
    unconfigured: "未配置授权",
    unreachable: "授权中心不可达",
  };
  return map[license.status] || license.status || "未知";
}

function applyLicenseGate(license = {}, allowed = true) {
  state.licenseAllowed = Boolean(allowed);
  qsa(".core-action").forEach((button) => {
    button.disabled = !state.licenseAllowed;
  });

  const banner = qs("#haltBanner");
  if (state.licenseAllowed) {
    banner.classList.add("hidden");
    return;
  }

  banner.classList.remove("hidden");
  banner.innerHTML = `
    <strong>核心功能已停止。</strong>
    <span>${escapeHtml(licenseLabel(license))}: ${escapeHtml(license.reason || "请配置企业授权或联系管理员。")}</span>
  `;
}

function getCloudData(cloud = {}) {
  return {
    cloudRun: cloud.cloudRun?.data || {},
    acceptance: cloud.cloudAcceptance?.data || {},
    inboxText: cloud.ownerInbox?.content || cloud.ownerInbox?.inbox?.content || "",
  };
}

function renderCloudStatus(cloud = {}) {
  state.cloud = cloud;
  const license = cloud.license || {};
  const allowed = cloud.allowed !== false;
  const { cloudRun, acceptance, inboxText } = getCloudData(cloud);

  qs("#licenseStatus").textContent = licenseLabel(license);
  qs("#licenseDetail").textContent = license.reason || license.enterpriseName || license.enterpriseId || "v11 本地运行可用";
  qs("#cloudStatus").textContent = acceptance.ok || cloudRun.ok ? "已连接" : "待确认";
  qs("#cloudDetail").textContent = `阶段: ${cloudRun.stage || acceptance.stage || "local"} / 结论: ${cloudRun.conclusion || acceptance.conclusion || "pending"}`;
  qs("#ownerInbox").textContent = inboxText || "暂无待处理事项。";
  applyLicenseGate(license, allowed);
  setRuntime(allowed ? "v11 online" : "授权停服", allowed ? "ok" : "danger");
}

function normalizeMission(raw = {}) {
  if (raw.snapshot) return raw.snapshot;
  if (raw.data) return raw.data;
  return raw;
}

async function loadMissionControl() {
  try {
    const mission = await api("/api/mission-control");
    state.mission = normalizeMission(mission);
    renderMissionControl(state.mission);
  } catch {
    try {
      const mission = await api("/v1/mission-control");
      state.mission = normalizeMission(mission);
      renderMissionControl(state.mission);
    } catch (error) {
      qs("#missionStatus").textContent = "未读取";
      qs("#missionReport").textContent = error.message;
    }
  }
}

function evidenceTile(label, value) {
  return `<div class="evidence-tile"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function renderMissionControl(mission = {}) {
  const evidence = mission.capability_evidence || {};
  const command = mission.command_center || {};
  const search = mission.search_and_learning || {};
  qs("#missionStatus").textContent = mission.status || "operating";
  qs("#approvalCount").textContent = String(command.waiting_for_owner ?? state.approvals.filter((item) => item.status === "waiting").length);
  qs("#capabilityEvidence").innerHTML = [
    evidenceTile("知识领域", evidence.knowledge_domains ?? 0),
    evidenceTile("海关分库", evidence.customs_information_domain ? "已建立" : "缺失"),
    evidenceTile("Benchmark", evidence.benchmark_questions ?? 0),
    evidenceTile("答案评分", `${evidence.answer_score ?? 0} / ${evidence.answer_score_verdict || "missing"}`),
    evidenceTile("情报关键词", evidence.intelligence_keywords ?? 0),
    evidenceTile("团队报告", evidence.team_execution_reports ?? 0),
    evidenceTile("证据档案", evidence.evidence_dossiers ?? 0),
    evidenceTile("最新核验", evidence.latest_evidence_status || "missing"),
    evidenceTile("任务板", evidence.action_boards ?? 0),
    evidenceTile("任务状态", evidence.latest_action_board_status || "missing"),
    evidenceTile("团队答复", evidence.team_responses ?? 0),
    evidenceTile("答复评分", evidence.latest_team_response_score ?? 0),
  ].join("");

  const priority = mission.priority_queue || [];
  qs("#priorityQueue").innerHTML = priority.length
    ? priority.map((item) => `
        <article class="mission-card danger-card">
          <strong>${escapeHtml(item.project || "未命名项目")}</strong>
          <p>${escapeHtml(item.country || "")} / 风险: ${escapeHtml(item.risk_level || "unknown")}</p>
          <p>${escapeHtml(item.required_decision || "等待人工决策")}</p>
        </article>
      `).join("")
    : `<p class="empty">暂无重大事项等待老板决策。</p>`;

  const keywords = search.top_keywords || [];
  qs("#keywordBank").innerHTML = keywords.length
    ? keywords.slice(0, 18).map((keyword) => `<span>${escapeHtml(keyword)}</span>`).join("")
    : `<p class="empty">暂无关键词。运行每日任务后会自动生成。</p>`;

  qs("#missionReport").textContent = renderMissionText(mission);
}

function renderMissionText(mission = {}) {
  const evidence = mission.capability_evidence || {};
  const command = mission.command_center || {};
  const lines = [
    `状态: ${mission.status || "unknown"}`,
    `项目: ${command.project_count ?? 0} / 案例: ${command.case_count ?? 0}`,
    `重大事项: ${command.major_matter_count ?? 0} / 等待老板: ${command.waiting_for_owner ?? 0}`,
    `知识领域: ${evidence.knowledge_domains ?? 0}, 海关分库: ${evidence.customs_information_domain ? "是" : "否"}`,
    `Benchmark: ${evidence.benchmark_questions ?? 0} 题, 答案评分: ${evidence.answer_score ?? 0}`,
    `证据档案: ${evidence.evidence_dossiers ?? 0}, 最新核验: ${evidence.latest_evidence_status || "missing"} (${evidence.latest_evidence_confidence ?? 0})`,
    `任务板: ${evidence.action_boards ?? 0}, 最新状态: ${evidence.latest_action_board_status || "missing"} (${evidence.latest_action_board_tasks ?? 0} tasks)`,
    `团队答复: ${evidence.team_responses ?? 0}, 最新评分: ${evidence.latest_team_response_score ?? 0}`,
    `情报关键词: ${evidence.intelligence_keywords ?? 0}, 团队执行报告: ${evidence.team_execution_reports ?? 0}`,
    "",
    "规则:",
    ...(mission.rules || []).map((rule) => `- ${rule}`),
  ];
  return lines.join("\n");
}

async function loadStatus() {
  try {
    const [cloud, store] = await Promise.all([
      api("/api/cloud/status"),
      api("/api/state").catch(() => ({ approvals: [], learning: {} })),
    ]);
    state.approvals = store.approvals || [];
    state.learning = store.learning || {};
    renderCloudStatus(cloud);
    await loadMissionControl();
    await loadProjectLibrary(false);
    renderApprovals();
    renderDiagnostics();
  } catch (error) {
    setRuntime(error.message, "danger");
  }
}

async function loadProjectLibrary(showRuntime = true) {
  try {
    const library = await api("/api/projects/library");
    state.projectLibrary = library;
    renderProjectLibrary(library);
    if (showRuntime) setRuntime("项目库已刷新", "ok");
  } catch (error) {
    const target = qs("#projectLibraryGroups");
    if (target) target.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    if (error.payload?.license) applyLicenseGate(error.payload.license, false);
    if (showRuntime) setRuntime("项目库刷新失败", "danger");
  }
}

function projectSummaryCard(label, value, detail, accent = "") {
  return `
    <article class="metric-panel ${accent}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <p>${escapeHtml(detail)}</p>
    </article>
  `;
}

function renderProjectLibrary(library = {}) {
  if (!qs("#projectLibrarySummary")) return;
  const summary = library.summary || {};
  qs("#projectLibrarySummary").innerHTML = [
    projectSummaryCard("项目总数", summary.total ?? 0, "所有已沉淀到 v11 的项目线索", "accent-blue"),
    projectSummaryCard("在建项目", summary.under_construction ?? 0, "有开工、施工或合同授予证据", "accent-teal"),
    projectSummaryCard("计划建设", summary.planned ?? 0, "有规划、可研、EIA、公示或招标证据", "accent-blue"),
    projectSummaryCard("待核验", summary.unconfirmed ?? 0, "需要继续补官方证据", "accent-red"),
    projectSummaryCard("可进入招商筛选", summary.official_ready ?? 0, "政府确认且置信度达到 90+", "accent-teal"),
    projectSummaryCard("招商草稿", summary.promotion_draft_ready ?? 0, "证据足够生成内部招商草稿", "accent-teal"),
    projectSummaryCard("仅线索", summary.lead_only ?? 0, "只能内部搜索和补证据", "accent-red"),
    projectSummaryCard("缺证据", summary.needs_evidence ?? 0, "不能对外承诺或发布", "accent-red"),
  ].join("");

  const watchlist = library.high_value_watchlist || [];
  qs("#projectLibraryWatchlist").innerHTML = `
    <h3>高价值关注清单</h3>
    <p class="meta">按政府确认、置信度、业主线索、开发者线索排序。只允许内部筛选，外部沟通仍需人工审批。</p>
    <div class="project-table">
      ${watchlist.length ? watchlist.map(renderProjectRow).join("") : `<p class="empty">暂无项目。请先从搜索或项目执行包沉淀证据。</p>`}
    </div>
  `;

  const categories = library.categories || {};
  const groups = [
    ["under_construction", "在建项目", "开工、施工、合同授予、现场建设证据"],
    ["planned", "计划建设项目", "规划、可研、EIA、公示、招标、投资项目证据"],
    ["unconfirmed", "待核验线索", "只有搜索计划、弱信号或二手资料，不能对外使用"],
  ];
  qs("#projectLibraryGroups").innerHTML = groups.map(([key, label, hint]) => `
    <article class="source-panel library-panel">
      <h3>${escapeHtml(label)}<span class="badge">${escapeHtml((categories[key] || []).length)} 项</span></h3>
      <p class="meta">${escapeHtml(hint)}</p>
      <div class="project-table">
        ${(categories[key] || []).length ? categories[key].map(renderProjectRow).join("") : `<p class="empty">暂无${escapeHtml(label)}。</p>`}
      </div>
    </article>
  `).join("");
}

function renderProjectRow(project = {}) {
  const owner = (project.owner_candidates || [])[0] || "业主待确认";
  const developer = (project.developer_candidates || [])[0] || "开发者待确认";
  const confidence = project.confidence ?? 0;
  const level = project.confirmation_level || "unverified_or_secondary";
  return `
    <div class="project-row">
      <div>
        <strong>${escapeHtml(project.title || project.topic || "未命名项目")}</strong>
        <p class="muted">${escapeHtml(project.country || "")} / ${escapeHtml(project.category_label || project.category || "待确认")}</p>
      </div>
      <div>
        <span class="project-chip">${escapeHtml(level)}</span>
        <span class="project-chip">${escapeHtml(confidence)}%</span>
      </div>
      <p>${escapeHtml(owner)}</p>
      <p>${escapeHtml(developer)}</p>
    </div>
  `;
}

async function runCloudCommand(path, label) {
  qs("#cloudOutput").textContent = `${label}运行中...`;
  try {
    const data = await api(path, { method: "POST", body: "{}" });
    qs("#cloudOutput").textContent = data.output || JSON.stringify(data, null, 2);
    await loadStatus();
  } catch (error) {
    qs("#cloudOutput").textContent = error.message;
    if (error.payload?.license) applyLicenseGate(error.payload.license, false);
    setRuntime(`${label}失败`, "danger");
  }
}

async function doSearch() {
  const query = qs("#searchQuery").value.trim();
  const sources = qsa(".source-selector input:checked").map((item) => item.value);
  if (!query) {
    setRuntime("请输入搜索问题", "warn");
    return;
  }
  qs("#searchResults").innerHTML = `<p class="empty">正在增强关键词并查询多源情报...</p>`;
  try {
    const data = await api("/api/search", {
      method: "POST",
      body: JSON.stringify({ query, sources }),
    });
    renderSearch(data);
    setRuntime("搜索完成", "ok");
  } catch (error) {
    qs("#searchResults").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    if (error.payload?.license) applyLicenseGate(error.payload.license, false);
    setRuntime("搜索失败", "danger");
  }
}

function briefingPayload() {
  return {
    topic: qs("#briefTopic").value.trim(),
    country: qs("#briefCountry").value.trim() || "Kazakhstan",
    industry: qs("#briefIndustry").value.trim() || "infrastructure",
    items: [
      {
        title: qs("#briefItemTitle").value.trim(),
        summary: qs("#briefItemSummary").value.trim(),
        source_type: qs("#briefItemSource").value,
      },
    ],
  };
}

async function buildBriefing() {
  const payload = briefingPayload();
  if (!payload.topic) {
    setRuntime("请填写简报主题", "warn");
    return;
  }
  qs("#briefingResult").innerHTML = `<p class="empty">正在生成行业情报简报和搜索词库...</p>`;
  try {
    const data = await api("/api/intelligence/brief", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderBriefing(data);
    await loadStatus();
    setRuntime("情报简报已生成", "ok");
  } catch (error) {
    qs("#briefingResult").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    if (error.payload?.license) applyLicenseGate(error.payload.license, false);
    setRuntime("情报简报失败", "danger");
  }
}

function renderBriefing(data = {}) {
  const system = data.search_system || {};
  const classified = data.classified?.buckets || {};
  const categories = system.categories || [];
  const watchlist = classified.watchlist || [];
  const focus = [
    ["high_value", "高价值"],
    ["high_growth", "高成长"],
    ["high_return", "高回报"],
    ["political_impact", "政治影响"],
    ["high_attention", "高关注"],
    ["project_critical", "项目关键"],
  ];
  qs("#briefingResult").innerHTML = `
    <h3>行业情报简报</h3>
    <p class="meta">主题: ${escapeHtml((system.topics || []).join(", "))} / 国家: ${escapeHtml((system.countries || []).join(", "))} / 行业: ${escapeHtml((system.industries || []).join(", "))}</p>
    <div class="pipeline-grid">
      ${focus.map(([key, label]) => `
        <div class="pipeline-card">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml((classified[key] || []).length)}</strong>
          <p>按价值、风险和项目推进相关性分类。</p>
        </div>
      `).join("")}
    </div>
    <h3>重点关注线索</h3>
    <div class="team-role-list">
      ${watchlist.length ? watchlist.map((item) => `
        <article class="source-panel">
          <h3>${escapeHtml(item.title || "未命名线索")}<span class="badge">${escapeHtml(item.score?.overall_score ?? 0)}</span></h3>
          <p class="muted">${escapeHtml(item.summary || item.snippet || "")}</p>
        </article>
      `).join("") : `<p class="empty">暂无线索。先从情报搜索或外部资料粘贴证据片段。</p>`}
    </div>
    <h3>分类检索体系</h3>
    <div class="team-role-list">
      ${categories.slice(0, 9).map((category) => `
        <article class="source-panel">
          <h3>${escapeHtml(category.label)}<span class="badge">${escapeHtml(category.id)}</span></h3>
          <ul class="action-list">
            ${(category.search_terms || []).slice(0, 4).map((term) => `<li>${escapeHtml(term)}</li>`).join("")}
          </ul>
        </article>
      `).join("")}
    </div>
    <h3>内部简报草稿</h3>
    <pre class="report-surface">${escapeHtml(data.content || "")}</pre>
    <h3>审批边界</h3>
    <ul class="risk-list">
      <li>该简报是内部情报草稿，不可直接对外发送。</li>
      <li>政治、制裁、合同、付款、报价、客户承诺必须进入人工审批。</li>
      <li>论坛、社交、视频只作为关注度信号，不能替代官方证据。</li>
    </ul>
    <p class="meta">输出文件: ${escapeHtml(data.path || "")}</p>
  `;
}

function renderSearch(data = {}) {
  const results = data.results || [];
  const projectPlan = data.project_search_plan || [];
  const execution = data.evidence_execution_brief || {};
  const readiness = data.source_readiness || {};
  const confirmationGate = data.project_confirmation_gate || execution.project_confirmation_gate || {};
  const backendSources = data.sources || [];
  const expansion = data.search_expansion || {};
  const sourceStatus = data.source_status || [];
  const resultCategories = data.result_categories || {};
  const candidateProjects = data.candidate_projects || resultCategories.projects || [];
  const briefDraft = data.project_brief_draft || {};
  const sourceGroups = results.length ? results : backendSources.map((source) => ({
    source: source.source,
    ok: source.status !== "missing_configuration",
    error: source.reason || source.note || source.status,
    query: source.query,
    items: source.url ? [{ title: source.source, url: source.url, summary: source.status || "", meta: source.source_type || "search" }] : [],
  }));

  const executionHtml = execution.mode
    ? `
      <article class="source-panel execution-panel">
        <h3>证据核验与执行判断 <span class="badge">${escapeHtml(execution.verification_status || "search_plan_only")}</span></h3>
        <p class="meta">置信度: ${escapeHtml(execution.confidence ?? 0)} / ${escapeHtml(execution.why_not_confirmed || "搜索线索尚未形成官方证据。")}</p>
        <h4>必须补齐的证据</h4>
        <ul class="action-list">
          ${(execution.evidence_requirements || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
        <h4>下一步执行</h4>
        <ul class="action-list">
          ${(execution.project_execution?.next_actions || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
        <h4>阻断动作</h4>
        <ul class="risk-list">
          ${(execution.blocked_actions || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
      </article>
    `
    : "";

  const expansionTerms = [
    ...(expansion.chinese_terms || []),
    ...(expansion.english_terms || []),
    ...(expansion.russian_terms || []),
    ...(expansion.industry_terms || []),
    ...(expansion.risk_terms || []),
  ];
  const expansionHtml = expansionTerms.length
    ? `
      <article class="source-panel">
        <h3>增强搜索词 <span class="badge">${escapeHtml(expansion.region_key || "region")}</span></h3>
        <div class="keyword-cloud">
          ${expansionTerms.slice(0, 32).map((term) => `<span>${escapeHtml(term)}</span>`).join("")}
        </div>
        ${(expansion.project_stage_terms || []).length ? `<p class="meta">项目阶段词: ${(expansion.project_stage_terms || []).map(escapeHtml).join(" / ")}</p>` : ""}
        ${(expansion.platform_terms || []).length ? `<p class="meta">平台词: ${(expansion.platform_terms || []).map(escapeHtml).join(" / ")}</p>` : ""}
      </article>
    `
    : "";

  const sourceStatusHtml = sourceStatus.length
    ? `
      <article class="source-panel">
        <h3>搜索源明细 <span class="badge">${sourceStatus.length} 个来源</span></h3>
        ${sourceStatus.slice(0, 14).map((item) => `
          <div class="result-row">
            <strong>${escapeHtml(item.source)}</strong>
            <p class="meta">${escapeHtml(item.status)} / ${escapeHtml(item.result_count ?? 0)} 条</p>
            <p class="muted">${escapeHtml(item.reason)}</p>
            <p class="muted">${escapeHtml(item.next_action)}</p>
          </div>
        `).join("")}
      </article>
    `
    : "";

  const categoryHtml = Object.keys(resultCategories).length
    ? `
      <article class="source-panel">
        <h3>结果分类 <span class="badge">第一阶段</span></h3>
        <div class="pipeline-grid">
          ${Object.entries(resultCategories).map(([name, items]) => `
            <div class="pipeline-card">
              <span>${escapeHtml(name)}</span>
              <strong>${escapeHtml(Array.isArray(items) ? items.length : 0)}</strong>
              <p>${name === "official_sources" ? "优先补官方证据" : "按需下钻查看"}</p>
            </div>
          `).join("")}
        </div>
      </article>
    `
    : "";

  const candidateHtml = candidateProjects.length
    ? `
      <article class="source-panel">
        <h3>候选项目 <span class="badge">${candidateProjects.length} 条</span></h3>
        ${candidateProjects.slice(0, 6).map((project) => `
          <div class="result-row">
            <strong>${escapeHtml(project.project_name || project.title || "未命名候选项目")}</strong>
            <p class="meta">${escapeHtml(project.country || "")} / ${escapeHtml(project.sector || "")} / ${escapeHtml(project.stage_label || project.stage || "")}</p>
            <p class="muted">官方来源: ${escapeHtml(project.official_source_status || project.confirmation_level || "待核验")} / 置信度: ${escapeHtml(project.confidence ?? 0)}</p>
            <p class="muted">业主: ${escapeHtml(project.owner || "待官方证据确认")} / 开发者: ${escapeHtml(project.developer || "待官方证据确认")}</p>
            ${(project.risk_flags || []).length ? `<ul class="risk-list">${project.risk_flags.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
          </div>
        `).join("")}
      </article>
    `
    : "";

  const briefHtml = briefDraft.status
    ? `
      <article class="source-panel execution-panel">
        <h3>项目简报草稿 <span class="badge">${escapeHtml(briefDraft.status)}</span></h3>
        <p class="meta">${escapeHtml(briefDraft.summary || "")}</p>
        <div class="pipeline-grid">
          <div class="pipeline-card"><span>增强词</span><strong>${escapeHtml(briefDraft.enhanced_query_count ?? 0)}</strong><p>用于深度检索。</p></div>
          <div class="pipeline-card"><span>候选项目</span><strong>${escapeHtml((briefDraft.candidate_projects || []).length)}</strong><p>未确认线索。</p></div>
          <div class="pipeline-card"><span>官方状态</span><strong>${escapeHtml(briefDraft.official_source_status || "lead_only")}</strong><p>先补官方证据。</p></div>
        </div>
        <p class="muted">${escapeHtml(briefDraft.risk_notice || "")}</p>
        <h4>下一步</h4>
        <ul class="action-list">
          ${(briefDraft.next_actions || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
      </article>
    `
    : "";

  const readinessHtml = readiness.configured_count !== undefined
    ? `
      <article class="source-panel">
        <h3>来源状态 <span class="badge">${readiness.ok ? "已配置" : "需配置"}</span></h3>
        <div class="pipeline-grid">
          <div class="pipeline-card"><span>可用来源</span><strong>${escapeHtml(readiness.configured_count ?? 0)}</strong><p>含手动官方搜索入口。</p></div>
          <div class="pipeline-card"><span>实时适配器</span><strong>${escapeHtml(readiness.live_adapter_count ?? 0)}</strong><p>配置 API key 后可自动抓取。</p></div>
          <div class="pipeline-card"><span>手动入口</span><strong>${escapeHtml(readiness.manual_entry_count ?? 0)}</strong><p>仍需打开并提取证据。</p></div>
        </div>
        ${(readiness.missing_configuration || []).length ? `<h4>缺失配置</h4><ul class="risk-list">${readiness.missing_configuration.map((item) => `<li>${escapeHtml(item.source)}: ${escapeHtml(item.reason)}</li>`).join("")}</ul>` : ""}
        <p class="meta">${escapeHtml(readiness.explanation || "")}</p>
      </article>
    `
    : "";

  const gateHtml = confirmationGate.status
    ? `
      <article class="source-panel">
        <h3>项目确认门 <span class="badge">${escapeHtml(confirmationGate.status)}</span></h3>
        <div class="pipeline-grid">
          <div class="pipeline-card"><span>线索入库</span><strong>${confirmationGate.can_create_lead_record ? "允许" : "禁止"}</strong><p>仅作为内部线索。</p></div>
          <div class="pipeline-card"><span>确认项目</span><strong>${confirmationGate.can_create_confirmed_project_record ? "允许" : "禁止"}</strong><p>必须先补官方证据。</p></div>
        </div>
        <h4>确认前必须补齐</h4>
        <ul class="action-list">
          ${(confirmationGate.required_before_confirmed_project || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
        <h4>确认前阻断</h4>
        <ul class="risk-list">
          ${(confirmationGate.blocked_until_confirmed || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
      </article>
    `
    : "";

  const planHtml = projectPlan.length
    ? `
      <article class="source-panel">
        <h3>v11 分类检索计划 <span class="badge">${projectPlan.length} 条</span></h3>
        ${projectPlan.slice(0, 12).map((item) => `
          <div class="result-row">
            <strong>${escapeHtml(item.label || item.intent)}</strong>
            <p class="meta">${item.required ? "必查" : "辅助"} / ${escapeHtml(item.evidence_tier || "supporting")}</p>
            <p class="muted">${escapeHtml(item.query)}</p>
          </div>
        `).join("")}
      </article>
    `
    : "";

  const groupsHtml = sourceGroups.length
    ? sourceGroups.map((group) => {
        const items = group.items || [];
        const body = group.ok
          ? items.map((item) => `
              <article class="result-row">
                <a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.title)}</a>
                <p class="meta">${escapeHtml(item.meta || "")}</p>
                <p class="muted">${escapeHtml(item.summary || "").slice(0, 360)}</p>
              </article>
            `).join("") || `<p class="empty">该来源没有结果。</p>`
          : `<p class="empty">${escapeHtml(group.error || "来源不可用")}</p>`;
        return `
          <article class="source-panel">
            <h3>${escapeHtml(sourceLabels[group.source] || group.source)}<span class="badge">${items.length} 条</span></h3>
            ${group.query ? `<p class="meta">增强词: ${escapeHtml(group.query).slice(0, 260)}</p>` : ""}
            ${body}
          </article>
        `;
      }).join("")
    : `<p class="empty">没有结果。请检查搜索源配置或稍后重试。</p>`;

  qs("#searchResults").innerHTML = expansionHtml + sourceStatusHtml + categoryHtml + candidateHtml + briefHtml + readinessHtml + gateHtml + executionHtml + planHtml + groupsHtml;
}

function evidencePayload() {
  return {
    claim: qs("#evidenceClaim").value.trim(),
    project: qs("#evidenceProject").value.trim(),
    country: qs("#evidenceCountry").value.trim() || "Kazakhstan",
    evidence: [
      {
        title: qs("#evidenceTitle").value.trim(),
        url: qs("#evidenceUrl").value.trim(),
        source_type: qs("#evidenceSourceType").value,
        snippet: qs("#evidenceSnippet").value.trim(),
      },
    ],
  };
}

async function verifyEvidence() {
  const payload = evidencePayload();
  if (!payload.claim) {
    setRuntime("请填写待核验结论", "warn");
    return;
  }
  qs("#evidenceResult").innerHTML = `<p class="empty">正在生成证据核验档案...</p>`;
  try {
    const data = await api("/api/evidence/verify", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderEvidenceDossier(data);
    await loadStatus();
    setRuntime("证据核验完成", "ok");
  } catch (error) {
    qs("#evidenceResult").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    if (error.payload?.license) applyLicenseGate(error.payload.license, false);
    setRuntime("证据核验失败", "danger");
  }
}

function renderEvidenceDossier(data = {}) {
  const dossier = data.dossier || {};
  const summary = dossier.summary || {};
  const evidence = dossier.evidence || [];
  qs("#evidenceResult").innerHTML = `
    <h3>证据核验结果</h3>
    <p class="meta">状态: ${escapeHtml(dossier.verification_status || "unknown")} / 置信度: ${escapeHtml(dossier.confidence ?? 0)} / 人工复核: ${dossier.requires_human_review ? "需要" : "未触发"}</p>
    <div class="pipeline-grid">
      <div class="pipeline-card">
        <span>官方来源</span>
        <strong>${escapeHtml(summary.official_sources ?? 0)}</strong>
        <p>政府、海关、采购、监管来源优先。</p>
      </div>
      <div class="pipeline-card">
        <span>弱信号</span>
        <strong>${escapeHtml(summary.weak_signals ?? 0)}</strong>
        <p>社交、论坛、视频只能作为线索。</p>
      </div>
      <div class="pipeline-card">
        <span>报告文件</span>
        <strong>${data.report_path ? "已生成" : "未生成"}</strong>
        <p>${escapeHtml(data.report_path || "")}</p>
      </div>
    </div>
    <h3>证据项</h3>
    <div class="team-role-list">
      ${evidence.map((item) => `
        <article class="source-panel">
          <h3>T${escapeHtml(item.tier)} / ${escapeHtml(item.score)} / ${escapeHtml(item.source_label)}</h3>
          <a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.title || item.domain || "打开证据")}</a>
          <p class="muted">${escapeHtml(item.snippet || "")}</p>
        </article>
      `).join("") || `<p class="empty">没有证据项。</p>`}
    </div>
    <h3>下一步核验</h3>
    <ul class="action-list">
      ${(dossier.next_verification_steps || []).map((item) => `<li>${escapeHtml(item.source)}: ${escapeHtml(item.query)} / ${escapeHtml(item.reason)}</li>`).join("")}
    </ul>
    <h3>阻断动作</h3>
    <ul class="risk-list">
      ${(dossier.blocked_actions || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
  `;
}

function projectPayload() {
  return {
    title: qs("#projectTitle").value.trim(),
    country: qs("#projectCountry").value.trim(),
    amount: Number(qs("#projectAmount").value || 0),
    stage: qs("#projectStage").value,
    latest_communication: qs("#projectCommunication").value.trim(),
    risks: qs("#projectRisks").value.split(",").map((item) => item.trim()).filter(Boolean),
    options: [
      { name: "分阶段推进", evidence: "可验证、低成本、可回滚", risk: "推进速度较慢" },
      { name: "直接全面推进", evidence: "速度快", risk: "不可逆、对外承诺风险高" },
    ],
    criteria: [
      { name: "收益", weight: 4 },
      { name: "风险", weight: 5 },
      { name: "可逆性", weight: 4 },
    ],
  };
}

function videoPayload() {
  return {
    topic: qs("#videoTopic").value.trim(),
    country: qs("#videoCountry").value.trim() || "Kazakhstan",
    industry: qs("#videoIndustry").value.trim() || "infrastructure",
  };
}

async function buildVideoCenter() {
  const payload = videoPayload();
  if (!payload.topic) {
    setRuntime("请填写视频主题", "warn");
    return;
  }
  qs("#videoCenterResult").innerHTML = `<p class="empty">正在生成视频选题、平台搜索词和脚本模板...</p>`;
  try {
    const data = await api("/api/video/center", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderVideoCenter(data);
    await loadStatus();
    setRuntime("视频选题包已生成", "ok");
  } catch (error) {
    qs("#videoCenterResult").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    if (error.payload?.license) applyLicenseGate(error.payload.license, false);
    setRuntime("视频中心失败", "danger");
  }
}

function renderVideoCenter(data = {}) {
  const keywords = data.video_keywords || [];
  const searches = data.platform_searches || [];
  const templates = data.script_templates || [];
  const rules = data.rules || [];
  const firstStyle = keywords[0]?.style_cues || [];
  qs("#videoCenterResult").innerHTML = `
    <h3>视频选题包</h3>
    <p class="meta">主题: ${escapeHtml((data.topics || []).join(", "))} / 国家: ${escapeHtml((data.countries || []).join(", "))} / 行业: ${escapeHtml((data.industries || []).join(", "))}</p>
    <div class="pipeline-grid">
      <div class="pipeline-card">
        <span>关键词</span>
        <strong>${escapeHtml(keywords.length)}</strong>
        <p>用于追踪前沿视频、提炼选题和制作角度。</p>
      </div>
      <div class="pipeline-card">
        <span>平台搜索</span>
        <strong>${escapeHtml(searches.length)}</strong>
        <p>YouTube、TikTok、抖音和 Google Video。</p>
      </div>
      <div class="pipeline-card">
        <span>发布状态</span>
        <strong>草稿</strong>
        <p>DRAFT - Not approved for sending</p>
      </div>
    </div>
    <h3>国家风格提示</h3>
    <div class="keyword-cloud">
      ${firstStyle.map((item) => `<span>${escapeHtml(item)}</span>`).join("") || `<p class="empty">暂无风格提示。</p>`}
    </div>
    <h3>平台搜索词</h3>
    <div class="team-role-list">
      ${searches.slice(0, 16).map((item) => `
        <article class="source-panel">
          <h3>${escapeHtml(item.platform)}<span class="badge">视频搜索</span></h3>
          <a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.keyword)}</a>
        </article>
      `).join("")}
    </div>
    <h3>脚本模板</h3>
    <div class="team-role-list">
      ${templates.map((template) => `
        <article class="source-panel">
          <h3>${escapeHtml(template.name)}</h3>
          <ol class="action-list">
            ${(template.structure || []).map((step) => `<li>${escapeHtml(step)}</li>`).join("")}
          </ol>
        </article>
      `).join("")}
    </div>
    <h3>审批与版权边界</h3>
    <ul class="risk-list">
      ${rules.map((rule) => `<li>${escapeHtml(rule)}</li>`).join("")}
      <li>正式发布到抖音、视频号、TikTok、YouTube 前必须人工审批。</li>
    </ul>
    <p class="meta">输出文件: ${escapeHtml(data.path || "")}</p>
  `;
}

async function analyzeProject() {
  const payload = projectPayload();
  if (!payload.title) {
    setRuntime("请填写项目名称", "warn");
    return;
  }
  qs("#projectResult").innerHTML = `<p class="empty">正在进行 v11 项目风险判断...</p>`;
  try {
    const data = await api("/api/decision", {
      method: "POST",
      body: JSON.stringify({
        type: "project",
        title: payload.title,
        context: `${payload.country} ${payload.stage} ${payload.latest_communication} ${payload.risks.join(" ")}`,
        options: payload.options,
        criteria: payload.criteria,
      }),
    });
    renderProjectDecision(data);
    await loadStatus();
  } catch (error) {
    qs("#projectResult").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    if (error.payload?.license) applyLicenseGate(error.payload.license, false);
    setRuntime("项目分析失败", "danger");
  }
}

async function buildProjectPipeline() {
  const payload = projectPayload();
  if (!payload.title) {
    setRuntime("请填写项目名称", "warn");
    return;
  }
  qs("#projectResult").innerHTML = `<p class="empty">正在生成项目执行包：搜索计划、项目库、行动板、可行性报告草稿...</p>`;
  try {
    const data = await api("/api/project/pipeline", {
      method: "POST",
      body: JSON.stringify({
        topic: payload.title,
        country: payload.country || "Kazakhstan",
        evidence: [],
      }),
    });
    renderProjectPipeline(data);
    await loadStatus();
    setRuntime("项目执行包已生成", "ok");
  } catch (error) {
    qs("#projectResult").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    if (error.payload?.license) applyLicenseGate(error.payload.license, false);
    setRuntime("项目执行包失败", "danger");
  }
}

async function buildTeamExecution() {
  const payload = projectPayload();
  if (!payload.title) {
    setRuntime("请填写项目名称", "warn");
    return;
  }
  qs("#projectResult").innerHTML = `<p class="empty">正在生成六角色团队执行包：贸易、科研、招商、视频、项目经理、风控审批...</p>`;
  try {
    const data = await api("/api/team/execute", {
      method: "POST",
      body: JSON.stringify({
        objective: `${payload.title} ${payload.latest_communication}`,
        country: payload.country || "Kazakhstan",
        industries: ["infrastructure", "mining", "logistics", "energy"],
        evidence: [],
        audience: "internal",
      }),
    });
    renderTeamExecution(data);
    await loadStatus();
    setRuntime("团队执行包已生成", "ok");
  } catch (error) {
    qs("#projectResult").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    if (error.payload?.license) applyLicenseGate(error.payload.license, false);
    setRuntime("团队执行包失败", "danger");
  }
}

function renderProjectDecision(data) {
  const analysis = data.decision?.analysis || {};
  const ranked = analysis.ranked || [];
  qs("#projectResult").innerHTML = `
    <h3>${escapeHtml(analysis.recommendation || "项目分析完成")}</h3>
    <p class="meta">置信度: ${escapeHtml(analysis.confidence || "unknown")} / ${analysis.askNeeded ? "需要人工审批" : "可低风险推进"}</p>
    <ul class="risk-list">
      ${(analysis.rationale || ["已生成项目推进建议。"]).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
    <h3>方案排序</h3>
    <ul class="action-list">
      ${ranked.map((item) => `<li>${escapeHtml(item.name)}: ${escapeHtml(item.score)} / 100</li>`).join("")}
    </ul>
    ${data.approval ? `<p class="meta">已进入审批队列: ${escapeHtml(data.approval.question)}</p>` : ""}
  `;
  setRuntime("项目分析完成", analysis.askNeeded ? "warn" : "ok");
}

function renderTeamExecution(data = {}) {
  const roles = data.team_roles || [];
  const deliverables = data.deliverables || [];
  const risk = data.risk || {};
  const videoSearches = data.search_plan?.video_platform_searches || [];
  qs("#projectResult").innerHTML = `
    <h3>v11 团队执行包</h3>
    <p class="meta">国家: ${escapeHtml(data.country || "")} / 阶段: ${escapeHtml(data.project_stage?.label || data.project_stage?.category || "待确认")} / 人工审批: ${risk.needs_human_approval ? "需要" : "未触发"}</p>
    <div class="pipeline-grid">
      ${roles.map((role) => `
        <div class="pipeline-card">
          <span>${escapeHtml(role.role)}</span>
          <strong>${escapeHtml(role.label)}</strong>
          <p>${escapeHtml(role.responsibility)}</p>
        </div>
      `).join("")}
    </div>
    <h3>角色下一步</h3>
    <div class="team-role-list">
      ${roles.map((role) => `
        <article class="source-panel">
          <h3>${escapeHtml(role.label)}</h3>
          <h4>行动</h4>
          <ul class="action-list">
            ${(role.next_actions || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
          </ul>
          <h4>需要证据</h4>
          <ul class="action-list">
            ${(role.evidence_needed || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
          </ul>
        </article>
      `).join("")}
    </div>
    <h3>交付物</h3>
    <ul class="action-list">
      ${deliverables.map((item) => `<li>${escapeHtml(item.name)} / ${escapeHtml(item.owner)} / ${escapeHtml(item.status)}</li>`).join("")}
    </ul>
    <h3>视频与传播搜索</h3>
    <ul class="action-list">
      ${videoSearches.slice(0, 8).map((item) => `<li>${escapeHtml(item.platform)}: <a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.keyword)}</a></li>`).join("")}
    </ul>
    <h3>审批边界</h3>
    <ul class="risk-list">
      ${(risk.blocked_actions || ["外部发布仍需配置人工审批"]).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
  `;
}

function renderProjectPipeline(data = {}) {
  const project = data.project || {};
  const promotion = data.promotion_readiness || project.promotion_readiness || {};
  const actionBoard = data.action_board || {};
  const tasks = actionBoard.tasks || [];
  const blocked = data.blocked_actions || [];
  const nextActions = data.next_actions || [];
  const plan = data.search_plan?.queries || [];
  const feasibility = data.feasibility_report || {};
  qs("#projectResult").innerHTML = `
    <h3>项目执行包已生成</h3>
    <p class="meta">模式: ${escapeHtml(data.mode || "project_intelligence_pipeline")} / 国家: ${escapeHtml(data.country || project.country || "")}</p>
    <div class="pipeline-grid">
      <div class="pipeline-card">
        <span>项目分类</span>
        <strong>${escapeHtml(project.category_label || project.category || "待确认项目")}</strong>
        <p>确认级别: ${escapeHtml(project.confirmation_level || "search_plan_only")} / 置信度: ${escapeHtml(project.confidence ?? 0)}</p>
      </div>
      <div class="pipeline-card">
        <span>项目库</span>
        <strong>${data.project_library?.updated ? "已更新" : "待证据确认"}</strong>
        <p>${escapeHtml(data.project_library?.rule || "")}</p>
      </div>
      <div class="pipeline-card">
        <span>招商准入</span>
        <strong>${escapeHtml(promotion.label || promotion.status || "待判断")}</strong>
        <p>内部草稿: ${promotion.can_generate_internal_promotion_draft ? "允许" : "禁止"} / 对外: ${promotion.approved_for_external_use ? "已批准" : "未批准"}</p>
      </div>
      <div class="pipeline-card">
        <span>行动板</span>
        <strong>${escapeHtml(actionBoard.status || "created")}</strong>
        <p>${tasks.length} 个任务，重大事项继续进入人工审批。</p>
      </div>
      <div class="pipeline-card">
        <span>可行性草稿</span>
        <strong>${feasibility.ok ? "已生成" : "待生成"}</strong>
        <p>${escapeHtml(feasibility.path || "DRAFT - Not approved for sending")}</p>
      </div>
    </div>
    <h3>优先检索词</h3>
    <ul class="action-list">
      ${plan.slice(0, 8).map((item) => `<li>${escapeHtml(item.intent || "")}: ${escapeHtml(item.query || "")}</li>`).join("")}
    </ul>
    <h3>阻断动作</h3>
    <ul class="risk-list">
      ${[...blocked, ...(promotion.blocked_actions || [])].map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
    <h3>下一步</h3>
    <ul class="action-list">
      ${nextActions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
  `;
}

function warRoomPayload() {
  const evidence = [];
  const title = qs("#warRoomEvidenceTitle").value.trim();
  const url = qs("#warRoomEvidenceUrl").value.trim();
  const snippet = qs("#warRoomEvidenceSnippet").value.trim();
  if (title || url || snippet) {
    evidence.push({
      title,
      url,
      snippet,
      source_type: "government",
    });
  }
  return {
    objective: qs("#warRoomObjective").value.trim(),
    country: qs("#warRoomCountry").value.trim() || "Kazakhstan",
    industries: qs("#warRoomIndustries").value.split(",").map((item) => item.trim()).filter(Boolean),
    evidence,
    audience: "internal",
  };
}

async function buildWarRoom() {
  const payload = warRoomPayload();
  if (!payload.objective) {
    setRuntime("请填写作战目标", "warn");
    return;
  }
  qs("#warRoomResult").innerHTML = `<p class="empty">正在生成行业作战室：搜索确认、证据、项目、团队、视频、评分、审批边界...</p>`;
  try {
    const data = await api("/api/war-room/build", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderWarRoom(data.war_room || data);
    if ((data.war_room || data).execution_queue) {
      renderWarRoomQueue((data.war_room || data).execution_queue, data.execution_queue_report_path || data.execution_queue_path || "");
    } else {
      await loadWarRoomExecutionQueue(false);
    }
    await loadStatus();
    setRuntime("行业作战室已生成", "ok");
  } catch (error) {
    qs("#warRoomResult").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    if (error.payload?.license) applyLicenseGate(error.payload.license, false);
    setRuntime("行业作战室失败", "danger");
  }
}

async function loadWarRoomExecutionQueue(showStatus = true) {
  if (showStatus) qs("#warRoomQueueResult").innerHTML = `<p class="empty">正在读取最新作战室执行队列...</p>`;
  try {
    const data = await api("/api/war-room/execution-queue");
    if (!data.ok || !data.queue) {
      qs("#warRoomQueueResult").innerHTML = `<p class="empty">暂无执行队列，请先生成行业作战室。</p>`;
      return;
    }
    renderWarRoomQueue(data.queue, data.report_path || data.json_path || "");
    if (showStatus) setRuntime("执行队列已读取", "ok");
  } catch (error) {
    qs("#warRoomQueueResult").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    if (error.payload?.license) applyLicenseGate(error.payload.license, false);
    if (showStatus) setRuntime("执行队列读取失败", "danger");
  }
}

function renderWarRoomQueue(queue = {}, path = "") {
  const summary = queue.summary || {};
  const tasks = queue.tasks || [];
  const grouped = tasks.reduce((acc, task) => {
    const role = task.role || "unassigned";
    if (!acc[role]) acc[role] = [];
    acc[role].push(task);
    return acc;
  }, {});
  qs("#warRoomQueueResult").innerHTML = `
    <h3>作战室执行队列</h3>
    <div class="pipeline-grid">
      <div class="pipeline-card">
        <span>任务总数</span>
        <strong>${escapeHtml(summary.task_count ?? tasks.length)}</strong>
        <p>开放 ${escapeHtml(summary.open_count ?? 0)} / 阻断 ${escapeHtml(summary.blocked_count ?? 0)}</p>
      </div>
      <div class="pipeline-card">
        <span>证据任务</span>
        <strong>${escapeHtml(summary.evidence_required_count ?? 0)}</strong>
        <p>政府、海关、采购、官方企业证据优先</p>
      </div>
      <div class="pipeline-card">
        <span>审批任务</span>
        <strong>${escapeHtml(summary.approval_required_count ?? 0)}</strong>
        <p>对外动作默认阻断</p>
      </div>
    </div>
    <div class="team-role-list">
      ${Object.entries(grouped).map(([role, items]) => `
        <article class="source-panel">
          <h3>${escapeHtml(role)} <span class="badge">${escapeHtml(items.length)}</span></h3>
          <ul class="action-list">
            ${items.slice(0, 8).map((task) => `
              <li>
                <strong>${escapeHtml(task.status || "open")}</strong>
                · ${escapeHtml(task.task || "")}
                <br><span class="meta">证据: ${escapeHtml((task.evidence_needed || []).join("; "))}</span>
                <br><span class="meta">风控: ${escapeHtml(task.risk_gate || "standard_review")}</span>
              </li>
            `).join("")}
          </ul>
        </article>
      `).join("")}
    </div>
    <h3>阻断动作</h3>
    <ul class="risk-list">
      ${Array.from(new Set(tasks.flatMap((task) => task.blocked_actions || []))).slice(0, 16).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>正式外联、报价、合同、付款、客户承诺、公开视频发布必须人工审批。</li>"}
    </ul>
    <p class="meta">队列文件: ${escapeHtml(path || queue.id || "")}</p>
  `;
}

function renderWarRoom(room = {}) {
  const searchGate = room.search_confirmation?.project_confirmation_gate || {};
  const evidence = room.evidence || {};
  const execution = room.project_execution || {};
  const promotion = execution.promotion_readiness || {};
  const team = room.team || {};
  const roles = team.roles || [];
  const videoSearches = room.video_center?.platform_searches || [];
  const tasks = room.action_board?.tasks || [];
  const quality = room.quality_score || {};
  const boundary = room.approval_boundary || {};
  qs("#warRoomResult").innerHTML = `
    <h3>作战室总判断</h3>
    <pre class="report-surface">${escapeHtml(room.executive_synthesis || "")}</pre>
    <div class="pipeline-grid">
      <div class="pipeline-card">
        <span>搜索确认门</span>
        <strong>${escapeHtml(searchGate.status || "missing")}</strong>
        <p>确认项目: ${searchGate.can_create_confirmed_project_record ? "允许" : "禁止"} / 先补官方证据</p>
      </div>
      <div class="pipeline-card">
        <span>证据状态</span>
        <strong>${escapeHtml(evidence.verification_status || "unknown")}</strong>
        <p>置信度 ${escapeHtml(evidence.confidence ?? 0)} / 官方证据 ${escapeHtml(evidence.summary?.official_sources ?? 0)} 条</p>
      </div>
      <div class="pipeline-card">
        <span>招商准入</span>
        <strong>${escapeHtml(promotion.status || "missing")}</strong>
        <p>内部草稿: ${promotion.can_generate_internal_promotion_draft ? "允许" : "禁止"} / 对外: ${promotion.approved_for_external_use ? "已批准" : "未批准"}</p>
      </div>
      <div class="pipeline-card">
        <span>质量评分</span>
        <strong>${escapeHtml(quality.overall_score ?? 0)}</strong>
        <p>${escapeHtml(quality.verdict || "unknown")}</p>
      </div>
      <div class="pipeline-card">
        <span>人工审批</span>
        <strong>${boundary.human_approval_required ? "需要" : "未触发"}</strong>
        <p>DRAFT - Not approved for sending</p>
      </div>
    </div>
    <h3>六角色团队</h3>
    <div class="team-role-list">
      ${roles.map((role) => `
        <article class="source-panel">
          <h3>${escapeHtml(role.label || role.role)} <span class="badge">${escapeHtml(role.role || "")}</span></h3>
          <p>${escapeHtml(role.contribution || role.responsibility || "")}</p>
          <h4>下一步</h4>
          <ul class="action-list"><li>${escapeHtml(role.next_step || "")}</li></ul>
        </article>
      `).join("")}
    </div>
    <h3>优先官方检索</h3>
    <ul class="action-list">
      ${(room.search_confirmation?.priority_queries || []).slice(0, 10).map((item) => `<li>${escapeHtml(item.intent || "")}: ${escapeHtml(item.query || "")}</li>`).join("")}
    </ul>
    <h3>项目下一步</h3>
    <ul class="action-list">
      ${(execution.next_actions || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
    <h3>视频与社媒学习</h3>
    <ul class="action-list">
      ${videoSearches.slice(0, 10).map((item) => `<li>${escapeHtml(item.platform || "")}: <a href="${escapeHtml(item.url || "#")}" target="_blank" rel="noreferrer">${escapeHtml(item.keyword || "")}</a></li>`).join("")}
    </ul>
    <h3>任务板</h3>
    <ul class="action-list">
      ${tasks.slice(0, 12).map((task) => `<li>${escapeHtml(task.owner || "")}: ${escapeHtml(task.title || task.task || "")}</li>`).join("")}
    </ul>
    <h3>执行队列</h3>
    <ul class="action-list">
      ${(room.execution_queue?.tasks || []).slice(0, 12).map((task) => `<li>${escapeHtml(task.role || "")}: ${escapeHtml(task.task || "")} [${escapeHtml(task.status || "open")}]</li>`).join("")}
    </ul>
    <h3>阻断动作</h3>
    <ul class="risk-list">
      ${(boundary.blocked_actions || ["正式外联、报价、合同、付款、客户承诺、公开视频发布必须人工审批。"]).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
    <p class="meta">报告: ${escapeHtml(room.report_path || "")}</p>
  `;
}

function teamResponsePayload() {
  return {
    question: qs("#teamResponseQuestion").value.trim(),
    country: qs("#teamResponseCountry").value.trim() || "Kazakhstan",
    industries: qs("#teamResponseIndustries").value.split(",").map((item) => item.trim()).filter(Boolean),
    evidence: [
      {
        title: qs("#teamResponseEvidenceTitle").value.trim(),
        url: qs("#teamResponseEvidenceUrl").value.trim(),
        snippet: qs("#teamResponseEvidenceSnippet").value.trim(),
        source_type: "government",
      },
    ],
  };
}

async function buildTeamResponse() {
  const payload = teamResponsePayload();
  if (!payload.question) {
    setRuntime("请填写团队答复问题", "warn");
    return;
  }
  qs("#teamResponseResult").innerHTML = `<p class="empty">正在生成六角色团队答复包...</p>`;
  try {
    const data = await api("/api/team/response", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderTeamResponse(data.pack || data);
    await loadStatus();
    setRuntime("团队答复包已生成", "ok");
  } catch (error) {
    qs("#teamResponseResult").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    if (error.payload?.license) applyLicenseGate(error.payload.license, false);
    setRuntime("团队答复失败", "danger");
  }
}

function renderTeamResponse(pack = {}) {
  const evidence = pack.evidence_status || {};
  const roles = pack.team_roles || [];
  const officialQueries = pack.search_plan?.official_queries || [];
  const videoSearches = pack.video_plan?.platform_searches || [];
  const tasks = pack.action_board?.tasks || [];
  const quality = pack.quality_score || {};
  const boundary = pack.approval_boundary || {};
  qs("#teamResponseResult").innerHTML = `
    <h3>团队结论</h3>
    <pre class="report-surface">${escapeHtml(pack.executive_answer || "")}</pre>
    <div class="pipeline-grid">
      <div class="pipeline-card">
        <span>证据状态</span>
        <strong>${escapeHtml(evidence.verification_status || "unknown")}</strong>
        <p>置信度 ${escapeHtml(evidence.confidence ?? 0)} / 官方证据 ${escapeHtml(evidence.official_sources ?? 0)} 条</p>
      </div>
      <div class="pipeline-card">
        <span>质量评分</span>
        <strong>${escapeHtml(quality.overall_score ?? 0)}</strong>
        <p>${escapeHtml(quality.verdict || "unknown")}</p>
      </div>
      <div class="pipeline-card">
        <span>人工审批</span>
        <strong>${boundary.human_approval_required ? "需要" : "未触发"}</strong>
        <p>DRAFT - Not approved for sending</p>
      </div>
    </div>
    <h3>六角色工作输出</h3>
    <div class="team-role-list">
      ${roles.map((role) => `
        <article class="source-panel">
          <h3>${escapeHtml(role.label)} <span class="badge">${escapeHtml(role.role)}</span></h3>
          <p>${escapeHtml(role.contribution)}</p>
          <h4>下一步</h4>
          <ul class="action-list"><li>${escapeHtml(role.next_step || "")}</li></ul>
        </article>
      `).join("")}
    </div>
    <h3>官方核验检索式</h3>
    <ul class="action-list">
      ${officialQueries.slice(0, 8).map((item) => `<li>${escapeHtml(item.query || "")}</li>`).join("")}
    </ul>
    <h3>视频与社媒学习检索</h3>
    <ul class="action-list">
      ${videoSearches.slice(0, 8).map((item) => `<li>${escapeHtml(item.platform || "")}: <a href="${escapeHtml(item.url || "#")}" target="_blank" rel="noreferrer">${escapeHtml(item.keyword || "")}</a></li>`).join("")}
    </ul>
    <h3>任务板</h3>
    <ul class="action-list">
      ${tasks.slice(0, 8).map((task) => `<li>${escapeHtml(task.title || task.task || "")}</li>`).join("")}
    </ul>
    <h3>阻断动作</h3>
    <ul class="risk-list">
      ${(boundary.blocked_actions || ["正式外联、报价、合同、付款、客户承诺、公开视频发布必须人工审批。"]).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
    <p class="meta">报告: ${escapeHtml(pack.report_path || "")}</p>
  `;
}

function qualityPayload() {
  return {
    question: qs("#qualityQuestion").value.trim(),
    v11: qs("#qualityV11Answer").value.trim(),
    doubao: qs("#qualityDoubaoAnswer").value.trim(),
    yuanbao: qs("#qualityYuanbaoAnswer").value.trim(),
  };
}

async function scoreQualityAnswer() {
  const payload = qualityPayload();
  if (!payload.question || !payload.v11) {
    setRuntime("请填写问题和 v11 回答", "warn");
    return;
  }
  qs("#qualityResult").innerHTML = `<p class="empty">正在评分 v11 回答...</p>`;
  try {
    const data = await api("/api/answers/score", {
      method: "POST",
      body: JSON.stringify({
        question: payload.question,
        answer: payload.v11,
        evidence: [{ source_type: "official", url: "desktop-quality-review" }],
      }),
    });
    renderAnswerScore(data);
    setRuntime("答案评分完成", "ok");
  } catch (error) {
    qs("#qualityResult").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    if (error.payload?.license) applyLicenseGate(error.payload.license, false);
    setRuntime("答案评分失败", "danger");
  }
}

async function compareQualityAnswers() {
  const payload = qualityPayload();
  if (!payload.question || !payload.v11 || !payload.doubao || !payload.yuanbao) {
    setRuntime("请填写问题和三方回答", "warn");
    return;
  }
  qs("#qualityResult").innerHTML = `<p class="empty">正在对比 v11、豆包、元宝...</p>`;
  try {
    const data = await api("/api/benchmark/compare", {
      method: "POST",
      body: JSON.stringify({
        question: payload.question,
        answers: {
          v11: payload.v11,
          Doubao: payload.doubao,
          Yuanbao: payload.yuanbao,
        },
      }),
    });
    renderBenchmarkCompare(data);
    setRuntime("Benchmark 对比完成", "ok");
  } catch (error) {
    qs("#qualityResult").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    if (error.payload?.license) applyLicenseGate(error.payload.license, false);
    setRuntime("Benchmark 对比失败", "danger");
  }
}

async function buildKnowledgeBase() {
  qs("#qualityResult").innerHTML = `<p class="empty">正在建立行业知识库：国际贸易、EPC、招商、科研、视频、政治风险、海关信息...</p>`;
  try {
    const data = await api("/api/knowledge/build", {
      method: "POST",
      body: "{}",
    });
    renderKnowledgeBuild(data);
    await loadStatus();
    setRuntime("行业知识库已建立", "ok");
  } catch (error) {
    qs("#qualityResult").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    if (error.payload?.license) applyLicenseGate(error.payload.license, false);
    setRuntime("知识库建立失败", "danger");
  }
}

async function buildBenchmarkSet() {
  qs("#qualityResult").innerHTML = `<p class="empty">正在建立 v11 50 题 Benchmark，用于对比 v11、豆包、元宝...</p>`;
  try {
    const data = await api("/api/benchmark/build", {
      method: "POST",
      body: "{}",
    });
    renderBenchmarkBuild(data);
    await loadStatus();
    setRuntime("Benchmark 已建立", "ok");
  } catch (error) {
    qs("#qualityResult").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    if (error.payload?.license) applyLicenseGate(error.payload.license, false);
    setRuntime("Benchmark 建立失败", "danger");
  }
}

function renderKnowledgeBuild(data = {}) {
  const domains = data.data?.domains || {};
  qs("#qualityResult").innerHTML = `
    <h3>行业知识库已建立</h3>
    <p class="meta">文件: ${escapeHtml(data.path || "")}</p>
    <div class="pipeline-grid">
      ${Object.entries(domains).map(([key, domain]) => `
        <div class="pipeline-card">
          <span>${escapeHtml(domain.label || key)}</span>
          <strong>${escapeHtml((domain.topics || []).length)} 项主题</strong>
          <p>${escapeHtml(domain.role || "")}</p>
        </div>
      `).join("")}
    </div>
    <h3>运行规则</h3>
    <ul class="risk-list">
      ${(data.data?.operating_rule || []).map((rule) => `<li>${escapeHtml(rule)}</li>`).join("")}
    </ul>
  `;
}

function renderBenchmarkBuild(data = {}) {
  const questions = data.data?.questions || [];
  qs("#qualityResult").innerHTML = `
    <h3>v11 Benchmark 已建立</h3>
    <p class="meta">题数: ${escapeHtml(data.data?.question_count ?? questions.length)} / 文件: ${escapeHtml(data.path || "")}</p>
    <p class="meta">${escapeHtml(data.data?.winner_rule || "")}</p>
    <div class="team-role-list">
      ${questions.slice(0, 10).map((item) => `
        <article class="source-panel">
          <h3>${escapeHtml(item.id)} <span class="badge">${escapeHtml(item.domain)}</span></h3>
          <p>${escapeHtml(item.question)}</p>
        </article>
      `).join("")}
    </div>
  `;
}

function renderAnswerScore(data = {}) {
  const dimensions = data.dimensions || {};
  qs("#qualityResult").innerHTML = `
    <h3>答案评分</h3>
    <p class="meta">总分: ${escapeHtml(data.overall_score ?? 0)} / 结论: ${escapeHtml(data.verdict || "unknown")}</p>
    <div class="pipeline-grid">
      ${Object.entries(dimensions).map(([key, item]) => `
        <div class="pipeline-card">
          <span>${escapeHtml(item.label || key)}</span>
          <strong>${escapeHtml(item.score ?? 0)}</strong>
          <p>${escapeHtml((item.hits || []).join(", ") || "缺少关键词命中")}</p>
        </div>
      `).join("")}
    </div>
    <h3>改进建议</h3>
    <ul class="action-list">
      ${(data.recommendations || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
  `;
}

function renderBenchmarkCompare(data = {}) {
  const ranked = data.ranked || [];
  const scores = data.scores || {};
  qs("#qualityResult").innerHTML = `
    <h3>三方 Benchmark 对比</h3>
    <p class="meta">${escapeHtml(data.rule || "更高分代表证据、执行、风险边界和专业深度更强。")}</p>
    <div class="pipeline-grid">
      ${ranked.map((item, index) => `
        <div class="pipeline-card ${index === 0 ? "winner-card" : ""}">
          <span>第 ${index + 1} 名</span>
          <strong>${escapeHtml(item.name)}</strong>
          <p>${escapeHtml(item.score)} / ${escapeHtml(item.verdict)}</p>
        </div>
      `).join("")}
    </div>
    ${Object.entries(scores).map(([name, score]) => `
      <article class="source-panel">
        <h3>${escapeHtml(name)} <span class="badge">${escapeHtml(score.overall_score ?? 0)}</span></h3>
        <div class="evidence-grid">
          ${Object.entries(score.dimensions || {}).map(([key, item]) => `
            <div class="evidence-tile">
              <span>${escapeHtml(item.label || key)}</span>
              <strong>${escapeHtml(item.score ?? 0)}</strong>
            </div>
          `).join("")}
        </div>
      </article>
    `).join("")}
  `;
}

function communicationPayload() {
  return {
    channel: qs("#communicationChannel").value,
    recipient: qs("#communicationRecipient").value.trim() || "partner",
    audience: qs("#communicationAudience").value,
    message: qs("#communicationMessage").value.trim(),
    authorization: { scope: "draft_only" },
    evidence: [],
  };
}

async function analyzeCommunication() {
  const payload = communicationPayload();
  if (!payload.message) {
    setRuntime("请填写对方消息", "warn");
    return;
  }
  qs("#communicationResult").innerHTML = `<p class="empty">正在分析沟通风险...</p>`;
  try {
    const data = await api("/api/social/analyze", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderCommunicationAssessment(data);
    setRuntime("沟通风险分析完成", data.needs_human_approval ? "warn" : "ok");
  } catch (error) {
    qs("#communicationResult").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    if (error.payload?.license) applyLicenseGate(error.payload.license, false);
    setRuntime("沟通分析失败", "danger");
  }
}

async function draftCommunication() {
  const payload = communicationPayload();
  if (!payload.message) {
    setRuntime("请填写对方消息", "warn");
    return;
  }
  qs("#communicationResult").innerHTML = `<p class="empty">正在生成回复草稿和审批包...</p>`;
  try {
    const data = await api("/api/social/reply-draft", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderCommunicationDraft(data);
    setRuntime("沟通草稿已生成", "ok");
  } catch (error) {
    qs("#communicationResult").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    if (error.payload?.license) applyLicenseGate(error.payload.license, false);
    setRuntime("沟通草稿失败", "danger");
  }
}

function renderCommunicationAssessment(data = {}) {
  qs("#communicationResult").innerHTML = `
    <h3>沟通风险判断</h3>
    <p class="meta">动作: ${escapeHtml(data.action || "draft_only")} / 风险: ${escapeHtml(data.risk_level || "unknown")} / 置信度: ${escapeHtml(data.confidence ?? 0)}</p>
    <div class="pipeline-grid">
      <div class="pipeline-card">
        <span>人工审批</span>
        <strong>${data.needs_human_approval ? "需要" : "未触发"}</strong>
        <p>${escapeHtml(data.boundary || "")}</p>
      </div>
      <div class="pipeline-card">
        <span>官方证据</span>
        <strong>${escapeHtml(data.official_evidence_count ?? 0)}</strong>
        <p>事实性项目回复必须有官方、海关、采购或企业证据。</p>
      </div>
      <div class="pipeline-card">
        <span>渠道语气</span>
        <strong>${escapeHtml(qs("#communicationChannel").selectedOptions[0]?.textContent || "")}</strong>
        <p>${escapeHtml(data.tone || "")}</p>
      </div>
    </div>
    <h3>原因</h3>
    <ul class="risk-list">
      ${(data.reasons || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
  `;
}

function renderCommunicationDraft(data = {}) {
  const assessment = data.assessment || {};
  const review = data.internal_review || {};
  qs("#communicationResult").innerHTML = `
    <h3>回复草稿与审批包</h3>
    <p class="meta">sent: ${escapeHtml(String(data.sent))} / 动作: ${escapeHtml(assessment.action || "draft_only")} / 风险: ${escapeHtml(assessment.risk_level || "unknown")}</p>
    <div class="pipeline-grid">
      <div class="pipeline-card">
        <span>人工审批</span>
        <strong>${assessment.needs_human_approval ? "需要" : "未触发"}</strong>
        <p>${escapeHtml(assessment.boundary || "")}</p>
      </div>
      <div class="pipeline-card">
        <span>草稿文件</span>
        <strong>${data.draft_path ? "已保存" : "未保存"}</strong>
        <p>${escapeHtml(data.draft_path || "")}</p>
      </div>
    </div>
    <h3>团队内部判断</h3>
    <ul class="action-list">
      ${(review.team_judgment || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
    <h3>审批清单</h3>
    <ul class="risk-list">
      ${(data.approval_checklist || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
    <h3>草稿内容</h3>
    <pre class="report-surface">${escapeHtml(data.draft?.message || "")}</pre>
  `;
}

function renderApprovals() {
  const waiting = state.approvals.filter((item) => item.status === "waiting");
  const missionWaiting = state.mission?.command_center?.waiting_for_owner;
  qs("#approvalCount").textContent = String(missionWaiting ?? waiting.length);
  if (!waiting.length) {
    qs("#approvalList").innerHTML = `<p class="empty">暂无本地待审批事项。云端重大事项请看作战指挥台和老板收件箱。</p>`;
    return;
  }
  qs("#approvalList").innerHTML = waiting.map((item) => `
    <article class="approval-item" data-approval="${escapeHtml(item.id)}" data-decision="${escapeHtml(item.decisionId)}">
      <h3>${escapeHtml(item.question)}<span class="badge">等待人工</span></h3>
      <p class="muted">${escapeHtml(item.recommendation || "请复核后决定。")}</p>
      <div class="approval-actions">
        <input class="approval-reply" placeholder="填写 /approve、/reject 或 /revise 的理由">
        <button class="primary-command approve-btn core-action">批准</button>
        <button class="danger-outline reject-btn core-action">驳回</button>
      </div>
    </article>
  `).join("");
  applyLicenseGate(state.cloud?.license || {}, state.licenseAllowed);
}

async function submitApproval(button, accepted) {
  const item = button.closest(".approval-item");
  const reply = qs(".approval-reply", item).value.trim();
  if (!reply) {
    setRuntime("请填写审批意见", "warn");
    return;
  }
  try {
    await api("/api/feedback", {
      method: "POST",
      body: JSON.stringify({
        approvalId: item.dataset.approval,
        decisionId: item.dataset.decision,
        reply,
        notes: reply,
        accepted,
      }),
    });
    await loadStatus();
    setRuntime("审批已记录", "ok");
  } catch (error) {
    setRuntime(error.message, "danger");
  }
}

function diagnosticItems() {
  const cloud = state.cloud || {};
  const license = cloud.license || {};
  const inbox = qs("#ownerInbox")?.textContent || "";
  const mission = state.mission || {};
  return [
    ["v11 主干", "global-intelligence-v11 已设为主仓库，旧平台只作为能力来源。", true],
    ["授权保护", license.status ? `当前状态: ${licenseLabel(license)}` : "等待授权状态。", state.licenseAllowed],
    ["作战指挥台", mission.status ? `已生成: ${mission.status}` : "等待 Mission Control 数据。", Boolean(mission.status)],
    ["搜索增强", "搜索入口包含 Bing、Google、Yandex、中亚、社交、学术、图书馆和视频线索。", true],
    ["团队答复", "六角色团队答复包会同时生成结论、证据计划、招商判断、视频计划、任务板和审批边界。", true],
    ["项目执行包", "项目线索可进入搜索计划、项目库、行动板、可行性草稿和审批边界。", true],
    ["质量评测", "答案可按准确性、证据、可执行性、风险判断、专业深度评分，并对比 v11、豆包、元宝。", true],
    ["沟通草稿", "微信、企微、飞书、邮件和社媒只生成草稿与审批包，不自动发送。", true],
    ["审批边界", "合同、报价、付款、发布、客户承诺必须人工审批。", true],
    ["老板收件箱", inbox ? "已读取老板收件箱。" : "暂无收件箱内容。", true],
    ["云端验收", cloud.cloudAcceptance || cloud.cloudRun ? "已读取云端验收文件。" : "等待云端验收报告。", Boolean(cloud.cloudAcceptance || cloud.cloudRun)],
  ];
}

function renderDiagnostics() {
  qs("#diagnosticGrid").innerHTML = diagnosticItems().map(([title, detail, ok]) => `
    <article class="diagnostic-item">
      <h3>${escapeHtml(title)}<span class="badge">${ok ? "OK" : "待处理"}</span></h3>
      <p class="muted">${escapeHtml(detail)}</p>
    </article>
  `).join("");
}

document.addEventListener("click", (event) => {
  const nav = event.target.closest(".nav-item");
  if (nav) switchView(nav.dataset.view);
  if (event.target.id === "refreshAllBtn" || event.target.id === "refreshInboxBtn" || event.target.id === "refreshApprovalBtn") loadStatus();
  if (event.target.id === "refreshProjectLibraryBtn") loadProjectLibrary(true);
  if (event.target.id === "cloudCheckBtn") runCloudCommand("/api/cloud/check", "云端检查");
  if (event.target.id === "cloudRunBtn") runCloudCommand("/api/cloud/run", "云端验收");
  if (event.target.id === "searchBtn") doSearch();
  if (event.target.id === "buildBriefingBtn") buildBriefing();
  if (event.target.id === "verifyEvidenceBtn") verifyEvidence();
  if (event.target.id === "analyzeProjectBtn") analyzeProject();
  if (event.target.id === "buildPipelineBtn") buildProjectPipeline();
  if (event.target.id === "buildTeamExecutionBtn") buildTeamExecution();
  if (event.target.id === "buildWarRoomBtn") buildWarRoom();
  if (event.target.id === "loadWarRoomQueueBtn") loadWarRoomExecutionQueue();
  if (event.target.id === "buildTeamResponseBtn") buildTeamResponse();
  if (event.target.id === "buildVideoCenterBtn") buildVideoCenter();
  if (event.target.id === "buildKnowledgeBtn") buildKnowledgeBase();
  if (event.target.id === "buildBenchmarkBtn") buildBenchmarkSet();
  if (event.target.id === "scoreAnswerBtn") scoreQualityAnswer();
  if (event.target.id === "compareAnswersBtn") compareQualityAnswers();
  if (event.target.id === "analyzeCommunicationBtn") analyzeCommunication();
  if (event.target.id === "draftCommunicationBtn") draftCommunication();
  if (event.target.id === "selfCheckBtn") {
    renderDiagnostics();
    setRuntime("AI 自检完成", "ok");
  }
  if (event.target.classList.contains("approve-btn")) submitApproval(event.target, true);
  if (event.target.classList.contains("reject-btn")) submitApproval(event.target, false);
});

loadStatus();



