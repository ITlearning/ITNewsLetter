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

function setProgressVisible(progressEl, visible) {
  if (!progressEl) {
    return;
  }

  if (visible) {
    progressEl.classList.remove("is-hidden");
    return;
  }

  progressEl.classList.add("is-hidden");
  progressEl.classList.remove("is-slow");
}

function setProgressStep(progressEl, stepIndex, note) {
  if (!progressEl) {
    return;
  }

  var steps = progressEl.querySelectorAll(".detail-progress-step");
  for (var index = 0; index < steps.length; index += 1) {
    var stepEl = steps[index];
    stepEl.classList.remove("is-active");
    stepEl.classList.remove("is-complete");

    if (index < stepIndex) {
      stepEl.classList.add("is-complete");
    } else if (index === stepIndex) {
      stepEl.classList.add("is-active");
    }
  }

  var noteEl = document.getElementById("detail-progress-note");
  if (noteEl) {
    noteEl.textContent = note || "";
  }
}

function clearProgressTimers(timerIds) {
  while (timerIds.length) {
    clearTimeout(timerIds.pop());
  }
}

function startProgressSequence(progressEl) {
  var timers = [];
  setProgressVisible(progressEl, true);
  setProgressStep(progressEl, 0, "캐시와 요청 상태를 확인하고 있습니다.");

  timers.push(
    setTimeout(function () {
      setProgressStep(progressEl, 1, "원문 페이지를 읽고 핵심 문맥을 정리하고 있습니다.");
    }, 1100)
  );

  timers.push(
    setTimeout(function () {
      setProgressStep(progressEl, 2, "한국어 브리핑으로 다듬고 있습니다.");
    }, 2800)
  );

  timers.push(
    setTimeout(function () {
      progressEl.classList.add("is-slow");
      setProgressStep(progressEl, 2, "조금 더 걸리고 있습니다. 브라우저를 닫지 않아도 됩니다.");
    }, 8000)
  );

  return timers;
}

async function loadLazyDetail() {
  document.documentElement.dataset.detailReady = "true";

  var shell = document.querySelector(".detail-shell");
  var summaryEl = document.getElementById("detail-summary");
  var statusEl = document.getElementById("detail-status");
  var progressEl = document.getElementById("detail-progress");
  if (!shell || !summaryEl || !statusEl || !progressEl) {
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
  var progressTimers = startProgressSequence(progressEl);

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
      clearProgressTimers(progressTimers);
      setProgressVisible(progressEl, false);
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
      clearProgressTimers(progressTimers);
      setProgressVisible(progressEl, false);
      setStatus(statusEl, "muted", message || "이 기사는 추가 브리핑을 지원하지 않습니다.");
      return;
    }

    clearProgressTimers(progressTimers);
    setProgressVisible(progressEl, false);
    setStatus(
      statusEl,
      "error",
      message || "추가 브리핑 생성에 실패했습니다. 원문에서 확인해 주세요."
    );
  } catch (error) {
    clearProgressTimers(progressTimers);
    setProgressVisible(progressEl, false);
    setStatus(statusEl, "error", "추가 브리핑 생성에 실패했습니다. 원문에서 확인해 주세요.");
  }
}

document.addEventListener("DOMContentLoaded", function () {
  loadLazyDetail();
});
