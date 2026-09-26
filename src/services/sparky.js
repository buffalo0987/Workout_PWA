/**
 * SparkyFitness REST API Client Module
 *
 * Integrates with self-hosted SparkyFitness instances to pull daily nutritional
 * summaries (calories, protein, carbohydrates, fats, water) and provide
 * structured data for progressive overload and recovery calculations.
 */

const DEFAULT_BASE_URL = process.env.SPARKY_BASE_URL || 'http://localhost:8080';
const DEFAULT_API_TOKEN = process.env.SPARKY_API_TOKEN || '';
const DEFAULT_TIMEOUT_MS = parseInt(process.env.SPARKY_TIMEOUT_MS || '15000', 10);

/**
 * Custom Error class for SparkyFitness integration errors
 */
class SparkyError extends Error {
  constructor(message, details = null) {
    super(message);
    this.name = 'SparkyError';
    this.details = details;
  }
}

/**
 * Normalizes and parses dates to YYYY-MM-DD
 * @param {string|Date} dateInput
 * @returns {string}
 */
function formatDateKey(dateInput) {
  if (!dateInput) {
    return new Date().toISOString().split('T')[0];
  }
  if (dateInput instanceof Date) {
    return dateInput.toISOString().split('T')[0];
  }
  return String(dateInput).split('T')[0];
}

/**
 * Fetches daily macro and calorie summary for a specific date from SparkyFitness.
 *
 * @param {string|Date} date - Target date (YYYY-MM-DD or Date object)
 * @param {Object} [options]
 * @param {string} [options.baseUrl] - Custom base URL override
 * @param {string} [options.apiToken] - Bearer/API token
 * @param {number} [options.timeoutMs] - Request timeout in ms
 * @returns {Promise<{
 *   date: string,
 *   calories: number,
 *   protein_grams: number,
 *   carbs_grams: number,
 *   fat_grams: number,
 *   water_ml: number,
 *   raw: Object,
 *   isFallback: boolean
 * }>}
 */
async function getDailySummary(date, options = {}) {
  const targetDate = formatDateKey(date);
  const baseUrl = (options.baseUrl || DEFAULT_BASE_URL).replace(/\/+$/, '');
  const apiToken = options.apiToken || DEFAULT_API_TOKEN;
  const timeoutMs = options.timeoutMs || DEFAULT_TIMEOUT_MS;

  // Typical Sparky endpoints for daily summaries
  const endpoint = `${baseUrl}/api/v1/nutrition/summary?date=${targetDate}`;

  const headers = {
    'Accept': 'application/json',
  };
  if (apiToken) {
    headers['Authorization'] = `Bearer ${apiToken}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(endpoint, {
      method: 'GET',
      headers,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new SparkyError(
        `SparkyFitness API returned HTTP ${response.status} ${response.statusText}`,
        { status: response.status }
      );
    }

    const payload = await response.json();
    const normalized = normalizeSparkyResponse(payload, targetDate);

    return {
      ...normalized,
      raw: payload,
      isFallback: false,
    };
  } catch (error) {
    clearTimeout(timeoutId);
    console.warn(`[SparkyFitnessService] Unable to reach ${endpoint} (${error.message}). Returning safe fallback mock summary.`);

    return getFallbackDailySummary(targetDate, error.message);
  }
}

/**
 * Fetches nutrition summaries across a multi-day range (e.g. for weekly recovery trend analysis).
 *
 * @param {string|Date} startDate
 * @param {string|Date} endDate
 * @param {Object} [options]
 */
async function getNutritionRange(startDate, endDate, options = {}) {
  const start = new Date(formatDateKey(startDate));
  const end = new Date(formatDateKey(endDate));

  const days = [];
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    days.push(formatDateKey(new Date(d)));
  }

  // Fetch summaries in parallel
  const summaries = await Promise.all(
    days.map((dayStr) => getDailySummary(dayStr, options))
  );

  return summaries;
}

/**
 * Normalizes varying response structures from SparkyFitness into a consistent schema.
 * @param {Object} payload
 * @param {string} date
 */
function normalizeSparkyResponse(payload, date) {
  const data = payload?.data || payload?.summary || payload || {};

  return {
    date,
    calories: Number(data.calories ?? data.total_calories ?? data.energy_kcal ?? 0),
    protein_grams: Number(data.protein ?? data.protein_grams ?? data.total_protein ?? 0),
    carbs_grams: Number(data.carbs ?? data.carbohydrates ?? data.total_carbs ?? 0),
    fat_grams: Number(data.fat ?? data.fat_grams ?? data.total_fat ?? 0),
    water_ml: Number(data.water ?? data.water_ml ?? data.total_water ?? 0),
  };
}

/**
 * Returns a fallback/mock nutritional summary when SparkyFitness is offline or unreachable.
 * @param {string} date
 * @param {string} errorMessage
 */
function getFallbackDailySummary(date, errorMessage) {
  return {
    date,
    calories: 0,
    protein_grams: 0,
    carbs_grams: 0,
    fat_grams: 0,
    water_ml: 0,
    raw: {
      error: errorMessage,
      notice: 'Fallback mock summary generated due to network/endpoint timeout or unreachability.',
    },
    isFallback: true,
  };
}

module.exports = {
  DEFAULT_BASE_URL,
  DEFAULT_API_TOKEN,
  SparkyError,
  formatDateKey,
  getDailySummary,
  getNutritionRange,
  getFallbackDailySummary,
};
