function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

var BRIEFING_BOLD_RE = /\*\*(.+?)\*\*/g;

function prefersReducedMotion() {
  return Boolean(
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

function normalizeBriefingMarkdown(text) {
  var normalized = String(text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
  if (!normalized) {
    return "";
  }

  var normalizedLines = [];
  var previousBlank = false;

  normalized.split("\n").forEach(function (rawLine) {
    var line = String(rawLine || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .join(" ");

    if (!line) {
      if (normalizedLines.length && !previousBlank) {
        normalizedLines.push("");
      }
      previousBlank = true;
      return;
    }

    if (line.indexOf("* ") === 0) {
      line = "- " + line.slice(2).trim();
    } else if (line.indexOf("- ") === 0) {
      line = "- " + line.slice(2).trim();
    }

    normalizedLines.push(line);
    previousBlank = false;
  });

  return normalizedLines.join("\n").trim();
}

function renderInlineBriefingMarkdown(text) {
  return escapeHtml(text).replace(BRIEFING_BOLD_RE, "<strong>$1</strong>");
}

function renderSummaryHtml(text, options) {
  var normalized = normalizeBriefingMarkdown(text);
  if (!normalized) {
    return "<p class='detail-summary-empty'>요약이 없습니다. 원문에서 자세히 확인하세요.</p>";
  }

  var settings = options || {};
  var animated = Boolean(settings.animated) && !prefersReducedMotion();
  var lines = normalized.split("\n");
  var htmlBlocks = [];
  var paragraphLines = [];
  var listItems = [];
  var revealIndex = 0;

  function buildBlockClass() {
    var classNames = ["detail-summary-block"];
    if (animated) {
      classNames.push("detail-summary-line", "is-reveal");
    }
    return classNames.join(" ");
  }

  function buildBlockAttrs() {
    var attrs = " class='" + buildBlockClass() + "'";
    if (animated) {
      attrs += " style='--reveal-index:" + revealIndex + "'";
      revealIndex += 1;
    }
    return attrs;
  }

  function flushParagraph() {
    if (!paragraphLines.length) {
      return;
    }

    var paragraph = paragraphLines.join(" ").trim();
    if (paragraph) {
      htmlBlocks.push("<p" + buildBlockAttrs() + ">" + renderInlineBriefingMarkdown(paragraph) + "</p>");
    }
    paragraphLines = [];
  }

  function flushList() {
    if (!listItems.length) {
      return;
    }

    var itemsHtml = listItems
      .filter(Boolean)
      .map(function (item) {
        return "<li" + buildBlockAttrs() + ">" + renderInlineBriefingMarkdown(item) + "</li>";
      })
      .join("");

    if (itemsHtml) {
      htmlBlocks.push("<ul class='detail-summary-list'>" + itemsHtml + "</ul>");
    }
    listItems = [];
  }

  lines.forEach(function (line) {
    if (!line) {
      flushParagraph();
      flushList();
      return;
    }

    if (line.indexOf("- ") === 0) {
      flushParagraph();
      listItems.push(line.slice(2).trim());
      return;
    }

    flushList();
    paragraphLines.push(line);
  });

  flushParagraph();
  flushList();

  return htmlBlocks.join("");
}

function setStatus(statusEl, kind, text) {
  if (!statusEl) {
    return;
  }

  statusEl.className = "detail-status";
  if (!text) {
    statusEl.className += " is-hidden";
    statusEl.textContent = "";
    return;
  }

  statusEl.className += " is-" + kind;
  statusEl.textContent = text;
}

function setLoadingVisible(loadingEl, visible) {
  if (!loadingEl) {
    return;
  }

  if (visible) {
    loadingEl.classList.remove("is-hidden");
    return;
  }

  loadingEl.classList.add("is-hidden");
  loadingEl.classList.remove("is-slow");
}

function setLoadingNote(loadingEl, note) {
  var noteEl = document.getElementById("detail-loading-note");
  if (!loadingEl || !noteEl) {
    return;
  }
  noteEl.textContent = note || "";
}

function renderLoadingSkeletonHtml() {
  return [
    "<div class='detail-summary-skeleton is-wide' aria-hidden='true'></div>",
    "<div class='detail-summary-skeleton is-mid' aria-hidden='true'></div>",
    "<div class='detail-summary-skeleton is-short' aria-hidden='true'></div>",
  ].join("");
}

function formatElapsed(seconds) {
  var minutes = Math.floor(seconds / 60);
  var remaining = seconds % 60;
  return String(minutes).padStart(2, "0") + ":" + String(remaining).padStart(2, "0");
}

function clearLoadingTimers(state) {
  if (state.intervalId) {
    clearInterval(state.intervalId);
    state.intervalId = null;
  }

  if (state.slowTimerId) {
    clearTimeout(state.slowTimerId);
    state.slowTimerId = null;
  }
}

function startLoadingUi(loadingEl, summaryEl) {
  var elapsedEl = document.getElementById("detail-loading-elapsed");
  var originalHtml = summaryEl.innerHTML;
  var state = {
    originalHtml: originalHtml,
    intervalId: null,
    slowTimerId: null,
    startedAt: Date.now(),
  };

  summaryEl.classList.add("is-loading");
  summaryEl.innerHTML = renderLoadingSkeletonHtml();
  setLoadingVisible(loadingEl, true);
  setLoadingNote(loadingEl, "원문을 확인하고 한국어 브리핑으로 정리하고 있습니다.");
  if (elapsedEl) {
    elapsedEl.textContent = "00:00";
  }

  state.intervalId = setInterval(function () {
    if (elapsedEl) {
      var seconds = Math.max(0, Math.floor((Date.now() - state.startedAt) / 1000));
      elapsedEl.textContent = formatElapsed(seconds);
    }
  }, 1000);

  state.slowTimerId = setTimeout(function () {
    loadingEl.classList.add("is-slow");
    setLoadingNote(loadingEl, "조금 더 걸리고 있습니다. 브라우저를 닫지 않아도 됩니다.");
  }, 8000);

  return state;
}

function finishLoadingUi(loadingEl, summaryEl, state, fallbackHtml) {
  clearLoadingTimers(state);
  setLoadingVisible(loadingEl, false);
  summaryEl.classList.remove("is-loading");
  if (typeof fallbackHtml === "string") {
    summaryEl.innerHTML = fallbackHtml;
  }
}

function animateSummaryReveal(summaryEl) {
  if (!summaryEl || prefersReducedMotion()) {
    return;
  }

  var lines = summaryEl.querySelectorAll(".detail-summary-line.is-reveal");
  if (!lines.length) {
    return;
  }
}

function readSummaryMarkdown(summaryEl) {
  if (!summaryEl) {
    return "";
  }

  return normalizeBriefingMarkdown(summaryEl.dataset.summaryMarkdown || "");
}

function animateInitialSummary(summaryEl) {
  if (!summaryEl || prefersReducedMotion()) {
    return;
  }

  if (summaryEl.dataset.initialRevealDone === "true") {
    return;
  }

  var markdown = readSummaryMarkdown(summaryEl);
  if (!markdown) {
    return;
  }

  summaryEl.innerHTML = renderSummaryHtml(markdown, { animated: true });
  summaryEl.dataset.initialRevealDone = "true";
  animateSummaryReveal(summaryEl);
}

async function loadLazyDetail() {
  document.documentElement.dataset.detailReady = "true";

  var shell = document.querySelector(".detail-shell");
  var summaryEl = document.getElementById("detail-summary");
  var statusEl = document.getElementById("detail-status");
  var loadingEl = document.getElementById("detail-loading");
  if (!shell || !summaryEl || !statusEl || !loadingEl) {
    return;
  }

  var hasDetailedSummary = shell.dataset.hasDetailedSummary === "true";
  var lazyDetailSupported = shell.dataset.lazyDetailSupported === "true";
  var apiUrl = String(shell.dataset.lazyDetailApiUrl || "").trim();
  var itemId = String(shell.dataset.itemId || "").trim();
  var hnStoryId = String(shell.dataset.hnStoryId || "").trim();

  if (hasDetailedSummary || !lazyDetailSupported || !apiUrl || !itemId) {
    animateInitialSummary(summaryEl);
    return;
  }

  setStatus(statusEl, "", "");
  var loadingState = startLoadingUi(loadingEl, summaryEl);

  try {
    var requestUrl = new URL(apiUrl);
    requestUrl.searchParams.set("id", itemId);
    if (hnStoryId) {
      requestUrl.searchParams.set("hn_story_id", hnStoryId);
    }

    var response = await fetch(requestUrl.toString(), {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    var payload = {};
    try {
      payload = await response.json();
    } catch (error) {
      payload = {};
    }

    var status = String(payload.status || "");
    var detailedSummary = normalizeBriefingMarkdown(payload.detailed_summary || "");
    var message = String(payload.message || "").trim();

    if ((status === "cached" || status === "generated") && detailedSummary) {
      finishLoadingUi(loadingEl, summaryEl, loadingState);
      summaryEl.dataset.summaryMarkdown = detailedSummary;
      summaryEl.innerHTML = renderSummaryHtml(detailedSummary, { animated: true });
      animateSummaryReveal(summaryEl);
      shell.dataset.hasDetailedSummary = "true";
      setStatus(
        statusEl,
        "success",
        status === "generated" ? "추가 브리핑을 불러왔습니다." : "저장된 상세 브리핑을 불러왔습니다."
      );
      return;
    }

    if (status === "unsupported") {
      finishLoadingUi(loadingEl, summaryEl, loadingState, loadingState.originalHtml);
      animateInitialSummary(summaryEl);
      setStatus(statusEl, "muted", message || "이 기사는 추가 브리핑을 지원하지 않습니다.");
      return;
    }

    finishLoadingUi(loadingEl, summaryEl, loadingState, loadingState.originalHtml);
    animateInitialSummary(summaryEl);
    setStatus(
      statusEl,
      "error",
      message || "추가 브리핑 생성에 실패했습니다. 원문에서 확인해 주세요."
    );
  } catch (error) {
    finishLoadingUi(loadingEl, summaryEl, loadingState, loadingState.originalHtml);
    animateInitialSummary(summaryEl);
    setStatus(statusEl, "error", "추가 브리핑 생성에 실패했습니다. 원문에서 확인해 주세요.");
  }
}

document.addEventListener("DOMContentLoaded", function () {
  loadLazyDetail();
});
