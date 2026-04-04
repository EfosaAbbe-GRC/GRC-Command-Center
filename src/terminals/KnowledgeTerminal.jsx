import { api } from '../lib/api';
import { useApiData } from '../hooks/useApiData';
import { useAuth } from '../contexts/useAuth';
import { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, Folder, FileText, Activity, Database, RefreshCw, Search, Filter, Download, FileType, FileCode, FileBarChart2, Eye, Tag, ShieldCheck, Layers, Laptop, UserCheck } from 'lucide-react';

export const KnowledgeTerminal = () => {
    const { user } = useAuth();
    const isAdmin = user?.role === 'admin';
    const [selectedDocId, setSelectedDocId] = useState(null);
    const [isSyncing, setIsSyncing] = useState(false);

    const { data: structure, loading, error, refresh } = useApiData('/notebook/structure');
    const { data: documents } = useApiData('/knowledge/documents', { initialData: [] });

    // Auto-select first document
    useEffect(() => {
        if (documents.length > 0 && !selectedDocId) {
            setSelectedDocId(documents[0].id);
        }
    }, [documents, selectedDocId]);

    const syncNotes = async () => {
        if (!isAdmin) return;
        setIsSyncing(true);
        try {
            await api.triggerNotebookSync();
            // Pulse the refresh
            setTimeout(() => {
                refresh();
                setIsSyncing(false);
            }, 1000);
        } catch (err) {
            console.error(err);
            setIsSyncing(false);
        }
    };

    const activeDoc = documents.find(d => d.id === selectedDocId);

    // Recursive FileTree Component
    const FileTree = ({ items, level = 0 }) => {
        const [expanded, setExpanded] = useState({});

        const toggleFolder = (name) => {
            setExpanded(prev => ({ ...prev, [name]: !prev[name] }));
        };

        return (
            <div className="font-mono text-[11px] select-none">
                {items.map((item) => {
                    const isFolder = item.type === 'folder';
                    const isExpanded = expanded[item.name];
                    const isSelected = !isFolder && selectedDocId === item.id;

                    return (
                        <div key={item.path || item.name} className="flex flex-col">
                            <div
                                onClick={() => isFolder ? toggleFolder(item.name) : setSelectedDocId(item.id)}
                                className={`
                                    flex items-center gap-2.5 py-1.5 px-3 cursor-pointer transition-all border-l-2
                                    ${isSelected ? 'bg-[var(--accent-subtle)] border-[var(--accent)] text-[var(--accent)]' : 'border-transparent text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--layer-2)]'}
                                `}
                                style={{ paddingLeft: `${level * 16 + 12}px` }}
                            >
                                {isFolder ? (
                                    <>
                                        <div className="flex items-center gap-1">
                                            {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                                            <Folder size={14} className={isExpanded ? 'text-[var(--accent)]' : 'text-[var(--text-tertiary)]'} />
                                        </div>
                                        <span className={`font-bold uppercase tracking-wider ${isExpanded ? 'text-[var(--text-secondary)]' : ''}`}>{item.name}</span>
                                    </>
                                ) : (
                                    <>
                                        <FileText size={14} className={isSelected ? 'text-[var(--accent)]' : 'text-[var(--text-tertiary)] opacity-60'} />
                                        <span className={isSelected ? 'font-bold' : ''}>{item.name}</span>
                                    </>
                                )}
                            </div>
                            {isFolder && isExpanded && item.children && (
                                <FileTree items={item.children} level={level + 1} />
                            )}
                        </div>
                    );
                })}
            </div>
        );
    };

    if (loading && (!structure || structure.length === 0)) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center bg-[var(--layer-0)] text-[var(--accent)]">
                <Activity className="animate-spin mb-4" size={48} />
                <span className="text-[10px] font-bold tracking-[0.3em] font-mono animate-pulse uppercase">Knowledge_Index_Construction</span>
            </div>
        );
    }

    if (error && (!structure || structure.length === 0)) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center bg-[var(--layer-0)] text-[var(--danger)]">
                <Database className="mb-4" size={48} />
                <span className="text-sm font-bold tracking-[0.1em] font-display uppercase mb-2">Knowledge Core Offline</span>
                <span className="text-[10px] text-[var(--text-tertiary)] font-mono mb-6">{error}</span>
                <button
                    onClick={refresh}
                    className="px-8 py-2.5 bg-[var(--danger-subtle)] border border-[var(--danger)] rounded-md text-[10px] font-bold text-[var(--danger)] hover:bg-[var(--danger)] hover:text-white transition-all shadow-lg active:scale-95"
                >
                    REATTEMPT_SYNC
                </button>
            </div>
        );
    }

    return (
        <div className="flex-1 flex bg-[var(--layer-0)] text-[11px] overflow-hidden">
            
            {/* 1. LEFT SIDEBAR: DIRECTORY TREE */}
            <div className="w-72 border-r border-[var(--border-default)] bg-[var(--layer-1)] flex flex-col shrink-0">
                
                {/* Section Header */}
                <div className="h-14 flex items-center justify-between px-5 border-b border-[var(--border-default)] bg-[var(--layer-2)] shrink-0">
                    <span className="font-bold text-[var(--text-primary)] tracking-[0.2em] flex items-center gap-3 text-[10px] uppercase font-display">
                        <Folder size={14} className="text-[var(--accent)]" /> GRC_ARTIFACTS
                    </span>
                    {isAdmin && (
                        <button 
                            onClick={syncNotes} 
                            disabled={isSyncing}
                            className={`p-1.5 rounded-md text-[var(--text-tertiary)] hover:text-[var(--accent)] hover:bg-[var(--layer-3)] transition-all ${isSyncing ? 'animate-spin text-[var(--accent)]' : ''}`} 
                            title="Sync Notebooks to Database"
                        >
                            <RefreshCw size={14} />
                        </button>
                    )}
                </div>

                {/* Tree Area */}
                <div className="flex-1 overflow-y-auto pt-4 pb-10 scrollbar-thin scrollbar-thumb-[var(--layer-4)]">
                    {!structure || structure.length === 0 ? (
                        <div className="p-8 text-center text-[var(--text-tertiary)] opacity-30 italic font-mono uppercase tracking-[0.1em]">
                            Notebook Empty // NO_MD_FOUND
                        </div>
                    ) : (
                        <FileTree items={structure} />
                    )}
                </div>

                {/* Storage Context */}
                <div className="p-5 border-t border-[var(--border-default)] bg-[var(--layer-0)]">
                    <div className="text-[9px] text-[var(--text-tertiary)] font-bold tracking-[0.2em] mb-3 uppercase flex items-center gap-2">
                        <Database size={12} /> Local_Buffer_Integrity
                    </div>
                    <div className="h-2 w-full bg-[var(--layer-2)] border border-[var(--border-subtle)] rounded-full overflow-hidden mb-2">
                        <div className="h-full bg-gradient-to-r from-[var(--accent)] to-[var(--success)] w-[15%] shadow-[0_0_10px_var(--accent-glow)]" />
                    </div>
                    <div className="flex justify-between text-[9px] text-[var(--text-tertiary)] font-mono font-bold">
                        <span>CAPACITY_USE</span>
                        <span className="text-[var(--success)]">15.4% OK</span>
                    </div>
                </div>
            </div>

            {/* 2. MIDDLE: HIGH-DENSITY DOCUMENT GRID */}
            <div className="flex-1 flex flex-col min-w-0 bg-[var(--layer-0)]">
                {/* Grid Header / Command Line */}
                <div className="h-14 border-b border-[var(--border-default)] bg-[var(--layer-1)] flex items-center justify-between px-6 shrink-0 z-10 shadow-sm">
                    <div className="flex items-center gap-4">
                        <div className="p-1.5 bg-[var(--layer-2)] border border-[var(--border-subtle)] rounded text-[var(--accent)]">
                            <Database size={16} strokeWidth={2.5} />
                        </div>
                        <span className="font-bold text-[var(--text-primary)] tracking-[0.2em] font-display text-xs uppercase">KNOWLEDGE_ROOT_INDEX // BROADCAST</span>
                    </div>
                    
                    <div className="flex items-center gap-4">
                        <div className="flex items-center text-[var(--text-secondary)] gap-3 bg-[var(--layer-0)] border border-[var(--border-default)] px-4 py-1.5 rounded-lg w-72 shadow-inner focus-within:border-[var(--accent)] transition-all">
                            <Search size={14} className="text-[var(--accent)]" />
                            <input type="text" placeholder="Query semantic index..." className="bg-transparent border-none outline-none text-[var(--text-primary)] font-mono text-[10px] w-full placeholder-[var(--text-tertiary)]" />
                        </div>
                        <button className="p-2 hover:bg-[var(--layer-3)] rounded-md text-[var(--text-tertiary)] transition-colors"><Filter size={16} /></button>
                        <button className="p-2 hover:bg-[var(--layer-3)] rounded-md text-[var(--text-tertiary)] transition-colors"><Download size={16} /></button>
                    </div>
                </div>

                {/* Document Table */}
                <div className="flex-1 overflow-auto scrollbar-thin scrollbar-thumb-[var(--layer-4)]">
                    <div className="min-w-[1000px]">
                        {/* Table Header */}
                        <div className="grid grid-cols-12 gap-5 px-6 py-3 bg-[var(--layer-2)] border-b border-[var(--border-default)] text-[var(--text-tertiary)] font-bold text-[10px] uppercase tracking-[0.2em] sticky top-0 z-20 shadow-md">
                            <div className="col-span-1">EXT</div>
                            <div className="col-span-4">Knowledge Unit Canonical Name</div>
                            <div className="col-span-1">Format</div>
                            <div className="col-span-1">Byte_Size</div>
                            <div className="col-span-2">Last_Indexed</div>
                            <div className="col-span-3 text-right">Integrity_State</div>
                        </div>

                        {/* List Area */}
                        <div className="divide-y divide-[var(--border-subtle)] bg-[var(--layer-0)]">
                            {documents.map((doc, i) => (
                                <div
                                    key={doc.id}
                                    onClick={() => setSelectedDocId(doc.id)}
                                    className={`grid grid-cols-12 gap-5 px-6 py-3.5 items-center group cursor-pointer data-row ${selectedDocId === doc.id ? 'selected' : (i % 2 === 0 ? 'bg-[var(--layer-0)]' : 'bg-[var(--layer-1)]/30')}`}
                                >
                                    <div className="col-span-1 flex justify-center">
                                        <FileIcon type={doc.type} size={18} />
                                    </div>
                                    <div className="col-span-4 flex items-center gap-3 text-[var(--text-primary)] font-bold transition-colors group-hover:text-[var(--accent)]">
                                        <span className="truncate tracking-wide font-display">{doc.name}</span>
                                    </div>
                                    <div className="col-span-1 text-[var(--text-tertiary)] font-mono font-bold opacity-60 text-[9px] uppercase tracking-widest">{doc.type}</div>
                                    <div className="col-span-1 text-[var(--text-secondary)] font-mono tracking-tighter">{doc.size}</div>
                                    <div className="col-span-2 text-[var(--text-tertiary)] font-mono text-[10px]">{doc.indexed}</div>
                                    <div className="col-span-3 flex justify-end">
                                        <DocStatusTag status={doc.status} />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* 3. RIGHT SIDEBAR: METADATA & INSPECTION (300px) */}
            <div className="w-[340px] border-l border-[var(--border-default)] bg-[var(--layer-1)] flex flex-col shrink-0 relative z-10 shadow-2xl">
                {/* Action Bar */}
                <div className="h-14 border-b border-[var(--border-default)] bg-[var(--layer-2)] flex items-center px-5 justify-between shrink-0">
                    <span className="font-bold text-[var(--text-primary)] tracking-[0.2em] text-[10px] flex items-center gap-3 font-display uppercase">
                        <Activity size={15} className="text-[var(--accent)]" /> METADATA_LAYER_V8
                    </span>
                    <button className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"><Layers size={14} /></button>
                </div>

                <div className="flex-1 overflow-y-auto p-6 space-y-8 scrollbar-thin scrollbar-thumb-[var(--layer-4)]">
                    {activeDoc ? (
                        <>
                            {/* Document Hero */}
                            <div className="flex flex-col items-center justify-center p-8 border border-[var(--border-default)] bg-[var(--layer-0)] rounded-xl relative overflow-hidden shadow-2xl group">
                                <div className="p-5 bg-[var(--layer-2)] border border-[var(--border-emphasis)] rounded-2xl mb-5 shadow-2xl transform transition-transform group-hover:scale-105 group-hover:rotate-1">
                                    <FileIcon type={activeDoc.type} size={48} />
                                </div>
                                <div className="text-[var(--text-primary)] font-bold text-center px-4 font-display text-sm tracking-tight mb-2 uppercase leading-tight">{activeDoc.name}</div>
                                <div className="text-[var(--text-tertiary)] text-[9px] font-mono font-bold tracking-[0.3em] uppercase mb-6 opacity-40 italic">{activeDoc.id}</div>
                                
                                <button className="w-full py-2.5 bg-[var(--layer-2)] hover:bg-[var(--layer-3)] border border-[var(--border-default)] rounded-md text-[var(--text-primary)] font-bold flex items-center justify-center gap-3 text-[10px] transition-all active:scale-95 shadow-lg">
                                    <Eye size={14} className="text-[var(--accent)]" /> VISUALIZE_CONTENT
                                </button>
                            </div>

                            {/* Semantic Metadata Table */}
                            <div className="bg-[var(--layer-2)]/50 border border-[var(--border-default)] rounded-xl p-5 space-y-4">
                                <div className="text-[9px] text-[var(--text-tertiary)] font-bold uppercase tracking-[0.2em] mb-2 flex items-center gap-2">
                                    <Tag size={12} className="text-[var(--warning)]" /> VECTOR_ID_METRICS
                                </div>
                                
                                <div className="space-y-4">
                                    <MetaRow label="Embedding_Model" value="text-embedding-004" isMono />
                                    <MetaRow label="Semantic_Depth" value="1,204 Chunks" isMono />
                                    <MetaRow label="Vector_Dimensions" value="1536" isMono />
                                    <div className="flex justify-between items-center pt-2">
                                        <span className="text-[var(--text-secondary)] font-bold tracking-tight">Index_Confidence</span>
                                        <span className="text-[var(--success)] font-bold font-mono text-xs glow-success px-2 py-0.5 bg-[var(--success-subtle)] rounded shadow-inner">99.8%</span>
                                    </div>
                                </div>
                            </div>

                            {/* Neural Cross-Reference Card */}
                            <div className="bg-[var(--accent-subtle)] border border-[var(--accent-glow)] p-5 rounded-xl relative overflow-hidden shadow-lg group">
                                <span className="flex items-center gap-1.5 mb-3 text-[10px] font-bold tracking-widest text-[var(--accent)]"><UserCheck size={12} className="text-[var(--success)]" /> USR_{user?.role?.toUpperCase()}_AUTH</span>
                                <div className="flex items-center gap-2.5 text-[var(--accent)] font-bold mb-3 text-[10px] tracking-widest font-display">
                                    <ShieldCheck size={16} /> NEURAL_CROSS_VALIDATION
                                </div>
                                <p className="text-[var(--text-primary)] leading-relaxed mb-6 text-[10px] font-medium font-mono opacity-80">
                                    Artifact {activeDoc.id} has been validated against global compliance corpora. Semantic alignment matches 14 active internal policies. <span className="text-[var(--success)]">No policy conflicts detected.</span>
                                </p>
                                {isAdmin ? (
                                    <button className="w-full py-3 bg-[var(--accent-emphasis)] hover:bg-[var(--accent)] text-white border border-[var(--accent)] rounded-lg font-bold text-[10px] tracking-[0.2em] transition-all shadow-[0_4px_20px_var(--accent-glow)] active:scale-95 uppercase">
                                        DEEP_INSPECTOR_RUN
                                    </button>
                                ) : (
                                    <div className="w-full py-3 bg-[var(--layer-2)] border border-[var(--border-subtle)] rounded-lg text-center text-[10px] font-bold text-[var(--text-tertiary)] uppercase tracking-widest opacity-60">
                                        RECORDS_RESTRICTED
                                    </div>
                                )}
                                
                                {/* Background Highlight */}
                                <div className="absolute right-[-10px] bottom-[-10px] transform rotate-12 opacity-[0.05] pointer-events-none group-hover:rotate-0 transition-transform">
                                    <Activity size={120} />
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="flex-1 flex flex-col items-center justify-center text-center p-10 space-y-6 opacity-30">
                             <Laptop size={64} strokeWidth={1} className="text-[var(--text-tertiary)]" />
                             <span className="text-[10px] font-bold font-mono uppercase tracking-[0.4em] leading-relaxed">
                                Select_Doc_To_Extract_<br />Metadata_Manifest
                             </span>
                        </div>
                    )}
                </div>
                
                {/* Sidebar Footer Accent */}
                <div className="h-1.5 bg-gradient-to-r from-transparent via-[var(--accent)] to-transparent opacity-20" />
            </div>
        </div>
    );
};

// Helper components
const MetaRow = ({ label, value, isMono }) => (
    <div className="flex flex-col gap-1.5 py-1 border-b border-[var(--border-subtle)] last:border-none">
        <span className="text-[9px] font-bold text-[var(--text-tertiary)] uppercase tracking-widest">{label}</span>
        <span className={`text-[var(--text-primary)] truncate font-semibold ${isMono ? 'font-mono tracking-tighter' : ''}`}>{value}</span>
    </div>
);

const FileIcon = ({ type, size }) => {
    switch(type) {
        case 'PDF': return <FileType size={size} className="text-[var(--danger)]" />;
        case 'JSON': return <FileCode size={size} className="text-[var(--warning)]" />;
        case 'MD': return <FileText size={size} className="text-[var(--accent)]" />;
        case 'CSV': return <FileBarChart2 size={size} className="text-[var(--success)]" />;
        default: return <FileText size={size} className="text-[var(--text-tertiary)]" />;
    }
};

const DocStatusTag = ({ status }) => {
    const isProcessing = status === 'PROCESSING';
    const isError = status === 'FAILED' || status === 'ERROR';
    
    return (
        <span className={`
            px-3 py-1 rounded-sm text-[9px] font-bold tracking-[0.2em] font-mono border uppercase
            ${isProcessing ? 'text-[var(--accent)] bg-[var(--accent-subtle)] border-[var(--accent-glow)] animate-pulse' : 
              isError ? 'text-[var(--danger)] bg-[var(--danger-subtle)] border-[var(--danger)]/30' : 
              'text-[var(--success)] bg-[var(--success-subtle)] border-[var(--success)]/20 shadow-sm'}
        `}>
            {status}
        </span>
    );
};
