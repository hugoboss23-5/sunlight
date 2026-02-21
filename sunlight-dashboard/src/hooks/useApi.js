import { useState, useEffect, useCallback } from 'react';
import { useApp } from '../context/AppContext';

const API_BASE = '/api/v2';

function useApiFetch(path, { skip = false } = {}) {
  const { apiFetch } = useApp();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(!skip);
  const [error, setError] = useState(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiFetch(path);
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [apiFetch, path]);

  useEffect(() => {
    if (skip) return;
    refetch();
  }, [refetch, skip]);

  return { data, loading, error, refetch };
}

export function useLeads() {
  return useApiFetch(`${API_BASE}/risk-inbox`);
}

export function useCasePacket(jobId) {
  return useApiFetch(`${API_BASE}/jobs/${jobId}`, { skip: !jobId });
}

export function usePortfolioStats() {
  return useApiFetch(`${API_BASE}/portfolio`);
}

export function useOnboardingStatus() {
  return useApiFetch(`${API_BASE}/onboarding/status`);
}

export function useAdminConfig() {
  const { apiFetch, isDemoMode } = useApp();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (isDemoMode) {
        const res = await fetch('/mock/admin.json');
        setData(await res.json());
      } else {
        const [health, tenants] = await Promise.all([
          apiFetch('/admin/dashboard/health'),
          apiFetch(`${API_BASE}/tenants`),
        ]);
        setData({ ...health, ...tenants });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [apiFetch, isDemoMode]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { data, loading, error, refetch };
}

export function useUpdateDisposition() {
  const { apiFetch, isDemoMode } = useApp();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const updateDisposition = useCallback(async ({ contract_id, disposition, notes, analyst_id }) => {
    setLoading(true);
    setError(null);
    try {
      if (isDemoMode) {
        return { status: 'ok' };
      }
      const result = await apiFetch(`${API_BASE}/disposition`, {
        method: 'POST',
        body: JSON.stringify({ contract_id, disposition, notes }),
      });
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [apiFetch, isDemoMode]);

  return { updateDisposition, loading, error };
}
