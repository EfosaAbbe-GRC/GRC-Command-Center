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

/**
 * Robust fetch with exponential backoff retry and 401 Silent Refresh.
 * IAM-08: Includes a refresh lock to prevent race conditions during silent refresh.
 */
async function fetchWithRetry(url, options = {}, retries = 3) {
    for (let i = 0; i <= retries; i++) {
        try {
            const response = await fetch(url, options);

            // Handle 401 Unauthorized (Silent Refresh)
            if (response.status === 401 && !url.includes('/auth/refresh') && !url.includes('/auth/login')) {
                const refresh_token = tokenStore.getRefresh();
                if (refresh_token) {
                    try {
                        // REFRESH LOCK (IAM-08): Only one refresh attempt allowed at a time
                        if (!_refreshPromise) {
                            _refreshPromise = api.refresh(refresh_token)
                                .finally(() => { _refreshPromise = null; });
                        }
                        
                        const refreshData = await _refreshPromise;

                        // Retry original request with new token
                        const retryOptions = {
                            ...options,
                            headers: {
                                ...options.headers,
                                'Authorization': `Bearer ${refreshData.access_token}`
                            }
                        };
                        return await fetchWithRetry(url, retryOptions, retries - i);
                    } catch (refreshErr) {
                        tokenStore.clear();
                        window.location.reload(); 
                        throw refreshErr;
                    }
                }
            }

            // Handle 429 Too Many Requests (IAM-08: Jittered Retry)
            if (response.status === 429 && i < retries) {
                const backoff = Math.pow(2, i) * 1000 + Math.random() * 1000;
                await new Promise(res => setTimeout(res, backoff));
                continue;
            }

            if (!response.ok) {
                let errorData = {};
                try { errorData = await response.json(); } catch { /* ignore parse error on fail */ }
                
                // IAM-08: Route security codes to the AuthContext callback
                if (errorData.code && api.onSecurityError) {
                    console.info(`API Security: Intercepted code [${errorData.code}]`);
                    api.onSecurityError(errorData.code);
                }
                
                const error = new Error(errorData.detail || `API Error: ${response.status}`);
                error.status = response.status;
                error.code = errorData.code;
                throw error;
            }
            return await response.json();
        } catch (err) {
            if (err.name === 'AbortError') throw err;
            if (err.status === 401) throw err; 
            if (i === retries) throw err;

            const delay = Math.pow(2, i) * 1000 + (Math.random() * 500); // Backoff + Jitter
            await new Promise(res => setTimeout(res, delay));
        }
    }
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
        const response = await fetch(`${API_BASE_URL}${API_PREFIX}${endpoint}`, {
            method: 'POST',
            headers: { ...getAuthHeaders() },  // no Content-Type — browser sets the multipart boundary
            body: formData,
        });
        if (!response.ok) {
            let errorData = {};
            try { errorData = await response.json(); } catch { /* ignore parse error */ }
            throw new Error(errorData.detail || `Upload failed (${response.status})`);
        }
        return await response.json();
    },

    downloadFile: async (endpoint, filename) => {
        const response = await fetch(`${API_BASE_URL}${API_PREFIX}${endpoint}`, {
            headers: { ...getAuthHeaders() }
        });
        if (!response.ok) {
            throw new Error(`Download failed (${response.status})`);
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
    runAgent: (agentName, args = {}) =>
        api.post('/run-agent', { agent_name: agentName, args }),

    // Ingestion
    triggerIngest: () => api.post('/ingest'),
    triggerNotebookSync: () => api.post('/ingest/notes'),

    // Health check
    checkHealth: () => api.get('/health')
};
