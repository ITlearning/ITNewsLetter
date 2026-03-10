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

async function loadLazyDetail() {
  document.documentElement.dataset.detailReady = "true";

  var shell = document.querySelector(".detail-shell");
  var summaryEl = document.getElementById("detail-summary");
  var statusEl = document.getElementById("detail-status");
  if (!shell || !summaryEl || !statusEl) {
    return;
  }

  var hasDetailedSummary = shell.dataset.hasDetailedSummary === "true";
  var lazyDetailSupported = shell.dataset.lazyDetailSupported === "true";
  var apiUrl = String(shell.dataset.lazyDetailApiUrl || "").trim();
  var itemId = String(shell.dataset.itemId || "").trim();

  if (hasDetailedSummary || !lazyDetailSupported || !apiUrl || !itemId) {
    return;
  }

  setStatus(statusEl, "loading", "추가 브리핑을 준비하고 있습니다.");

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
      setStatus(statusEl, "muted", message || "이 기사는 추가 브리핑을 지원하지 않습니다.");
      return;
    }

    setStatus(
      statusEl,
      "error",
      message || "추가 브리핑 생성에 실패했습니다. 원문에서 확인해 주세요."
    );
  } catch (error) {
    setStatus(statusEl, "error", "추가 브리핑 생성에 실패했습니다. 원문에서 확인해 주세요.");
  }
}

document.addEventListener("DOMContentLoaded", function () {
  loadLazyDetail();
});
