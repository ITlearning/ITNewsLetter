const state = {
  items: [],
  itemById: new Map(),
  filteredItems: [],
  metadata: null,
  spotlightModules: [],
  featuredSpotlight: null,
  spotlightIndex: 0,
  search: "",
  source: "all",
  slot: "all",
};

const elements = {
  searchInput: document.querySelector("#search-input"),
  sourceFilter: document.querySelector("#source-filter"),
  slotFilter: document.querySelector("#slot-filter"),
  resetButton: document.querySelector("#reset-filters"),
  sourceStrip: document.querySelector("#source-strip"),
  spotlightSection: document.querySelector("#spotlight-section"),
  spotlightStage: document.querySelector("#spotlight-stage"),
  spotlightNav: document.querySelector("#spotlight-nav"),
  spotlightTitle: document.querySelector("#spotlight-title"),
  newsList: document.querySelector("#news-list"),
  emptyState: document.querySelector("#empty-state"),
  cardTemplate: document.querySelector("#news-card-template"),
  resultsTitle: document.querySelector("#results-title"),
  resultsMeta: document.querySelector("#results-meta"),
  statTotal: document.querySelector("#stat-total"),
  statSources: document.querySelector("#stat-sources"),
  statUpdated: document.querySelector("#stat-updated"),
};

