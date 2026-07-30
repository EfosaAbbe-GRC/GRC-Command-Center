import { useState } from 'react'
import { TerminalSwitcher } from './components/TerminalSwitcher'
import { ComplianceTerminal } from './terminals/ComplianceTerminal'
import { OpsTerminal } from './terminals/OpsTerminal'
import { ExecutiveTerminal } from './terminals/ExecutiveTerminal'
import { KnowledgeTerminal } from './terminals/KnowledgeTerminal'
import VendorRiskTerminal from './terminals/VendorRiskTerminal'
import { AuthProvider } from './contexts/AuthContext'
import { useAuth } from './contexts/useAuth'
import ErrorBoundary from './components/ErrorBoundary'
import PasswordResetModal from './components/PasswordResetModal'

const Login = () => {
    const { login } = useAuth();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            await login(username, password);
        } catch {
            setError('Invalid credentials');
        }
    };

    return (
        <div className="flex items-center justify-center h-screen bg-[var(--layer-0)]">
            <div className="w-full max-w-md p-8 rounded-xl bg-[var(--layer-1)] border border-[var(--layer-2)] shadow-xl">
                <h1 className="text-2xl font-bold mb-6 text-center text-[var(--accent-glow)]">GRC.OS COMMAND CENTER</h1>
                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium mb-1">Username</label>
                        <input 
                            type="text" 
                            className="w-full p-2 rounded bg-[var(--layer-2)] border border-[var(--layer-3)]" 
                            value={username} 
                            onChange={(e) => setUsername(e.target.value)} 
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium mb-1">Password</label>
                        <input 
                            type="password" 
                            className="w-full p-2 rounded bg-[var(--layer-2)] border border-[var(--layer-3)] text-sm font-mono focus:border-[var(--accent-glow)] outline-none transition-colors" 
                            value={password} 
                            onChange={(e) => setPassword(e.target.value)} 
                            required
                        />
                    </div>
                    {error && <p className="text-[var(--danger)] text-[10px] font-bold tracking-wide text-center">{error}</p>}
                    <button type="submit" className="w-full py-2.5 rounded bg-[var(--accent-glow)] text-black font-bold tracking-widest hover:opacity-90 transition-all active:scale-[0.98]">
                        AUTHENTICATE_IDENTITY
                    </button>
                    <div className="text-center pt-2">
                        <span className="text-[8px] text-[var(--text-tertiary)] opacity-50 uppercase tracking-widest">Protocol: Secure_Handshake_v3.2</span>
                    </div>
                </form>
            </div>
        </div>
    );
};

function AppContent() {
  const { user, logout, needsReset, clearResetState } = useAuth();
  const [activeTerminal, setActiveTerminal] = useState('COMPLIANCE');

  if (!user) return <Login />;

  const renderTerminal = () => {
    switch (activeTerminal) {
      case 'COMPLIANCE': return <ErrorBoundary><ComplianceTerminal /></ErrorBoundary>;
      case 'OPS': return <ErrorBoundary><OpsTerminal /></ErrorBoundary>;
      case 'EXEC': return <ErrorBoundary><ExecutiveTerminal /></ErrorBoundary>;
      case 'KNOWLEDGE': return <ErrorBoundary><KnowledgeTerminal /></ErrorBoundary>;
      case 'TPRM': return <ErrorBoundary><VendorRiskTerminal /></ErrorBoundary>;
      default: return <ErrorBoundary><ComplianceTerminal /></ErrorBoundary>;
    }
  };

  return (
    <div className="flex flex-col h-screen bg-[var(--layer-0)] text-[var(--text-primary)] font-display selection:bg-[var(--accent-glow)] overflow-hidden">
      {/* SECURITY GATE: MANDATORY PASSWORD RESET */}
      <PasswordResetModal 
        isOpen={needsReset} 
        user={user} 
        onResetSuccess={clearResetState} 
        onLogout={logout} 
      />

      {/* GLOBAL NAVIGATION & STATUS BAR */}
      <div className="flex items-center justify-between z-50 bg-[var(--layer-1)] border-b border-[var(--border-default)] pr-6">
        <TerminalSwitcher activeTerminal={activeTerminal} setActiveTerminal={setActiveTerminal} />
        
        <div className="flex items-center gap-6">
            <div className="flex items-center gap-2 bg-[var(--layer-2)] border border-[var(--border-subtle)] px-3 py-1 rounded-md">
                <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] glow-accent shadow-[0_0_5px_var(--accent-glow)]" />
                <span className="text-[9px] font-bold tracking-widest text-[var(--text-tertiary)] uppercase">IDENTITY: </span>
                <span className="text-[9px] font-mono font-bold text-[var(--accent)] uppercase">{user.role}</span>
            </div>
            
            <button 
                onClick={logout} 
                className="text-[9px] font-bold tracking-widest text-[var(--text-tertiary)] hover:text-[var(--danger)] transition-colors uppercase border-l border-[var(--border-subtle)] pl-6"
            >
                TERMINATE_SESSION
            </button>
        </div>
      </div>

      {/* ACTIVE TERMINAL VIEWPORT */}
      <main className="flex-1 flex overflow-hidden relative bg-[var(--layer-0)]">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-[var(--accent-glow)] blur-[120px] rounded-full opacity-20 pointer-events-none" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-[var(--success-subtle)] blur-[120px] rounded-full opacity-10 pointer-events-none" />
        
        <div className="flex-1 flex z-10 overflow-hidden">
           {renderTerminal()}
        </div>
      </main>
      
      <div className="fixed inset-0 pointer-events-none border-[12px] border-[var(--layer-1)] opacity-20 z-[100]" />
    </div>
  )
}

function App() {
    return (
        <AuthProvider>
            <AppContent />
        </AuthProvider>
    );
}

export default App
