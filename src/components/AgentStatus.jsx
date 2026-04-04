import React, { useState } from 'react';
import { Play, Activity, AlertCircle, Check } from 'lucide-react';

export default function AgentStatus() {
    const [agents, setAgents] = useState([
        { id: 'compliance_checker', name: 'COMPLIANCE_AUDITOR', status: 'IDLE', lastRun: '--' },
        { id: 'cloud_auditor', name: 'AWS_SEC_SCANNER', status: 'IDLE', lastRun: '--' },
    ]);

    const runAgent = async (agentId) => {
        setAgents(prev => prev.map(a => a.id === agentId ? { ...a, status: 'RUNNING' } : a));
        try {
            const response = await fetch(`http://localhost:8001/api/run-agent?agent_name=${agentId}`, { method: 'POST' });
            const data = await response.json();
            setAgents(prev => prev.map(a => a.id === agentId ? {
                ...a,
                status: data.result?.status === 'success' ? 'PASSED' : 'FAILED',
                lastRun: new Date().toLocaleTimeString('en-US', { hour12: false })
            } : a));
        } catch (err) {
            setAgents(prev => prev.map(a => a.id === agentId ? { ...a, status: 'ERROR' } : a));
        }
    };

    const getStatusIcon = (status) => {
        if (status === 'RUNNING') return <Activity className="w-3 h-3 animate-spin text-blue-400" />;
        if (status === 'PASSED') return <Check className="w-3 h-3 text-emerald-400" />;
        if (status === 'FAILED' || status === 'ERROR') return <AlertCircle className="w-3 h-3 text-rose-400" />;
        return <div className="w-2 h-2 rounded-full bg-[#334155]" />;
    }

    return (
        <div className="bg-[#0B1221] border border-[#1E293B]">
            <div className="bg-[#0F172A] border-b border-[#1E293B] px-3 py-1 flex justify-between items-center">
                <span className="text-[#94A3B8] font-bold text-[10px] font-mono">AGENT_CONTROLLER</span>
                <span className="text-[9px] text-emerald-500 font-mono">ONLINE</span>
            </div>

            <div className="p-2 space-y-1">
                {agents.map(agent => (
                    <div key={agent.id} className="group flex items-center justify-between p-2 hover:bg-[#1E293B] border border-transparent hover:border-[#334155] transition-colors">
                        <div className="flex items-center gap-3">
                            <div className="w-4 flex justify-center">{getStatusIcon(agent.status)}</div>
                            <div className="flex flex-col">
                                <span className="text-xs font-bold text-[#E2E8F0] font-mono">{agent.name}</span>
                                <span className="text-[9px] text-[#64748B] font-mono">LAST_EXEC: {agent.lastRun}</span>
                            </div>
                        </div>

                        <button
                            onClick={() => runAgent(agent.id)}
                            className="p-1.5 rounded hover:bg-[#0ea5e9]/20 text-[#64748B] hover:text-[#0ea5e9] transition-colors"
                            title="Execute Agent"
                        >
                            <Play className="w-3 h-3" />
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
}
