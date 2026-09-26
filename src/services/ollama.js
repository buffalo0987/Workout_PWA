/**
 * Ollama Service Integration Module
 *
 * Connects to local/remote Ollama instance for progressive overload calculations
 * and recovery evaluation. Supports dynamic model selection, auto-discovery of
 * installed models, healthchecks, and fallback/mock mechanisms on network timeouts.
 */

const DEFAULT_BASE_URL = process.env.OLLAMA_BASE_URL || 'http://localhost:11434';
const DEFAULT_MODEL = process.env.DEFAULT_OLLAMA_MODEL || 'qwen3:14b';
const DEFAULT_TIMEOUT_MS = parseInt(process.env.OLLAMA_TIMEOUT_MS || '45000', 10);

/**
 * Custom Error class for Ollama client failures
 */
class OllamaError extends Error {
  constructor(message, details = null) {
    super(message);
    this.name = 'OllamaError';
    this.details = details;
  }
}

/**
 * Queries Ollama tags endpoint to auto-discover locally installed models.
 *
 * @param {Object} [options]
 * @param {string} [options.baseUrl] - Custom base URL override
 * @param {number} [options.timeoutMs] - Request timeout in milliseconds
 * @returns {Promise<Array<{name: string, modified_at: string, size: number, digest: string}>>}
 */
async function getAvailableModels(options = {}) {
  const baseUrl = (options.baseUrl || DEFAULT_BASE_URL).replace(/\/+$/, '');
  const timeoutMs = options.timeoutMs || 10000;
  const endpoint = `${baseUrl}/api/tags`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(endpoint, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new OllamaError(
        `Failed to fetch Ollama models: HTTP ${response.status} ${response.statusText}`,
        { status: response.status }
      );
    }

    const data = await response.json();
    return Array.isArray(data.models) ? data.models : [];
  } catch (error) {
    clearTimeout(timeoutId);

    // Fallback: return mock/cached models so the UI and settings never crash
    console.warn(`[OllamaService] Warning: Unable to query models from ${endpoint}. Using fallback list. Reason: ${error.message}`);
    return getFallbackModelList(error.message);
  }
}

/**
 * Returns fallback model list when Ollama server is unreachable or offline.
 * @param {string} reason
 */
function getFallbackModelList(reason = 'Service unreachable') {
  return [
    { name: 'qwen3:14b', status: 'fallback', reason },
    { name: 'gemma4:12b', status: 'fallback', reason },
    { name: 'llama3.3:8b', status: 'fallback', reason },
  ];
}

/**
 * Generates progressive overload or recovery completions via Ollama.
 *
 * @param {Object} params
 * @param {string} params.prompt - Formatted instruction prompt
 * @param {string} [params.systemPrompt] - System prompt defining persona and JSON constraints
 * @param {string} [params.model] - Desired model (defaults to setting/env default)
 * @param {Object} [params.contextData] - Structured workout context passed to fallback generator if call fails
 * @param {string} [params.baseUrl] - Ollama base URL override
 * @param {number} [params.timeoutMs] - Custom timeout in milliseconds
 * @param {boolean} [params.rawJsonFormat] - Force JSON format output from Ollama
 * @returns {Promise<{content: string, parsedJson: Object|null, model: string, isFallback: boolean}>}
 */
