import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../lib/api';

/**
 * Custom hook for fetching and managing API data with loading and error states.
 */
export const useApiData = (endpoint, options = {}) => {
    const {
        initialData = [],
        pollInterval = null,
        onSuccess = null
    } = options;

    const [data, setData] = useState(initialData);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const onSuccessRef = useRef(onSuccess);
    onSuccessRef.current = onSuccess;

    const fetchData = useCallback(async (signal = null) => {
        try {
            const result = await api.get(endpoint, signal);
            setData(result);
            setError(null);
            if (onSuccessRef.current) onSuccessRef.current(result);
        } catch (err) {
            if (err.name === 'AbortError') return;
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [endpoint]);

    useEffect(() => {
        const controller = new AbortController();
        fetchData(controller.signal);

        if (pollInterval) {
            const interval = setInterval(() => fetchData(controller.signal), pollInterval);
            return () => {
                controller.abort();
                clearInterval(interval);
            };
        }
        return () => controller.abort();
    }, [fetchData, pollInterval]);

    return { data, loading, error, refresh: fetchData, setData };
};
