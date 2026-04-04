import React from 'react';

const STATUS_CONFIG = {
    // Compliance & Generic Statuses
    ACTIVE: { color: 'var(--success)', bg: 'var(--success-subtle)', label: 'ACTIVE' },
    SATISFIED: { color: 'var(--success)', bg: 'var(--success-subtle)', label: 'SATISFIED' },
    COMPLETED: { color: 'var(--success)', bg: 'var(--success-subtle)', label: 'COMPLETED' },
    
    WARN: { color: 'var(--warning)', bg: 'var(--warning-subtle)', label: 'WARNING' },
    PARTIAL: { color: 'var(--warning)', bg: 'var(--warning-subtle)', label: 'PARTIAL' },
    QUEUED: { color: 'var(--warning)', bg: 'var(--warning-subtle)', label: 'QUEUED' },
    
    FAIL: { color: 'var(--danger)', bg: 'var(--danger-subtle)', label: 'CRITICAL' },
    FAILED: { color: 'var(--danger)', bg: 'var(--danger-subtle)', label: 'FAILED' },
    NOT_MET: { color: 'var(--danger)', bg: 'var(--danger-subtle)', label: 'NOT MET' },
    CRITICAL: { color: 'var(--danger)', bg: 'var(--danger-subtle)', label: 'CRITICAL' },
    
    REVIEW: { color: 'var(--accent)', bg: 'var(--accent-subtle)', label: 'UNDER REVIEW' },
    RUNNING: { color: 'var(--accent)', bg: 'var(--accent-subtle)', label: 'RUNNING', animate: true },
    PROCESSING: { color: 'var(--accent)', bg: 'var(--accent-subtle)', label: 'PROCESSING', animate: true },
    INDEXED: { color: 'var(--success)', bg: 'var(--success-subtle)', label: 'INDEXED' },
};

export const StatusBadge = ({ status, variant = 'default' }) => {
    const config = STATUS_CONFIG[status] || { color: 'var(--text-tertiary)', bg: 'var(--layer-2)', label: status };
    
    const isLarge = variant === 'large';
    
    return (
        <span 
            className={`
                inline-flex items-center gap-1.5 font-mono font-bold tracking-wider rounded-sm border
                ${isLarge ? 'px-2.5 py-1 text-[10px]' : 'px-1.5 py-0.5 text-[9px]'}
                ${config.animate ? 'animate-pulse' : ''}
            `}
            style={{ 
                color: config.color, 
                backgroundColor: config.bg,
                borderColor: `rgba(${config.color === 'var(--success)' ? '63,185,80' : 
                                    config.color === 'var(--warning)' ? '210,153,34' : 
                                    config.color === 'var(--danger)' ? '248,81,73' : '88,166,255'}, 0.2)`
            }}
        >
            <span 
                className="w-1 h-1 rounded-full" 
                style={{ backgroundColor: config.color }} 
            />
            {config.label}
        </span>
    );
};
