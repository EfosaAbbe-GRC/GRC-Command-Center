import React from 'react';
import { AlertCircle, RotateCcw } from 'lucide-react';

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error("ErrorBoundary caught an error", error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="flex-1 flex flex-col items-center justify-center p-12 bg-[var(--layer-0)] border border-[var(--danger-subtle)] rounded-lg glow-danger relative overflow-hidden text-center">
                    
                    {/* Background Detail */}
                    <div className="absolute inset-0 opacity-5 pointer-events-none">
                        <div className="absolute top-0 left-0 w-full h-1 bg-[var(--danger)]" />
                        <div className="absolute bottom-0 left-0 w-full h-1 bg-[var(--danger)]" />
                        <div className="w-full h-full flex items-center justify-center">
                             <AlertCircle size={400} strokeWidth={0.5} className="text-[var(--danger)]" />
                        </div>
                    </div>

                    <div className="w-20 h-20 bg-[var(--danger-subtle)] border border-[var(--danger)] rounded-2xl flex items-center justify-center mb-8 shadow-2xl z-10">
                        <AlertCircle className="w-10 h-10 text-[var(--danger)]" />
                    </div>

                    <h2 className="text-2xl font-bold font-display text-[var(--text-primary)] mb-4 tracking-tight z-10">
                        CRITICAL_INTERFACE_FAULT
                    </h2>
                    
                    <div className="max-w-md bg-[var(--layer-1)] border border-[var(--border-default)] p-6 rounded-md mb-10 text-left z-10 shadow-lg">
                        <div className="text-[10px] font-bold text-[var(--danger)] uppercase tracking-wider mb-2">Error Diagnostic</div>
                        <p className="text-[var(--text-secondary)] text-xs font-mono leading-relaxed break-all">
                            {this.state.error?.stack || this.state.error?.message || "SYSTEM_THREAD_EXCEPTION_NOT_HANDLED"}
                        </p>
                    </div>

                    <button
                        onClick={() => window.location.reload()}
                        className="px-8 py-3 bg-[var(--danger)] hover:bg-[#f86d67] text-white font-bold rounded-md transition-all shadow-xl active:scale-95 flex items-center gap-3 z-10"
                    >
                        <RotateCcw size={18} />
                        REBOOT_INTERFACE
                    </button>

                    <div className="mt-8 text-[10px] text-[var(--text-disabled)] font-mono tracking-widest uppercase z-10">
                        Reference ID: ERR_UI_V8_CRASH
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
