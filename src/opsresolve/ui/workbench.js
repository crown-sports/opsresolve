"use strict";

const translations = {
  zh: {
    traceTools: "调用追踪分析",
    importTraces: "导入 OTLP JSON",
    labTraces: "分析实验的真实调用记录",
    traceTitle: "历史调用追踪",
    traceHint:
      "根据已记录的调用树定位错误起点候选，区分下游错误和传播到入口的错误。",
    traces: "追踪",
    spans: "调用片段",
    failedTraces: "含错误的追踪",
    origins: "记录中的错误起点候选",
    traceLimits:
      "这些候选依据历史记录，不能证明当前故障仍存在。缺失的埋点可能隐藏更深的原因。独占耗时扣除同一服务子调用的重叠区间，不等同于 CPU 时间或分布式关键路径。",
    operations: "服务与操作",
    exclusive: "累计独占耗时",
    traceFileTooLarge: "追踪文件不能超过 5 MiB",
    planExpired: "方案已过期，请重新诊断后再应用。",
    targets: "应用",
    addTarget: "＋ 检查自己的服务",
    realLab: "真实故障实验",
    labHint: "五个服务进程、真实依赖调用与 SQLite 查询。",
    scenario: "故障场景",
    inject: "载入场景",
    restart: "尝试仅重启进程",
    history: "最近的调查",
    local: "本地运行 · 数据保留在本机",
    workspace: "故障工作台",
    eyebrow: "FROM FAILURE TO VERIFIED RECOVERY",
    headline: "把故障定位到可以验证的改动。",
    intro: "检查服务 → 找出原因 → 审阅改动 → 验证恢复。每一步都有真实证据。",
    budget: "检查预算",
    diagnose: "开始诊断 ↗",
    cancel: "停止调查",
    entry: "入口业务请求",
    notChecked: "未检查",
    causes: "最小解释中的故障",
    noGuess: "证据不足时保留备选解释",
    probeCost: "已使用检查成本",
    costHint: "按信息价值与声明成本选择检查",
    recovery: "恢复后的业务检查",
    recoveryHint: "全部服务检查两轮后才标记恢复",
    dependencyMap: "服务与依赖",
    liveChecks: "实时检查",
    ok: "通过",
    failure: "失败",
    drift: "配置偏差",
    unknown: "未知",
    mapHint: "点击服务查看证据",
    diagnosis: "诊断与下一步",
    apply: "应用方案并验证恢复",
    explain: "生成 AI 解释",
    download: "下载事件报告 ↓",
    timeline: "调查过程",
    changes: "具体改动",
    evidence: "原始证据",
    recoveryTab: "恢复验证",
    scope: "HTTP 检查与声明的 JSON 配置契约 · 不执行任意 Shell 命令",
    ownService: "检查自己的应用",
    setupHint: "输入 URL 可以检查单个服务；添加依赖清单可以定位跨服务故障。",
    applicationName: "应用名称",
    advanced: "使用依赖清单（JSON）",
    manifestHint:
      "读取本机配置时，以 opsresolve serve --target target.json 添加应用。网页导入的配置文件默认不可读。",
    connect: "添加并开始使用",
    initialNotice:
      "当前实验已注入两个持久配置错误。开始诊断后可审阅精确改动，再验证真实恢复。",
    realNotice:
      "单个 URL 支持端点排查；依赖清单与配置契约支持跨服务定位和修复。",
    healthy: "业务检查通过",
    diagnosed: "解释已收敛",
    needs_evidence: "需要更多证据",
    model_conflict: "模型与事实冲突",
    probing: "正在调查",
    queued: "等待调查",
    verified: "恢复已验证",
    rolled_back: "验证失败 · 已回滚",
    manual_recovery: "需要人工恢复",
    refused: "改动已拒绝",
    cancelled: "调查已停止",
    failed: "调查失败",
    validating: "正在验证恢复",
    empty: "选择应用并开始诊断。",
    emptyDetail: "真实检查、证据与改动会显示在这里。",
    configFault: "配置与声明意图不符",
    localFault: "服务本身返回业务错误",
    unavailableFault: "服务端点无法连接",
    affected: "影响服务",
    provisional: "最小解释基于声明的依赖模型，恢复前仍需通过实际改动验证。",
    ambiguous: "仍有多种解释。增加检查预算、补充配置契约或检查未获取的证据。",
    conflict:
      "现有故障模型无法解释全部观测。请检查依赖声明、超时或模型未覆盖的问题。",
    verifiedNotice:
      "精确改动后，全部服务的两轮业务请求均通过。恢复结果已写入事件报告。",
    rollbackNotice:
      "恢复验证未通过，已恢复本次修改前的配置。请继续调查剩余故障。",
    manualNotice: "外部修改与回滚冲突。请依据备份和事件报告完成恢复。",
    waitingRecovery: "尚未应用修复方案。",
    waitingChanges: "完成诊断后，符合条件的配置改动会显示在这里。",
    setting: "配置字段",
    before: "当前值",
    after: "目标值",
    evidenceLabel: "证据",
    check: "检查",
    outcome: "结果",
    candidates: "可行故障组合",
    time: "耗时",
    business: "业务请求",
    liveness: "存活检查",
    config: "配置契约",
    round: "轮次",
    clear: "显示全部",
    costUnits: "声明成本单位；不等同于实际耗时",
    modelRejected: "AI 解释未通过证据校验",
    modelChecked: "AI 解释 · 引用已校验",
    readOnly:
      "当前应用仅诊断。服务器以 --allow-repair 启动后才可修改已授权的配置字段。",
    injectDone: "故障已载入。请开始一次新调查。",
    restartDone: "进程已重启，持久配置保持当前值。开始诊断可查看是否恢复。",
    busy: "应用正在执行操作",
    cancelDone: "已请求停止，当前检查将在超时内结束。",
    unknownHint: "有检查未获得有效结果，不应视为正常。",
    seconds: "秒",
    singleUrl: "单个 URL 仅能定位端点异常。进一步定位需要依赖关系与配置契约。",
  },
  en: {
    traceTools: "TRACE INVESTIGATION",
    importTraces: "Import OTLP JSON",
    labTraces: "Analyze actual lab traces",
    traceTitle: "Historical call traces",
    traceHint:
      "Inspect recorded origin candidates and separate downstream failures from propagated errors.",
    traces: "Traces",
    spans: "Spans",
    failedTraces: "Traces with errors",
    origins: "Recorded origin candidates",
    traceLimits:
      "Candidates reflect historical records, not current fault presence. Missing instrumentation can hide deeper causes. Exclusive time subtracts overlapping same-service child intervals; it is not CPU time or a distributed critical path.",
    operations: "Services & operations",
    exclusive: "Total exclusive duration",
    traceFileTooLarge: "Trace exports must be at most 5 MiB",
    planExpired: "Plan expired. Investigate again before applying changes.",
    targets: "APPLICATIONS",
    addTarget: "＋ Connect your service",
    realLab: "LIVE FAILURE LAB",
    labHint:
      "Five service processes, real dependency calls, and SQLite queries.",
    scenario: "Failure scenario",
    inject: "Load scenario",
    restart: "Try restarting processes only",
    history: "RECENT INVESTIGATIONS",
    local: "Local · Your data stays here",
    workspace: "Incident workbench",
    eyebrow: "FROM FAILURE TO VERIFIED RECOVERY",
    headline: "Turn an outage into a verified change.",
    intro:
      "Check services → identify causes → review changes → test recovery. Evidence at every step.",
    budget: "Probe budget",
    diagnose: "Investigate ↗",
    cancel: "Stop investigation",
    entry: "Entry business request",
    notChecked: "Not checked",
    causes: "Faults in minimum explanation",
    noGuess: "Alternatives remain when evidence is incomplete",
    probeCost: "Investigation cost used",
    costHint: "Choose checks by information per declared cost",
    recovery: "Business checks after repair",
    recoveryHint: "All services checked twice before recovery is verified",
    dependencyMap: "Services & dependencies",
    liveChecks: "Live checks",
    ok: "Passed",
    failure: "Failed",
    drift: "Config drift",
    unknown: "Unknown",
    mapHint: "Select a service to inspect evidence",
    diagnosis: "Diagnosis & next action",
    apply: "Apply plan & verify recovery",
    explain: "Generate AI explanation",
    download: "Download incident report ↓",
    timeline: "Investigation",
    changes: "Exact changes",
    evidence: "Evidence",
    recoveryTab: "Recovery checks",
    scope:
      "HTTP checks & declared JSON contracts · No arbitrary shell execution",
    ownService: "Connect your application",
    setupHint:
      "A URL enables endpoint triage. A dependency manifest enables service diagnosis.",
    applicationName: "Application name",
    advanced: "Use a dependency manifest (JSON)",
    manifestHint:
      "For local configuration access, register with opsresolve serve --target target.json. Browser-imported files are not available by default.",
    connect: "Connect application",
    initialNotice:
      "Two persistent configuration faults are loaded. Investigate, review the precise changes, then test actual recovery.",
    realNotice:
      "A URL enables endpoint triage. Dependencies and configuration contracts enable deeper diagnosis and repair.",
    healthy: "Business check passed",
    diagnosed: "Explanation converged",
    needs_evidence: "More evidence needed",
    model_conflict: "Model conflicts with facts",
    probing: "Investigating",
    queued: "Investigation queued",
    verified: "Recovery verified",
    rolled_back: "Validation failed · rolled back",
    manual_recovery: "Manual recovery needed",
    refused: "Change refused",
    cancelled: "Investigation stopped",
    failed: "Investigation failed",
    validating: "Testing recovery",
    empty: "Select an application and investigate.",
    emptyDetail: "Real checks, evidence, and changes appear here.",
    configFault: "Configuration differs from declared intent",
    localFault: "Local application request fails",
    unavailableFault: "Service endpoint cannot be reached",
    affected: "Affected services",
    provisional:
      "Minimum explanations depend on the declared model. An intervention must establish actual recovery.",
    ambiguous:
      "Multiple explanations remain. Increase the budget, add configuration contracts, or obtain missing evidence.",
    conflict:
      "The fault catalog cannot explain all observations. Check dependency assumptions, timeouts, or unmodeled faults.",
    verifiedNotice:
      "After precise changes, every service passed both rounds of business requests. Recovery is recorded in the report.",
    rollbackNotice:
      "Recovery validation failed. Original configuration bytes were restored. Investigate the remaining fault.",
    manualNotice:
      "External changes conflict with rollback. Use the backups and report to complete recovery.",
    waitingRecovery: "The repair plan has not been applied.",
    waitingChanges:
      "Eligible configuration changes appear after investigation.",
    setting: "Configuration field",
    before: "Current value",
    after: "Intended value",
    evidenceLabel: "Evidence",
    check: "Check",
    outcome: "Result",
    candidates: "Feasible fault sets",
    time: "Time",
    business: "Business request",
    liveness: "Liveness",
    config: "Configuration contract",
    round: "Round",
    clear: "Show all",
    costUnits: "Declared cost units; distinct from elapsed time",
    modelRejected: "AI explanation failed evidence validation",
    modelChecked: "AI explanation · references checked",
    readOnly:
      "Diagnosis only. Start the server with --allow-repair to enable owner-declared configuration changes.",
    injectDone: "Failure loaded. Start a new investigation.",
    restartDone:
      "Owned processes restarted with persisted configuration intact. Investigate to test recovery.",
    busy: "This application has an active operation",
    cancelDone:
      "Stop requested; the current check finishes within its timeout.",
    unknownHint:
      "Some checks produced no known result; they do not establish health.",
    seconds: "seconds",
    singleUrl:
      "A single URL localizes an endpoint problem. Dependencies and configuration contracts enable further diagnosis.",
  },
};
const state = {
  lang: localStorage.getItem("opsresolve-language") || "zh",
  targets: [],
  selected: null,
  incident: null,
  bootstrap: null,
  tab: "timeline",
  serviceFilter: null,
  pending: false,
  history: [],
};
const byId = (id) => document.getElementById(id);
const t = (key) => translations[state.lang][key] || key;
const node = (tag, cls, text) => {
  const element = document.createElement(tag);
  if (cls) element.className = cls;
  if (text !== undefined) element.textContent = String(text);
  return element;
};
const svgNode = (tag, attributes, text) => {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attributes || {}))
    element.setAttribute(key, String(value));
  if (text !== undefined) element.textContent = text;
  return element;
};
const selected = () =>
  state.targets.find((item) => item.id === state.selected) ||
  (state.incident?.target_id === state.selected
    ? {
        id: state.selected,
        manifest: state.incident.target,
        managed_lab: false,
        busy: false,
        repair_enabled: false,
        historical: true,
      }
    : undefined);
