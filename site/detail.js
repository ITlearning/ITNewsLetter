function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderSummaryHtml(text) {
  var normalized = String(text || "").trim();
  if (!normalized) {
    return "<p class='detail-summary-empty'>요약이 없습니다. 원문에서 자세히 확인하세요.</p>";
  }

  var parts = normalized
    .split(/\n+/)
    .map(function (part) {
      return part.trim();
    })
    .filter(Boolean);

  if (!parts.length) {
    parts = [normalized];
  }

  return parts
    .map(function (part) {
      return "<p>" + escapeHtml(part) + "</p>";
    })
    .join("");
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

  if (hasDetailedSummary || !lazyDetailSupported || !apiUrl || !itemId) {
    return;
  }

  setStatus(statusEl, "", "");
  var loadingState = startLoadingUi(loadingEl, summaryEl);

  try {
    var requestUrl = new URL(apiUrl);
    requestUrl.searchParams.set("id", itemId);

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
    var detailedSummary = String(payload.detailed_summary || "").trim();
    var message = String(payload.message || "").trim();

    if ((status === "cached" || status === "generated") && detailedSummary) {
      finishLoadingUi(loadingEl, summaryEl, loadingState);
      summaryEl.innerHTML = renderSummaryHtml(detailedSummary);
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
      setStatus(statusEl, "muted", message || "이 기사는 추가 브리핑을 지원하지 않습니다.");
      return;
    }

    finishLoadingUi(loadingEl, summaryEl, loadingState, loadingState.originalHtml);
    setStatus(
      statusEl,
      "error",
      message || "추가 브리핑 생성에 실패했습니다. 원문에서 확인해 주세요."
    );
  } catch (error) {
    finishLoadingUi(loadingEl, summaryEl, loadingState, loadingState.originalHtml);
    setStatus(statusEl, "error", "추가 브리핑 생성에 실패했습니다. 원문에서 확인해 주세요.");
  }
}

document.addEventListener("DOMContentLoaded", function () {
  loadLazyDetail();
});
