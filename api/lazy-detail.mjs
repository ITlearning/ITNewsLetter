import { getArchiveItem } from "./_lib/lazy-detail-archive.mjs";
import { getCachedDetail, setCachedDetail } from "./_lib/lazy-detail-cache.mjs";
import {
  corsHeaders,
  evaluateLazyDetailSupport,
  jsonResponse,
  loadLazyDetailConfig,
  normalizeText,
} from "./_lib/lazy-detail-config.mjs";
import { fetchArticleText } from "./_lib/lazy-detail-extract.mjs";
import { fetchHnDiscussionText } from "./_lib/lazy-detail-hn.mjs";
import { generateDetailedSummary } from "./_lib/lazy-detail-openai.mjs";

export const runtime = "nodejs";

function unsupportedMessage(reason) {
  switch (reason) {
    case "not_english":
    case "source_excluded":
    case "source_not_allowlisted":
    case "source_domain_not_allowlisted":
    case "domain_not_allowlisted":
      return "이 기사는 추가 브리핑을 지원하지 않습니다.";
    case "missing_domain":
      return "원문 링크를 확인할 수 없어 추가 브리핑을 지원하지 않습니다.";
    default:
      return "이 기사는 추가 브리핑을 지원하지 않습니다.";
  }
}

export async function OPTIONS() {
  return new Response(null, {
    status: 204,
    headers: corsHeaders(),
  });
}

export async function GET(request) {
  try {
    const config = await loadLazyDetailConfig();
    const requestUrl = new URL(request.url);
    const itemId = normalizeText(requestUrl.searchParams.get("id"));
    const requestHnStoryId = normalizeText(requestUrl.searchParams.get("hn_story_id"));

    if (!itemId) {
      return jsonResponse(
        {
          status: "failed",
          message: "기사 id가 없어 추가 브리핑을 생성할 수 없습니다.",
          cached: false,
        },
        400
      );
    }

    if (!config.archiveDataUrl) {
      return jsonResponse(
        {
          status: "failed",
          message: "아카이브 데이터 URL이 설정되지 않아 추가 브리핑을 생성할 수 없습니다.",
          cached: false,
        },
        500
      );
    }

    if (!config.redisUrl || !config.redisToken) {
      return jsonResponse(
        {
          status: "failed",
          message: "추가 브리핑 캐시가 설정되지 않아 생성할 수 없습니다.",
          cached: false,
        },
        500
      );
    }

    if (!config.openaiApiKey) {
      return jsonResponse(
        {
          status: "failed",
          message: "OpenAI 설정이 없어 추가 브리핑을 생성할 수 없습니다.",
          cached: false,
        },
        500
      );
    }

    try {
      const cached = await getCachedDetail(config, itemId);
      if (cached?.detailed_summary) {
        return jsonResponse({
          status: "cached",
          detailed_summary: normalizeText(cached.detailed_summary),
          message: "저장된 상세 브리핑을 불러왔습니다.",
          cached: true,
        });
      }
    } catch (error) {
      console.error("lazy-detail cache read failed", error);
    }

    const item = await getArchiveItem(config, itemId);
    if (!item) {
      return jsonResponse(
        {
          status: "unsupported",
          message: "아카이브에 없는 기사라 추가 브리핑을 지원하지 않습니다.",
          cached: false,
        },
        404
      );
    }

    if (
      normalizeText(item.source) === "Hacker News Frontpage (HN RSS)" &&
      requestHnStoryId &&
      !normalizeText(item.hn_story_id)
    ) {
      item.hn_story_id = requestHnStoryId;
      item.hn_discussion_url = `https://news.ycombinator.com/item?id=${requestHnStoryId}`;
    }

    const archivedSummary = normalizeText(item.detailed_summary);
    if (archivedSummary) {
      return jsonResponse({
        status: "cached",
        detailed_summary: archivedSummary,
        message: "저장된 상세 브리핑을 불러왔습니다.",
        cached: true,
      });
    }

    const eligibility = evaluateLazyDetailSupport(item, config);
    if (!eligibility.supported) {
      return jsonResponse({
        status: "unsupported",
        message: unsupportedMessage(eligibility.reason),
        cached: false,
      });
    }

    const articleText =
      normalizeText(item.source) === "Hacker News Frontpage (HN RSS)" && normalizeText(item.hn_story_id)
        ? await fetchHnDiscussionText(item, config)
        : await fetchArticleText(item.link, config);
    const generated = await generateDetailedSummary(item, articleText, config);
    const cachePayload = {
      item_id: itemId,
      source: normalizeText(item.source),
      link: normalizeText(item.link),
      ai_model: normalizeText(generated.aiModel),
      generated_at: new Date().toISOString(),
      detailed_summary: generated.detailedSummary,
    };

    try {
      await setCachedDetail(config, itemId, cachePayload);
    } catch (error) {
      console.error("lazy-detail cache write failed", error);
    }

    return jsonResponse({
      status: "generated",
      detailed_summary: generated.detailedSummary,
      message: "추가 브리핑을 생성했습니다.",
      cached: false,
    });
  } catch (error) {
    console.error("lazy-detail request failed", error);
    return jsonResponse(
      {
        status: "failed",
        message: "추가 브리핑 생성에 실패했습니다. 원문에서 확인해 주세요.",
        cached: false,
      },
      500
    );
  }
}
