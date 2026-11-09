const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
const API_PREFIX = '/api/v1';

/**
 * Hardened Session Storage (IAM-08)
 * In-memory variables provide the fastest access and protection from storage inspection.
 * sessionStorage provides the fallback for page refreshes within the same tab.
 */
let _accessToken = sessionStorage.getItem('grc_access_token') || null;
let _refreshToken = sessionStorage.getItem('grc_refresh_token') || null;
let _refreshPromise = null;

const tokenStore = {
    getAccess: () => _accessToken || sessionStorage.getItem('grc_access_token'),
    setAccess: (token) => {
        _accessToken = token;
        if (token) sessionStorage.setItem('grc_access_token', token);
        else sessionStorage.removeItem('grc_access_token');
    },
    getRefresh: () => _refreshToken || sessionStorage.getItem('grc_refresh_token'),
    setRefresh: (token) => {
        _refreshToken = token;
        if (token) sessionStorage.setItem('grc_refresh_token', token);
        else sessionStorage.removeItem('grc_refresh_token');
    },
    getRole: () => sessionStorage.getItem('grc_user_role'),
    setRole: (role) => sessionStorage.setItem('grc_user_role', role),
    getResetRequired: () => sessionStorage.getItem('grc_must_reset') === 'true',
    setResetRequired: (flag) => sessionStorage.setItem('grc_must_reset', flag ? 'true' : 'false'),
    clear: () => {
        _accessToken = null;
        _refreshToken = null;
        _refreshPromise = null;
        sessionStorage.removeItem('grc_access_token');
        sessionStorage.removeItem('grc_refresh_token');
        sessionStorage.removeItem('grc_user_role');
        sessionStorage.removeItem('grc_must_reset');
    },
};

function getAuthHeaders() {
    const token = tokenStore.getAccess();
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

const IDEMPOTENT_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);
const backoff = (i) => new Promise(res => setTimeout(res, Math.pow(2, i) * 1000 + Math.random() * 500));

/**
 * Readable message from an API error body. FastAPI validation errors arrive as a list of
 * {loc, msg}; showing them raw printed "[object Object]" (Client_Export_Hardening_refactor.md RA3).
 */
function errorMessage(errorData, status, fallback) {
    const d = errorData && errorData.detail;
    if (typeof d === 'string') return d;
    if (Array.isArray(d)) {
        return d.map(e => {
            const field = (e.loc || []).filter(p => p !== 'body' && p !== 'query' && p !== 'path').join('.');
            return field ? `${field}: ${e.msg}` : e.msg;
        }).join('; ');
    }
    return fallback || `API Error: ${status}`;
}

/** One shared refresh at a time (IAM-08 refresh lock). Returns the new access token, or null. */
async function refreshAccessToken() {
    const refresh_token = tokenStore.getRefresh();
    if (!refresh_token) return null;
    try {
        if (!_refreshPromise) {
            _refreshPromise = api.refresh(refresh_token)
                .finally(() => { _refreshPromise = null; });
        }
        const refreshData = await _refreshPromise;
        return refreshData.access_token;
    } catch (refreshErr) {
        tokenStore.clear();
        window.location.reload();
        throw refreshErr;
    }
}

/**
 * Fetch with silent refresh and SAFE retries (Client_Export_Hardening_refactor.md F3).
 * - 401: refresh once, resend once. A 401 means the server didn't process it: safe for any method.
 * - 429: back off and resend: also rejected before processing.
 * - Network error or 5xx: retried for reads only. A write may already have been applied, and
 *   resending it could create a duplicate record that the append-only history keeps for good.
 * - Any other 4xx: the server refused. Shown at once; resending won't change its answer.
 */
async function fetchWithRetry(url, options = {}, retries = 3, refreshed = false) {
    const idempotent = IDEMPOTENT_METHODS.has((options.method || 'GET').toUpperCase());
    for (let i = 0; i <= retries; i++) {
        let response;
        try {
            response = await fetch(url, options);
        } catch (err) {
            if (err.name === 'AbortError' || !idempotent || i === retries) throw err;
            await backoff(i);
            continue;
        }

        if (response.status === 401 && !refreshed && !url.includes('/auth/refresh') && !url.includes('/auth/login')) {
            const token = await refreshAccessToken();
            if (token) {
                return fetchWithRetry(url, {
                    ...options,
                    headers: { ...options.headers, 'Authorization': `Bearer ${token}` }
                }, retries, true);
            }
        }

        if (response.status === 429 && i < retries) { await backoff(i); continue; }
        if (response.status >= 500 && idempotent && i < retries) { await backoff(i); continue; }

        if (!response.ok) {
            let errorData = {};
            try { errorData = await response.json(); } catch { /* ignore parse error on fail */ }

            // IAM-08: Route security codes to the AuthContext callback
            if (errorData.code && api.onSecurityError) {
                console.info(`API Security: Intercepted code [${errorData.code}]`);
                api.onSecurityError(errorData.code);
            }

            const error = new Error(errorMessage(errorData, response.status));
            error.status = response.status;
            error.code = errorData.code;
            throw error;
        }
        return await response.json();
    }
}

