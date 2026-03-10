function cacheKey(itemId) {
  return `lazy-detail:v2:${itemId}`;
}

async function runRedisCommand(config, command) {
  if (!config.redisUrl || !config.redisToken) {
    throw new Error("Redis cache is not configured.");
  }

  const response = await fetch(config.redisUrl, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${config.redisToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(command),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Redis command failed (${response.status}): ${body}`);
  }

  const payload = await response.json();
  return payload.result;
}

export async function getCachedDetail(config, itemId) {
  const result = await runRedisCommand(config, ["GET", cacheKey(itemId)]);
  if (!result) {
    return null;
  }

  try {
    const parsed = JSON.parse(result);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch (error) {
    return null;
  }
}

export async function setCachedDetail(config, itemId, payload) {
  await runRedisCommand(config, [
    "SET",
    cacheKey(itemId),
    JSON.stringify(payload),
    "EX",
    String(config.cacheTtlSeconds),
  ]);
}
