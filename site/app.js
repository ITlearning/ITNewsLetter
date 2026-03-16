const state = {
  items: [],
  filteredItems: [],
  metadata: null,
  todayPicks: [],
  topicDigests: { weekly: [], monthly: [] },
  search: "",
  source: "all",
  slot: "all",
};

const elements = {
  searchInput: document.querySelector("#search-input"),
  sourceFilter: document.querySelector("#source-filter"),
  slotFilter: document.querySelector("#slot-filter"),
  resetButton: document.querySelector("#reset-filters"),
  todaySection: document.querySelector("#today-section"),
  todayList: document.querySelector("#today-list"),
  topicSection: document.querySelector("#topic-section"),
  topicList: document.querySelector("#topic-list"),
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
  if (!element) {
    return;
  }
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
      : "필터된 결과";
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

function renderTodayCuration() {
  clearChildren(elements.todayList);

  if (!Array.isArray(state.todayPicks) || !state.todayPicks.length) {
    elements.todaySection.hidden = true;
    return;
  }

  elements.todaySection.hidden = false;
  const fragment = document.createDocumentFragment();

  state.todayPicks.forEach((item) => {
    const link = document.createElement("a");
    link.className = "today-card";
    link.href = getDetailUrl(item);

    const source = document.createElement("span");
    source.className = "today-source";
    source.textContent = `${item.source || "Unknown"} · ${item.primary_slot_label || "미분류"}`;
    link.appendChild(source);

    const title = document.createElement("strong");
    title.className = "today-title";
    title.textContent = item.translated_title || item.title || "(제목 없음)";
    link.appendChild(title);

    const summary = document.createElement("p");
    summary.className = "today-summary";
    summary.textContent = item.short_summary || item.summary || "요약 없음";
    link.appendChild(summary);

    fragment.appendChild(link);
  });

  elements.todayList.appendChild(fragment);
}

function renderTopicDigests() {
  clearChildren(elements.topicList);

  const weekly = Array.isArray(state.topicDigests?.weekly) ? state.topicDigests.weekly.slice(0, 2) : [];
  const monthly = Array.isArray(state.topicDigests?.monthly) ? state.topicDigests.monthly.slice(0, 2) : [];
  const digests = weekly.concat(monthly);

  if (!digests.length) {
    elements.topicSection.hidden = true;
    return;
  }

  elements.topicSection.hidden = false;
  const fragment = document.createDocumentFragment();

  digests.forEach((digest) => {
    const link = document.createElement("a");
    link.className = "topic-card";
    link.href = digest.url || "#";
    link.setAttribute(
      "aria-label",
      `${digest.headline || "토픽 브리핑"} 열기`
    );

    const top = document.createElement("div");
    top.className = "topic-card-top";

    const chips = document.createElement("div");
    chips.className = "topic-card-chips";

    const period = document.createElement("span");
    period.className = "topic-chip topic-chip-period";
    period.textContent = digest.period === "monthly" ? "Monthly Topic" : "Weekly Topic";
    chips.appendChild(period);

    const slot = document.createElement("span");
    slot.className = "topic-chip topic-chip-slot";
    slot.textContent = digest.slot_label || "미분류";
    chips.appendChild(slot);

    top.appendChild(chips);

    const count = document.createElement("span");
    count.className = "topic-card-count";
    count.textContent = `기사 ${digest.total_items || 0}건`;
    top.appendChild(count);
    link.appendChild(top);

    const headline = document.createElement("strong");
    headline.className = "topic-headline";
    headline.textContent = digest.headline || "토픽 브리핑";
    link.appendChild(headline);

    const summary = document.createElement("p");
    summary.className = "topic-summary";
    summary.textContent = digest.summary || "요약 없음";
    link.appendChild(summary);

    const cta = document.createElement("span");
    cta.className = "topic-card-cta";
    cta.textContent = "브리핑 보기";
    link.appendChild(cta);

    fragment.appendChild(link);
  });

  elements.topicList.appendChild(fragment);
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

async function init() {
  try {
    const response = await fetch("./data/news-archive.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Failed to load archive: ${response.status}`);
    }

    const payload = await response.json();
    state.metadata = payload;
    state.items = Array.isArray(payload.items) ? payload.items : [];
    state.todayPicks = Array.isArray(payload.today_picks) ? payload.today_picks : [];
    state.topicDigests = payload.topic_digests || { weekly: [], monthly: [] };
    renderStats();
    renderFilterOptions();
    renderTodayCuration();
    renderTopicDigests();
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
