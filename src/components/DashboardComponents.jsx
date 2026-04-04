import React from 'react';
import { Shield, Activity, Lock, TriangleAlert, CheckCircle, Clock, Server, Eye, FileText, Database, ShieldAlert, ShieldCheck, Terminal, Cpu, Network } from 'lucide-react';
import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Tooltip } from 'recharts';
import clsx from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs) {
    return twMerge(clsx(inputs));
}

// 1. Metric Card (Tech/Dense)
export const MetricCard = ({ label, value, subvalue, icon, trend = 'neutral', accentColor = 'blue' }) => {
    const Icon = icon;
    const accents = {
        blue: 'border-blue-500/30 text-blue-400',
        emerald: 'border-emerald-500/30 text-emerald-400',
        rose: 'border-rose-500/30 text-rose-400',
        amber: 'border-amber-500/30 text-amber-400',
        indigo: 'border-indigo-500/30 text-indigo-400',
        purple: 'border-purple-500/30 text-purple-400',
        cyan: 'border-cyan-500/30 text-cyan-400',
    };

    const colorClasses = accents[accentColor] || accents['blue'];

    return (
        <div className={cn("bg-[#0B1221] border-l-2 p-4 relative group overflow-hidden", colorClasses.split(' ')[0], "border-y border-r border-[#1E293B]")}>
            <div className="absolute top-0 right-0 p-2 opacity-20 group-hover:opacity-100 transition-opacity">
                <Icon className={cn("w-6 h-6", colorClasses.split(' ')[1])} />
            </div>
            <div className="relative z-10">
                <div className="text-[#64748B] text-[10px] font-bold uppercase tracking-widest mb-1 font-mono">{label}</div>
                <div className="text-2xl font-bold text-[#E2E8F0] tracking-tighter font-mono">{value}</div>
                <div className="text-[10px] text-[#475569] font-medium mt-1 font-mono flex items-center gap-2">
                    <span className={cn("w-1.5 h-1.5 rounded-full", trend === 'up' ? 'bg-emerald-500' : 'bg-[#334155]')} />
                    {subvalue}
                </div>
            </div>
        </div>
    );
};

// 2. Scorecard (Reactor Core)
export const ComplianceScorecard = ({ metrics }) => {
    const { complianceScore, riskLevel } = metrics || { complianceScore: 0, riskLevel: 'UNKNOWN' };
    const radius = 60;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference - (complianceScore / 100) * circumference;

    const getColor = (score) => {
        if (score >= 90) return '#10b981'; // emerald
        if (score >= 70) return '#f59e0b'; // amber
        return '#f43f5e'; // rose
    };
    const color = getColor(complianceScore);

    return (
        <div className="flex flex-col items-center justify-center p-6 relative h-full w-full">
            <div className="absolute top-4 left-4 bg-[#1E293B]/50 px-2 py-0.5 text-[10px] font-bold text-[#94A3B8] font-mono rounded">
                CORE_INTEGRITY
            </div>

            <div className="relative">
                <svg width="140" height="140" className="transform -rotate-90">
                    <circle cx="70" cy="70" r={radius} stroke="#1E293B" strokeWidth="8" fill="none" />
                    <circle
                        cx="70" cy="70" r={radius}
                        stroke={color} strokeWidth="8" fill="none"
                        strokeLinecap="round"
                        strokeDasharray={circumference}
                        strokeDashoffset={strokeDashoffset}
                        className="transition-all duration-1000 ease-out"
                        style={{ filter: `drop-shadow(0 0 4px ${color}80)` }}
                    />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-3xl font-bold text-white font-mono">{complianceScore}%</span>
                    <span className="text-[9px] text-[#64748B] uppercase tracking-wider font-bold">Health</span>
                </div>
            </div>

            <div className="mt-4 w-full grid grid-cols-2 gap-2">
                <div className="bg-[#0F172A] border border-[#1E293B] p-2 text-center">
                    <div className="text-[9px] text-[#64748B]">RISK LEVEL</div>
                    <div className={cn("text-xs font-bold font-mono", riskLevel === 'LOW' ? 'text-emerald-400' : 'text-rose-400')}>
                        {riskLevel}
                    </div>
                </div>
                <div className="bg-[#0F172A] border border-[#1E293B] p-2 text-center">
                    <div className="text-[9px] text-[#64748B]">CONTROLS</div>
                    <div className="text-xs font-bold font-mono text-blue-400">ACTIVE</div>
                </div>
            </div>
        </div>
    );
};

