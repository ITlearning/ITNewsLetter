function decodeHtmlEntities(text) {
  const named = {
    amp: "&",
    lt: "<",
    gt: ">",
    quot: "\"",
    apos: "'",
    nbsp: " ",
    mdash: "—",
    ndash: "–",
    rsquo: "’",
    lsquo: "‘",
    rdquo: "”",
    ldquo: "“",
    hellip: "…",
  };

  return String(text || "")
    .replace(/&#(\d+);/g, (_, code) => String.fromCodePoint(Number.parseInt(code, 10)))
    .replace(/&#x([0-9a-f]+);/gi, (_, code) => String.fromCodePoint(Number.parseInt(code, 16)))
    .replace(/&([a-z]+);/gi, (match, name) => named[name.toLowerCase()] || match);
}

function stripTags(html) {
  return decodeHtmlEntities(String(html || "").replace(/<[^>]+>/g, " "));
}

function collapseWhitespace(text) {
  return String(text || "")
    .replace(/\r/g, "\n")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function removeBlockedSections(html) {
  return String(html || "")
    .replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/<(script|style|noscript|svg|template|iframe)[^>]*>[\s\S]*?<\/\1>/gi, " ");
}

function extractMetaContent(html, patterns) {
  for (const pattern of patterns) {
    const match = html.match(pattern);
    if (match && match[1]) {
      return collapseWhitespace(stripTags(match[1]));
    }
  }
  return "";
}

function extractParagraphs(fragment) {
  const matches = fragment.matchAll(/<(p|li|h2|h3)[^>]*>([\s\S]*?)<\/\1>/gi);
  const parts = [];

  for (const match of matches) {
    const text = collapseWhitespace(stripTags(match[2]));
    if (text.length >= 40 && !parts.includes(text)) {
      parts.push(text);
    }
  }

  return parts;
}

function extractFallbackBodyText(html) {
  const bodyMatch = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  const source = bodyMatch ? bodyMatch[1] : html;
  return collapseWhitespace(stripTags(source));
}

function extractArticleText(html, maxChars) {
  const cleaned = removeBlockedSections(html);
  const articleMatch = cleaned.match(/<article[^>]*>([\s\S]*?)<\/article>/i);
  const primaryFragment = articleMatch ? articleMatch[1] : cleaned;

  const title = extractMetaContent(cleaned, [/<title[^>]*>([\s\S]*?)<\/title>/i]);
  const metaDescription = extractMetaContent(cleaned, [
    /<meta[^>]+property=["']og:description["'][^>]+content=["']([^"']+)["'][^>]*>/i,
    /<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)["'][^>]*>/i,
    /<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:description["'][^>]*>/i,
    /<meta[^>]+content=["']([^"']+)["'][^>]+name=["']description["'][^>]*>/i,
  ]);

  const parts = [];
  if (title) {
    parts.push(title);
  }
  if (metaDescription && !parts.includes(metaDescription)) {
    parts.push(metaDescription);
  }

  for (const paragraph of extractParagraphs(primaryFragment)) {
    parts.push(paragraph);
    if (parts.join("\n\n").length >= maxChars) {
      break;
    }
  }

  let text = collapseWhitespace(parts.join("\n\n")).slice(0, maxChars);
  if (text.length >= 400) {
    return text;
  }

  const fallback = extractFallbackBodyText(cleaned).slice(0, maxChars);
  return fallback;
}

export async function fetchArticleText(url, config) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), config.requestTimeoutMs);

  try {
    const response = await fetch(url, {
      method: "GET",
      redirect: "follow",
      signal: controller.signal,
      headers: {
        Accept: "text/html,application/xhtml+xml",
        "User-Agent": config.userAgent,
      },
    });

    if (!response.ok) {
      throw new Error(`Article fetch failed (${response.status}).`);
    }

    const contentType = String(response.headers.get("content-type") || "").toLowerCase();
    if (contentType && !contentType.includes("text/html") && !contentType.includes("text/plain")) {
      throw new Error(`Unsupported content type: ${contentType}`);
    }

    const html = await response.text();
    const extracted = extractArticleText(html, config.maxArticleChars);
    if (extracted.length < 400) {
      throw new Error("Not enough readable article text was extracted.");
    }
    return extracted;
  } finally {
    clearTimeout(timer);
  }
}