let toastTimer;
function toast(message) {
  byId("toast").textContent = message;
  byId("toast").classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => byId("toast").classList.add("hidden"), 6500);
}
async function api(path, value) {
  const options = { headers: {} };
  if (value !== undefined) {
    options.method = "POST";
    options.headers = {
      "Content-Type": "application/json",
      "X-OpsResolve-CSRF": state.bootstrap.csrf,
    };
    options.body = JSON.stringify(value);
  }
  const response = await fetch(path, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || "Request failed");
  return result;
}
function translate() {
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
  for (const element of document.querySelectorAll("[data-i18n]"))
    element.textContent = t(element.dataset.i18n);
  byId("language").textContent = state.lang === "zh" ? "English" : "中文";
}
function badge(outcome) {
  const color =
    outcome === "ok" || outcome === "verified" || outcome === "healthy"
      ? "good"
      : outcome === "drift" || outcome === "diagnosed"
        ? "drift"
        : [
              "failure",
              "unreachable",
              "model_conflict",
              "manual_recovery",
              "rolled_back",
              "failed",
            ].includes(outcome)
          ? "bad"
          : "muted";
  return node(
    "span",
    "tag " + color,
    t(outcome === "unreachable" ? "failure" : outcome),
  );
}
function outcomeFor(service) {
  const record = state.incident;
  if (!record) return "notChecked";
  const recovery = record.repair?.checks?.filter(
    (item) => item.subject === service,
  );
  if (recovery?.length) return recovery.at(-1).outcome;
  const direct = record.observations
    .filter((item) => item.probe_id === "http/" + service)
    .at(-1);
  if (direct) return direct.outcome;
  const drift = record.observations.find(
    (item) =>
      item.outcome === "drift" &&
      record.target.bindings.find((binding) => binding.id === item.subject)
        ?.service === service,
  );
  return drift ? "drift" : "notChecked";
}
function renderTargets() {
  const container = byId("targets");
  container.replaceChildren();
  for (const item of state.targets) {
    const button = node(
      "button",
      "target-button" + (item.id === state.selected ? " active" : ""),
      item.manifest.name,
    );
    button.append(
      node(
        "small",
        "",
        item.managed_lab
          ? "LIVE LAB · 5 SERVICES"
          : item.manifest.services.length + " SERVICES · HTTP",
      ),
    );
    button.onclick = () => selectTarget(item.id);
    container.append(button);
  }
  byId("lab-controls").classList.toggle(
    "hidden",
    !state.bootstrap?.lab_available,
  );
}
function renderGraph() {
  const item = selected();
  const container = byId("topology");
  container.replaceChildren();
  if (!item) return;
  const manifest = item.manifest;
  const levels = new Map([[manifest.entry, 0]]);
  for (let i = 0; i < manifest.services.length; i++)
    for (const edge of manifest.dependencies)
      if (levels.has(edge.source))
        levels.set(
          edge.target,
          Math.max(levels.get(edge.target) || 0, levels.get(edge.source) + 1),
        );
  const maxLevel = Math.max(...levels.values(), 1);
  const groups = new Map();
  for (const service of manifest.services) {
    const level = levels.get(service.id) || 0;
    if (!groups.has(level)) groups.set(level, []);
    groups.get(level).push(service);
  }
  const width = Math.max(740, 192 * (maxLevel + 1));
  const height = 260;
  const positions = new Map();
  for (const [level, services] of groups)
    services.forEach((service, index) =>
      positions.set(service.id, {
        x: 88 + (level * (width - 176)) / maxLevel,
        y: (height * (index + 1)) / (services.length + 1),
      }),
    );
  const svg = svgNode("svg", {
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": t("dependencyMap"),
  });
  const defs = svgNode("defs");
  const marker = svgNode("marker", {
    id: "arrow",
    markerWidth: 6,
    markerHeight: 6,
    refX: 5,
    refY: 3,
    orient: "auto",
  });
  marker.append(svgNode("path", { d: "M0,0 L6,3 L0,6", fill: "#c4d0bd" }));
  defs.append(marker);
  svg.append(defs);
  for (const edge of manifest.dependencies) {
    const a = positions.get(edge.source),
      b = positions.get(edge.target);
    const start = a.x + 69,
      end = b.x - 77;
    svg.append(
      svgNode("path", {
        d: `M${start},${a.y} C${(start + end) / 2},${a.y} ${(start + end) / 2},${b.y} ${end},${b.y}`,
        fill: "none",
        stroke: "#d9e2d2",
        "stroke-width": 1.7,
        "marker-end": "url(#arrow)",
      }),
    );
  }
  const colors = {
    ok: ["#f0f8ef", "#bad8b4", "#33724c"],
    failure: ["#fff1ea", "#e6beaa", "#a45b3c"],
    unreachable: ["#fff1ea", "#e6beaa", "#a45b3c"],
    drift: ["#fff8e9", "#e5d29c", "#92732c"],
    unknown: ["#f3f5ed", "#d4decb", "#7b8e6d"],
    notChecked: ["#f7f9f3", "#dae3d2", "#8b9e7b"],
  };
  for (const service of manifest.services) {
    const pos = positions.get(service.id),
      outcome = outcomeFor(service.id),
      color = colors[outcome] || colors.notChecked;
    const group = svgNode("g", {
      class: "node",
      tabindex: 0,
      role: "button",
      "aria-label": service.name,
      transform: `translate(${pos.x - 70},${pos.y - 32})`,
    });
    group.append(
      svgNode("rect", {
        width: 140,
        height: 64,
        rx: 8,
        fill: color[0],
        stroke: color[1],
        "stroke-width": 1.2,
      }),
    );
    group.append(svgNode("circle", { cx: 15, cy: 20, r: 3.2, fill: color[2] }));
    group.append(
      svgNode(
        "text",
        { x: 26, y: 24, fill: "#456039", "font-size": 11, "font-weight": 550 },
        service.name.length > 17
          ? service.name.slice(0, 16) + "…"
          : service.name,
      ),
    );
    group.append(
      svgNode(
        "text",
        { x: 15, y: 47, fill: color[2], "font-size": 9 },
        t(outcome === "unreachable" ? "failure" : outcome),
      ),
    );
    const choose = () => {
      state.serviceFilter = service.id;
      state.tab = "evidence";
      renderDetails();
    };
    group.onclick = choose;
    group.onkeydown = (event) => {
      if (event.key === "Enter" || event.key === " ") choose();
    };
    svg.append(group);
  }
  container.append(svg);
}
function renderMetrics() {
  const record = state.incident;
  const item = selected();
  byId("target-name").textContent = item?.manifest.name || "—";
  const entry = item ? outcomeFor(item.manifest.entry) : "notChecked";
  const entryChecks = record?.repair?.checks?.filter(
    (check) => check.subject === item?.manifest.entry,
  );
  const observation =
    entryChecks?.at(-1) ||
    record?.observations.find(
      (check) => check.probe_id === "http/" + item?.manifest.entry,
    );
  byId("metric-entry").textContent = observation?.facts.status
    ? "HTTP " + observation.facts.status
    : entry === "notChecked"
      ? "—"
      : t(entry === "unreachable" ? "failure" : entry);
  byId("metric-entry").className =
    entry === "ok"
      ? "good"
      : ["failure", "unreachable"].includes(entry)
        ? "bad"
        : "";
  byId("entry-detail").textContent = observation ? t(entry) : t("notChecked");
  const worlds = record?.diagnosis?.explanations || [];
  byId("metric-causes").textContent =
    worlds.length === 1 ? worlds[0].length : "—";
  byId("cause-detail").textContent = record?.diagnosis
    ? t(record.diagnosis.state) +
      (worlds.length > 1 ? " · " + record.diagnosis.explanation_count : "")
    : t("noGuess");
  byId("metric-cost").replaceChildren(
    document.createTextNode(String(record?.spent || 0) + " "),
    node("em", "", "/ " + (record?.budget || byId("budget").value)),
  );
  byId("cost-detail").textContent = record
    ? record.steps.length +
      " " +
      t("check") +
      " · " +
      (record.duration_ms
        ? (record.duration_ms / 1000).toFixed(2) + " " + t("seconds")
        : t("probing"))
    : t("costHint");
  const checks = record?.repair?.checks || [];
  byId("metric-recovery").textContent = checks.length
    ? checks.filter((check) => check.outcome === "ok").length +
      " / " +
      checks.length
    : "—";
  byId("metric-recovery").className =
    record?.repair?.state === "verified" ? "good" : checks.length ? "bad" : "";
  byId("recovery-detail").textContent = record?.repair
    ? t(record.repair.state)
    : t("recoveryHint");
}
function renderDiagnosis() {
  const container = byId("diagnosis-content");
  container.replaceChildren();
  const record = state.incident;
  const item = selected();
  const status = record?.state || "notChecked";
  byId("diagnosis-state").replaceWith(
    Object.assign(badge(status), { id: "diagnosis-state" }),
  );
  byId("graph-state").replaceWith(
    Object.assign(badge(status), { id: "graph-state" }),
  );
  let notice = item?.managed_lab ? t("initialNotice") : t("realNotice");
  byId("notice").className = "notice";
  if (record?.repair?.state === "verified") {
    notice = t("verifiedNotice");
    byId("notice").classList.add("good");
  } else if (record?.repair?.state === "rolled_back") {
    notice = t("rollbackNotice");
    byId("notice").classList.add("bad");
  } else if (record?.repair?.state === "manual_recovery") {
    notice = t("manualNotice");
    byId("notice").classList.add("bad");
  } else if (record?.state === "model_conflict") {
    notice = t("conflict");
    byId("notice").classList.add("bad");
  } else if (record?.state === "needs_evidence") notice = t("ambiguous");
  byId("notice-text").textContent = notice;
  const faults = record?.diagnosis?.faults || [];
  if (!record) {
    const empty = node("div", "empty-state");
    empty.append(node("span", "empty-icon", "⌁"), node("span", "", t("empty")));
    container.append(empty);
  } else if (!faults.length) {
    container.append(node("p", "model-note", t(record.state)));
  } else {
    faults.forEach((fault, index) => {
      const row = node("div", "fault-item"),
        text = node("div");
      row.append(node("span", "fault-index", index + 1));
      const binding = item?.manifest.bindings.find(
        (b) => b.id === fault.binding,
      );
      text.append(
        node(
          "strong",
          "",
          binding ? binding.file + binding.pointer : fault.service,
        ),
      );
      text.append(
        node(
          "p",
          "",
          t(
            fault.kind === "config_drift"
              ? "configFault"
              : fault.kind === "unavailable"
                ? "unavailableFault"
                : "localFault",
          ),
        ),
      );
      text.append(
        node(
          "p",
          "",
          t("affected") + ": " + fault.affected_services.join(" · "),
        ),
      );
      row.append(text);
      container.append(row);
    });
    container.append(node("p", "model-note", t("provisional")));
  }
  if (record?.diagnosis?.unknown_probes?.length)
    container.append(node("p", "blocked-reason", t("unknownHint")));
  if (item && item.manifest.services.length === 1)
    container.append(node("p", "model-note", t("singleUrl")));
  if (record?.advisor) {
    if (record.advisor.state === "accepted") {
      container.append(
        node(
          "div",
          "advisor-text",
          t("modelChecked") + "\n" + record.advisor.content.summary,
        ),
      );
    } else
      container.append(
        node(
          "p",
          "blocked-reason",
          t("modelRejected") + ": " + record.advisor.error,
        ),
      );
  }
  const busy = item?.busy || state.pending;
  const expired =
    record?.plan &&
    Date.now() - Date.parse(record.plan.created_at) >
      record.plan.expires_after_seconds * 1000;
  byId("diagnose").disabled = !item || busy || item.historical;
  byId("cancel").classList.toggle(
    "hidden",
    !record || !["queued", "probing"].includes(record.state),
  );
  byId("apply").disabled =
    !record?.plan?.can_apply ||
    !item?.repair_enabled ||
    busy ||
    Boolean(record?.repair) ||
    expired;
  if (expired && !record?.repair)
    container.append(node("p", "blocked-reason", t("planExpired")));
  if (record?.plan?.changes?.length && !item?.repair_enabled)
    container.append(node("p", "blocked-reason", t("readOnly")));
  byId("explain").classList.toggle(
    "hidden",
    !state.bootstrap?.model_available ||
      !record?.diagnosis ||
      record.diagnosis.state !== "diagnosed",
  );
  byId("explain").disabled = busy || item?.historical;
  byId("download").classList.toggle("hidden", !record);
  if (record) byId("download").href = "/api/incidents/" + record.id + "/report";
  byId("incident-id").textContent = record?.id || "—";
  byId("inject").disabled = busy;
  byId("restart").disabled = busy;
}
function describeProbe(probe) {
  const [kind, subject] = probe.split("/");
  return (
    t(kind === "http" ? "business" : kind === "live" ? "liveness" : "config") +
    " · " +
    subject
  );
}
function renderDetails() {
  for (const button of document.querySelectorAll("[data-tab]"))
    button.classList.toggle("selected", button.dataset.tab === state.tab);
  const container = byId("detail-panel");
  container.replaceChildren();
  const record = state.incident;
  if (!record) {
    container.append(node("div", "empty-state", t("emptyDetail")));
    return;
  }
  if (state.tab === "timeline") {
    const header = node("div", "timeline-row timeline-header");
    ["", t("check"), t("outcome"), t("candidates"), t("time")].forEach((text) =>
      header.append(node("span", "", text)),
    );
    container.append(header);
    record.steps.forEach((step, index) => {
      const row = node("div", "timeline-row"),
        title = node("div", "timeline-title", describeProbe(step.probe_id));
      title.append(node("small", "", step.evidence_id));
      row.append(
        node("span", "timeline-number", String(index + 1).padStart(2, "0")),
        title,
        badge(step.outcome),
        node(
          "span",
          "timeline-worlds",
          step.worlds_before + " → " + step.worlds_after,
        ),
        node("span", "timeline-time", step.duration_ms + " ms"),
      );
      container.append(row);
    });
  } else if (state.tab === "changes") {
    const changes = record.plan?.changes || [];
    if (!changes.length) {
      container.append(node("div", "empty-state", t("waitingChanges")));
      for (const message of record.plan?.blocked || [])
        container.append(node("p", "blocked-reason", message));
      return;
    }
    const table = node("table", "changes-table"),
      head = node("tr");
    ["setting", "before", "after", "evidenceLabel"].forEach((key) =>
      head.append(node("th", "", t(key))),
    );
    const thead = node("thead");
    thead.append(head);
    table.append(thead);
    const tbody = node("tbody");
    for (const change of changes) {
      const row = node("tr");
      row.append(node("td", "", change.file + change.pointer));
      for (const [key, cls] of [
        ["before", "before-value"],
        ["after", "after-value"],
      ]) {
        const cell = node("td"),
          code = node("code", cls, JSON.stringify(change[key]));
        cell.append(code);
        row.append(cell);
      }
      row.append(node("td", "", change.evidence_id.slice(0, 15) + "…"));
      tbody.append(row);
    }
    table.append(tbody);
    container.append(table);
  } else if (state.tab === "evidence") {
    if (state.serviceFilter) {
      const filter = node("div", "evidence-filter", state.serviceFilter),
        clear = node("button", "", t("clear"));
      clear.onclick = () => {
        state.serviceFilter = null;
        renderDetails();
      };
      filter.append(clear);
      container.append(filter);
    }
    for (const observation of record.observations) {
      const binding = record.target.bindings.find(
        (b) => b.id === observation.subject,
      );
      if (
        state.serviceFilter &&
        observation.subject !== state.serviceFilter &&
        binding?.service !== state.serviceFilter
      )
        continue;
      const details = node("details", "evidence-item"),
        summary = node(
          "summary",
          "",
          describeProbe(observation.probe_id) +
            " · " +
            t(observation.outcome) +
            " · " +
            observation.id,
        );
      details.append(
        summary,
        node("pre", "", JSON.stringify(observation.facts, null, 2)),
      );
      container.append(details);
    }
  } else if (state.tab === "recovery") {
    const checks = record.repair?.checks || [];
    if (!checks.length) {
      container.append(
        node(
          "div",
          "empty-state",
          t(record.state === "validating" ? "validating" : "waitingRecovery"),
        ),
      );
      if (record.repair?.error)
        container.append(node("p", "blocked-reason", record.repair.error));
      return;
    }
    for (const check of checks) {
      const row = node("div", "timeline-row"),
        title = node("div", "timeline-title", check.subject);
      title.append(node("small", "", check.facts.url));
      row.append(
        node("span", "timeline-number", check.round),
        title,
        badge(check.outcome),
        node("span", "timeline-worlds", "HTTP " + (check.facts.status || "—")),
        node("span", "timeline-time", check.duration_ms + " ms"),
      );
      container.append(row);
    }
    if (record.repair?.error)
      container.append(node("p", "blocked-reason", record.repair.error));
  }
}
function renderHistory() {
  const container = byId("history");
  container.replaceChildren();
  for (const item of state.history.slice(0, 6)) {
    const button = node("button", "history-item", item.target_name);
    button.append(
      node(
        "small",
        "",
        t(item.state) +
          " · " +
          new Date(item.created_at).toLocaleTimeString(
            state.lang === "zh" ? "zh-CN" : "en-US",
            { hour: "2-digit", minute: "2-digit" },
          ),
      ),
    );
    button.onclick = async () => {
      try {
        state.selected = item.target_id;
        state.incident = await api("/api/incidents/" + item.id);
        state.pending = false;
        render();
      } catch (error) {
        toast(error.message);
      }
    };
    container.append(button);
  }
}
function render() {
  translate();
  renderTargets();
  renderMetrics();
  renderGraph();
  renderDiagnosis();
  renderDetails();
  renderHistory();
}
async function selectTarget(key) {
  state.selected = key;
  state.incident = null;
  state.serviceFilter = null;
  state.history = await api("/api/incidents");
  const last = state.history.find((item) => item.target_id === key);
  if (last) state.incident = await api("/api/incidents/" + last.id);
  render();
}
async function refresh() {
  state.targets = await api("/api/targets");
  if (state.incident)
    state.incident = await api("/api/incidents/" + state.incident.id);
  state.history = await api("/api/incidents");
  if (!selected()?.busy) state.pending = false;
  render();
}
async function perform(operation) {
  try {
    await operation();
  } catch (error) {
    state.pending = false;
    toast(error.message);
    render();
  }
}
byId("language").onclick = () => {
  state.lang = state.lang === "zh" ? "en" : "zh";
  localStorage.setItem("opsresolve-language", state.lang);
  populateScenarios();
  render();
};
byId("diagnose").onclick = () =>
  perform(async () => {
    state.pending = true;
    renderDiagnosis();
    const result = await api(
      "/api/targets/" + state.selected + "/investigations",
      { budget: Number(byId("budget").value), max_faults: 2 },
    );
    state.incident = await api("/api/incidents/" + result.incident_id);
    state.serviceFilter = null;
    state.tab = "timeline";
    render();
  });
