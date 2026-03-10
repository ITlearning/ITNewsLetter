import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..", "..");
const CONFIG_PATH = path.join(ROOT, "config", "lazy_detail_allowlist.json");

const DEFAULT_OPENAI_MODEL = "gpt-4.1-mini-2025-04-14";
const DEFAULT_OPENAI_FALLBACK_MODELS =
  "gpt-4.1-mini,gpt-4.1-nano-2025-04-14,gpt-4.1-nano,gpt-4o-mini-2024-07-18,gpt-4o-mini";

let cachedConfig = null;

export function normalizeText(value, fallback = "") {
  return String(value || fallback)
    .replace(/\n/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .join(" ");
}

export function normalizeBriefingMarkdown(value, fallback = "") {
  const text = String(value || fallback).replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
  if (!text) {
    return "";
  }

  const normalizedLines = [];
  let previousBlank = false;
  for (const rawLine of text.split("\n")) {
    let line = String(rawLine || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .join(" ");

    if (!line) {
      if (normalizedLines.length && !previousBlank) {
        normalizedLines.push("");
      }
      previousBlank = true;
      continue;
    }

    if (line.startsWith("* ")) {
      line = "- " + line.slice(2).trim();
    } else if (line.startsWith("- ")) {
      line = "- " + line.slice(2).trim();
    }

    normalizedLines.push(line);
    previousBlank = false;
  }

  return normalizedLines.join("\n").trim();
}

function toLowerSet(values) {
  if (!Array.isArray(values)) {
    return new Set();
  }

  return new Set(
    values
      .map((value) => normalizeText(value).toLowerCase())
      .filter(Boolean)
  );
}

function toLowerSetMap(values) {
  if (!values || typeof values !== "object" || Array.isArray(values)) {
    return new Map();
  }

  const result = new Map();
  for (const [sourceName, domains] of Object.entries(values)) {
    const normalizedSource = normalizeText(sourceName).toLowerCase();
    const normalizedDomains = toLowerSet(domains);
    if (normalizedSource && normalizedDomains.size) {
      result.set(normalizedSource, normalizedDomains);
    }
  }
  return result;
}

function toInt(value, fallback) {
  const parsed = Number.parseInt(String(value || ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function splitModelList(primary, fallbackCsv) {
  const models = [];
  for (const token of [primary, ...String(fallbackCsv || "").split(",")]) {
    const normalized = normalizeText(token);
    if (normalized && !models.includes(normalized)) {
      models.push(normalized);
    }
  }
  return models;
}

export function extractLinkDomain(url) {
  try {
    return new URL(normalizeText(url)).hostname.toLowerCase();
  } catch (error) {
    return "";
  }
}

export function domainIsAllowlisted(domain, allowlist) {
  if (!domain) {
    return false;
  }
  for (const candidate of allowlist) {
    if (domain === candidate || domain.endsWith("." + candidate)) {
      return true;
    }
  }
  return false;
}

export function evaluateLazyDetailSupport(item, config) {
  if (!item || typeof item !== "object") {
    return { supported: false, reason: "missing_item" };
  }

  if (!item.is_english_source) {
    return { supported: false, reason: "not_english" };
  }

  const source = normalizeText(item.source).toLowerCase();
  if (source === "hacker news frontpage (hn rss)" && normalizeText(item.hn_story_id)) {
    return { supported: true, reason: "hn_api" };
  }

  const domain = extractLinkDomain(item.link);
  if (!domain) {
    return { supported: false, reason: "missing_domain" };
  }

  const overrideDomains = config.sourceDomainOverrides.get(source);
  if (overrideDomains && overrideDomains.size) {
    if (domainIsAllowlisted(domain, overrideDomains)) {
      return { supported: true, reason: "supported" };
    }
    return { supported: false, reason: "source_domain_not_allowlisted" };
  }

  if (config.excludedSources.has(source)) {
    return { supported: false, reason: "source_excluded" };
  }

  if (config.allowedSources.size && !config.allowedSources.has(source)) {
    return { supported: false, reason: "source_not_allowlisted" };
  }

  if (config.allowedDomains.size && !domainIsAllowlisted(domain, config.allowedDomains)) {
    return { supported: false, reason: "domain_not_allowlisted" };
  }

  return { supported: true, reason: "supported" };
}

export function corsHeaders() {
  return {
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET, OPTIONS",
    "access-control-allow-headers": "content-type",
    "cache-control": "no-store",
  };
}

export function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      ...corsHeaders(),
    },
  });
}

export async function loadLazyDetailConfig() {
  if (cachedConfig) {
    return cachedConfig;
  }

  let rawConfig = {};
  try {
    rawConfig = JSON.parse(await fs.readFile(CONFIG_PATH, "utf-8"));
  } catch (error) {
    rawConfig = {};
  }

  cachedConfig = {
    allowedSources: toLowerSet(rawConfig.allowed_sources),
    excludedSources: toLowerSet(rawConfig.excluded_sources),
    allowedDomains: toLowerSet(rawConfig.allowed_domains),
    sourceDomainOverrides: toLowerSetMap(rawConfig.source_domain_overrides),
    archiveDataUrl: normalizeText(process.env.ARCHIVE_DATA_URL),
    openaiApiKey: normalizeText(process.env.OPENAI_API_KEY),
    openaiModels: splitModelList(
      process.env.OPENAI_MODEL || DEFAULT_OPENAI_MODEL,
      process.env.OPENAI_FALLBACK_MODELS || DEFAULT_OPENAI_FALLBACK_MODELS
    ),
    redisUrl: normalizeText(process.env.UPSTASH_REDIS_REST_URL),
    redisToken: normalizeText(process.env.UPSTASH_REDIS_REST_TOKEN),
    requestTimeoutMs: toInt(rawConfig.request_timeout_ms, 15000),
    maxArticleChars: toInt(rawConfig.max_article_chars, 12000),
    cacheTtlSeconds: toInt(rawConfig.cache_ttl_seconds, 15552000),
    archiveCacheTtlSeconds: toInt(rawConfig.archive_cache_ttl_seconds, 900),
    userAgent: "ITNewsLetterLazyDetail/1.0 (+https://github.com/ITlearning/ITNewsLetter)",
  };

  return cachedConfig;
}
