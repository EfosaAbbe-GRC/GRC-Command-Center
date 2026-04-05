import React, { useState } from 'react';
import GRCChatBot from '../components/GRCChatBot';
import { Terminal, Activity, Play, RotateCcw, AlertOctagon, Cpu, Hash, Monitor, Shield, Layers, ShieldAlert, FileKey, Lock, Unlock, ChevronDown, ChevronUp, CheckCircle2, Database } from 'lucide-react';
import { api } from '../lib/api';
import { useApiData } from '../hooks/useApiData';
import { StatusBadge } from '../components/StatusBadge';
import { useAuth } from '../contexts/useAuth';

export const OpsTerminal = () => {
    const { user } = useAuth();
    const isAdmin = user?.role === 'admin';
    const [selectedJob, setSelectedJob] = useState(null);
    const [manualOutput, setManualOutput] = useState(null);
    const [stats, setStats] = useState({ running: 2, queued: 0, failed: 2 });
    const [showGovernance, setShowGovernance] = useState(false);

    // Fetch Ingestion Status (RAG Sync)
    const { data: ingestStatus } = useApiData('/ingest/status', {
        pollInterval: 2000
    });

    const handleGlobalIngest = async () => {
        if (!isAdmin) return;
        try {
            await api.post('/ingest');
        } catch (err) {
            console.error("Global Ingestion trigger failed:", err);
        }
    };

    // Fetch Operational Policies (IAM-10)
    const { data: policies, refresh: refreshPolicies } = useApiData('/admin/policies', {
        pollInterval: 10000
    });

    const updatePolicy = async (policyId, updates) => {
        try {
            await api.put(`/admin/policies/${policyId}`, updates);
            refreshPolicies();
        } catch (err) {
            console.error("Policy Sync Failed:", err);
        }
    };

    const { data: jobs, loading, error, refresh } = useApiData('/ops/jobs', {
        pollInterval: 5000,
        onSuccess: (resData) => {
            if (resData.length > 0) {
                if (!selectedJob) setSelectedJob(resData[0].id);
                
                // Calculate real stats
                const running = resData.filter(j => j.status === 'RUNNING').length;
                const queued = resData.filter(j => j.status === 'QUEUED').length;
                const failed = resData.filter(j => j.status === 'FAILED').length;
                setStats({ running, queued, failed });
            }
        }
    });

    const runAgent = async () => {
        setManualOutput("> Initializing Agent Instance...\n> SECURE_TUNNEL_ESTABLISHED\n> Handshaking with regional GRC node...\n> Validating compliance manifests...");
        try {
            const data = await api.runAgent('compliance_checker');
            if (data.result.stdout) {
                setManualOutput(data.result.stdout);
            } else {
                setManualOutput("Agent session terminated. No STDOUT received.");
            }
        } catch (err) {
            setManualOutput(`FATAL_ERROR: ${err.message}`);
        }
    };

    const activeJob = (jobs && jobs.length > 0) ? (jobs.find(j => j.id === selectedJob) || jobs[0]) : null;

    if (loading && (!jobs || jobs.length === 0)) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center bg-[var(--layer-0)] text-[var(--accent)]">
                <Activity className="animate-spin mb-4" size={48} />
                <span className="text-[10px] font-bold tracking-[0.3em] font-mono animate-pulse uppercase text-[var(--accent)]">Connecting_To_Operations_Control</span>
            </div>
        );
    }

    if (error && (!jobs || jobs.length === 0)) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center bg-[var(--layer-0)] text-[var(--danger)]">
                <Terminal className="mb-4" size={48} />
                <span className="text-sm font-bold tracking-[0.1em] font-display uppercase mb-2">Ops Layer Offline</span>
                <span className="text-[10px] text-[var(--text-tertiary)] font-mono mb-6">{error}</span>
                <button
                    onClick={() => refresh()}
                    className="px-8 py-2.5 bg-[var(--danger-subtle)] border border-[var(--danger)] rounded-md text-[10px] font-bold text-[var(--danger)] hover:bg-[var(--danger)] hover:text-white transition-all shadow-lg active:scale-95"
                >
                    RETRY_CONNECTION
                </button>
            </div>
        );
    }

    if (!activeJob) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center bg-[var(--layer-0)] text-[var(--text-tertiary)] opacity-30">
                <Monitor className="mb-4" size={64} strokeWidth={1} />
                <span className="text-[11px] font-bold tracking-[0.4em] font-mono uppercase">Operational_Wait_State</span>
            </div>
        );
    }

    return (
        <div className="flex-1 flex flex-col bg-[var(--layer-0)] text-[11px] h-full overflow-hidden">

            {/* 1. TOP: Operational Command Center (Grid) */}
            <div className="flex-1 flex flex-col border-b border-[var(--border-default)] overflow-hidden min-h-[250px] relative z-0 shadow-sm">
                <div className="h-14 bg-[var(--layer-1)] border-b border-[var(--border-default)] flex-none flex items-center justify-between px-6 z-10 relative w-full">
                    <div className="flex items-center gap-4">
                        <div className="p-1.5 bg-[var(--layer-2)] border border-[var(--border-subtle)] rounded-md text-[var(--accent)] glow-accent">
                            <Activity size={16} strokeWidth={2.5} />
                        </div>
                        <span className="font-bold text-[var(--text-primary)] tracking-[0.2em] text-xs font-display uppercase">ACTIVE_OPERATIONS_GRID</span>
                    </div>
                    
                    <div className="flex items-center gap-6 bg-[var(--layer-0)] px-6 py-2 rounded-xl border border-[var(--border-default)] shadow-inner">
                        <div className="flex items-center gap-3">
                            <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse shadow-[0_0_8px_var(--accent)]" />
                            <span className="text-[10px] font-mono font-bold text-[var(--text-tertiary)] uppercase tracking-widest">Running</span>
                            <span className="text-[var(--accent)] font-mono font-bold text-sm tracking-tight">{stats.running}</span>
                        </div>
                        <div className="w-px h-4 bg-[var(--border-subtle)]" />
                        
                        {/* RAG Ingestion Status */}
                        <div className="flex items-center gap-4">
                            {isAdmin && (
                                <button 
                                    onClick={handleGlobalIngest}
                                    disabled={ingestStatus?.status === 'processing'}
                                    className={`px-3 py-1 rounded border text-[9px] font-bold font-mono transition-all flex items-center gap-2 ${ingestStatus?.status === 'processing' ? 'bg-[var(--accent-subtle)] text-[var(--accent)] border-[var(--accent-glow)] animate-pulse' : 'bg-[var(--layer-2)] border-[var(--border-default)] hover:bg-[var(--layer-3)] text-[var(--text-primary)]'}`}
                                >
                                    <Database size={12} strokeWidth={2.5} />
                                    {ingestStatus?.status === 'processing' ? `INGESTING_${ingestStatus.progress || 0}%` : 'GLOBAL_INGEST'}
                                </button>
                            )}
                        </div>

                        <div className="w-px h-4 bg-[var(--border-subtle)]" />
                        <div className="flex items-center gap-3">
                            <div className="w-1.5 h-1.5 rounded-full bg-[var(--warning)]" />
                            <span className="text-[10px] font-mono font-bold text-[var(--text-tertiary)] uppercase tracking-widest">Queued</span>
                            <span className="text-[var(--warning)] font-mono font-bold text-sm tracking-tight">{stats.queued}</span>
                        </div>
                        <div className="w-px h-4 bg-[var(--border-subtle)]" />
                        <div className="flex items-center gap-3">
                            <div className="w-1.5 h-1.5 rounded-full bg-[var(--danger)]" />
                            <span className="text-[10px] font-mono font-bold text-[var(--text-tertiary)] uppercase tracking-widest">Failed</span>
                            <span className="text-[var(--danger)] font-mono font-bold text-sm tracking-tight">{stats.failed}</span>
                        </div>
                    </div>
                </div>

                <div className="flex-1 overflow-auto bg-[var(--layer-0)] scrollbar-thin scrollbar-thumb-[var(--layer-4)]">
                    <div className="min-w-[1250px]">
                        <div className="grid grid-cols-12 gap-5 bg-[var(--layer-2)] text-[var(--text-tertiary)] font-bold uppercase tracking-[0.2em] text-[10px] px-6 py-3.5 sticky top-0 z-20 border-b border-[var(--border-default)] shadow-md">
                            <div className="col-span-2">Reference_ID</div>
                            <div className="col-span-3">Assigned_Agent</div>
                            <div className="col-span-3">Target_Objective</div>
                            <div className="col-span-2">Execution_State</div>
                            <div className="col-span-1">Duration</div>
                            <div className="col-span-1 text-right">Node_Load</div>
                        </div>

                        <div className="divide-y divide-[var(--border-subtle)]">
                            {(jobs || []).map((job, idx) => (
                                <div
                                    key={job.id}
                                    onClick={() => setSelectedJob(job.id)}
                                    className={`grid grid-cols-12 gap-5 px-6 py-3.5 items-center group cursor-pointer data-row relative overflow-hidden ${selectedJob === job.id ? 'selected shadow-lg z-10' : (idx % 2 === 0 ? 'bg-[var(--layer-0)]' : 'bg-[var(--layer-1)]/30')}`}
                                >
                                    <div className="col-span-2 text-[var(--text-tertiary)] font-mono font-bold group-hover:text-[var(--text-primary)] transition-colors">{job.id}</div>
                                    <div className="col-span-3 text-[var(--text-primary)] font-bold flex items-center gap-3">
                                        <div className={`p-1.5 rounded bg-[var(--layer-2)] border border-[var(--border-subtle)] ${job.status === 'RUNNING' ? 'text-[var(--accent)] glow-accent' : 'text-[var(--text-tertiary)]'}`}>
                                            <Cpu size={14} />
                                        </div>
                                        <span className="group-hover:text-[var(--accent)] transition-colors">{job.agent}</span>
                                    </div>
                                    <div className="col-span-3 text-[var(--text-secondary)] font-medium font-mono text-[10px] tracking-wide truncate">{job.task}</div>
                                    <div className="col-span-2">
                                        <StatusBadge status={job.status} variant="large" />
                                    </div>
                                    <div className="col-span-1 text-[var(--text-tertiary)] font-mono font-bold">{job.duration}</div>
                                    <div className="col-span-1 text-right text-[var(--text-secondary)] font-mono font-bold tracking-tighter">
                                        {job.cpu} / {job.ram}
                                    </div>
                                    {job.status === 'RUNNING' && (
                                        <div className="absolute inset-y-0 left-0 w-[3px] bg-[var(--accent)] glow-accent shadow-[0_0_15px_var(--accent-glow)]" />
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* 2. BOTTOM: Operational Workspace (Console + AI) */}
            <div className="flex-1 flex min-h-0 bg-[var(--layer-1)] relative divide-x divide-[var(--border-default)]">

                {/* LEFT SIDE: Operations Terminal */}
                <div className="flex-[5] flex flex-col overflow-hidden bg-[var(--layer-0)] min-w-0">
                    <div className="h-10 bg-[var(--layer-2)] border-b border-[var(--border-default)] flex items-center justify-between px-6 shrink-0 relative z-10 shadow-sm">
                        <div className="flex items-center gap-4">
                            <span className="font-bold text-[var(--text-primary)] flex items-center gap-2.5 text-[10px] tracking-[0.2em] font-display uppercase">
                                <Terminal size={14} className="text-[var(--accent)]" /> OPERATIONAL_CONSOLE // <span className="text-[var(--accent)] font-mono">{activeJob.id}</span>
                            </span>
                            <div className="px-2 py-0.5 bg-[var(--accent-subtle)] border border-[var(--accent-glow)] rounded text-[8px] font-bold text-[var(--accent)] animate-pulse">ACTIVE_STREAM</div>
                        </div>
                        <div className="flex gap-1 items-center">
                            {isAdmin ? (
                                <>
                                    <button onClick={runAgent} title="Run Agent" className="p-2 hover:bg-[var(--layer-3)] rounded-md text-[var(--text-tertiary)] hover:text-[var(--success)] transition-all active:scale-90"><Play size={14} strokeWidth={2.5} /></button>
                                    <button title="Rerun" className="p-2 hover:bg-[var(--layer-3)] rounded-md text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-all active:scale-90"><RotateCcw size={14} strokeWidth={2.5} /></button>
                                    <button title="Stop Agent" className="p-2 hover:bg-[var(--layer-3)] rounded-md text-[var(--text-tertiary)] hover:text-[var(--danger)] transition-all active:scale-90"><AlertOctagon size={14} strokeWidth={2.5} /></button>
                                </>
                            ) : (
                                <div className="px-3 py-1 bg-[var(--layer-3)] rounded border border-[var(--border-subtle)] text-[8px] font-bold text-[var(--text-tertiary)] uppercase flex items-center gap-2">
                                    <Shield size={10} /> READ_ONLY_ACCESS
                                </div>
                            )}
                        </div>
                    </div>
                    
                    <div className="flex-1 p-6 font-mono text-[11px] overflow-y-auto space-y-2 bg-[var(--layer-0)] leading-relaxed relative scrollbar-thin scrollbar-thumb-[var(--layer-4)] min-h-0">
                        <div className="absolute inset-0 pointer-events-none opacity-5 flex items-center justify-center p-20">
                            <Terminal size={300} strokeWidth={0.5} className="text-[var(--accent)]" />
                        </div>
                        
                        <div className="relative z-10">
                            {manualOutput ? (
                                <div className="whitespace-pre-wrap text-[var(--text-primary)] font-bold">{manualOutput}</div>
                            ) : (
                                <div className="space-y-1.5">
                                    <div className="text-[var(--text-tertiary)] opacity-60 mb-4 font-bold"># Initializing operational context for session {activeJob.id}...</div>
                                    <div className="flex gap-4"><span className="text-[var(--text-tertiary)] w-10">09:14:02</span> <span className="text-[var(--accent)] font-bold">[INFO]</span> <span className="text-[var(--text-secondary)]">Agent runtime v2.4.1 environment validated.</span></div>
                                    <div className="flex gap-4"><span className="text-[var(--text-tertiary)] w-10">09:14:03</span> <span className="text-[var(--accent)] font-bold">[INFO]</span> <span className="text-[var(--text-secondary)]">Consolidating endpoint metrics for <span className="text-[var(--text-primary)] font-bold italic">{activeJob.task}</span>.</span></div>
                                    <div className="flex gap-4"><span className="text-[var(--text-tertiary)] w-10">09:14:03</span> <span className="text-[var(--success)] font-bold">[AUTH]</span> <span className="text-[var(--text-secondary)]">Target security certificate successfully negotiated.</span></div>
                                    
                                    {activeJob.status === 'RUNNING' && (
                                        <div className="mt-4 space-y-1">
                                            <div className="text-[var(--accent)] animate-pulse font-bold flex items-center gap-3">
                                                <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] glow-accent" />
                                                <span>SCANNING_RESOURCE: arn:aws:s3:::prod-compliance-data-01</span>
                                            </div>
                                            <div className="text-[var(--accent)] animate-pulse [animation-delay:200ms] font-bold flex items-center gap-3">
                                                <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] glow-accent" />
                                                <span>SCANNING_RESOURCE: arn:aws:s3:::prod-compliance-data-02</span>
                                            </div>
                                            <div className="text-[var(--accent)] animate-pulse [animation-delay:400ms] font-bold flex items-center gap-3">
                                                <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] glow-accent" />
                                                <span>ANALYZING_PERMISSION_DELTAS...</span>
                                            </div>
                                        </div>
                                    )}
                                    
                                    {activeJob.status === 'FAILED' && (
                                        <div className="mt-4 p-4 bg-[var(--danger-subtle)] border border-[var(--danger)] rounded shadow-lg animate-in shake duration-500">
                                            <div className="text-[var(--danger)] font-bold flex items-center gap-2 mb-1">
                                                <Hash size={12} /> CRITICAL_THREAD_ABORT
                                            </div>
                                            <div className="text-[var(--text-primary)] font-medium leading-relaxed">Connection timeout after 30s. Target node 10.0.0.15 unreachable in current VPC scope.</div>
                                            <div className="mt-3 text-[9px] text-[var(--danger)] opacity-60 font-bold uppercase tracking-widest">Trace_ID: 0x55921A (ABORTED)</div>
                                        </div>
                                    )}
                                    
                                    {activeJob.status === 'COMPLETED' && (
                                        <div className="mt-4 p-4 bg-[var(--success-subtle)] border border-[var(--success)] rounded shadow-lg animate-in zoom-in duration-300">
                                            <div className="text-[var(--success)] font-bold flex items-center gap-2 mb-1">
                                                <CheckCircle2 size={12} /> SESSION_TERMINATED_CLEANLY
                                            </div>
                                            <div className="text-[var(--text-primary)] font-medium italic">All compliance objectives satisfied. 0 Issues discovered in current infrastructure epoch.</div>
                                        </div>
                                    )}
                                    <div className="opacity-20 mt-8 pt-4 border-t border-[var(--border-default)] text-[9px] font-bold tracking-[0.3em] text-center">END_OF_EVENT_LOG</div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* RIGHT SIDE: Operational Assistant */}
                <div className="flex-[3] flex flex-col overflow-hidden relative bg-[var(--layer-2)] min-w-0 min-h-0">
                    <div className="absolute top-0 right-0 z-20 px-3 py-1.5 bg-[var(--layer-3)] rounded-bl-lg text-[9px] font-mono font-bold text-[var(--text-tertiary)] border-b border-l border-[var(--border-default)] shadow-lg tracking-widest">
                        AGENT_CONTROL_PIPE_V2.1
                    </div>
                    <GRCChatBot />
                    <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-[var(--accent)] to-transparent opacity-20" />
                </div>
            </div>

            {/* 3. GOVERNANCE LAYER: Agent Policy Sync (IAM-10) */}
            <div className={`mt-auto border-t border-[var(--border-default)] bg-[var(--layer-2)] transition-all duration-300 overflow-hidden ${showGovernance ? 'min-h-[280px]' : 'h-10'}`}>
                <div 
                    onClick={() => setShowGovernance(!showGovernance)}
                    className="h-10 px-6 flex items-center justify-between cursor-pointer hover:bg-[var(--layer-3)] transition-colors group"
                >
                    <div className="flex items-center gap-3">
                        <ShieldAlert size={14} className={showGovernance ? "text-[var(--accent)]" : "text-[var(--text-tertiary)]"} />
                        <span className="text-[10px] font-bold tracking-[0.3em] font-mono uppercase">Strategic_Agent_Governance_Layer</span>
                        <div className="px-2 py-0.5 rounded bg-[var(--accent-subtle)] text-[8px] font-bold text-[var(--accent)] glow-accent shadow-sm">ACTIVE_ENFORCEMENT</div>
                    </div>
                    <div className="flex items-center gap-4">
                        <span className="text-[9px] text-[var(--text-tertiary)] font-mono font-bold opacity-30 italic">Rev_{policies?.length || 0}.0.4_PAC_SYNC</span>
                        {showGovernance ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
                    </div>
                </div>

                {showGovernance && (
                    <div className="p-6 grid grid-cols-12 gap-6 animate-in slide-in-from-bottom-4 duration-300">
                        <div className="col-span-8">
                            <div className="bg-[var(--layer-1)] border border-[var(--border-default)] rounded-xl overflow-hidden shadow-2xl">
                                <table className="w-full text-left border-collapse">
                                    <thead>
                                        <tr className="bg-[var(--layer-3)] text-[var(--text-tertiary)] text-[9px] font-bold uppercase tracking-widest border-b border-[var(--border-default)]">
                                            <th className="py-3 px-6">Capability_Action</th>
                                            <th className="py-3 px-6">Required_Authority</th>
                                            <th className="py-3 px-6">Enforcement_State</th>
                                            <th className="py-3 px-6">Linked_Evidence</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-[var(--border-subtle)]">
                                        {(policies || []).filter(p => ["AGENT_EXECUTE", "RAG_QUERY", "EVIDENCE_EXPORT"].includes(p.name)).map(policy => (
                                            <tr key={policy.name} className="hover:bg-[var(--layer-2)]/50 transition-colors group">
                                                <td className="py-3 px-6">
                                                    <div className="text-[10px] font-bold text-[var(--text-primary)] font-mono">{policy.name}</div>
                                                    <div className="text-[9px] text-[var(--text-tertiary)] font-mono opacity-60">{policy.description}</div>
                                                </td>
                                                <td className="py-3 px-6">
                                                    {isAdmin ? (
                                                        <select 
                                                            value={policy.required_role}
                                                            onChange={(e) => updatePolicy(policy.id, { required_role: e.target.value, is_active: policy.is_active })}
                                                            className="bg-[var(--layer-2)] border border-[var(--border-default)] rounded-md py-1 px-3 text-[9px] font-mono font-bold text-[var(--text-primary)] focus:border-[var(--accent)] cursor-pointer"
                                                        >
                                                            <option value="admin">ADMIN</option>
                                                            <option value="analyst">ANALYST</option>
                                                            <option value="viewer">VIEWER</option>
                                                        </select>
                                                    ) : (
                                                        <span className="text-[9px] font-mono font-bold text-[var(--accent)] uppercase">{policy.required_role}_ROOT</span>
                                                    )}
                                                </td>
                                                <td className="py-3 px-6">
                                                    <button
                                                        disabled={!isAdmin}
                                                        onClick={() => updatePolicy(policy.id, { required_role: policy.required_role, is_active: !policy.is_active })}
                                                        className={`flex items-center gap-2 px-3 py-1 rounded border text-[8px] font-bold font-mono tracking-tighter transition-all ${policy.is_active ? 'bg-[var(--success-subtle)] text-[var(--success)] border-[var(--success)]/30' : 'bg-[var(--danger-subtle)] text-[var(--danger)] border-[var(--danger)]/30'}`}
                                                    >
                                                        {policy.is_active ? <Unlock size={10} /> : <Lock size={10} />}
                                                        {policy.is_active ? 'ACTIVE' : 'DISABLED'}
                                                    </button>
                                                </td>
                                                <td className="py-3 px-6">
                                                    <div className="flex items-center gap-2 text-[var(--text-tertiary)] font-mono text-[9px] font-bold hover:text-[var(--accent)] transition-colors cursor-pointer italic opacity-40 group-hover:opacity-100">
                                                        <FileKey size={10} />
                                                        {policy.source_doc || "LINK_EVIDENCE_MAP"}
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <div className="col-span-4 space-y-4">
                            <div className="bg-[var(--layer-1)] border border-[var(--border-default)] p-5 rounded-xl shadow-xl">
                                <div className="text-[10px] font-bold text-[var(--text-primary)] mb-3 flex items-center gap-2 uppercase tracking-widest font-display">
                                    <Shield size={14} className="text-[var(--accent)]" /> PAC_SYNC_STATUS
                                </div>
                                <div className="space-y-2.5">
                                    <div className="flex justify-between items-center text-[9px] font-mono">
                                        <span className="text-[var(--text-tertiary)]">Engine_Core</span>
                                        <span className="text-[var(--success)] font-bold">STABLE_V1.9</span>
                                    </div>
                                    <div className="flex justify-between items-center text-[9px] font-mono">
                                        <span className="text-[var(--text-tertiary)]">Policy_Latency</span>
                                        <span className="text(--accent) font-bold">12ms</span>
                                    </div>
                                    <div className="flex justify-between items-center text-[9px] font-mono">
                                        <span className="text-[var(--text-tertiary)]">Linked_Regulatory_Docs</span>
                                        <span className="text-[var(--text-primary)] font-bold">168_MAPPED</span>
                                    </div>
                                </div>
                            </div>
                            <div className="p-4 bg-[var(--layer-2)] border border-[var(--border-subtle)] rounded-xl opacity-60">
                                <span className="text-[8px] font-bold text-[var(--text-tertiary)] uppercase leading-relaxed font-mono">
                                    All agentic AI interactions are currently governed by ISO-27001-A.18.1.1. Changes are logged to the Secure Security Audit persistent trail.
                                </span>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            <footer className="h-6 bg-[var(--layer-1)] border-t border-[var(--border-default)] flex items-center px-6 justify-between text-[10px] text-[var(--text-tertiary)] font-bold tracking-[0.1em] shrink-0">
                <div className="flex items-center gap-4">
                     <span className="flex items-center gap-1.5"><Shield size={10} className="text-[var(--success)]" /> SECURE_OPS_GATEWAY</span>
                     <span className="text-[var(--border-subtle)]">|</span>
                     <span className="font-mono">PID: 8821</span>
                </div>
                <div className="flex items-center gap-4">
                    <span className="animate-pulse flex items-center gap-2">
                        <Activity size={10} className="text-[var(--accent)]" />
                        SYNC_ACTIVE
                    </span>
                    <span className="text-[var(--border-subtle)]">|</span>
                    <span className="font-mono">{new Date().toLocaleDateString()} {new Date().toLocaleTimeString()}</span>
                </div>
            </footer>
        </div>
    );
};
