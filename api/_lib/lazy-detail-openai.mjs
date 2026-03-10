import { normalizeBriefingMarkdown, normalizeText } from "./lazy-detail-config.mjs";

const HUMANIZER_PROMPT_GUIDANCE = [
  "- 한국어 문장을 사람이 쓴 것처럼 자연스럽게 써라.",
  "- 쉼표를 과하게 쓰지 말고, 필요하면 문장을 나눠라.",
  "- 영어 번역투를 줄이고 한국어다운 어순과 호흡을 사용하라.",
  "- '핵심적이다', '효과적이다', '혁신적이다', '중요하다', '다양하다' 같은 상투적 표현을 반복하지 말라.",
  "- 문장 길이와 리듬을 조금씩 다르게 써라.",
  "- 불필요한 대명사, 지시어, 복수형 '-들' 남발을 피하라.",
  "- 의미와 사실은 바꾸지 말고, 설명은 더 읽기 쉽게 재구성하라.",
].join("\n");

function parseJsonFromText(text) {
  const raw = String(text || "").trim();
  const first = raw.indexOf("{");
  const last = raw.lastIndexOf("}");
  if (first === -1 || last === -1 || last <= first) {
    return {};
  }

  try {
    const parsed = JSON.parse(raw.slice(first, last + 1));
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (error) {
    return {};
  }
}

function isModelAccessDenied(bodyText) {
  const lowered = String(bodyText || "").toLowerCase();
  if (lowered.includes("model_not_found") || lowered.includes("does not have access to model")) {
    return true;
  }

  try {
    const payload = JSON.parse(bodyText);
    const err = payload && typeof payload === "object" ? payload.error || {} : {};
    const code = String(err.code || "").toLowerCase();
    const message = String(err.message || "").toLowerCase();
    return code === "model_not_found" || message.includes("does not have access to model");
  } catch (error) {
    return false;
  }
}

function extractMessageContent(payload) {
  const choices = Array.isArray(payload?.choices) ? payload.choices : [];
  const content = choices[0]?.message?.content;
  if (Array.isArray(content)) {
    return content
      .map((part) => normalizeText(part?.text))
      .filter(Boolean)
      .join(" ");
  }
  return String(content || "");
}

export async function generateDetailedSummary(item, articleText, config) {
  if (!config.openaiApiKey) {
    throw new Error("OPENAI_API_KEY is not configured.");
  }

  if (!Array.isArray(config.openaiModels) || config.openaiModels.length === 0) {
    throw new Error("No OpenAI model candidates are configured.");
  }

  const isHnItem = normalizeText(item?.source) === "Hacker News Frontpage (HN RSS)";
  const userPrompt = [
    isHnItem
      ? "아래 Hacker News 스토리와 댓글 맥락을 바탕으로 한국어 브리핑을 만들어줘."
      : "아래 IT 기사 원문을 바탕으로 한국어 브리핑을 만들어줘.",
    "반드시 JSON만 출력해.",
    '스키마: {"detailed_summary":""}',
    "- detailed_summary: Markdown 허용. 총 350~900자.",
    "  형식: 짧은 도입 문단 1개 + '- ' bullet 3~5개 + 의미/맥락 문단 1개",
    "  허용 문법: 문단, '- ' bullet, '**강조**'만 사용",
    "- 기사 핵심 주장, 맥락, 실제 의미를 중심으로 정리",
    "- 긴 인용문이나 원문 문장을 그대로 베끼지 말고 재서술",
    isHnItem
      ? "- 외부 기사 원문이 없더라도 HN 본문과 댓글 논의에서 드러난 쟁점을 중심으로 정리"
      : "- 원문 핵심 주장과 맥락을 중심으로 정리",
    "",
    HUMANIZER_PROMPT_GUIDANCE,
    "",
    `Title: ${normalizeText(item.title)}`,
    `Source: ${normalizeText(item.source)}`,
    `URL: ${normalizeText(item.link)}`,
    "",
    `${isHnItem ? "HN Context" : "Article"}:\n${articleText.slice(0, config.maxArticleChars)}`,
  ].join("\n");

  let lastError = new Error("OpenAI request failed.");

  for (const model of config.openaiModels) {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${config.openaiApiKey}`,
        "Content-Type": "application/json",
        Accept: "application/json",
        "User-Agent": config.userAgent,
      },
      body: JSON.stringify({
        model,
        temperature: 0.2,
        messages: [
          {
            role: "system",
            content:
              "You are a precise Korean translator and tech news summarizer. Output strictly valid JSON.",
          },
          {
            role: "user",
            content: userPrompt,
          },
        ],
      }),
    });

    if (!response.ok) {
      const bodyText = await response.text();
      if (isModelAccessDenied(bodyText)) {
        lastError = new Error(`Model access denied: ${model}`);
        continue;
      }
      lastError = new Error(`OpenAI request failed (${response.status}): ${bodyText}`);
      continue;
    }

    const payload = await response.json();
    const content = extractMessageContent(payload);
    const parsed = parseJsonFromText(content);
    const detailedSummary = normalizeBriefingMarkdown(parsed.detailed_summary);
    if (detailedSummary) {
      return {
        detailedSummary,
        aiModel: model,
      };
    }

    lastError = new Error(`OpenAI response did not include detailed_summary (model=${model}).`);
  }

  throw lastError;
}
