import React, { useState } from 'react';
import { GraduationCap, Send, RotateCcw, AlertTriangle, CheckCircle2, XCircle, Clock } from 'lucide-react';
import { useApiData } from '../hooks/useApiData';
import { StatusBadge } from '../components/StatusBadge';
import { api } from '../lib/api';

const RUBRIC_LABELS = {
  completeness: 'Completeness',
  technical_accuracy: 'Technical Accuracy',
  defensibility: 'Defensibility',
};

const STATUS_BADGE_KEY = {
  in_progress: 'REVIEW',
  completed: 'COMPLETED',
};

function ScoreBar({ label, value }) {
  const color = value >= 70 ? 'var(--success)' : value >= 40 ? 'var(--warning)' : 'var(--danger)';
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[9px] font-mono uppercase tracking-wider">
        <span className="text-[var(--text-tertiary)]">{label}</span>
        <span style={{ color }} className="font-bold">{value}</span>
      </div>
      <div className="h-1.5 rounded-full bg-[var(--layer-2)] overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${value}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function GradedTurnCard({ turn }) {
  const rubric = turn.rubric_json ? JSON.parse(turn.rubric_json) : null;
  return (
    <div className="rounded border border-[var(--border-default)] bg-[var(--layer-1)] p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-bold text-[var(--text-tertiary)] uppercase tracking-widest">
          Stage {turn.turn_number} · {turn.question_category}
        </div>
        {turn.grading_status === 'graded' ? (
          <div className="flex items-center gap-1.5 text-[var(--success)]">
            <CheckCircle2 size={12} />
            <span className="text-[11px] font-bold font-mono">{turn.score}/100</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-[var(--warning)]">
            <XCircle size={12} />
            <span className="text-[9px] font-bold uppercase font-mono">Grading Unavailable</span>
          </div>
        )}
      </div>
      <div className="text-[11px] text-[var(--text-secondary)] leading-relaxed">{turn.question_text}</div>
      <div className="text-[11px] text-[var(--text-primary)] bg-[var(--layer-0)] rounded p-2.5 border border-[var(--border-subtle)] whitespace-pre-wrap">
        {turn.user_response_text}
      </div>
      {turn.grading_status === 'graded' ? (
        <>
          {rubric && (
            <div className="grid grid-cols-3 gap-3">
              {Object.entries(rubric).map(([key, value]) => (
                <ScoreBar key={key} label={RUBRIC_LABELS[key] || key} value={value} />
              ))}
            </div>
          )}
          <div className="text-[11px] text-[var(--text-secondary)] italic border-l-2 pl-2.5"
               style={{ borderColor: 'var(--accent)' }}>
            {turn.feedback_text}
          </div>
        </>
      ) : (
        <div className="text-[10px] text-[var(--warning)] flex items-center gap-1.5">
          <AlertTriangle size={11} />
          The AI grader could not score this answer. Your response was saved.
        </div>
      )}
    </div>
  );
}

