const API_URL = 'https://api.groq.com/openai/v1/chat/completions';
const MAX_HISTORY_MESSAGES = 6;
const MAX_MESSAGE_LENGTH = 1400;

const SHOPPING_ASSISTANT_PROMPT = `You are Ani, a concise shopping assistant. Your scope is shopping: product discovery, comparisons, buying advice, and questions that directly help someone choose or use a product. Politely decline unrelated requests in one short sentence and invite a shopping question. Do not use browser search for unrelated requests or simple conversational follow-ups.

Use India and INR (₹) as the default shopping market. Interpret shorthand budgets such as “30k” as ₹30,000 unless the user specifies another currency or region. Do not ask for currency/region when the user has not signaled another market.

Keep each reply concise (aim for 140 words, excluding source links and table headings). Ask one short follow-up if budget, region, or use case is essential and missing. Research with browser search before stating current product facts or making a shortlist. Never invent a product, price, feature, review, or source. Say when price or availability can vary by retailer or region.

Use trusted sources only: manufacturer product/specification and warranty pages; official government or standards sources; established, reputable independent product-testing publications; and direct listings from well-known authorized retailers for current prices/availability. Verify that each source matches the exact model/variant and country. Do not rely on search snippets alone. Do not cite forums, social posts, anonymous reviews, scraped comparison/affiliate blogs, unknown shops, or unverified marketplace sellers. If a claim cannot be verified through a trusted source, omit it. Link the source inline with Markdown close to the claim; never invent URLs or use opaque citation markers. If trusted sources do not support a reliable price or three distinct choices, say that plainly and provide fewer well-supported options rather than guessing.

When you have enough details, shortlist up to three products (exactly three only when all three are adequately supported). Keep the response compact: one short Markdown comparison table with columns Product, Approx. price, Why it fits, and Main trade-off; one row per product, with short cells. Do not create a separate multi-paragraph subsection for each product. Follow the table with one concise **Recommendation** sentence, then one short paragraph headed **In simple terms** explaining why that choice suits the shopper in everyday language. Avoid jargon, unexplained specs, and talking down to the user. Keep answers focused on the shopping request. Do not emit raw HTML or JSON.`;

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function normalizeHistory(history) {
  if (!Array.isArray(history)) {
    throw new ApiError(400, 'Send a message to start shopping with Ani.');
  }

  const messages = history
    .slice(-MAX_HISTORY_MESSAGES)
    .filter((item) => item && ['user', 'assistant'].includes(item.role))
    .filter((item) => typeof item.content === 'string')
    .map(({ role, content }) => ({
      role,
      content: content.trim().slice(0, MAX_MESSAGE_LENGTH),
    }))
    .filter((item) => item.content.length > 0);

  if (!messages.length || messages.at(-1).role !== 'user') {
    throw new ApiError(400, 'Send a message to start shopping with Ani.');
  }

  return messages;
}

function getUpstreamError(status, message) {
  if (status === 401 || status === 403) {
    return new ApiError(502, 'Groq could not authenticate the server API key. Check the GROQ_API_KEY setting.');
  }
  if (status === 429) {
    return new ApiError(429, 'Ani is busy right now. Wait a moment and try again.');
  }
  if (/parsing failed|failed_generation/i.test(message)) {
    return new ApiError(502, 'Ani’s search returned an incomplete result. Please try again.');
  }
  return new ApiError(502, 'Ani could not reach Groq just now. Please try again in a moment.');
}

function collectSearchSources(message) {
  const executedTools = Array.isArray(message.executed_tools) ? message.executed_tools : [];
  const sources = [];
  const seenUrls = new Set();

  for (const tool of executedTools) {
    const results = tool?.search_results?.results;
    if (!Array.isArray(results)) continue;

    for (const result of results) {
      if (typeof result?.url !== 'string' || typeof result?.title !== 'string') continue;

      let sourceUrl;
      try {
        sourceUrl = new URL(result.url);
      } catch {
        continue;
      }
      if (sourceUrl.protocol !== 'https:' || seenUrls.has(sourceUrl.href)) continue;

      seenUrls.add(sourceUrl.href);
      sources.push({
        id: String(sources.length + 1),
        title: result.title.trim().slice(0, 180),
        url: sourceUrl.href,
      });
      if (sources.length >= 30) return sources;
    }
  }

  return sources;
}

async function requestGroq(messages, { apiKey, model, maxCompletionTokens }) {
  const body = {
    model,
    messages: [
      { role: 'system', content: SHOPPING_ASSISTANT_PROMPT },
      ...messages,
    ],
    tools: [{ type: 'browser_search' }],
    tool_choice: 'auto',
    temperature: 0.2,
    max_completion_tokens: maxCompletionTokens,
  };

  for (let attempt = 0; attempt < 2; attempt += 1) {
    let response;
    try {
      response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${apiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(90_000),
      });
    } catch (error) {
      if (error.name === 'TimeoutError') {
        throw new ApiError(504, 'That research took too long. Try a more focused request.');
      }
      throw new ApiError(502, 'Ani could not reach Groq just now. Check the connection and try again.');
    }

    const result = await response.json().catch(() => ({}));
    if (response.ok) {
      const message = result.choices?.[0]?.message;
      const answer = message?.content;
      if (typeof answer === 'string' && answer.trim()) {
        return { answer: answer.trim(), sources: collectSearchSources(message) };
      }
      throw new ApiError(502, 'Ani did not receive a usable answer. Please try again.');
    }

    const upstreamMessage = result.error?.message || '';
    const canRetry = response.status === 400
      && /parsing failed|failed_generation/i.test(upstreamMessage)
      && attempt === 0;

    if (canRetry) {
      body.temperature = 0.1;
      continue;
    }

    console.error('Groq request failed with status', response.status);
    throw getUpstreamError(response.status, upstreamMessage);
  }

  throw new ApiError(502, 'Ani could not complete that request. Please try again.');
}

async function getAssistantReply(history) {
  const apiKey = process.env.GROQ_API_KEY;
  if (!apiKey) {
    throw new ApiError(503, 'Ani needs a Groq API key before she can research products.');
  }

  const messages = normalizeHistory(history);
  const model = process.env.GROQ_MODEL || 'openai/gpt-oss-120b';
  const configuredLimit = Number.parseInt(process.env.GROQ_MAX_COMPLETION_TOKENS, 10);
  const maxCompletionTokens = Number.isFinite(configuredLimit)
    ? Math.min(Math.max(configuredLimit, 256), 1200)
    : 900;

  return requestGroq(messages, { apiKey, model, maxCompletionTokens });
}

module.exports = { ApiError, getAssistantReply };