// 3. Radar (Tactical Grid)
export const SecurityRadar = ({ metrics }) => {
    const data = [
        { subject: 'CONF', A: 90, fullMark: 100 },
        { subject: 'INTG', A: metrics?.complianceScore || 80, fullMark: 100 },
        { subject: 'AVAL', A: 95, fullMark: 100 },
        { subject: 'RISK', A: metrics?.riskLevel === 'LOW' ? 100 : 50, fullMark: 100 },
        { subject: 'AUDT', A: 100, fullMark: 100 },
        { subject: 'RSIL', A: 85, fullMark: 100 },
    ];

    return (
        <div className="p-2 h-full w-full flex flex-col relative">
            <div className="absolute top-4 right-4 bg-[#1E293B]/50 px-2 py-0.5 text-[10px] font-bold text-[#94A3B8] font-mono rounded z-10">
                DOMAIN_COVERAGE
            </div>

            <ResponsiveContainer width="100%" height="100%">
                <RadarChart cx="50%" cy="50%" outerRadius="65%" data={data}>
                    <PolarGrid stroke="#1E293B" strokeDasharray="3 3" />
                    <PolarAngleAxis dataKey="subject" tick={{ fill: '#475569', fontSize: 9, fontFamily: 'monospace', fontWeight: 'bold' }} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                    <Radar
                        name="Controls"
                        dataKey="A"
                        stroke="#0ea5e9"
                        strokeWidth={2}
                        fill="#0ea5e9"
                        fillOpacity={0.1}
                        isAnimationActive={true}
                    />
                    <Tooltip
                        contentStyle={{ backgroundColor: '#020617', borderColor: '#1E293B', fontSize: '10px', fontFamily: 'monospace' }}
                        itemStyle={{ color: '#bae6fd' }}
                    />
                </RadarChart>
            </ResponsiveContainer>
        </div>
    );
};

// 4. Log Feed (System Console)
export const LogFeed = ({ logs = [] }) => {
    const safeLogs = (Array.isArray(logs) ? logs : []).filter(l => l && typeof l === 'object');

    const formatTime = (ts) => {
        if (!ts) return "00:00:00";
        return ts.includes('T') ? ts.split('T')[1].split('.')[0] : ts;
    };

    return (
        <div className="bg-[#020617] border border-[#1E293B] h-[300px] flex flex-col font-mono text-[10px]">
            <div className="bg-[#0F172A] border-b border-[#1E293B] px-3 py-1 flex justify-between items-center">
                <span className="text-[#94A3B8] font-bold">SYSTEM_EVENTS</span>
                <div className="flex gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-2 scrollbar-thin scrollbar-thumb-[#1E293B]">
                {safeLogs.map((log, i) => (
                    <div key={i} className="flex gap-3 py-0.5 hover:bg-[#1E293B]/30 cursor-crosshair">
                        <span className="text-[#475569]">{formatTime(log.timestamp)}</span>
                        <span className={cn(
                            "font-bold w-16",
                            log.type === 'ERROR' ? 'text-rose-500' :
                                log.type === 'SECURITY' ? 'text-purple-500' :
                                    log.type === 'VETO' ? 'text-amber-500' : 'text-blue-500'
                        )}>{log.type || 'INFO'}</span>
                        <span className="text-[#94A3B8] truncate">{log.message || log.raw}</span>
                    </div>
                ))}
                {safeLogs.length === 0 && <div className="text-[#334155] p-2">_waiting_for_stream...</div>}
            </div>
        </div>
    );
};
