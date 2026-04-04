import React, { useState, useRef, useEffect } from 'react';
import { Send, Terminal, Cpu, User, Database, MessagesSquare } from 'lucide-react';
import { api } from '../lib/api';

export default function GRCChatBot() {
  const [messages, setMessages] = useState([
    { role: 'system', content: 'GRC_OS v2.5.0 Initialized. All knowledge nodes online. Security context: USR_ADMIN.' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    const userMsg = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const data = await api.post('/chat', { query: userMsg.content });
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: data.response || "INSUFFICIENT_DATA", 
        sources: data.sources 
      }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: "ERR_CONNECTION_REFUSED. Critical interface failure." }]);
    }
    setLoading(false);
  };

  return (
    <div className="bg-[var(--layer-1)] border border-[var(--border-default)] h-full flex flex-col font-mono shadow-xl relative overflow-hidden">
      
      {/* 1. Command Interface Header */}
      <div className="bg-[var(--layer-2)] border-b border-[var(--border-default)] px-4 py-3 flex items-center justify-between z-10">
        <div className="flex items-center gap-3">
            <MessagesSquare className="w-4 h-4 text-[var(--accent)]" />
            <h3 className="text-[var(--text-primary)] font-bold text-[11px] tracking-[0.2em] uppercase">
                CO-PILOT_ASSISTANT
            </h3>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-[var(--text-tertiary)] font-bold">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--success)] shadow-sm shadow-[var(--success)]" />
            VIRTUAL_ANALYST_READY
        </div>
      </div>

      {/* 2. Message Stream */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6 scroll-smooth" ref={scrollRef}>
        {messages.map((msg, idx) => {
          if (msg.role === 'system') {
            return (
              <div key={idx} className="flex justify-center my-4">
                <span className="px-4 py-1.5 bg-[var(--layer-2)] border border-[var(--border-subtle)] text-[var(--text-tertiary)] text-[9px] font-bold tracking-[0.1em] rounded-full uppercase">
                  {msg.content}
                </span>
              </div>
            );
          }
          
          const isUser = msg.role === 'user';
          
          return (
            <div key={idx} className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-300`}>
              <div className={`max-w-[85%] flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
                
                {/* Message Context */}
                <div className="flex items-center gap-2 mb-1.5 px-2">
                    <span className="text-[9px] font-bold text-[var(--text-tertiary)] uppercase tracking-widest leading-none">
                        {isUser ? 'USR_REQUEST' : 'AI_SYNTHESIS'}
                    </span>
                    {isUser ? <User size={10} className="text-[var(--text-secondary)]" /> : <Cpu size={10} className="text-[var(--accent)]" />}
                </div>

                {/* Content Bubble */}
                <div className={`
                    p-3.5 rounded-lg border text-[11px] leading-relaxed relative
                    ${isUser 
                        ? 'bg-[var(--accent-subtle)] border-[var(--accent)] text-[var(--text-primary)]' 
                        : 'bg-[var(--layer-2)] border-[var(--border-default)] text-[var(--text-secondary)]'
                    }
                `}>
                  {msg.content}
                  
                  {/* Sources chips */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-4 pt-3 border-t border-[var(--border-subtle)] flex flex-wrap gap-2">
                      <span className="text-[9px] font-bold text-[var(--text-tertiary)] flex items-center gap-1">
                        <Database size={8} /> CITATIONS:
                      </span>
                      {msg.sources.map((src, i) => (
                        <span key={i} className="text-[9px] bg-[var(--layer-3)] border border-[var(--border-default)] px-1.5 py-0.5 rounded text-[var(--text-secondary)] hover:text-[var(--accent)] transition-colors cursor-pointer font-bold">
                          {src}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
        {loading && (
          <div className="flex items-center gap-1.5 text-[var(--accent)] text-[10px] font-bold p-2 animate-pulse">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)]" />
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] [animation-delay:200ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] [animation-delay:400ms]" />
            <span className="ml-2 uppercase tracking-[0.2em] font-mono">Synthesizing...</span>
          </div>
        )}
      </div>

      {/* 3. Command Input Area */}
      <div className="p-4 bg-[var(--layer-2)] border-t border-[var(--border-default)] flex gap-3 items-center">
        <div className="flex-1 relative flex items-center">
            <div className="absolute left-4 text-[var(--accent)] font-bold text-sm tracking-widest opacity-60">➜</div>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              className="w-full bg-[var(--layer-0)] border border-[var(--border-default)] h-12 pl-10 pr-4 rounded-md text-[var(--text-primary)] placeholder-[var(--text-tertiary)] focus:border-[var(--accent-emphasis)] focus:ring-1 focus:ring-[var(--accent-glow)] outline-none transition-all font-mono font-medium tracking-wide text-xs"
              placeholder="Ask the compliance engine (e.g., 'Describe GDPR Article 5')..."
              disabled={loading}
            />
        </div>
        <button 
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="w-12 h-12 bg-[var(--accent-emphasis)] hover:bg-[var(--accent)] disabled:bg-[var(--layer-2)] disabled:text-[var(--text-tertiary)] text-white rounded-md flex items-center justify-center transition-all shadow-lg active:scale-95"
        >
            <Send size={18} />
        </button>
      </div>

      {/* DRAGGABLE DIVIDER LOOK-ALIKE */}
      <div className="absolute left-[-2px] inset-y-0 w-1 bg-gradient-to-b from-transparent via-[var(--border-emphasis)] to-transparent opacity-20" />
    </div>
  );
}
