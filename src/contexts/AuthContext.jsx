import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../lib/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(() => {
        const { role, isAuthenticated, mustChangePassword } = api.getUser();
        return isAuthenticated ? { role, mustChangePassword } : null;
    });

    const [needsReset, setNeedsReset] = useState(() => {
        const { mustChangePassword, isAuthenticated } = api.getUser();
        return isAuthenticated && mustChangePassword;
    });

    useEffect(() => {
        // 1. Wire security events to state
        api.onSecurityError = (code) => {
            if (code === 'PASSWORD_RESET_REQUIRED') {
                setNeedsReset(true);
            }
        };

        // 2. Periodic Session Heartbeat (IAM-08)
        // Detects server-side revocation or expiration proactively
        const heartbeat = setInterval(async () => {
            if (api.getUser().isAuthenticated) {
                try {
                    await api.checkHealth();
                } catch (err) {
                    if (err.status === 401) {
                        console.warn("Auth: Session validation failed, logging out.");
                        logout();
                    }
                }
            }
        }, 60000 * 5); // 5 minute check

        return () => { 
            api.onSecurityError = null;
            clearInterval(heartbeat);
        };
    }, [user]);

    const login = async (username, password) => {
        const data = await api.login(username, password);
        
        // Extract role from the access token payload
        let role = 'viewer';
        try {
            const tokenPayloadJSON = atob(data.access_token.split('.')[1]);
            const payload = JSON.parse(tokenPayloadJSON);
            role = payload.role || 'viewer';
        } catch {
            console.error("Auth: Failed to decode role from token");
        }
        
        const mcp = !!data.must_change_password;
        
        setUser({ username, role, mustChangePassword: mcp });
        setNeedsReset(mcp);
        return data;
    };

    const clearResetState = () => {
        setNeedsReset(false);
        setUser(prev => prev ? { ...prev, mustChangePassword: false } : null);
    };

    const logout = async () => {
        await api.logout();
        setUser(null);
        setNeedsReset(false);
    };

    return (
        <AuthContext.Provider value={{ 
            user, 
            login, 
            logout, 
            isAuthenticated: !!user,
            needsReset,
            setNeedsReset,
            clearResetState
        }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