export default function InterviewSimTerminal() {
  const { data: vendors } = useApiData('/tprm/vendors');
  const { data: history, refresh: refreshHistory } = useApiData('/interview-sim/sessions');

  const [mode, setMode] = useState('vendor');
  const [selectedVendor, setSelectedVendor] = useState('');
  const [direction, setDirection] = useState('egress');
  const [transferMethod, setTransferMethod] = useState('file');
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState(null);

  const [activeSession, setActiveSession] = useState(null);
  const [responseText, setResponseText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [justGraded, setJustGraded] = useState(null);

  const startSession = async () => {
    setStarting(true);
    setStartError(null);
    try {
      const payload = mode === 'vendor'
        ? { scenario_vendor: selectedVendor }
        : { direction, transfer_method: transferMethod };
      const session = await api.post('/interview-sim/sessions', payload);
      setActiveSession(session);
      setJustGraded(null);
      setResponseText('');
      refreshHistory();
    } catch (err) {
      setStartError(err.message || 'Failed to start session');
    } finally {
      setStarting(false);
    }
  };

  const openSession = async (summary) => {
    setStartError(null);
    setJustGraded(null);
    setResponseText('');
    const detail = await api.get(`/interview-sim/sessions/${summary.id}`);
    setActiveSession(detail);
  };

  const currentTurn = activeSession?.turns.find((t) => !t.user_response_text);

  const submitResponse = async () => {
    if (!currentTurn || !responseText.trim()) return;
    setSubmitting(true);
    setStartError(null);
    try {
      const result = await api.post(
        `/interview-sim/sessions/${activeSession.id}/turns/${currentTurn.id}/respond`,
        { response_text: responseText }
      );
      setActiveSession((prev) => {
        const turns = [...prev.turns];
        const idx = turns.findIndex((t) => t.id === result.turn.id);
        if (idx !== -1) turns[idx] = result.turn;
        if (result.next_turn) {
          const nIdx = turns.findIndex((t) => t.id === result.next_turn.id);
          if (nIdx !== -1) turns[nIdx] = result.next_turn;
        }
        return { ...prev, turns, status: result.session_status, overall_score: result.overall_score };
      });
      setJustGraded(result.turn);
      setResponseText('');
      refreshHistory();
    } catch (err) {
      setStartError(err.message || 'Failed to submit response');
    } finally {
      setSubmitting(false);
    }
  };

  const continueSession = () => setJustGraded(null);

  const answeredTurns = activeSession?.turns.filter((t) => t.user_response_text) || [];

  return (
    <div className="flex-1 flex bg-[var(--layer-0)] text-[var(--text-primary)] overflow-hidden h-full">
      {/* LEFT: start form + history */}
      <div className="w-[340px] border-r border-[var(--border-default)] flex flex-col min-h-0 bg-[var(--layer-1)]">
        <div className="h-14 border-b border-[var(--border-default)] flex items-center gap-2 px-4 shrink-0">
          <GraduationCap size={16} className="text-[var(--accent)]" />
          <h2 className="text-[11px] font-bold tracking-widest uppercase font-display">Interview Simulator</h2>
        </div>

        <div className="p-4 space-y-3 border-b border-[var(--border-default)]">
          <div className="flex rounded-sm border border-[var(--border-default)] overflow-hidden text-[10px] font-bold uppercase tracking-wider">
            <button
              onClick={() => setMode('vendor')}
              className="flex-1 py-1.5"
              style={mode === 'vendor'
                ? { backgroundColor: 'var(--accent-subtle)', color: 'var(--accent)' }
                : { color: 'var(--text-tertiary)' }}
            >
              Vendor Scenario
            </button>
            <button
              onClick={() => setMode('method')}
              className="flex-1 py-1.5"
              style={mode === 'method'
                ? { backgroundColor: 'var(--accent-subtle)', color: 'var(--accent)' }
                : { color: 'var(--text-tertiary)' }}
            >
              Generic Drill
            </button>
          </div>

          {mode === 'vendor' ? (
            <div className="space-y-1.5">
              <label className="text-[9px] text-[var(--text-tertiary)] uppercase tracking-widest font-mono">
                Vendor (interviews on its real open GAP/IN_REVIEW stages)
              </label>
              <select
                value={selectedVendor}
                onChange={(e) => setSelectedVendor(e.target.value)}
                className="w-full bg-[var(--layer-2)] border border-[var(--border-default)] rounded px-2 py-1.5 text-[11px]"
              >
                <option value="">Select a vendor…</option>
                {vendors?.map((v) => (
                  <option key={v.id} value={v.name}>{v.name}</option>
                ))}
              </select>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5">
                <label className="text-[9px] text-[var(--text-tertiary)] uppercase tracking-widest font-mono">Direction</label>
                <select value={direction} onChange={(e) => setDirection(e.target.value)}
                  className="w-full bg-[var(--layer-2)] border border-[var(--border-default)] rounded px-2 py-1.5 text-[11px]">
                  <option value="egress">Egress</option>
                  <option value="ingress">Ingress</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-[9px] text-[var(--text-tertiary)] uppercase tracking-widest font-mono">Method</label>
                <select value={transferMethod} onChange={(e) => setTransferMethod(e.target.value)}
                  className="w-full bg-[var(--layer-2)] border border-[var(--border-default)] rounded px-2 py-1.5 text-[11px]">
                  <option value="file">File</option>
                  <option value="api">API</option>
                </select>
              </div>
            </div>
          )}

          <button
            onClick={startSession}
            disabled={starting || (mode === 'vendor' && !selectedVendor)}
            className="w-full flex items-center justify-center gap-2 py-2 bg-[var(--accent-emphasis)] hover:bg-[var(--accent)] disabled:opacity-40 text-white rounded-md text-[10px] font-bold uppercase tracking-wider transition active:scale-[0.98]"
          >
            <RotateCcw size={12} /> {starting ? 'Starting…' : 'Start Session'}
          </button>
        </div>

        <div className="px-4 py-2 text-[9px] text-[var(--text-tertiary)] uppercase tracking-widest font-mono shrink-0">
          Session History
        </div>
        <div className="flex-1 overflow-y-auto min-h-0 scrollbar-thin scrollbar-thumb-[var(--layer-4)]">
          {history?.length === 0 && (
            <div className="p-4 text-[10px] text-[var(--text-tertiary)]">No sessions yet — start one above.</div>
          )}
          {history?.map((s) => (
            <button
              key={s.id}
              onClick={() => openSession(s)}
              className={`w-full text-left px-4 py-2.5 border-b border-[var(--border-subtle)] hover:bg-[var(--layer-2)] transition flex items-center justify-between ${activeSession?.id === s.id ? 'bg-[var(--layer-2)]' : ''}`}
            >
              <div className="min-w-0">
                <div className="text-[11px] text-[var(--text-primary)] truncate font-bold">
                  {s.scenario_vendor || s.scenario_method}
                </div>
                <div className="text-[9px] text-[var(--text-tertiary)] font-mono mt-0.5">
                  {new Date(s.started_at).toLocaleString()}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {s.overall_score !== null && s.overall_score !== undefined && (
                  <span className="text-[10px] font-bold font-mono text-[var(--accent)]">{s.overall_score}</span>
                )}
                <StatusBadge status={STATUS_BADGE_KEY[s.status] || 'PENDING'} />
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* RIGHT: active session */}
      <div className="flex-1 flex flex-col min-w-0 bg-[var(--layer-0)]">
        {!activeSession && (
          <div className="flex-1 flex items-center justify-center text-[var(--text-tertiary)] text-[11px] font-mono uppercase tracking-widest">
            Start a session to begin the mock interview
          </div>
        )}

        {activeSession && (
          <>
            <div className="h-14 border-b border-[var(--border-default)] flex items-center justify-between px-6 bg-[var(--layer-1)] shrink-0">
              <div>
                <h3 className="text-[var(--text-primary)] font-bold text-xs font-display tracking-wide">
                  {activeSession.scenario_vendor || activeSession.scenario_method}
                </h3>
                <div className="text-[9px] text-[var(--text-tertiary)] uppercase tracking-widest font-mono mt-0.5">
                  {answeredTurns.length}/{activeSession.total_turns} stages answered
                </div>
              </div>
              <div className="flex items-center gap-3">
                {activeSession.overall_score !== null && activeSession.overall_score !== undefined && (
                  <span className="text-sm font-bold font-mono text-[var(--accent)]">{activeSession.overall_score}/100</span>
                )}
                <StatusBadge status={STATUS_BADGE_KEY[activeSession.status] || 'PENDING'} variant="large" />
              </div>
            </div>

            {startError && (
              <div className="px-6 py-2 bg-[var(--danger-subtle)] border-b border-[var(--danger)] text-[10px] text-[var(--danger)] font-mono flex items-center gap-2">
                <AlertTriangle size={12} /> {startError}
              </div>
            )}

            <div className="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-thin scrollbar-thumb-[var(--layer-4)]">
              {justGraded && <GradedTurnCard turn={justGraded} />}

              {justGraded && currentTurn && (
                <button
                  onClick={continueSession}
                  className="w-full py-2 bg-[var(--layer-2)] hover:bg-[var(--layer-3)] border border-[var(--border-default)] rounded-md text-[10px] font-bold uppercase tracking-wider transition"
                >
                  Next Question →
                </button>
              )}

              {!justGraded && currentTurn && (
                <div className="rounded border border-[var(--border-default)] bg-[var(--layer-1)] p-4 space-y-3">
                  <div className="flex items-center gap-2 text-[10px] font-bold text-[var(--text-tertiary)] uppercase tracking-widest">
                    <Clock size={11} /> Stage {currentTurn.turn_number} · {currentTurn.question_category}
                  </div>
                  <div className="text-[13px] text-[var(--text-primary)] leading-relaxed">
                    {currentTurn.question_text}
                  </div>
                  <textarea
                    value={responseText}
                    onChange={(e) => setResponseText(e.target.value)}
                    placeholder="Answer as you would in a live interview…"
                    rows={6}
                    className="w-full bg-[var(--layer-0)] border border-[var(--border-default)] rounded px-3 py-2 text-[12px] resize-none focus:border-[var(--accent-glow)] outline-none transition-colors"
                  />
                  <button
                    onClick={submitResponse}
                    disabled={submitting || !responseText.trim()}
                    className="flex items-center gap-2 px-4 py-1.5 bg-[var(--accent-emphasis)] hover:bg-[var(--accent)] disabled:opacity-40 text-white rounded-md text-[10px] font-bold uppercase tracking-wider transition active:scale-95"
                  >
                    <Send size={12} /> {submitting ? 'Grading…' : 'Submit Answer'}
                  </button>
                </div>
              )}

              {!currentTurn && (
                <div className="rounded border border-[var(--border-default)] bg-[var(--layer-1)] p-4 text-center space-y-2">
                  <div className="text-[11px] font-bold uppercase tracking-widest text-[var(--success)]">
                    Session Complete
                  </div>
                  {activeSession.overall_score !== null && activeSession.overall_score !== undefined ? (
                    <div className="text-2xl font-bold font-mono text-[var(--accent)]">{activeSession.overall_score}/100</div>
                  ) : (
                    <div className="text-[10px] text-[var(--text-tertiary)]">No turns were successfully graded.</div>
                  )}
                </div>
              )}

              {!justGraded && answeredTurns.slice().reverse().map((t) => (
                <GradedTurnCard key={t.id} turn={t} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