const formatter = new Intl.DateTimeFormat("ko-KR", {
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

function getDisplayDate(item) {
  return item.sent_at || item.published_at || item.fetched_at || "";
}

function formatDate(value) {
  if (!value) return "날짜 없음";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return formatter.format(date);
}

function buildSearchHaystack(item) {
  return normalizeText(
    [
      item.translated_title,
      item.title,
      item.short_summary,
      item.detailed_summary,
      item.summary,
      item.source,
      item.primary_slot_label,
      ...(item.matched_terms || []),
    ].join(" ")
  );
}

function clearChildren(element) {
  if (!element) return;
  while (element.firstChild) {
    element.removeChild(element.firstChild);
  }
}

function getDetailUrl(item) {
  return item.detail_url || "#";
}

function applyFilters() {
  const query = normalizeText(state.search);
  state.filteredItems = state.items.filter((item) => {
    if (state.source !== "all" && item.source !== state.source) {
      return false;
    }
    if (state.slot !== "all" && item.primary_slot !== state.slot) {
      return false;
    }
    if (query && !buildSearchHaystack(item).includes(query)) {
      return false;
    }
    return true;
  });

  renderResultsHeader();
  renderList();
}

function renderStats() {
  const metadata = state.metadata;
  elements.statTotal.textContent = metadata?.archive_total ?? "-";
  elements.statSources.textContent = metadata?.sources?.length ?? "-";
  elements.statUpdated.textContent = formatDate(metadata?.generated_at || metadata?.last_dispatch_at || "");
}

function renderSourceStrip() {
  clearChildren(elements.sourceStrip);
  const sources = state.metadata?.sources || [];
  if (!elements.sourceStrip || !sources.length) {
    return;
  }

  sources.slice(0, 8).forEach((source) => {
    const pill = document.createElement("div");
    pill.className = "source-pill";
    const name = document.createElement("strong");
    name.textContent = source.name;
    const count = document.createElement("span");
    count.textContent = `${source.count}건`;
    pill.append(name, count);
    elements.sourceStrip.appendChild(pill);
  });
}

function renderFilterOptions() {
  const metadata = state.metadata;
  const sourceOptions = metadata?.sources || [];
  const slotOptions = metadata?.slots || [];

  while (elements.sourceFilter.options.length > 1) {
    elements.sourceFilter.remove(1);
  }

  while (elements.slotFilter.options.length > 1) {
    elements.slotFilter.remove(1);
  }

  sourceOptions.forEach((source) => {
    const option = document.createElement("option");
    option.value = source.name;
    option.textContent = `${source.name} (${source.count})`;
    elements.sourceFilter.appendChild(option);
  });

  slotOptions.forEach((slot) => {
    const option = document.createElement("option");
    option.value = slot.name;
    option.textContent = `${slot.label} (${slot.count})`;
    elements.slotFilter.appendChild(option);
  });
}

function renderResultsHeader() {
  const total = state.filteredItems.length;
  elements.resultsTitle.textContent =
    state.source === "all" && state.slot === "all" && !state.search
      ? "보낸 뉴스 전체"
      : "필터된 뉴스";
  elements.resultsMeta.textContent = `${total}건 표시 중`;
}

function populateMatchedTerms(container, terms) {
  clearChildren(container);
  terms.slice(0, 4).forEach((term) => {
    const chip = document.createElement("span");
    chip.textContent = term;
    container.appendChild(chip);
  });
}

function renderCard(item) {
  const fragment = elements.cardTemplate.content.cloneNode(true);
  const card = fragment.querySelector(".news-card");
  const sourceBadge = fragment.querySelector(".badge-source");
  const slotBadge = fragment.querySelector(".badge-slot");
  const date = fragment.querySelector(".card-date");
  const titleLink = fragment.querySelector(".card-title-link");
  const original = fragment.querySelector(".card-original");
  const summary = fragment.querySelector(".card-summary");
  const matchedTerms = fragment.querySelector(".matched-terms");
  const detailLink = fragment.querySelector(".card-detail-link");
  const sourceLink = fragment.querySelector(".card-source-link");

  card.dataset.slot = item.primary_slot || "unknown";
  sourceBadge.textContent = item.source || "Unknown";
  slotBadge.textContent = item.primary_slot_label || "미분류";
  date.textContent = formatDate(getDisplayDate(item));
  titleLink.textContent = item.translated_title || item.title || "(제목 없음)";
  titleLink.href = getDetailUrl(item);

  if (item.translated_title && item.title && item.translated_title !== item.title) {
    original.hidden = false;
    original.textContent = `원제: ${item.title}`;
  }

  summary.textContent = item.short_summary || item.summary || "요약 없음";
  detailLink.href = getDetailUrl(item);
  sourceLink.href = item.link || "#";

  if (Array.isArray(item.matched_terms) && item.matched_terms.length > 0) {
    matchedTerms.hidden = false;
    populateMatchedTerms(matchedTerms, item.matched_terms);
  }

  return fragment;
}

function resolveSpotlightPrimaryItem(module) {
  const relatedIds = Array.isArray(module?.related_item_ids) ? module.related_item_ids : [];
  for (const itemId of relatedIds) {
    const match = state.itemById.get(itemId);
    if (match) {
      return match;
    }
  }
  return null;
}

function renderSpotlightSignals(signals, className = "spotlight-signal-list") {
  const list = document.createElement("div");
  list.className = className;

  (signals || []).slice(0, 3).forEach((signal) => {
    const row = document.createElement("div");
    row.className = "spotlight-signal";
    row.textContent = signal;
    list.appendChild(row);
  });

  return list;
}

function renderQuietRiserBody(module) {
  const body = document.createElement("div");
  body.className = "spotlight-body spotlight-body-quiet-riser";

  const kicker = document.createElement("div");
  kicker.className = "spotlight-module-kicker";
  kicker.textContent = "이번 주";
  body.appendChild(kicker);

  const name = document.createElement("h3");
  name.className = "spotlight-module-name";
  name.textContent = module.topic_name || "반복되는 흐름";
  body.appendChild(name);

  const summary = document.createElement("p");
  summary.className = "spotlight-module-summary";
  summary.textContent = module.summary_line || "최근 기사 안에서 약하게 반복되기 시작한 흐름입니다.";
  body.appendChild(summary);

  body.appendChild(renderSpotlightSignals(module.signals));
  return body;
}

function renderHnSplitBody(module) {
  const body = document.createElement("div");
  body.className = "spotlight-body spotlight-body-hn-split";

  const headline = document.createElement("div");
  headline.className = "spotlight-hn-headline";
  headline.textContent = module.headline || "논쟁이 갈린 HN 기사";
  body.appendChild(headline);

  const grid = document.createElement("div");
  grid.className = "spotlight-hn-grid";

  const left = document.createElement("section");
  left.className = "spotlight-hn-column spotlight-hn-column-negative";
  const leftLabel = document.createElement("span");
  leftLabel.className = "spotlight-hn-label";
  leftLabel.textContent = "반대파";
  const leftCopy = document.createElement("p");
  leftCopy.textContent = module.opposition_summary || "회의적인 반응이 더 크게 나타났습니다.";
  left.append(leftLabel, leftCopy);

  const center = document.createElement("section");
  center.className = "spotlight-hn-column spotlight-hn-column-center";
  const centerLabel = document.createElement("span");
  centerLabel.className = "spotlight-hn-label";
  centerLabel.textContent = "쟁점";
  const centerTitle = document.createElement("h3");
  centerTitle.textContent = module.issue_title || module.headline || "어떤 점이 논쟁이 됐는지";
  center.append(centerLabel, centerTitle);

  const right = document.createElement("section");
  right.className = "spotlight-hn-column spotlight-hn-column-positive";
  const rightLabel = document.createElement("span");
  rightLabel.className = "spotlight-hn-label";
  rightLabel.textContent = "찬성파";
  const rightCopy = document.createElement("p");
  rightCopy.textContent = module.support_summary || "긍정적인 반응도 함께 이어졌습니다.";
  right.append(rightLabel, rightCopy);

  grid.append(left, center, right);
  body.appendChild(grid);
  return body;
}

function renderAnomalySignalBody(module) {
  const body = document.createElement("div");
  body.className = "spotlight-body spotlight-body-anomaly";

  const kicker = document.createElement("div");
  kicker.className = "spotlight-module-kicker";
  kicker.textContent = "Labs";
  body.appendChild(kicker);

  const name = document.createElement("h3");
  name.className = "spotlight-module-name";
  name.textContent = module.signal_title || "이번 주 이상 신호";
  body.appendChild(name);

  const summary = document.createElement("p");
  summary.className = "spotlight-module-summary";
  summary.textContent = module.summary_line || "아직 메인스트림은 아니지만 자꾸 감지되는 신호입니다.";
  body.appendChild(summary);

  body.appendChild(renderSpotlightSignals(module.signals, "spotlight-signal-grid"));
  return body;
}

function renderSpotlightBody(module) {
  switch (module?.kind) {
    case "quiet_riser":
      return renderQuietRiserBody(module);
    case "hn_split":
      return renderHnSplitBody(module);
    case "anomaly_signal":
      return renderAnomalySignalBody(module);
    default: {
      const fallback = document.createElement("p");
      fallback.className = "spotlight-module-summary";
      fallback.textContent = module?.summary_line || "표시할 Spotlight가 없습니다.";
      return fallback;
    }
  }
}

function renderSpotlightNav() {
  clearChildren(elements.spotlightNav);
  const total = state.spotlightModules.length;
  elements.spotlightNav.hidden = total <= 1;
  if (total <= 1) {
    return;
  }

  const previous = document.createElement("button");
  previous.type = "button";
  previous.className = "spotlight-nav-button";
  previous.textContent = "이전";
  previous.addEventListener("click", () => {
    state.spotlightIndex = (state.spotlightIndex - 1 + total) % total;
    renderSpotlight();
  });

  const dots = document.createElement("div");
  dots.className = "spotlight-nav-dots";

  state.spotlightModules.forEach((module, index) => {
    const dot = document.createElement("button");
    dot.type = "button";
    dot.className = "spotlight-nav-dot";
    dot.setAttribute("aria-label", `${module.title || "Spotlight"} ${index + 1} 보기`);
    dot.dataset.active = index === state.spotlightIndex ? "true" : "false";
    dot.addEventListener("click", () => {
      state.spotlightIndex = index;
      renderSpotlight();
    });
    dots.appendChild(dot);
  });

  const next = document.createElement("button");
  next.type = "button";
  next.className = "spotlight-nav-button";
  next.textContent = "다음";
  next.addEventListener("click", () => {
    state.spotlightIndex = (state.spotlightIndex + 1) % total;
    renderSpotlight();
  });

  elements.spotlightNav.append(previous, dots, next);
}

function renderSpotlight() {
  clearChildren(elements.spotlightStage);
  if (!Array.isArray(state.spotlightModules) || !state.spotlightModules.length) {
    elements.spotlightSection.hidden = true;
    return;
  }

  elements.spotlightSection.hidden = false;
  const activeModule = state.spotlightModules[state.spotlightIndex] || state.spotlightModules[0];
  const card = document.createElement("article");
  card.className = `spotlight-card spotlight-card-${activeModule.kind || "generic"}`;

  const head = document.createElement("div");
  head.className = "spotlight-card-head";

  const eyebrow = document.createElement("span");
  eyebrow.className = "spotlight-card-label";
  eyebrow.textContent = activeModule.label || "AI Spotlight";
  head.appendChild(eyebrow);

  const title = document.createElement("h3");
  title.className = "spotlight-card-title";
  title.textContent = activeModule.title || "오늘의 AI Spotlight";
  head.appendChild(title);

  card.appendChild(head);
  card.appendChild(renderSpotlightBody(activeModule));

  const footer = document.createElement("div");
  footer.className = "spotlight-card-footer";

  const footerMeta = document.createElement("span");
  footerMeta.className = "spotlight-card-meta";
  if (activeModule.meta_line) {
    footerMeta.textContent = activeModule.meta_line;
  } else if (typeof activeModule.score === "number") {
    footerMeta.textContent = `추천 강도 ${(activeModule.score * 100).toFixed(0)}%`;
  } else {
    footerMeta.textContent = "오늘의 추천";
  }
  footer.appendChild(footerMeta);

  const primaryItem = resolveSpotlightPrimaryItem(activeModule);
  const cta = document.createElement("a");
  cta.className = "spotlight-card-cta";
  cta.textContent = activeModule.cta_label || "관련 기사 보기";
  cta.href = primaryItem ? getDetailUrl(primaryItem) : "#";
  footer.appendChild(cta);

  card.appendChild(footer);
  elements.spotlightStage.appendChild(card);
  renderSpotlightNav();
}

function renderList() {
  clearChildren(elements.newsList);

  if (!state.filteredItems.length) {
    elements.emptyState.hidden = false;
    return;
  }

  elements.emptyState.hidden = true;
  const fragment = document.createDocumentFragment();
  state.filteredItems.forEach((item) => fragment.appendChild(renderCard(item)));
  elements.newsList.appendChild(fragment);
}

function wireEvents() {
  elements.searchInput.addEventListener("input", (event) => {
    state.search = event.target.value;
    applyFilters();
  });

  elements.sourceFilter.addEventListener("change", (event) => {
    state.source = event.target.value;
    applyFilters();
  });

  elements.slotFilter.addEventListener("change", (event) => {
    state.slot = event.target.value;
    applyFilters();
  });

  elements.resetButton.addEventListener("click", () => {
    state.search = "";
    state.source = "all";
    state.slot = "all";
    elements.searchInput.value = "";
    elements.sourceFilter.value = "all";
    elements.slotFilter.value = "all";
    applyFilters();
  });
}

function findInitialSpotlightIndex(modules, featured) {
  if (!Array.isArray(modules) || !modules.length) {
    return 0;
  }
  if (!featured?.id) {
    return 0;
  }
  const featuredIndex = modules.findIndex((module) => module.id === featured.id);
  return featuredIndex >= 0 ? featuredIndex : 0;
}

async function init() {
  try {
    const response = await fetch("./data/news-archive.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Failed to load archive: ${response.status}`);
    }

    const payload = await response.json();
    state.metadata = payload;
    state.items = Array.isArray(payload.items) ? payload.items : [];
    state.itemById = new Map(state.items.map((item) => [item.id, item]));
    state.spotlightModules = Array.isArray(payload.spotlight_modules) ? payload.spotlight_modules : [];
    state.featuredSpotlight = payload.featured_spotlight || null;
    state.spotlightIndex = findInitialSpotlightIndex(state.spotlightModules, state.featuredSpotlight);
    renderStats();
    renderSourceStrip();
    renderFilterOptions();
    renderSpotlight();
    wireEvents();
    applyFilters();
  } catch (error) {
    console.error(error);
    elements.resultsTitle.textContent = "아카이브를 불러오지 못했습니다";
    elements.resultsMeta.textContent = String(error);
    elements.emptyState.hidden = false;
    elements.emptyState.querySelector("h2").textContent = "데이터 로드 실패";
    elements.emptyState.querySelector("p").textContent = `오류: ${String(error)}`;
  }
}

init();
