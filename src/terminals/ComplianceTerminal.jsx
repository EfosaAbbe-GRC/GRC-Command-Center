import React, { useState, useEffect } from 'react';
import { Search, Filter, Download, ChevronDown, ChevronUp, ShieldCheck, AlertTriangle, CheckCircle, XCircle, FileJson, Activity, Terminal, Command, AlertOctagon } from 'lucide-react';
import { useApiData } from '../hooks/useApiData';
import { StatusBadge } from '../components/StatusBadge';
import { api } from '../lib/api';
import { useAuth } from '../contexts/useAuth';
import { useWebSocket } from '../hooks/useWebSocket';

export const ComplianceTerminal = () => {
    const { user, needsReset } = useAuth();
    const isAdmin = user?.role === 'admin';
    const [selectedId, setSelectedId] = useState(null);
    const [frameworks, setFrameworks] = useState([]);
    const [searchQuery, setSearchQuery] = useState('');

    const { data: policies, loading, error, refresh } = useApiData('/compliance/policies', {
        onSuccess: (resData) => {
            if (resData.length > 0 && !selectedId) {
                setSelectedId(resData[0].id);
            }
        }
    });

    // Real-time Telemetry: Refresh on broadcast events
    const { connected } = useWebSocket(user?.access_token, (message) => {
        if (message.type === 'INGEST_STATUS' && message.status === 'COMPLETED') {
            refresh();
        }
    });

    const activePolicy = (policies && policies.length > 0) ? (policies.find(p => p.id === selectedId) || policies[0]) : {};

    useEffect(() => {
        if (!selectedId) return;
        const controller = new AbortController();
        api.get(`/compliance/frameworks/${selectedId}`, controller.signal)
            .then(data => setFrameworks(data.frameworks || []))
            .catch(err => { if (err.name !== 'AbortError') setFrameworks([]); });
        return () => controller.abort();
    }, [selectedId]);

    if (loading) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center bg-[var(--layer-0)] text-[var(--accent)]">
                <Activity className="animate-spin mb-4" size={48} />
                <span className="text-[10px] font-bold tracking-[0.3em] font-mono animate-pulse uppercase">Synchronizing_Policy_Data</span>
            </div>
        );
    }

    if (error) {
        if (needsReset) return (
            <div className="flex-1 bg-[var(--layer-0)] animate-pulse flex items-center justify-center">
                 <ShieldCheck className="text-[var(--accent)] opacity-20" size={64} />
            </div>
        );

        return (
            <div className="flex-1 flex flex-col items-center justify-center bg-[var(--layer-0)] text-[var(--danger)]">
                <AlertTriangle className="mb-4" size={48} />
                <span className="text-sm font-bold tracking-[0.1em] font-display uppercase mb-2">Connectivity Failure</span>
                <span className="text-[10px] text-[var(--text-tertiary)] font-mono mb-6">{error.message || error}</span>
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
        <div className="flex-1 flex flex-col bg-[var(--layer-0)] text-[11px] h-full overflow-hidden">
            
            {/* 1. Command Bar */}
            <div className="h-14 bg-[var(--layer-1)] border-b border-[var(--border-default)] flex items-center justify-between px-6 shrink-0 z-20 shadow-sm">
                <div className="flex items-center gap-6">
                    <span className="text-[var(--text-primary)] font-bold tracking-widest text-xs font-display">POLICY_GRID_CONTROL</span>
                    <span className="px-2 py-0.5 rounded-sm border text-[9px] font-bold uppercase font-mono tracking-widest"
                        style={{ borderColor: 'var(--text-tertiary)', color: 'var(--text-tertiary)' }}
                        title="Illustrative reference data -- not connected to live infrastructure scanning">
                        REFERENCE_CATALOG
                    </span>
                    <div className="h-6 w-px bg-[var(--border-subtle)]" />
                    
                    {/* Command Search */}
                    <div className="relative group">
                        <div className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--accent)] pointer-events-none group-focus-within:scale-110 transition-transform">
                            <Command size={14} />
                        </div>
                        <input
                            type="text"
                            placeholder="Find policies..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="bg-[var(--layer-0)] border border-[var(--border-default)] pl-10 pr-12 py-2 rounded-md w-96 text-[11px] font-mono text-[var(--text-primary)] placeholder-[var(--text-tertiary)] focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent-subtle)] outline-none transition-all shadow-inner"
                        />
                        <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1.5 opacity-40 pointer-events-none">
                            <kbd className="px-1.5 py-0.5 bg-[var(--layer-2)] border border-[var(--border-default)] rounded text-[8px] font-mono font-bold">⌘</kbd>
                            <kbd className="px-1.5 py-0.5 bg-[var(--layer-2)] border border-[var(--border-default)] rounded text-[8px] font-mono font-bold">K</kbd>
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    <button className="flex items-center gap-2.5 px-6 py-2 bg-[var(--layer-2)] hover:bg-[var(--layer-3)] border border-[var(--border-default)] hover:border-[var(--border-emphasis)] rounded-md text-[var(--text-primary)] font-bold transition-all shadow-sm active:scale-95">
                        <Filter size={13} strokeWidth={2.5} />
                        <span>Filter Configuration</span>
                    </button>
                    {isAdmin && (
                        <button
                            onClick={() => api.downloadFile('/compliance/export', 'grc_compliance_report.csv')}
                            className="flex items-center gap-2.5 px-6 py-2 bg-[var(--accent-emphasis)] hover:bg-[var(--accent)] text-white rounded-md font-bold transition-all shadow-[0_0_15px_var(--accent-glow)] active:scale-95 group relative overflow-hidden"
                        >
                            <Download size={13} strokeWidth={2.5} />
                            <span>Export CSV Report</span>
                            <div className="absolute inset-0 bg-white/20 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-500 ease-in-out pointer-events-none" />
                        </button>
                    )}
                </div>
            </div>

            {/* 2. Main High-Density Grid */}
            <div className="flex-1 overflow-auto bg-[var(--layer-0)] scrollbar-thin scrollbar-thumb-[var(--layer-4)] scrollbar-track-transparent">
                <div className="min-w-[1250px]">
                    {/* Bloomberg Style Header */}
                    <div className="grid grid-cols-12 gap-4 bg-[var(--layer-1)] text-[var(--text-tertiary)] font-bold uppercase tracking-wider text-[10px] px-6 py-3 sticky top-0 z-30 border-b border-[var(--border-default)]">
                        <div className="col-span-1 font-mono tracking-tighter">REF_ID</div>
                        <div className="col-span-5 font-display">Target Architecture Policy</div>
                        <div className="col-span-1">Context</div>
                        <div className="col-span-1">Status</div>
                        <div className="col-span-3">Integrity Score</div>
                        <div className="col-span-1 text-right">Timestamp</div>
                    </div>

                    {/* Policy Rows */}
                    <div className="divide-y divide-[var(--border-subtle)]">
                        {(policies || []).filter(p => p.name.toLowerCase().includes(searchQuery.toLowerCase())).map((p, idx) => (
                            <div
                                key={idx}
                                onClick={() => setSelectedId(p.id)}
                                className={`grid grid-cols-12 gap-4 px-6 py-3 items-center group cursor-pointer data-row ${selectedId === p.id ? 'selected' : (idx % 2 === 0 ? 'bg-[var(--layer-0)]' : 'bg-[var(--layer-0)]/50')}`}
                            >
                                <div className={`col-span-1 font-mono font-bold ${selectedId === p.id ? 'text-[var(--accent)] animate-pulse' : 'text-[var(--text-tertiary)] opacity-60'}`}>{p.id}</div>
                                <div className="col-span-5 font-bold text-[var(--text-primary)] transition-colors group-hover:text-[var(--accent)] flex items-center gap-3 truncate">
                                    <ShieldCheck size={14} strokeWidth={2.5} className={p.status === 'FAIL' ? 'text-[var(--danger)] glow-danger' : 'text-[var(--success)]'} />
                                    <span className="truncate tracking-wide">{p.name}</span>
                                </div>
                                <div className="col-span-1 text-[var(--text-tertiary)] font-mono text-[10px] uppercase font-bold tracking-widest">{p.type}</div>
                                <div className="col-span-1">
                                    <StatusBadge status={p.status} />
                                </div>
                                <div className="col-span-3">
                                    <ProgressBar value={p.compliance} />
                                </div>
                                <div className="col-span-1 text-[var(--text-tertiary)] text-right font-mono font-bold">{p.lastScan}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* 3. Operational Inspector (Drawer Style) */}
            <div className="h-[320px] bg-[var(--layer-1)] flex flex-col border-t border-[var(--border-emphasis)] relative z-20 shadow-2xl">
                
                {/* Header Sub-bar */}
                <div className="h-10 bg-[var(--layer-2)] border-b border-[var(--border-default)] flex items-center justify-between px-6 shrink-0">
                    <div className="flex items-center gap-6">
                        <div className="flex items-center gap-2.5 text-[var(--text-primary)] font-bold text-xs">
                            <Activity size={15} className="text-[var(--accent)]" />
                            <span className="tracking-[0.1em] font-display">INSPECTOR_GATEWAY // <span className="text-[var(--accent)] font-mono">{activePolicy.id}</span></span>
                        </div>
                        <div className="h-4 w-px bg-[var(--border-emphasis)] opacity-30" />
                        <div className="flex items-center gap-2.5 text-[10px] text-[var(--text-secondary)]">
                            <span className="font-bold opacity-40 uppercase tracking-widest">Selected:</span>
                            <span className="font-bold text-[var(--text-primary)] font-mono">{activePolicy.name}</span>
                        </div>
                    </div>
                    <div className="flex items-center gap-3 text-[10px] text-[var(--text-tertiary)] font-mono font-bold">
                        <div className={`flex items-center gap-1.5 ${connected ? 'text-[var(--success)]' : 'text-[var(--danger)]'}`}>
                            <div className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-[var(--success)] glow-success animate-pulse' : 'bg-[var(--danger)]'}`} />
                            {connected ? 'SECURE_REAL_TIME_STREAM' : 'STREAM_OFFLINE_RECONNECTING'}
                        </div>
                    </div>
                </div>

                {/* Split Panel */}
                <div className="flex-1 grid grid-cols-12 overflow-hidden bg-[var(--layer-1)]">
                    
                    {/* Logs (4 cols) */}
                    <div className="col-span-4 p-5 space-y-3 overflow-y-auto border-r border-[var(--border-default)] scrollbar-thin scrollbar-thumb-[var(--layer-4)]">
                        <h4 className="text-[9px] font-bold text-[var(--text-tertiary)] uppercase tracking-[0.2em] mb-3 flex items-center gap-1.5">
                            <Terminal size={11} className="text-[var(--accent)]" /> REFERENCE_ENTRY_DETAIL
                        </h4>
                        <div className="text-[10px] text-[var(--text-tertiary)] leading-relaxed italic">
                            This entry is illustrative reference data (see REFERENCE_CATALOG above) —
                            not backed by live infrastructure scanning. Status and score are static.
                        </div>
                    </div>

                    {/* Data Model (4 cols) */}
                    <div className="col-span-4 p-5 overflow-y-auto bg-[var(--layer-0)] border-r border-[var(--border-default)] scrollbar-thin scrollbar-thumb-[var(--layer-4)]">
                        <h4 className="text-[9px] font-bold text-[var(--text-tertiary)] uppercase tracking-[0.2em] mb-3 flex items-center gap-1.5">
                            <FileJson size={11} className="text-[var(--warning)]" /> DATA_STRUCTURE_VIEW
                        </h4>
                        <pre className="text-[10px] font-mono text-[var(--success)] leading-tight opacity-90">
                            {JSON.stringify(activePolicy, null, 2)}
                        </pre>
                    </div>

                    {/* Framework Mapping & Context (4 cols) */}
                    <div className="col-span-4 p-5 flex flex-col overflow-hidden bg-[var(--layer-1)]">
                        <h4 className="text-[9px] font-bold text-[var(--text-tertiary)] uppercase tracking-[0.2em] mb-1">
                            Framework_Mappings
                        </h4>
                        <div className="text-[9px] text-[var(--text-tertiary)] italic mb-3">
                            Hand-curated reference mapping — not live-computed.
                        </div>

                        <div className="flex-1 overflow-y-auto space-y-3 pr-1 scrollbar-thin scrollbar-thumb-[var(--layer-4)]">
                            {frameworks.length > 0 ? (
                                frameworks.map((fw) => (
                                    <div 
                                        key={fw.id} 
                                        className={`p-3 border rounded bg-[var(--layer-2)] border-[var(--border-default)] relative overflow-hidden transition-all hover:border-[var(--border-emphasis)] ${
                                            fw.status === 'SATISFIED' ? 'border-l-2 border-l-[var(--success)]' :
                                            fw.status === 'PARTIAL' ? 'border-l-2 border-l-[var(--warning)]' :
                                            'border-l-2 border-l-[var(--danger)]'
                                        }`}
                                    >
                                        <div className="flex justify-between items-center mb-1.5 relative z-10">
                                            <span className="text-[10px] font-bold text-[var(--text-primary)] tracking-wide">{fw.name}</span>
                                            <div className="transform scale-90 origin-right">
                                                <StatusBadge status={fw.status} variant="large" />
                                            </div>
                                        </div>
                                        <div className="text-[9px] text-[var(--text-secondary)] font-mono leading-relaxed relative z-10">{fw.control}</div>
                                        
                                        {/* BG Subtle Decor */}
                                        <div className="absolute top-2 right-2 text-[var(--text-tertiary)] opacity-[0.03] pointer-events-none">
                                            <ShieldCheck size={40} />
                                        </div>
                                    </div>
                                ))
                            ) : (
                                <div className="text-center p-8 border border-dashed border-[var(--border-default)] rounded text-[10px] text-[var(--text-tertiary)] italic">
                                    No compliance framework identifiers found.
                                </div>
                            )}
                        </div>

                        {/* Summary Action */}
                        {isAdmin ? (
                            <div className="mt-4 pt-4 border-t border-[var(--border-default)] flex gap-3">
                                <div className="flex-1 text-center text-[9px] font-bold text-[var(--text-tertiary)] uppercase tracking-widest opacity-50 py-1">
                                    No live scan/remediate actions -- reference catalog only
                                </div>
                            </div>
                        ) : (
                            <div className="mt-4 pt-4 border-t border-[var(--border-default)] text-center text-[9px] font-bold text-[var(--text-tertiary)] uppercase tracking-widest opacity-50">
                                Administrative Actions Locked
                            </div>
                        )}
                    </div>

                </div>
            </div>

            {/* Footer Bar */}
            <footer className="h-6 bg-[var(--layer-0)] border-t border-[var(--border-default)] flex items-center px-4 justify-between text-[10px] text-[var(--text-tertiary)] font-bold shrink-0">
                <div className="flex items-center gap-6">
                    <span className="tracking-widest">GATEWAY_STATUS // <span className="text-[var(--success)] animate-pulse">OPTIMAL</span></span>
                    <span className="h-3 w-px bg-[var(--border-subtle)]" />
                    <span className="tracking-[0.2em] font-mono">OBJECT_POOL: {policies.length}</span>
                </div>
                <div className={`flex items-center gap-2 ${connected ? 'text-[#0ea5e9]' : 'text-[var(--danger)]'}`}>
                    <Activity size={10} className={connected ? "animate-pulse" : ""} />
                    <span className="tracking-[0.1em]">{connected ? 'LIVE TELEMETRY' : 'SIGNAL_LOST'} // {new Date().toLocaleTimeString()}</span>
                </div>
            </footer>
        </div>
    );
};