byId("apply").onclick = () =>
  perform(async () => {
    state.pending = true;
    renderDiagnosis();
    await api("/api/incidents/" + state.incident.id + "/repair", {
      plan_id: state.incident.plan.id,
    });
    state.tab = "recovery";
    renderDetails();
  });
byId("explain").onclick = () =>
  perform(async () => {
    state.pending = true;
    renderDiagnosis();
    await api("/api/incidents/" + state.incident.id + "/explain", {});
  });
byId("cancel").onclick = () =>
  perform(async () => {
    await api("/api/incidents/" + state.incident.id + "/cancel", {});
    toast(t("cancelDone"));
  });
byId("inject").onclick = () =>
  perform(async () => {
    const result = await api("/api/lab/scenario", {
      scenario: byId("scenario").value,
    });
    state.selected = result.target_id;
    state.incident = null;
    state.pending = false;
    render();
    toast(t("injectDone"));
  });
byId("restart").onclick = () =>
  perform(async () => {
    state.pending = true;
    renderDiagnosis();
    await api("/api/lab/restart", {});
    state.pending = false;
    state.incident = null;
    render();
    toast(t("restartDone"));
  });
byId("add-target").onclick = () => byId("target-dialog").showModal();
byId("close-dialog").onclick = () => byId("target-dialog").close();
byId("target-form").onsubmit = (event) => {
  event.preventDefault();
  perform(async () => {
    const raw = byId("new-manifest").value.trim();
    const value = raw
      ? { manifest: JSON.parse(raw) }
      : { name: byId("new-name").value, url: byId("new-url").value };
    const result = await api("/api/targets", value);
    byId("target-dialog").close();
    state.targets = await api("/api/targets");
    await selectTarget(result.id);
  });
};
byId("new-manifest").oninput = () => {
  byId("new-url").required = !byId("new-manifest").value.trim();
};
for (const button of document.querySelectorAll("[data-tab]"))
  button.onclick = () => {
    state.tab = button.dataset.tab;
    state.serviceFilter = null;
    renderDetails();
  };
