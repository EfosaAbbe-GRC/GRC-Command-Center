import { Shield, Terminal, Activity, FileText, Network, GraduationCap, ShieldAlert } from 'lucide-react';

// The one list of terminals, used by both the switcher and App (Client_Export_Hardening_refactor.md F2).
// minRole must match the lowest capability the terminal's own data calls need; the backend still
// enforces every call. Compliance needs RAG_QUERY (analyst): shown to viewers, it opened on a 403.
export const TERMINALS = [
    { id: 'COMPLIANCE', label: 'COMPLIANCE', icon: Shield, color: 'var(--success)', minRole: 'analyst' },
    { id: 'OPS', label: 'OPERATIONS', icon: Terminal, color: 'var(--accent)', minRole: 'analyst' },
    { id: 'EXEC', label: 'EXECUTIVE', icon: Activity, color: '#bc8cff', minRole: 'admin' },
    { id: 'KNOWLEDGE', label: 'KNOWLEDGE', icon: FileText, color: 'var(--warning)', minRole: 'analyst' },
    { id: 'TPRM', label: 'VENDOR RISK', icon: Network, color: '#2dd4bf', minRole: 'analyst' },
    { id: 'RISK', label: 'RISK REGISTER', icon: ShieldAlert, color: '#f87171', minRole: 'viewer' },
    { id: 'INTERVIEW_SIM', label: 'INTERVIEW SIM', icon: GraduationCap, color: '#fb923c', minRole: 'analyst' },
];

const ROLE_LEVELS = { viewer: 1, analyst: 2, admin: 3 };

export const terminalsFor = (role) => {
    const level = ROLE_LEVELS[role] || 0;
    return TERMINALS.filter(t => level >= ROLE_LEVELS[t.minRole]);
};
