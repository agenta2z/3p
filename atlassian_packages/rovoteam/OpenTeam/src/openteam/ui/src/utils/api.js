/**
 * API client utilities.
 *
 * All API calls go through these helpers so the backend URL
 * and error handling are centralized in one place.
 */

const API_BASE = '/api';

export async function fetchJson(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    const error = new Error(errorBody.detail || `API error: ${response.status}`);
    error.status = response.status;
    throw error;
  }
  const json = await response.json();
  return json.data !== undefined ? json.data : json;
}

export async function postJson(endpoint, data) {
  return fetchJson(endpoint, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
