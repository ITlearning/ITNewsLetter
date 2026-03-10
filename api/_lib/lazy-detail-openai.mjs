import { normalizeText } from "./lazy-detail-config.mjs";

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

  const userPrompt = [
    "아래 IT 기사 원문을 바탕으로 한국어 브리핑을 만들어줘.",
    "반드시 JSON만 출력해.",
    '스키마: {"detailed_summary":""}',
    "- detailed_summary: 4~7문장, 250~700자",
    "- 기사 핵심 주장, 맥락, 실제 의미를 중심으로 정리",
    "- 긴 인용문이나 원문 문장을 그대로 베끼지 말고 재서술",
    "",
    `Title: ${normalizeText(item.title)}`,
    `Source: ${normalizeText(item.source)}`,
    `URL: ${normalizeText(item.link)}`,
    "",
    `Article:\n${articleText.slice(0, config.maxArticleChars)}`,
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
    const detailedSummary = normalizeText(parsed.detailed_summary);
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
