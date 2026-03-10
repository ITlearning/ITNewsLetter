import { normalizeText } from "./lazy-detail-config.mjs";

let archiveCache = {
  url: "",
  expiresAt: 0,
  itemsById: new Map(),
};

async function loadArchiveIndex(config) {
  if (!config.archiveDataUrl) {
    throw new Error("ARCHIVE_DATA_URL is not configured.");
  }

  const now = Date.now();
  if (
    archiveCache.url === config.archiveDataUrl &&
    archiveCache.expiresAt > now &&
    archiveCache.itemsById.size > 0
  ) {
    return archiveCache.itemsById;
  }

  const response = await fetch(config.archiveDataUrl, {
    headers: {
      Accept: "application/json",
      "User-Agent": config.userAgent,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to load archive data (${response.status}).`);
  }

  const payload = await response.json();
  const items = Array.isArray(payload.items) ? payload.items : [];
  const itemsById = new Map();

  for (const item of items) {
    const itemId = normalizeText(item?.id);
    if (itemId) {
      itemsById.set(itemId, item);
    }
  }

  archiveCache = {
    url: config.archiveDataUrl,
    expiresAt: now + config.archiveCacheTtlSeconds * 1000,
    itemsById,
  };

  return itemsById;
}

export async function getArchiveItem(config, itemId) {
  const index = await loadArchiveIndex(config);
  return index.get(normalizeText(itemId)) || null;
}