function populateScenarios() {
  const select = byId("scenario"),
    old = select.value;
  select.replaceChildren();
  const zh = {
    hidden_pair: "一个 503 背后的两个故障",
    wrong_port: "持久的上游端口错误",
    branch_pair: "两个依赖分支同时失败",
    process_down: "依赖服务进程不可用",
    healthy: "健康应用",
  };
  for (const item of state.bootstrap?.scenarios || []) {
    const option = node(
      "option",
      "",
      state.lang === "zh" ? zh[item.id] || item.title : item.title,
    );
    option.value = item.id;
    select.append(option);
  }
  if (old) select.value = old;
}
function renderTraceReport(report) {
  const container = byId("trace-content");
  container.replaceChildren();
  const metrics = node("div", "trace-metrics");
  for (const [key, count] of [
    ["traces", report.trace_count],
    ["spans", report.span_count],
    ["failedTraces", report.failed_trace_count],
  ]) {
    const item = node("div");
    item.append(node("strong", "", count), node("span", "", t(key)));
    metrics.append(item);
  }
  container.append(metrics, node("h3", "", t("origins")));
  if (!report.origins.length)
    container.append(node("p", "model-note", t("healthy")));
  for (const origin of report.origins.slice(0, 30)) {
    const details = node("details", "evidence-item");
    details.append(
      node(
        "summary",
        "",
        origin.service +
          " · " +
          origin.operation +
          " · " +
          origin.duration_ms +
          " ms",
      ),
    );
    details.append(
      node(
        "pre",
        "",
        JSON.stringify(
          {
            trace_id: origin.trace_id,
            span_id: origin.span_id,
            caller: origin.caller_service,
            attributes: origin.attributes,
          },
          null,
          2,
        ),
      ),
    );
    container.append(details);
  }
  container.append(node("h3", "", t("exclusive")));
  for (const service of report.services)
    container.append(
      node(
        "p",
        "model-note",
        service.service +
          ": " +
          service.exclusive_ms +
          " ms · p95 span " +
          service.p95_span_ms +
          " ms",
      ),
    );
  for (const warning of report.warnings)
    container.append(node("p", "blocked-reason", warning));
  container.append(node("p", "model-note", t("traceLimits")));
  byId("trace-dialog").showModal();
}
byId("import-traces").onclick = () => byId("trace-file").click();
byId("close-traces").onclick = () => byId("trace-dialog").close();
byId("lab-traces").onclick = () =>
  perform(async () => renderTraceReport(await api("/api/lab/traces")));
