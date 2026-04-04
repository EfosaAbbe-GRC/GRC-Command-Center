import React, { useState } from 'react';
import { useApiData } from '../hooks/useApiData';
import { useAuth } from '../contexts/useAuth';
import { api } from '../lib/api';
import { 
    Activity, Shield, Monitor, UserCheck, Clock, PieChart, AlertTriangle, 
    CheckCircle2, TrendingUp, DollarSign, Briefcase, Users, ChevronUp, 
    ChevronDown, ShieldAlert, Lock, Unlock, RefreshCw, LogOut, User, 
    Search, Filter, ShieldCheck, FileKey, AlertOctagon, AlertCircle
} from 'lucide-react';

export const ExecutiveTerminal = () => {
    const { user } = useAuth();
    const { data: stats, loading, error, refresh } = useApiData('/executive/stats', {
        initialData: {
            compliance: { value: "--", trend: "--" },
            risk_score: { value: "--", trend: "--" },
            vulnerabilities: { value: "--", trend: "--" },
            audit_readiness: { value: "--", trend: "--" },
            budget: { spent: 0, total: 0 },
            alerts: []
        }
    });

    const { data: dashboard } = useApiData('/executive/dashboard', {
        initialData: {
            open_findings: 0,
            policy_coverage: 0,
            active_users: 0,
            trend_data: []
        }
    });

    const [filterUser, setFilterUser] = useState('');
    const [filterType, setFilterType] = useState('');

    const { data: auditEvents, loading: auditLoading } = useApiData(
       `/admin/audit/security?user=${filterUser}&event_type=${filterType}`,
       { initialData: [] }
    );
    
    // Strategic Policy State (IAM-09)
    const { data: policies, setData: setPolicies, loading: policiesLoading } = useApiData('/admin/policies', {
        initialData: []
    });

    const handleUpdatePolicy = async (policyId, updates) => {
        try {
            const result = await api.put(`/admin/policies/${policyId}`, updates);
            if (result.status === 'success') {
                setPolicies(prev => prev.map(p => p.id === policyId ? { ...p, ...updates, version: p.version + 1 } : p));
            }
        } catch (err) {
            console.error("Policy Update Failed:", err);
        }
    };

    if (loading) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center bg-[var(--layer-0)] text-[var(--accent)]">
                <Activity className="animate-spin mb-4" size={48} />
                <span className="text-[10px] font-bold tracking-[0.3em] font-mono animate-pulse uppercase">Aggregating_Insight_Data</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center bg-[var(--layer-0)] text-[var(--danger)]">
                <Shield className="mb-4" size={48} strokeWidth={1} />
                <span className="text-sm font-bold tracking-[0.1em] font-display uppercase mb-2">Executive Layer Offline</span>
                <span className="text-[10px] text-[var(--text-tertiary)] font-mono mb-6">{error.message}</span>
                <button
                    onClick={() => refresh()}
                    className="px-8 py-2.5 bg-[var(--danger-subtle)] border border-[var(--danger)] rounded-md text-[10px] font-bold text-[var(--danger)] hover:bg-[var(--danger)] hover:text-white transition-all shadow-lg active:scale-95"
                >
                    RETRY_CONNECTION
                </button>
            </div>
        );
    }

    return (
        <div className="flex-1 bg-[var(--layer-0)] p-8 overflow-auto flex justify-center scrollbar-thin scrollbar-thumb-[var(--layer-4)]">
            <div className="w-full max-w-[1600px] space-y-8 animate-in fade-in duration-700">

                {/* 1. Dashboard Header */}
                <div className="flex items-end justify-between border-b border-[var(--border-default)] pb-8 bg-gradient-to-b from-[var(--layer-1)]/50 to-transparent p-6 rounded-t-xl">
                    <div className="flex items-start gap-6">
                        <div className="p-4 bg-[var(--layer-1)] border border-[var(--border-emphasis)] rounded-xl glow-accent">
                            <Shield className="text-[var(--accent)]" size={44} strokeWidth={1.5} />
                        </div>
                        <div>
                            <h1 className="text-4xl font-bold text-[var(--text-primary)] font-display tracking-tight leading-none mb-4 uppercase">
                                EXECUTIVE_RISK_OVERVIEW
                            </h1>
                            <div className="flex items-center gap-4 text-[var(--text-secondary)] font-mono text-[11px] font-bold tracking-widest">
                                <span className="flex items-center gap-1.5"><Monitor size={12} className="text-[var(--accent)]" /> GRC_COMMAND_LAYER</span>
                                <span className="text-[var(--border-emphasis)]">/</span>
                                <span className="flex items-center gap-1.5"><UserCheck size={12} className="text-[var(--success)]" /> USR_{user?.role?.toUpperCase()}_AUTH</span>
                                <span className="text-[var(--border-emphasis)]">/</span>
                                <span className="text-[var(--text-tertiary)] flex items-center gap-1.5"><Clock size={12} /> SECURE_SESSION</span>
                            </div>
                        </div>
                    </div>

                    <div className="flex gap-4">
                        <div className="bg-[var(--layer-1)] border border-[var(--border-default)] px-10 py-4 rounded-xl flex items-center gap-6 shadow-xl relative overflow-hidden group">
                            <div className="text-right">
                                <div className="text-[10px] text-[var(--text-tertiary)] font-bold tracking-[0.2em] mb-1.5">UNIT_HEALTH</div>
                                <div className="text-[var(--success)] font-bold text-2xl flex items-center justify-end gap-3 font-mono">
                                    <div className="relative flex h-3 w-3">
                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--success)] opacity-75"></span>
                                        <span className="relative inline-flex rounded-full h-3 w-3 bg-[var(--success)]"></span>
                                    </div>
                                    OPTIMAL
                                </div>
                            </div>
                            {/* Accent highlight */}
                            <div className="absolute left-0 bottom-0 top-0 w-1 bg-[var(--success)] glow-success transform -translate-x-full group-hover:translate-x-0 transition-transform duration-500" />
                        </div>
                        <div className="bg-[var(--layer-1)] border border-[var(--border-default)] px-10 py-4 rounded-xl flex items-center gap-6 shadow-xl">
                             <div className="text-right">
                                <div className="text-[10px] text-[var(--text-tertiary)] font-bold tracking-[0.2em] mb-1.5">FISCAL_CONTEXT</div>
                                <div className="text-[var(--text-primary)] font-bold text-2xl font-mono">Q3_FY2026</div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* 2. Primary KPI Cards */}
                <div className="grid grid-cols-4 gap-6">
                    <KPICard
                        title="GOVERNANCE_POSTURE"
                        value={stats.compliance.value}
                        trend={stats.compliance.trend}
                        icon={<PieChart size={32} strokeWidth={1.5} className="text-[var(--accent)]" />}
                        variant="accent"
                    />
                    <KPICard
                        title="CRITICAL_EXPOSURE"
                        value={stats.risk_score.value}
                        trend={stats.risk_score.trend}
                        icon={<AlertTriangle size={32} strokeWidth={1.5} className="text-[var(--danger)]" />}
                        subtext="Acceptable Threshold: <20"
                        variant="danger"
                    />
                    <KPICard
                        title="DETECTED_VULNERABILITIES"
                        value={stats.vulnerabilities.value}
                        trend={stats.vulnerabilities.trend}
                        icon={<Activity size={32} strokeWidth={1.5} className="text-[var(--warning)]" />}
                        variant="warning"
                    />
                    <KPICard
                        title="AUDIT_STATE"
                        value={stats.audit_readiness.value}
                        trend={stats.audit_readiness.trend}
                        icon={<CheckCircle2 size={32} strokeWidth={1.5} className="text-[var(--success)]" />}
                        variant="success"
                    />
                </div>

                {/* 3. Operational Analytics Strip */}
                <div className="grid grid-cols-12 gap-8 min-h-[500px]">

                    {/* Posture Trend Graph (8 cols) */}
                    <div className="col-span-8 bg-[var(--layer-1)] border border-[var(--border-default)] rounded-2xl p-8 flex flex-col shadow-2xl relative overflow-hidden group">
                        <div className="flex justify-between items-center mb-10 shrink-0 z-10">
                            <div>
                                <h3 className="font-bold text-[var(--text-primary)] text-xl font-display flex items-center gap-3 tracking-tight">
                                    <TrendingUp size={24} className="text-[var(--accent)]" />
                                    SECURITY_POSTURE_TRENDING
                                </h3>
                                <p className="text-[var(--text-tertiary)] text-[11px] font-mono mt-2 font-bold opacity-60">Aggregate compliance score variance over time.</p>
                            </div>
                            <div className="flex gap-2 bg-[var(--layer-2)] p-1.5 rounded-lg border border-[var(--border-default)]">
                                {['1M', '3M', '6M', 'YTD'].map(p => (
                                    <button key={p} className={`px-5 py-2 rounded-md text-[11px] font-bold font-mono transition-all ${p === 'YTD' ? 'bg-[var(--accent-emphasis)] text-white shadow-lg' : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--layer-3)]'}`}>
                                        {p}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Professional Visual Chart Container */}
                        <div className="flex-1 flex items-end justify-between px-16 pb-6 border-l border-b border-[var(--border-subtle)] relative z-10 mx-6 mb-4">
                            
                            {/* Y-Axis Labels */}
                            <div className="absolute left-[-50px] inset-y-0 flex flex-col justify-between text-[9px] font-mono font-bold text-[var(--text-tertiary)] uppercase tracking-tighter pb-10">
                                <span>100%</span>
                                <span>75%</span>
                                <span>50%</span>
                                <span>25%</span>
                                <span>0%</span>
                            </div>

                            {/* Horizontal Grid Lines */}
                            <div className="absolute inset-0 pointer-events-none flex flex-col justify-between opacity-50 pb-6 pr-4">
                                <div className="w-full h-px bg-[var(--border-default)] border-dashed border-b" />
                                <div className="w-full h-px bg-[var(--border-default)] border-dashed border-b" />
                                <div className="w-full h-px bg-[var(--border-default)] border-dashed border-b" />
                                <div className="w-full h-px bg-[var(--border-default)] border-dashed border-b" />
                                <div className="w-full h-px bg-[var(--border-default)]" />
                            </div>

                            {(dashboard.trend_data.length > 0 ? dashboard.trend_data : [{month:'--',score:0}, {month:'--',score:0}, {month:'--',score:0}]).map((point, i) => (
                                <div key={i} className="w-20 group relative flex flex-col justify-end h-full z-20 transition-all cursor-pointer">
                                    <div
                                        style={{ height: `${point.score}%` }}
                                        className={`w-full bg-gradient-to-t rounded-t-sm transition-all duration-500 relative ${point.score > 85 ? 'from-[var(--success-subtle)] to-[var(--success)] shadow-[0_0_20px_var(--success-subtle)]' : 'from-[var(--accent-subtle)] to-[var(--accent)] shadow-[0_0_20px_var(--accent-subtle)]'}`}
                                    >
                                        <div className="absolute -top-12 left-1/2 -translate-x-1/2 bg-[var(--layer-2)] border border-[var(--border-emphasis)] text-[var(--text-primary)] px-4 py-1.5 rounded-lg text-xs font-mono font-bold shadow-2xl opacity-0 group-hover:opacity-100 transition-all translate-y-3 group-hover:translate-y-0 scale-110 pointer-events-none">
                                            {point.score}%
                                        </div>
                                        {/* Highlight top border */}
                                        <div className="absolute top-0 left-0 right-0 h-1 bg-white/20" />
                                    </div>
                                    <span className="text-[var(--text-tertiary)] text-[10px] font-mono font-bold mt-6 tracking-[0.2em] group-hover:text-[var(--text-primary)] transition-colors text-center w-full uppercase">
                                        {point.month}
                                    </span>
                                </div>
                            ))}
                        </div>

                        {/* Background Decor */}
                        <div className="absolute right-0 bottom-0 opacity-[0.02] transform translate-x-1/4 translate-y-1/4 pointer-events-none">
                            <TrendingUp size={400} />
                        </div>
                    </div>

                    {/* Fiscal & Alert Summary (4 cols) */}
                    <div className="col-span-4 flex flex-col gap-8">
                        {/* Budget Status */}
                        <div className="bg-[var(--layer-1)] border border-[var(--border-default)] rounded-2xl p-8 relative overflow-hidden shadow-2xl">
                            <div className="flex justify-between items-center mb-10">
                                <h3 className="font-bold text-[var(--text-primary)] text-lg font-display flex items-center gap-3 tracking-tight">
                                    <DollarSign size={20} className="text-[var(--success)]" />
                                    GRC_CAPITAL_ALLOCATION
                                </h3>
                                <div className="text-[var(--success)] font-mono font-bold text-sm bg-[var(--success-subtle)] px-3 py-1 rounded">
                                    {stats.budget.total > 0 ? Math.round((stats.budget.spent / stats.budget.total) * 100) : 0}% UTILIZED
                                </div>
                            </div>
                            
                            <div className="space-y-8 relative">
                                <div className="flex justify-between text-[var(--text-secondary)] font-mono font-bold text-xs tracking-widest pl-1">
                                    <span>EXPENDED: ${stats.budget.spent}M</span>
                                    <span>AUTHORIZED: ${stats.budget.total}M</span>
                                </div>
                                <div className="h-6 w-full bg-[var(--layer-4)] rounded-full overflow-hidden shadow-inner p-1">
                                    <div 
                                        className="h-full bg-gradient-to-r from-[var(--success)] to-[#10b981] rounded-full transition-all duration-1000 ease-out shadow-[0_0_20px_rgba(16,185,129,0.3)]" 
                                        style={{ width: `${stats.budget.total > 0 ? (stats.budget.spent / stats.budget.total) * 100 : 0}%` }} 
                                    />
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="bg-[var(--layer-2)] p-6 rounded-xl border border-[var(--border-default)] shadow-lg hover:border-[var(--border-emphasis)] transition-colors">
                                        <div className="text-[var(--text-tertiary)] text-[9px] font-bold tracking-[0.2em] mb-2 font-mono uppercase">Infosec_Tools</div>
                                        <div className="text-[var(--text-primary)] font-bold text-2xl font-mono">$450k</div>
                                    </div>
                                    <div className="bg-[var(--layer-2)] p-6 rounded-xl border border-[var(--border-default)] shadow-lg hover:border-[var(--border-emphasis)] transition-colors">
                                        <div className="text-[var(--text-tertiary)] text-[9px] font-bold tracking-[0.2em] mb-2 font-mono uppercase">External_Audit</div>
                                        <div className="text-[var(--text-primary)] font-bold text-2xl font-mono">$120k</div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Recent Alerts */}
                        <div className="flex-1 bg-[var(--layer-1)] border border-[var(--border-default)] rounded-2xl p-8 overflow-hidden flex flex-col shadow-2xl">
                            <h3 className="font-bold text-[var(--text-primary)] text-lg font-display flex items-center gap-3 mb-8 shrink-0 tracking-tight">
                                <AlertTriangle size={20} className="text-[var(--warning)]" />
                                STRATEGIC_INDICATORS
                            </h3>
                            <div className="space-y-4 overflow-y-auto pr-3 scrollbar-thin scrollbar-thumb-[var(--layer-4)]">
                                {stats.alerts.map((alert, i) => (
                                    <AlertItem key={i} level={alert.level} msg={alert.msg} time={alert.time} />
                                ))}
                            </div>
                        </div>
                    </div>
                </div>

                {/* 4. Security Identity Audit (IAM-07) */}
                <div className="bg-[var(--layer-1)] border border-[var(--border-default)] rounded-2xl p-8 shadow-2xl relative overflow-hidden">
                    <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
                        <div>
                            <h3 className="font-bold text-[var(--text-primary)] text-xl font-display flex items-center gap-3 tracking-tight">
                                <ShieldAlert size={24} className="text-[var(--accent)]" />
                                SECURITY_IDENTITY_AUDIT
                            </h3>
                            <p className="text-[var(--text-tertiary)] text-[11px] font-mono mt-2 font-bold opacity-60 uppercase tracking-widest">Grc.os Identity Governance Trail</p>
                        </div>
                        
                        {/* Control Bar */}
                        <div className="flex gap-3 items-center w-full md:w-auto">
                            <div className="relative group flex-1 md:w-64">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] group-focus-within:text-[var(--accent)] transition-colors" size={14} />
                                <input 
                                    type="text"
                                    placeholder="FILTER_USER..."
                                    value={filterUser}
                                    onChange={(e) => setFilterUser(e.target.value)}
                                    className="w-full bg-[var(--layer-2)] border border-[var(--border-default)] rounded-lg py-2 pl-10 pr-4 text-[10px] font-mono font-bold text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)] transition-all placeholder:opacity-30"
                                />
                            </div>
                            <select 
                                value={filterType}
                                onChange={(e) => setFilterType(e.target.value)}
                                className="bg-[var(--layer-2)] border border-[var(--border-default)] rounded-lg py-2 px-6 text-[10px] font-mono font-bold text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)] transition-all"
                            >
                                <option value="">ALL_EVENTS</option>
                                <option value="LOGIN_SUCCESS">LOGIN_SUCCESS</option>
                                <option value="LOGIN_FAIL">LOGIN_FAIL</option>
                                <option value="PASSWORD_CHANGE">PASSWORD_CHANGE</option>
                                <option value="PASSWORD_RESET">PASSWORD_RESET</option>
                                <option value="FORBIDDEN">FORBIDDEN</option>
                                <option value="LOGOUT">LOGOUT</option>
                            </select>
                        </div>
                    </div>

                    <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse min-w-[1000px]">
                            <thead>
                                <tr className="border-b border-[var(--border-default)] bg-[var(--layer-2)]/30">
                                    <th className="py-4 px-6 text-[9px] font-mono font-bold text-[var(--text-tertiary)] tracking-widest uppercase">Timestamp</th>
                                    <th className="py-4 px-6 text-[9px] font-mono font-bold text-[var(--text-tertiary)] tracking-widest uppercase">Event_Type</th>
                                    <th className="py-4 px-6 text-[9px] font-mono font-bold text-[var(--text-tertiary)] tracking-widest uppercase">Identity</th>
                                    <th className="py-4 px-6 text-[9px] font-mono font-bold text-[var(--text-tertiary)] tracking-widest uppercase">Network_Origin</th>
                                    <th className="py-4 px-6 text-[9px] font-mono font-bold text-[var(--text-tertiary)] tracking-widest uppercase">Detail_Log</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-[var(--border-default)]/50">
                                {auditLoading ? (
                                    <tr>
                                        <td colSpan="5" className="py-20 text-center">
                                            <div className="inline-flex items-center gap-3 text-[var(--text-tertiary)] animate-pulse">
                                                <RefreshCw className="animate-spin" size={16} />
                                                <span className="text-[10px] font-mono font-bold tracking-widest uppercase">Deciphering_Security_Log...</span>
                                            </div>
                                        </td>
                                    </tr>
                                ) : auditEvents.length === 0 ? (
                                    <tr>
                                        <td colSpan="5" className="py-20 text-center">
                                            <div className="flex flex-col items-center gap-4 text-[var(--text-tertiary)] opacity-40">
                                                <Shield className="mb-2" size={48} strokeWidth={1} />
                                                <span className="text-[10px] font-mono font-bold tracking-[0.3em] uppercase">No_Security_Events_Recorded</span>
                                            </div>
                                        </td>
                                    </tr>
                                ) : (
                                    auditEvents.map((ev) => (
                                        <SecurityAuditRow key={ev.id} event={ev} />
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* 5. Strategic Footers Metrics */}
                <div className="grid grid-cols-3 gap-8 mb-8">
                    <FootMetricCard 
                        title="UNRESOLVED_AUDIT_FINDINGS" 
                        value={dashboard.open_findings} 
                        icon={<Briefcase size={32} />} 
                        label="Critical items pending triage."
                    />
                    <FootMetricCard 
                        title="FRAMEWORK_POSTURE_COVERAGE" 
                        value={`${dashboard.policy_coverage}%`} 
                        icon={<Shield size={32} />} 
                        label="Global system inventory coverage."
                    />
                    <FootMetricCard 
                        title="IDENTIFIED_SYSTEM_AUTHORS" 
                        value={dashboard.active_users} 
                        icon={<Users size={32} />} 
                        label="Active administrative connections."
                    />
                </div>

                {/* 6. Strategic Policy Management (IAM-09) */}
                <div className="bg-[var(--layer-1)] border border-[var(--border-default)] rounded-2xl p-8 shadow-2xl relative overflow-hidden pb-10">
                    <div className="flex justify-between items-center mb-8">
                        <div>
                            <h3 className="font-bold text-[var(--text-primary)] text-xl font-display flex items-center gap-3 tracking-tight">
                                <ShieldCheck size={24} className="text-[var(--success)]" />
                                STRATEGIC_POLICY_ENGINE
                            </h3>
                            <p className="text-[var(--text-tertiary)] text-[11px] font-mono mt-2 font-bold opacity-60 uppercase tracking-widest">Document-Informed Access Governance</p>
                        </div>
                        <div className="flex items-center gap-2 px-3 py-1.5 bg-[var(--success-subtle)] border border-[var(--success)]/20 rounded-lg">
                            <Lock size={12} className="text-[var(--success)]" />
                            <span className="text-[9px] font-bold font-mono text-[var(--success)] uppercase tracking-tighter">ENFORCEMENT_ACTIVE</span>
                        </div>
                    </div>

                    <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse min-w-[1000px]">
                            <thead>
                                <tr className="border-b border-[var(--border-default)] bg-[var(--layer-2)]/30">
                                    <th className="py-4 px-6 text-[9px] font-mono font-bold text-[var(--text-tertiary)] tracking-widest uppercase">Policy_Name</th>
                                    <th className="py-4 px-6 text-[9px] font-mono font-bold text-[var(--text-tertiary)] tracking-widest uppercase">Required_Authority</th>
                                    <th className="py-4 px-6 text-[9px] font-mono font-bold text-[var(--text-tertiary)] tracking-widest uppercase">State</th>
                                    <th className="py-4 px-6 text-[9px] font-mono font-bold text-[var(--text-tertiary)] tracking-widest uppercase">Version_Audit</th>
                                    <th className="py-4 px-6 text-[9px] font-mono font-bold text-[var(--text-tertiary)] tracking-widest uppercase">Governance_Source</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-[var(--border-default)]/50">
                                {policiesLoading ? (
                                    <tr>
                                        <td colSpan="5" className="py-16 text-center">
                                            <div className="inline-flex items-center gap-3 text-[var(--text-tertiary)] animate-pulse">
                                                <RefreshCw className="animate-spin" size={16} />
                                                <span className="text-[10px] font-mono font-bold tracking-widest uppercase">Parsing_Authority_Registry...</span>
                                            </div>
                                        </td>
                                    </tr>
                                ) : (
                                    policies.map((policy) => (
                                        <PolicyRow 
                                            key={policy.id} 
                                            policy={policy} 
                                            onUpdate={(updates) => handleUpdatePolicy(policy.id, updates)} 
                                        />
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                    
                    <div className="mt-8 pt-6 border-t border-[var(--border-dashed)] flex items-center justify-between text-[10px] font-mono text-[var(--text-tertiary)] font-bold">
                        <span className="flex items-center gap-2 text-[var(--warning)]">
                           <AlertCircle size={12} />
                           MANDATORY: DENY_BY_DEFAULT enforcement is active for all unmapped actions.
                        </span>
                        <span className="flex items-center gap-2">
                            {policies.length > 0 ? `v1.${policies.length}.0_ENGINE_STABLE` : 'ENGINE_INITIALIZING'}
                        </span>
                    </div>
                </div>

            </div>
        </div>
    );
};

// Helper Components
const KPICard = ({ title, value, trend, icon, variant }) => {
    const isUp = trend.includes('+');
    const colorClass = variant === 'danger' ? 'text-[var(--danger)]' : 
                       variant === 'warning' ? 'text-[var(--warning)]' : 
                       variant === 'success' ? 'text-[var(--success)]' : 'text-[var(--text-primary)]';
    
    return (
        <div className="bg-[var(--layer-1)] border border-[var(--border-default)] p-8 rounded-2xl hover:border-[var(--border-emphasis)] transition-all duration-300 shadow-xl group">
            <div className="flex justify-between items-start mb-6">
                <span className="text-[var(--text-tertiary)] font-bold text-[10px] tracking-[0.2em] font-mono leading-none group-hover:text-[var(--text-primary)] transition-colors uppercase">{title}</span>
                <div className="transform group-hover:rotate-12 transition-transform">{icon}</div>
            </div>
            <div className={`text-6xl font-bold font-mono tracking-tighter mb-4 ${colorClass}`}>{value}</div>
            <div className="flex items-center gap-3 px-1">
                <div className={`flex items-center gap-1 font-mono font-bold text-xs p-1.5 rounded-lg ${isUp ? 'bg-[var(--success-subtle)] text-[var(--success)]' : 'bg-[var(--danger-subtle)] text-[var(--danger)]'}`}>
                    {isUp ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    {trend}
                </div>
                <span className="text-[var(--text-tertiary)] text-[11px] font-bold">vs prior period</span>
            </div>
        </div>
    );
};

const AlertItem = ({ level, msg, time }) => {
    const severityColor = level === 'CRITICAL' ? 'border-l-[var(--danger)]' : 
                           level === 'WARNING' ? 'border-l-[var(--warning)]' : 'border-l-[var(--accent)]';
    const tagBg = level === 'CRITICAL' ? 'bg-[var(--danger-subtle)] text-[var(--danger)] border-[var(--danger)]/30' : 
                  level === 'WARNING' ? 'bg-[var(--warning-subtle)] text-[var(--warning)] border-[var(--warning)]/30' : 
                  'bg-[var(--accent-subtle)] text-[var(--accent)] border-[var(--accent)]/30';
    
    return (
        <div className={`p-4 bg-[var(--layer-0)] border-l-4 ${severityColor} rounded-r-lg hover:bg-[var(--layer-2)] transition-all group cursor-pointer border-y border-r border-[var(--border-default)]`}>
            <div className="flex justify-between items-center mb-3">
                <span className={`text-[9px] font-bold px-2 py-0.5 rounded border tracking-widest uppercase ${tagBg}`}>{level}</span>
                <span className="text-[var(--text-tertiary)] text-[10px] font-mono font-bold opacity-60 group-hover:opacity-100 transition-opacity">{time}</span>
            </div>
            <div className="text-[var(--text-primary)] font-bold text-[11px] leading-relaxed group-hover:text-[var(--accent)] transition-colors">{msg}</div>
        </div>
    );
};

const FootMetricCard = ({ title, value, icon, label }) => (
    <div className="bg-[var(--layer-1)] border border-[var(--border-default)] rounded-2xl p-8 flex items-center justify-between shadow-2xl group hover:border-[var(--border-emphasis)] transition-all">
        <div className="flex-1">
            <div className="text-[var(--text-tertiary)] text-[10px] font-bold uppercase tracking-[0.2em] mb-3 font-mono">{title}</div>
            <div className="text-5xl font-bold text-[var(--text-primary)] font-mono tracking-tighter mb-2">{value}</div>
            <div className="text-[var(--text-tertiary)] text-[10px] font-bold italic opacity-60">{label}</div>
        </div>
        <div className="text-[var(--text-tertiary)] opacity-10 group-hover:opacity-30 group-hover:scale-110 transition-all transform rotate-[-12deg]">
            {icon}
        </div>
    </div>
);

const SecurityAuditRow = ({ event }) => {
    const isCritical = ['LOGIN_FAIL', 'FORBIDDEN', 'PASSWORD_RESET'].includes(event.event_type);
    
    const getIcon = (type) => {
        switch(type) {
            case 'LOGIN_SUCCESS': return <Unlock className="text-[var(--success)]" size={14} />;
            case 'LOGIN_FAIL': return <Lock className="text-[var(--danger)]" size={14} />;
            case 'PASSWORD_CHANGE': return <FileKey className="text-[var(--accent)]" size={14} />;
            case 'PASSWORD_RESET': return <RefreshCw className="text-[var(--warning)]" size={14} />;
            case 'LOGOUT': return <LogOut className="text-[var(--text-tertiary)]" size={14} />;
            case 'FORBIDDEN': return <AlertOctagon className="text-[var(--danger)]" size={14} />;
            default: return <ShieldCheck className="text-[var(--text-tertiary)]" size={14} />;
        }
    };

    return (
        <tr className="hover:bg-[var(--layer-2)]/50 transition-colors group">
            <td className="py-4 px-6 text-[10px] font-mono text-[var(--text-secondary)] font-bold">{event.timestamp?.split('T')[0]} {event.timestamp?.split('T')[1]?.substring(0,8)}</td>
            <td className="py-4 px-6">
                <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full border text-[9px] font-bold font-mono tracking-tighter ${isCritical ? 'bg-[var(--danger-subtle)] text-[var(--danger)] border-[var(--danger)]/30 shadow-[0_0_10px_var(--danger-subtle)]' : 'bg-[var(--layer-3)] text-[var(--text-primary)] border-[var(--border-default)]'}`}>
                    {getIcon(event.event_type)}
                    {event.event_type}
                </div>
            </td>
            <td className="py-4 px-6">
                <div className="flex items-center gap-2.5">
                    <div className="w-7 h-7 rounded-lg bg-[var(--layer-3)] border border-[var(--border-default)] flex items-center justify-center text-[10px] text-[var(--accent)] font-bold group-hover:border-[var(--accent)] transition-colors">
                        <User size={14} strokeWidth={2.5} />
                    </div>
                    <span className="text-[11px] font-bold text-[var(--text-primary)] font-mono">{event.user}</span>
                </div>
            </td>
            <td className="py-4 px-6 text-[10px] font-mono text-[var(--text-tertiary)] font-bold">{event.ip_address}</td>
            <td className="py-4 px-6">
                <div className="text-[10px] text-[var(--text-secondary)] leading-relaxed max-w-md truncate group-hover:whitespace-normal group-hover:overflow-visible transition-all">
                    {event.detail}
                </div>
            </td>
        </tr>
    );
};

const PolicyRow = ({ policy, onUpdate }) => {
    return (
        <tr className="hover:bg-[var(--layer-2)]/50 transition-colors group">
            <td className="py-5 px-6">
                <div>
                    <div className="text-[11px] font-bold text-[var(--text-primary)] font-mono mb-1">{policy.name}</div>
                    <div className="text-[10px] text-[var(--text-tertiary)] font-bold opacity-60 leading-tight">{policy.description}</div>
                </div>
            </td>
            <td className="py-5 px-6">
                <select 
                    value={policy.required_role}
                    onChange={(e) => onUpdate({ required_role: e.target.value, is_active: policy.is_active })}
                    className="bg-[var(--layer-2)] border border-[var(--border-default)] rounded-lg py-1.5 px-4 text-[10px] font-mono font-bold text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)] transition-all cursor-pointer hover:border-[var(--border-emphasis)] shadow-inner"
                >
                    <option value="admin">ADMIN_ROOT (3)</option>
                    <option value="analyst">ANALYST_AUTH (2)</option>
                    <option value="viewer">VIEWER_ONLY (1)</option>
                </select>
            </td>
            <td className="py-5 px-6">
                <button
                    onClick={() => onUpdate({ required_role: policy.required_role, is_active: !policy.is_active })}
                    className={`flex items-center gap-2 px-4 py-1.5 rounded-lg border text-[9px] font-bold font-mono tracking-tighter transition-all group-hover:shadow-lg ${policy.is_active ? 'bg-[var(--success-subtle)] text-[var(--success)] border-[var(--success)]/30' : 'bg-[var(--danger-subtle)] text-[var(--danger)] border-[var(--danger)]/30'}`}
                >
                    {policy.is_active ? <Unlock size={12} /> : <Lock size={12} />}
                    {policy.is_active ? 'ACTIVE_ENFORCEMENT' : 'INACTIVE_DISABLED'}
                </button>
            </td>
            <td className="py-5 px-6">
                <div className="flex flex-col">
                    <div className="text-[10px] font-mono text-[var(--text-secondary)] font-bold mb-1">REV_{policy.policy_version || 1}</div>
                    <div className="text-[9px] text-[var(--text-tertiary)] font-mono font-bold opacity-60">MOD_{policy.modified_by || 'system'}</div>
                </div>
            </td>
            <td className="py-5 px-6">
                {policy.source_doc ? (
                    <div className="flex items-center gap-2 text-[var(--accent)] font-mono text-[10px] font-bold hover:underline cursor-pointer">
                        <FileKey size={12} />
                        {policy.source_doc}
                    </div>
                ) : (
                    <span className="text-[9px] text-[var(--text-tertiary)] font-mono font-bold opacity-30 italic">NO_LINKED_EVIDENCE</span>
                )}
            </td>
        </tr>
    );
};