const ProgressBar = ({ value }) => {
    const isCritical = value < 50;
    const isWarning = value >= 50 && value < 90;
    
    return (
        <div className="flex items-center gap-4 w-full h-full">
            <div className="flex-1 h-3 bg-[var(--layer-2)] border border-[var(--border-default)] rounded-sm overflow-hidden relative shadow-inner">
                <div
                    className={`h-full transition-all duration-1000 ease-out relative ${isCritical ? 'bg-[var(--danger)] glow-danger' : isWarning ? 'bg-[var(--warning)]' : 'bg-[var(--success)] glow-success'}`}
                    style={{ width: `${value}%` }}
                >
                    {/* Visual Highlights */}
                    <div className="absolute inset-0 bg-white/10" />
                    {value > 40 && (
                        <div className="absolute inset-0 flex items-center justify-center font-mono font-bold text-[8px] text-white/80 drop-shadow-sm uppercase tracking-tighter">
                            {value}% MET
                        </div>
                    )}
                </div>
            </div>
            {value <= 40 && (
                <span className={`text-[10px] font-mono font-bold w-12 text-right ${isCritical ? 'text-[var(--danger)]' : isWarning ? 'text-[var(--warning)]' : 'text-[var(--success)]'}`}>
                    {value}%
                </span>
            )}
        </div>
    )
}
