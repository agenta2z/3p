/**
 * useTaskTopologies — fetches the list of /task topology presets from the server
 * once on mount. Used by CommandAutocomplete to populate dynamic suggestions
 * after the user types `/task --agent-config `.
 *
 * GET /api/task/topologies returns: { topologies: [{name, description}, ...] }
 */

import { useEffect, useState } from 'react';

export default function useTaskTopologies() {
  const [topologies, setTopologies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/task/topologies')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (!cancelled) {
          setTopologies(Array.isArray(data?.topologies) ? data.topologies : []);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e);
          setLoading(false);
          // Soft-fail: empty list, autocomplete still works for static entries
        }
      });
    return () => { cancelled = true; };
  }, []);

  return { topologies, loading, error };
}

export { useTaskTopologies };
