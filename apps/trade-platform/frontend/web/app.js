const modules = [
  {
    title: "矿山与重工",
    desc: "矿山开采、破碎筛分、输送港口、冶炼辅助和EPC设备包。",
    result: "技术方案草稿",
  },
  {
    title: "现货贸易",
    desc: "库存设备、备件、快速询价和可交付资源整理。",
    result: "询价清单",
  },
  {
    title: "易货贸易",
    desc: "设备、商品、产能资源互换，支持差额结算的前置评估。",
    result: "等价性预审",
  },
  {
    title: "招商引资",
    desc: "国家、地方、园区项目包装，面向投资人与制造企业推荐。",
    result: "招商报告",
  },
  {
    title: "全球动态",
    desc: "政策、价格、航运、地缘风险和行业新闻的情报简报。",
    result: "市场简报",
  },
  {
    title: "机器人与无人机",
    desc: "工业、农业、安防、巡检和测绘场景的方案组合。",
    result: "应用方案",
  },
  {
    title: "大型项目对接",
    desc: "政府、央企、跨国项目库，合作方资质与联合体建议。",
    result: "合作建议书",
  },
  {
    title: "加工与备件",
    desc: "图纸、样件、非标件、易损件和长期备件供应。",
    result: "审图问题表",
  },
];

const equipment = [
  {
    category: "mining",
    code: "EX",
    name: "露天矿挖装与运输设备",
    desc: "面向铁矿、铜矿、煤矿、石灰石矿等露天采剥场景，适合新矿建设和存量矿山扩产。",
    specs: [
      ["适用客户", "矿山业主 / 承包商"],
      ["合作方式", "整机 + 备件 + 培训"],
      ["平台输出", "工况确认表"],
    ],
  },
  {
    category: "crushing",
    code: "CR",
    name: "破碎筛分成套生产线",
    desc: "覆盖粗碎、中碎、细碎、筛分、给料和输送，可用于采选前段与砂石骨料项目。",
    specs: [
      ["核心资料", "物料 / 产能 / 粒度"],
      ["合作方式", "设备包 / EPC"],
      ["平台输出", "产线配置草案"],
    ],
  },
  {
    category: "handling",
    code: "BC",
    name: "长距离皮带输送系统",
    desc: "适合矿山、港口、料场和电厂的散料转运，支持节能、除尘和自动控制方案。",
    specs: [
      ["适用场景", "矿区 / 港口 / 料场"],
      ["合作方式", "设计 + 供货 + 安装"],
      ["平台输出", "EPC边界清单"],
    ],
  },
  {
    category: "handling",
    code: "ST",
    name: "堆取料机与码头装卸",
    desc: "服务散货码头、钢厂、电厂和大型仓储基地，适合港口物流现代化项目。",
    specs: [
      ["关键参数", "吞吐量 / 轨距 / 料种"],
      ["合作方式", "改造 / 新建"],
      ["平台输出", "风险问题清单"],
    ],
  },
  {
    category: "mining",
    code: "DR",
    name: "钻机、铲装与辅助设备",
    desc: "提供矿山前端施工设备组合，支持不同国家工况、维护能力和备件周期评估。",
    specs: [
      ["关注重点", "维护 / 油耗 / 备件"],
      ["合作方式", "单机 / 批量采购"],
      ["平台输出", "采购对比表"],
    ],
  },
  {
    category: "parts",
    code: "SP",
    name: "非标备件与来料加工",
    desc: "支持图纸、样件、材料牌号、尺寸公差和交期要求，适合长期运维备件供应。",
    specs: [
      ["输入资料", "图纸 / 样件 / 材料"],
      ["合作方式", "定制加工"],
      ["平台输出", "审图问题表"],
    ],
  },
];

const moduleGrid = document.querySelector("#moduleGrid");
const equipmentList = document.querySelector("#equipmentList");
const filterButtons = document.querySelectorAll(".filter-button");
const draftButton = document.querySelector("#draftButton");
const draftOutput = document.querySelector("#draftOutput");
const needType = document.querySelector("#needType");
const countryInput = document.querySelector("#countryInput");
const contactInput = document.querySelector("#contactInput");
const requirementInput = document.querySelector("#requirementInput");
const filmFrame = document.querySelector(".film-frame");

function renderModules() {
  moduleGrid.innerHTML = modules
    .map(
      (item, index) => `
        <article class="module-card">
          <span>${String(index + 1).padStart(2, "0")}</span>
          <h3>${item.title}</h3>
          <p>${item.desc}</p>
          <strong>可交付：${item.result}</strong>
        </article>
      `,
    )
    .join("");
}

function renderEquipment(filter = "all") {
  const items = filter === "all" ? equipment : equipment.filter((item) => item.category === filter);
  equipmentList.innerHTML = items
    .map(
      (item) => `
        <article class="equipment-card">
          <div class="equipment-top">
            <div>
              <h3>${item.name}</h3>
              <p>${item.desc}</p>
            </div>
            <span class="equipment-icon">${item.code}</span>
          </div>
          <ul class="spec-list">
            ${item.specs.map(([label, value]) => `<li><span>${label}</span><strong>${value}</strong></li>`).join("")}
          </ul>
        </article>
      `,
    )
    .join("");
}

function buildDraft() {
  const type = needType.value;
  const country = countryInput.value.trim() || "未填写";
  const contact = contactInput.value.trim() || "未填写";
  const requirement = requirementInput.value.trim() || "未填写具体需求";
  const risk = /合同|报价|付款|交期|政府|融资|制裁|出口/i.test(requirement) ? "高" : "中";
  const nextStep =
    risk === "高"
      ? "进入人工复核，确认价格、合同、交期、合规或政府项目边界后再对外回复。"
      : "补充产能、物料、现场条件、预算范围和期望交付方式后，可生成初步方案。";

  return [
    "AI预审草稿（DRAFT，仅供内部跟进）",
    `需求类型：${type}`,
    `目标国家 / 地区：${country}`,
    `联系人：${contact}`,
    `需求摘要：${requirement}`,
    `初步风险：${risk}`,
    "建议角色：国际工程贸易风控官",
    `下一步：${nextStep}`,
  ].join("\n");
}

filterButtons.forEach((button) => {
  button.addEventListener("click", () => {
    filterButtons.forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    renderEquipment(button.dataset.filter);
    setupReveal();
  });
});

draftButton.addEventListener("click", () => {
  draftOutput.classList.add("visible");
  draftOutput.value = buildDraft();
});

const canAnimateScene = window.matchMedia("(prefers-reduced-motion: no-preference)").matches;

if (filmFrame && canAnimateScene) {
  window.addEventListener("mousemove", (event) => {
    const x = (event.clientX / window.innerWidth - 0.5) * 8;
    const y = (event.clientY / window.innerHeight - 0.5) * 5;
    filmFrame.style.transform = `rotateY(${x - 8}deg) rotateX(${2 - y}deg)`;
  });
}

const observer =
  "IntersectionObserver" in window
    ? new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-visible");
              observer.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.14 },
      )
    : null;

function setupReveal() {
  const revealItems = document.querySelectorAll(".scene-card, .module-card, .equipment-card, .project-grid article");
  revealItems.forEach((item) => {
    item.classList.add("reveal-item");
    if (observer) {
      observer.observe(item);
    } else {
      item.classList.add("is-visible");
    }
  });
}

renderModules();
renderEquipment();
setupReveal();
