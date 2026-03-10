import { normalizeText } from "./lazy-detail-config.mjs";

function stripHtml(raw) {
  return String(raw || "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

async function fetchHnJson(path, config) {
  const response = await fetch(`https://hacker-news.firebaseio.com/v0${path}`, {
    method: "GET",
    headers: {
      Accept: "application/json",
      "User-Agent": config.userAgent,
    },
  });

  if (!response.ok) {
    throw new Error(`HN API request failed (${response.status}).`);
  }

  return response.json();
}

function normalizeCommentText(raw) {
  return stripHtml(raw).slice(0, 420);
}

async function fetchCommentPreview(commentIds, config, maxComments = 3) {
  if (!Array.isArray(commentIds) || !commentIds.length) {
    return [];
  }

  const comments = [];
  for (const commentId of commentIds.slice(0, 12)) {
    let payload;
    try {
      payload = await fetchHnJson(`/item/${commentId}.json`, config);
    } catch (error) {
      continue;
    }
    if (!payload || typeof payload !== "object") {
      continue;
    }
    if (payload.deleted || payload.dead || normalizeText(payload.type).toLowerCase() !== "comment") {
      continue;
    }

    const text = normalizeCommentText(payload.text);
    if (text.length < 40) {
      continue;
    }

    const author = normalizeText(payload.by);
    comments.push(author ? `${author}: ${text}` : text);
    if (comments.length >= maxComments) {
      break;
    }
  }

  return comments;
}

export async function fetchHnDiscussionText(item, config) {
  const storyId = normalizeText(item?.hn_story_id);
  if (!storyId) {
    throw new Error("HN story id is missing.");
  }

  const story = await fetchHnJson(`/item/${storyId}.json`, config);
  if (!story || typeof story !== "object") {
    throw new Error("HN story payload is invalid.");
  }

  const title = normalizeText(story.title || item?.title);
  const storyType = normalizeText(story.type || item?.hn_story_type || "story");
  const points = normalizeText(story.score || item?.hn_points || "0");
  const commentsCount = normalizeText(story.descendants || item?.hn_comments_count || "0");
  const storyText = stripHtml(story.text).slice(0, 1400);
  const comments = await fetchCommentPreview(story.kids, config);

  const parts = [
    `HN title: ${title}`,
    `HN type: ${storyType}`,
    `HN points: ${points}`,
    `HN comments: ${commentsCount}`,
  ];

  const discussionUrl = normalizeText(item?.hn_discussion_url) || `https://news.ycombinator.com/item?id=${storyId}`;
  if (discussionUrl) {
    parts.push(`HN discussion URL: ${discussionUrl}`);
  }

  const originalUrl = normalizeText(story.url || item?.link);
  if (originalUrl) {
    parts.push(`Linked URL: ${originalUrl}`);
  }

  if (storyText) {
    parts.push(`HN post text:\n${storyText}`);
  }

  if (comments.length) {
    parts.push(`HN top comments:\n${comments.join("\n")}`);
  }

  return parts.join("\n\n").slice(0, config.maxArticleChars);
}
