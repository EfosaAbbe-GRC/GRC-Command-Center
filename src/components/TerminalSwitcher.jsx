import React, { useState, useEffect } from 'react';
import { Shield, Terminal, Activity, FileText, Monitor, Globe, Clock, UserCheck } from 'lucide-react';
import { useAuth } from '../contexts/useAuth';

export const TerminalSwitcher = ({ activeTerminal, setActiveTerminal }) => {
    const { user } = useAuth();
    const [currentTime, setCurrentTime] = useState(new Date());

    useEffect(() => {
        const timer = setInterval(() => setCurrentTime(new Date()), 1000);
        return () => clearInterval(timer);
    }, []);

    const timeString = currentTime.toLocaleTimeString('en-US', { 
        hour12: false, 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit' 
    });

    // Strategy: IA-02 Role-Based Access Control
    // Define terminals and their required roles for rendering.
    const allTerminals = [
        { id: 'COMPLIANCE', label: 'COMPLIANCE', icon: Shield, color: 'var(--success)', minRole: 'viewer' },
        { id: 'OPS', label: 'OPERATIONS', icon: Terminal, color: 'var(--accent)', minRole: 'analyst' },
        { id: 'EXEC', label: 'EXECUTIVE', icon: Activity, color: '#bc8cff', minRole: 'admin' },
        { id: 'KNOWLEDGE', label: 'KNOWLEDGE', icon: FileText, color: 'var(--warning)', minRole: 'analyst' },
    ];

    const roleLevels = { 'viewer': 1, 'analyst': 2, 'admin': 3 };
    const userLevel = roleLevels[user?.role || 'viewer'] || 0;
    
    // Filter terminals based on hierarchical permission level
    const terminals = allTerminals.filter(t => userLevel >= roleLevels[t.minRole]);

    // Stable session seed initialized once
    const [sessionSeed] = useState(() => Math.floor(Math.random() * 9000) + 1000);

    return (
        <header className="h-16 bg-[var(--layer-1)] border-b border-[var(--border-default)] flex items-center justify-between px-6 shrink-0 z-50 relative selection:bg-transparent transition-all">
            
            {/* 1. Branding (Bloomberg Institutional Style) */}
            <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-[var(--layer-2)] border border-[var(--border-emphasis)] rounded-sm flex items-center justify-center shadow-lg">
                    <Shield className="w-5 h-5 text-[var(--accent)]" />
                </div>
                <div className="flex flex-col">
                    <h1 className="text-sm font-bold tracking-[0.15em] text-[var(--text-primary)] leading-none mb-1.5 uppercase">
                        GRC COMMAND CENTER
                    </h1>
                    <div className="flex items-center gap-2 text-[10px] font-mono text-[var(--text-secondary)] font-medium">
                        <span className="text-[var(--accent)]">v2.5.0-STABLE</span>
                        <span className="text-[var(--text-tertiary)] opacity-30">//</span>
                        <div className="flex items-center gap-1.5 text-[var(--success)]">
                            <span className="w-1.5 h-1.5 rounded-full bg-[var(--success)] animate-pulse" />
                            SECURED_SESSION
                        </div>
                    </div>
                </div>
            </div>

            {/* 2. Switcher Tabs (Function Key Style) */}
            <nav className="flex items-center h-full">
                {terminals.map((t) => {
                    const Icon = t.icon;
                    const isActive = activeTerminal === t.id;
                    return (
                        <button
                            key={t.id}
                            onClick={() => setActiveTerminal(t.id)}
                            className={`
                                h-full px-6 flex flex-col items-center justify-center gap-1.5 relative group transition-all duration-200
                                ${isActive ? 'text-[var(--text-primary)]' : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--layer-2)]'}
                            `}
                        >
                            <Icon size={14} style={{ color: isActive ? t.color : 'inherit' }} className="transition-transform group-hover:scale-110" />
                            <span className="text-[10px] font-bold tracking-[0.2em]">{t.label}</span>
                            
                            {/* Bloomberg Underline Indicator */}
                            {isActive && (
                                <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-[var(--accent)] glow-accent" />
                            )}
                        </button>
                    )
                })}
            </nav>

            {/* 3. System Utility (Right) */}
            <div className="flex items-center gap-6 font-mono">
                {/* Clock */}
                <div className="flex flex-col items-end">
                    <div className="text-[10px] font-bold text-[var(--text-tertiary)] tracking-widest uppercase mb-1 flex items-center gap-1.5">
                        <Clock size={10} /> Universal Time
                    </div>
                    <div className="text-sm font-bold text-[var(--accent)] tracking-wider">
                        {timeString}
                    </div>
                </div>
                
                <div className="h-8 w-px bg-[var(--border-subtle)]" />
                
                {/* Session Context */}
                <div className="flex items-center gap-3">
                    <div className="text-right">
                        <div className="text-[10px] font-bold text-[var(--text-tertiary)] uppercase tracking-wider mb-0.5">Session ID</div>
                        <div className="text-[11px] font-bold text-[var(--text-primary)] uppercase">
                            USR_{user?.username || 'ANONYMOUS'}_{sessionSeed}
                        </div>
                    </div>
                    <div className="w-8 h-8 rounded-sm bg-[var(--layer-2)] border border-[var(--border-default)] flex items-center justify-center">
                        <UserCheck size={14} className="text-[#94A3B8]" />
                    </div>
                </div>
            </div>

            {/* Visual Accent Line */}
            <div className="absolute bottom-[-1px] left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-[var(--accent)] to-transparent opacity-20" />

        </header>
    );
};