byId("trace-file").onchange = () =>
  perform(async () => {
    const file = byId("trace-file").files[0];
    if (!file) return;
    if (file.size > 5242880) throw new Error(t("traceFileTooLarge"));
    const text = await file.text();
    let value;
    try {
      value = JSON.parse(text);
    } catch {
      const envelopes = text
        .split(/\r?\n/)
        .filter((line) => line.trim())
        .map((line) => JSON.parse(line));
      value = {
        resourceSpans: envelopes.flatMap((item) => item.resourceSpans),
      };
    }
    renderTraceReport(await api("/api/traces", value));
    byId("trace-file").value = "";
  });
async function bootstrap() {
  try {
    state.bootstrap = await api("/api/bootstrap");
    state.targets = await api("/api/targets");
    state.history = await api("/api/incidents");
    state.selected = state.targets[0]?.id || null;
    populateScenarios();
    byId("lab-traces").classList.toggle(
      "hidden",
      !state.bootstrap.lab_available,
    );
    render();
    let polling = false;
    setInterval(async () => {
      if (polling) return;
      polling = true;
      try {
        if (
          state.pending ||
          selected()?.busy ||
          ["queued", "probing", "validating"].includes(state.incident?.state)
        )
          await refresh();
      } catch (error) {
        toast(error.message);
      } finally {
        polling = false;
      }
    }, 800);
  } catch (error) {
    toast(error.message);
  }
}
bootstrap();