/**
 * Uploads and downloads bypass the JSON helper, so they used to skip the silent refresh: after
 * 15 idle minutes an evidence upload or export failed with 401 (RA4). Refresh once and resend
 * once; a 401 was never processed, so resending is safe. Never retried otherwise.
 */
async function authedFetch(url, init = {}) {
    let response = await fetch(url, { ...init, headers: { ...(init.headers || {}), ...getAuthHeaders() } });
    if (response.status === 401) {
        const token = await refreshAccessToken();
        if (token) {
            response = await fetch(url, { ...init, headers: { ...(init.headers || {}), 'Authorization': `Bearer ${token}` } });
        }
    }
    return response;
}

/**
 * Centralized API Client for GRC Command Center
 */
export const api = {
    // Security event callback (set by AuthContext)
    onSecurityError: null,
    get: (endpoint, signal = null) =>
        fetchWithRetry(`${API_BASE_URL}${API_PREFIX}${endpoint}`, {
            signal,
            headers: { ...getAuthHeaders() }
        }),

    post: (endpoint, data = {}, signal = null) =>
        fetchWithRetry(`${API_BASE_URL}${API_PREFIX}${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders()
            },
            body: JSON.stringify(data),
            signal
        }),

    patch: (endpoint, data = {}, signal = null) =>
        fetchWithRetry(`${API_BASE_URL}${API_PREFIX}${endpoint}`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders()
            },
            body: JSON.stringify(data),
            signal
        }),

    put: (endpoint, data = {}, signal = null) =>
        fetchWithRetry(`${API_BASE_URL}${API_PREFIX}${endpoint}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders()
            },
            body: JSON.stringify(data),
            signal
        }),

    // Auth
    login: async (username, password) => {
        const data = await fetchWithRetry(`${API_BASE_URL}${API_PREFIX}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        
        // Phase 5: Handle must_change_password flag
        tokenStore.setAccess(data.access_token);
        tokenStore.setRefresh(data.refresh_token);
        tokenStore.setResetRequired(!!data.must_change_password);
        
        // Simple JWT decode for role
        try {
            const payload = JSON.parse(atob(data.access_token.split('.')[1]));
            tokenStore.setRole(payload.role || 'viewer');
        } catch {
            tokenStore.setRole('viewer');
        }
        
        return data;
    },

    changePassword: (old_password, new_password) =>
        api.post('/auth/change-password', { old_password, new_password }),

    refresh: async (refresh_token) => {
        const data = await fetch(`${API_BASE_URL}${API_PREFIX}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token })
        }).then(res => {
            if (!res.ok) throw new Error('Refresh failed');
            return res.json();
        });

        tokenStore.setAccess(data.access_token);
        tokenStore.setRefresh(data.refresh_token);
        return data;
    },

    logout: async () => {
        const refresh_token = tokenStore.getRefresh();
        if (refresh_token) {
            try {
                await fetch(`${API_BASE_URL}${API_PREFIX}/auth/logout`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ refresh_token })
                });
            } catch (e) {
                console.error("Auth: Backend logout failed", e);
            }
        }
        tokenStore.clear();
        window.location.reload(); 
    },

    getUser: () => ({
        role: tokenStore.getRole(),
        isAuthenticated: !!tokenStore.getAccess(),
        mustChangePassword: tokenStore.getResetRequired()
    }),

    getAccessToken: () => tokenStore.getAccess(),

    uploadFile: async (endpoint, file) => {
        const formData = new FormData();
        formData.append('file', file);
        // no Content-Type — browser sets the multipart boundary
        const response = await authedFetch(`${API_BASE_URL}${API_PREFIX}${endpoint}`, {
            method: 'POST',
            body: formData,
        });
        if (!response.ok) {
            let errorData = {};
            try { errorData = await response.json(); } catch { /* ignore parse error */ }
            throw new Error(errorMessage(errorData, response.status, `Upload failed (${response.status})`));
        }
        return await response.json();
    },

    downloadFile: async (endpoint, filename) => {
        const response = await authedFetch(`${API_BASE_URL}${API_PREFIX}${endpoint}`);
        if (!response.ok) {
            let errorData = {};
            try { errorData = await response.json(); } catch { /* ignore parse error */ }
            throw new Error(errorMessage(errorData, response.status, `Download failed (${response.status})`));
        }
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    },

    // Agent execution
    runAgent: (agentId, args = {}) =>
        api.post('/run-agent', { agent_id: agentId, args }),

    // Ingestion
    triggerIngest: () => api.post('/ingest'),
    triggerNotebookSync: () => api.post('/ingest/notes'),

    // Health check
    checkHealth: () => api.get('/health')
};
