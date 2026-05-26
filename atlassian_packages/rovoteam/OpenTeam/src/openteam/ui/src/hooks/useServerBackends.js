/**
 * useServerBackends — fetches the list of registered LLM backends from
 * /api/server/backends, including availability + status messages.
 *
 * Cached for the app session via a module-level promise (no React Query
 * dependency added). Refetched only on explicit refresh().
 *
 * Returns:
 *   backends         — array of { name, display_name, description,
 *                                 available, status_message, default_model }
 *   defaultBackend   — server's default backend name
 *   defaultModel     — server's default model (may be null)
 *   loading          — boolean
 *   error            — Error | null
 *   refresh          — () => void
 */

import { useState, useEffect, useCallback, useRef } from 'react';

const ENDPOINT = '/api/server/backends';

let _cache = null;
let _inflight = null;

async function _fetchBackends() {
  const res = await fetch(ENDPOINT);
  if (!res.ok) {
    throw new Error(`GET ${ENDPOINT} returned ${res.status}`);
  }
  return res.json();
}

function _getCachedOrFetch() {
  if (_cache) return Promise.resolve(_cache);
  if (_inflight) return _inflight;
  _inflight = _fetchBackends()
    .then((data) => {
      _cache = data;
      _inflight = null;
      return data;
    })
    .catch((err) => {
      _inflight = null;
      throw err;
    });
  return _inflight;
}

export function useServerBackends() {
  const [data, setData] = useState(_cache);
  const [loading, setLoading] = useState(_cache === null);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  useEffect(() => {
    if (_cache) return;
    setLoading(true);
    _getCachedOrFetch()
      .then((d) => {
        if (mountedRef.current) {
          setData(d);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mountedRef.current) {
          setError(err);
          setLoading(false);
        }
      });
  }, []);

  const refresh = useCallback(() => {
    _cache = null;
    setLoading(true);
    setError(null);
    _getCachedOrFetch()
      .then((d) => {
        if (mountedRef.current) {
          setData(d);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mountedRef.current) {
          setError(err);
          setLoading(false);
        }
      });
  }, []);

  return {
    backends: data?.backends || [],
    defaultBackend: data?.default_backend || null,
    defaultModel: data?.default_model || null,
    loading,
    error,
    refresh,
  };
}

export default useServerBackends;