async function generateCompletion({
  prompt,
  systemPrompt = 'You are an elite strength and conditioning coach analyzing progressive overload.',
  model = DEFAULT_MODEL,
  contextData = null,
  baseUrl = DEFAULT_BASE_URL,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  rawJsonFormat = true,
}) {
  const cleanBaseUrl = baseUrl.replace(/\/+$/, '');
  const endpoint = `${cleanBaseUrl}/api/generate`;

  const requestBody = {
    model: model || DEFAULT_MODEL,
    prompt: prompt,
    system: systemPrompt,
    stream: false,
    options: {
      temperature: 0.2, // Low temperature for deterministic overload math
    },
  };

  if (rawJsonFormat) {
    requestBody.format = 'json';
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(requestBody),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorText = await response.text().catch(() => '');
      throw new OllamaError(`Ollama request failed [HTTP ${response.status}]: ${errorText}`, {
        status: response.status,
      });
    }

    const data = await response.json();
    const rawResponse = data.response || '';

    let parsedJson = null;
    if (rawJsonFormat) {
      try {
        parsedJson = JSON.parse(rawResponse);
      } catch (e) {
        console.warn('[OllamaService] Warning: Failed to parse JSON response from Ollama:', rawResponse);
      }
    }

    return {
      content: rawResponse,
      parsedJson,
      model: data.model || model,
      isFallback: false,
      totalDuration: data.total_duration || null,
    };
  } catch (error) {
    clearTimeout(timeoutId);
    console.warn(`[OllamaService] Ollama API unreachable or timed out (${error.message}). Invoking progressive overload fallback logic.`);

    const fallbackResult = generateFallbackOverload(contextData, model, error.message);
    return fallbackResult;
  }
}

/**
 * Fallback progressive overload heuristic when Ollama is offline or times out.
 * Implements standard double-progression rules.
 *
 * @param {Object} contextData - Current exercise and previous workout set data
 * @param {string} model - Requested model
 * @param {string} errorMessage - Failure reason
 */
function generateFallbackOverload(contextData, model, errorMessage) {
  const currentWeight = Number(contextData?.current_weight || contextData?.weight || 0);
  const targetRepsMin = Number(contextData?.target_rep_range?.[0] || 8);
  const targetRepsMax = Number(contextData?.target_rep_range?.[1] || 12);
  const lastReps = Number(contextData?.last_reps || 0);
  const lastRpe = Number(contextData?.last_rpe || 8.0);

  let suggestedWeight = currentWeight;
  let suggestedReps = `${targetRepsMin}-${targetRepsMax}`;
  let strategy = 'maintain';
  let rationale = '';

  if (lastReps >= targetRepsMax && lastRpe <= 8.5) {
    // Top of rep range hit with sub-maximal effort -> Increment weight by ~2.5% (or 2.5kg/5lbs)
    const increment = currentWeight >= 50 ? 2.5 : 1.25;
    suggestedWeight = +(currentWeight + increment).toFixed(2);
    suggestedReps = `${targetRepsMin}-${targetRepsMin + 2}`;
    strategy = 'weight_increase';
    rationale = `Fallback Heuristic: Hit top of rep target (${lastReps}/${targetRepsMax}) @ RPE ${lastRpe}. Increased weight by ${increment} to start new progression cycle.`;
  } else if (lastReps > 0 && lastReps < targetRepsMin && lastRpe >= 9.5) {
    // Under minimum rep range with extreme fatigue -> Slight deload or hold
    strategy = 'rep_consolidation';
    rationale = `Fallback Heuristic: High fatigue detected (${lastReps} reps @ RPE ${lastRpe}). Maintain ${currentWeight} to consolidate volume safely.`;
  } else {
    // In middle of range -> Add 1 rep
    strategy = 'rep_increase';
    rationale = `Fallback Heuristic: Progression active. Maintain ${currentWeight} and aim for ${Math.min(lastReps + 1, targetRepsMax)} reps before increasing load.`;
  }

  const fallbackJson = {
    suggested_weight: suggestedWeight,
    target_reps: suggestedReps,
    suggested_sets: contextData?.target_sets || 3,
    strategy,
    rationale,
    confidence_score: 0.80,
    offline_fallback: true,
  };

  return {
    content: JSON.stringify(fallbackJson),
    parsedJson: fallbackJson,
    model: `${model} (offline fallback: ${errorMessage})`,
    isFallback: true,
    totalDuration: 0,
  };
}

module.exports = {
  DEFAULT_BASE_URL,
  DEFAULT_MODEL,
  OllamaError,
  getAvailableModels,
  generateCompletion,
  generateFallbackOverload,
};
