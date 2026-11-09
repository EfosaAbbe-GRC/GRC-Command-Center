import React, { useState } from 'react';
import { ShieldAlert, Plus, X, Download, Grid3x3, History, CheckCircle2, Lock, Unlock, AlertTriangle } from 'lucide-react';
import { useApiData } from '../hooks/useApiData';
import { api } from '../lib/api';
import { useAuth } from '../contexts/useAuth';
import { useWebSocket } from '../hooks/useWebSocket';

// Risk register (linked data model, phase 1). Scores, bands, status and review dates all come
// from the backend; this screen never computes or sends a score.

const BAND_STYLE = {
  critical: { color: 'var(--danger)', bg: 'var(--danger-subtle)' },
  high: { color: 'var(--warning)', bg: 'var(--warning-subtle)' },
  medium: { color: 'var(--accent)', bg: 'var(--accent-subtle)' },
  low: { color: 'var(--success)', bg: 'var(--success-subtle)' },
};
const CATEGORIES = ['information_security', 'operational', 'compliance', 'third_party', 'privacy', 'strategic'];
const ENTITY_TYPES = ['organisation', 'business_unit', 'process', 'application', 'asset', 'vendor'];
const TREATMENTS = ['undecided', 'mitigate', 'transfer', 'avoid'];
const STATUSES = ['identified', 'assessed', 'treatment_in_progress', 'accepted', 'closed'];
const RATING_LABEL = { 1: '1 Rare / Minimal', 2: '2 Unlikely / Minor', 3: '3 Possible / Moderate', 4: '4 Likely / Major', 5: '5 Almost certain / Severe' };
const label = (s) => (s || '').replace(/_/g, ' ');

const BandChip = ({ band, score }) => {
  if (!band) return <span className="text-[10px] font-mono text-[var(--text-tertiary)]">not rated</span>;
  const s = BAND_STYLE[band];
  return (
    <span className="px-1.5 py-0.5 rounded-sm text-[9px] font-bold uppercase font-mono border"
      style={{ color: s.color, backgroundColor: s.bg, borderColor: s.color }}>
      {band}{score != null ? ` ${score}` : ''}
    </span>
  );
};

const Field = ({ label: l, children, hint }) => (
  <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
    {l}
    {children}
    {hint && <span className="normal-case font-normal tracking-normal text-[var(--text-tertiary)]">{hint}</span>}
  </label>
);
const inputCls = 'bg-[var(--layer-2)] border border-[var(--border-default)] rounded px-2 py-1.5 text-xs text-[var(--text-primary)] normal-case font-normal tracking-normal';

const RatingSelect = ({ value, onChange, allowEmpty }) => (
  <select className={inputCls} value={value ?? ''} onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}>
    {allowEmpty && <option value="">not rated</option>}
    {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{RATING_LABEL[n]}</option>)}
  </select>
);

const EMPTY_RISK = {
  title: '', statement: '', category: 'information_security', entity_id: '', owner: '',
  inherent_likelihood: 3, inherent_impact: 3, existing_controls: '', residual_likelihood: null, residual_impact: null,
};

export default function RiskRegisterTerminal() {
  const { user } = useAuth();
  const role = user?.role;
  const canEdit = role === 'analyst' || role === 'admin';
  const canApprove = role === 'admin';

  const [filters, setFilters] = useState({ status: '', band: '', overdue: '' });
  const query = new URLSearchParams(Object.entries(filters).filter(([, v]) => v !== '')).toString();
  const { data: risks, loading, refresh } = useApiData(`/risks${query ? `?${query}` : ''}`);
  const { data: entities, refresh: refreshEntities } = useApiData('/entities');
  const [basis, setBasis] = useState('residual');
  const { data: heat, refresh: refreshHeat } = useApiData(`/risks/heatmap?basis=${basis}`);

  const [selected, setSelected] = useState(null);
  const [mode, setMode] = useState(null);          // 'create' | 'edit' | 'entity' | 'propose' | 'accept'
  const [form, setForm] = useState(EMPTY_RISK);
  const [error, setError] = useState(null);

  const openRisk = async (id) => {
    setError(null);
    setSelected(await api.get(`/risks/${id}`));
  };

  useWebSocket(api.getAccessToken(), (message) => {
    if (message.type === 'RISK_REGISTER_CHANGED') {
      refresh(); refreshEntities(); refreshHeat();
      if (selected) openRisk(selected.id).catch(() => {});
    }
  });

  const run = async (fn) => {
    setError(null);
    try {
      const result = await fn();
      setMode(null);
      refresh(); refreshHeat();
      if (result?.id) await openRisk(result.id);
      return result;
    } catch (err) {
      setError(err.message || 'Action failed');
    }
  };

  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v?.target ? v.target.value : v }));

  const startCreate = () => { setForm({ ...EMPTY_RISK, entity_id: entities?.[0]?.id || '' }); setMode('create'); setError(null); };
  const startEdit = () => {
    const r = selected;
    setForm({
      title: r.title, statement: r.statement, category: r.category, entity_id: r.entity_id, owner: r.owner,
      inherent_likelihood: r.inherent_likelihood, inherent_impact: r.inherent_impact,
      existing_controls: r.existing_controls || '', residual_likelihood: r.residual_likelihood,
      residual_impact: r.residual_impact, treatment: r.treatment === 'accept' ? 'undecided' : r.treatment,
      treatment_plan: r.treatment_plan || '', target_date: r.target_date || '', reason: '',
    });
    setMode('edit'); setError(null);
  };

  const submitCreate = () => run(() => {
    const body = { ...form };
    if (!body.existing_controls) delete body.existing_controls;
    if (body.residual_likelihood == null || body.residual_impact == null) {
      delete body.residual_likelihood; delete body.residual_impact;
    }
    return api.post('/risks', body);
  });

  const submitEdit = () => run(() => {
    const r = selected;
    const body = { version: r.version, reason: form.reason };
    const keys = ['title', 'statement', 'category', 'entity_id', 'owner', 'inherent_likelihood', 'inherent_impact',
      'existing_controls', 'residual_likelihood', 'residual_impact', 'treatment', 'treatment_plan', 'target_date'];
    keys.forEach((k) => {
      const now = form[k] === '' ? null : form[k];
      const was = k === 'treatment' && r[k] === 'accept' ? 'undecided' : r[k];
      if (now !== (was ?? null)) body[k] = now;
    });
    return api.patch(`/risks/${r.id}`, body);
  });

  const submitEntity = () => run(async () => {
    const body = { name: form.e_name, entity_type: form.e_type || 'process' };
    if (form.e_owner) body.owner = form.e_owner;
    await api.post('/entities', body);
    refreshEntities();
  });

  const submitPropose = () => run(() => api.post(`/risks/${selected.id}/propose-acceptance`,
    { version: selected.version, days: Number(form.days), reason: form.reason }));
  const submitAccept = () => run(() => api.post(`/risks/${selected.id}/accept`,
    { version: selected.version, accepted_by_owner: form.owner_name, reason: form.reason }));
  const closeOrReopen = (action) => {
    const reason = window.prompt(action === 'close' ? 'Why is this risk being closed? (required)' : 'Why is this risk being reopened? (required)');
    if (!reason || reason.trim().length < 3) return;
    run(() => api.post(`/risks/${selected.id}/${action}`, { version: selected.version, reason: reason.trim() }));
  };

  const counts = (risks || []).reduce((acc, r) => {
    if (r.status !== 'closed') acc[r.residual_band || r.inherent_band] = (acc[r.residual_band || r.inherent_band] || 0) + 1;
    if (r.overdue) acc.overdue = (acc.overdue || 0) + 1;
    return acc;
  }, {});

  const modal = (title, body, onSubmit, submitLabel) => (
    <div className="absolute inset-0 bg-black/50 flex items-center justify-center z-20">
      <div className="w-[560px] max-h-[90%] overflow-y-auto bg-[var(--layer-1)] border border-[var(--border-emphasis)] rounded p-5 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h3 className="text-[11px] font-bold tracking-widest uppercase">{title}</h3>
          <button onClick={() => setMode(null)} aria-label="Close"><X size={14} /></button>
        </div>
        {body}
        {error && <div className="text-[11px] text-[var(--danger)]">{error}</div>}
        <div className="flex justify-end gap-2">
          <button onClick={() => setMode(null)} className="px-3 py-1.5 text-[10px] font-bold uppercase border border-[var(--border-default)] rounded">Cancel</button>
          <button onClick={onSubmit} className="px-3 py-1.5 text-[10px] font-bold uppercase rounded bg-[var(--accent)] text-white">{submitLabel}</button>
        </div>
      </div>
    </div>
  );

  const riskForm = (isEdit) => (
    <div className="grid grid-cols-2 gap-3">
      <div className="col-span-2"><Field label="Title"><input className={inputCls} maxLength={200} value={form.title} onChange={set('title')} /></Field></div>
      <div className="col-span-2"><Field label="Risk statement" hint="Cause → event → consequence. e.g. Because backups are untested, a ransomware attack could cause prolonged data loss.">
        <textarea className={inputCls} rows={3} maxLength={4000} value={form.statement} onChange={set('statement')} /></Field></div>
      <Field label="Category"><select className={inputCls} value={form.category} onChange={set('category')}>{CATEGORIES.map((c) => <option key={c} value={c}>{label(c)}</option>)}</select></Field>
      <Field label="Affects (entity)">
        <select className={inputCls} value={form.entity_id} onChange={set('entity_id')}>
          <option value="">choose…</option>
          {(entities || []).map((e) => <option key={e.id} value={e.id}>{e.name} ({label(e.entity_type)})</option>)}
        </select>
      </Field>
      <div className="col-span-2"><Field label="Risk owner" hint="The accountable business person or role. Only the owner can accept the residual risk."><input className={inputCls} maxLength={200} value={form.owner} onChange={set('owner')} /></Field></div>
      <Field label="Inherent likelihood"><RatingSelect value={form.inherent_likelihood} onChange={set('inherent_likelihood')} /></Field>
      <Field label="Inherent impact"><RatingSelect value={form.inherent_impact} onChange={set('inherent_impact')} /></Field>
      <div className="col-span-2"><Field label="Existing controls"><textarea className={inputCls} rows={2} maxLength={4000} value={form.existing_controls} onChange={set('existing_controls')} /></Field></div>
      <Field label="Residual likelihood"><RatingSelect allowEmpty value={form.residual_likelihood} onChange={set('residual_likelihood')} /></Field>
      <Field label="Residual impact"><RatingSelect allowEmpty value={form.residual_impact} onChange={set('residual_impact')} /></Field>
      {isEdit && (<>
        <Field label="Treatment" hint="To accept a risk, use Propose acceptance.">
          <select className={inputCls} value={form.treatment} onChange={set('treatment')}>{TREATMENTS.map((t) => <option key={t} value={t}>{label(t)}</option>)}</select>
        </Field>
        <Field label="Target date"><input type="date" className={inputCls} value={form.target_date || ''} onChange={set('target_date')} /></Field>
        <div className="col-span-2"><Field label="Treatment plan"><textarea className={inputCls} rows={2} maxLength={4000} value={form.treatment_plan} onChange={set('treatment_plan')} /></Field></div>
        <div className="col-span-2"><Field label="Reason for this change (kept in the history)"><input className={inputCls} maxLength={1000} value={form.reason} onChange={set('reason')} /></Field></div>
      </>)}
    </div>
  );

  return (
    <div className="flex-1 flex bg-[var(--layer-0)] text-[var(--text-primary)] overflow-hidden h-full relative">
      {/* LEFT: register */}
      <div className="flex-1 flex flex-col min-h-0 min-w-0 border-r border-[var(--border-default)]">
        <div className="h-14 border-b border-[var(--border-default)] flex items-center justify-between px-4 shrink-0 bg-[var(--layer-1)]">
          <div className="flex items-center gap-3">
            <ShieldAlert size={16} className="text-[var(--accent)]" />
            <h2 className="text-[11px] font-bold tracking-widest uppercase font-display">Risk Register</h2>
            <div className="flex items-center gap-1.5">
              {['critical', 'high', 'medium', 'low'].map((b) => counts[b] ? <BandChip key={b} band={b} score={counts[b]} /> : null)}
              {counts.overdue ? <span className="text-[9px] font-mono font-bold text-[var(--danger)] uppercase">{counts.overdue} overdue</span> : null}
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            {canApprove && (
              <button onClick={() => api.downloadFile('/risks/export', 'risk_register.csv').catch((err) => setError(err.message || 'Export failed'))} title="Export the risk register (CSV)"
                className="p-1.5 bg-[var(--layer-2)] hover:bg-[var(--layer-3)] border border-[var(--border-default)] rounded"><Download size={14} /></button>
            )}
            {canEdit && (<>
              <button onClick={() => { setForm({ e_name: '', e_type: 'process', e_owner: '' }); setMode('entity'); setError(null); }}
                className="px-2 py-1.5 text-[10px] font-bold uppercase bg-[var(--layer-2)] border border-[var(--border-default)] rounded">+ Entity</button>
              <button onClick={startCreate} disabled={!entities?.length} title={entities?.length ? 'Add a risk' : 'Add an entity first'}
                className="flex items-center gap-1 px-2 py-1.5 text-[10px] font-bold uppercase rounded bg-[var(--accent)] text-white disabled:opacity-40"><Plus size={12} /> Risk</button>
            </>)}
          </div>
        </div>

        <div className="flex items-center gap-2 px-4 py-2 border-b border-[var(--border-default)] text-[10px]">
          <select className={inputCls} value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
            <option value="">all statuses</option>{STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}
          </select>
          <select className={inputCls} value={filters.band} onChange={(e) => setFilters({ ...filters, band: e.target.value })}>
            <option value="">all bands</option>{['critical', 'high', 'medium', 'low'].map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
          <select className={inputCls} value={filters.overdue} onChange={(e) => setFilters({ ...filters, overdue: e.target.value })}>
            <option value="">any review date</option><option value="true">overdue only</option>
          </select>
        </div>

        <div className="flex-1 overflow-auto">
          {loading && <div className="p-4 text-xs text-[var(--text-tertiary)]">Loading…</div>}
          {!loading && !risks?.length && (
            <div className="p-8 text-center text-xs text-[var(--text-secondary)] flex flex-col gap-2 items-center">
              <ShieldAlert size={22} className="text-[var(--text-tertiary)]" />
              <div>No risks recorded yet.</div>
              <div className="text-[var(--text-tertiary)] max-w-sm">Add the process, application or vendor a risk is about with <b>+ Entity</b>, then record the risk with <b>+ Risk</b>. Every change is kept in a tamper-evident history.</div>
            </div>
          )}
          {!!risks?.length && (
            <table className="w-full text-xs">
              <thead className="text-[9px] uppercase tracking-wider text-[var(--text-tertiary)] sticky top-0 bg-[var(--layer-1)]">
                <tr>{['Ref', 'Risk', 'Entity', 'Owner', 'Inherent', 'Residual', 'Status', 'Review due'].map((h) => <th key={h} className="text-left px-3 py-2 font-bold">{h}</th>)}</tr>
              </thead>
              <tbody>
                {risks.map((r) => (
                  <tr key={r.id} onClick={() => openRisk(r.id)}
                    className={`border-t border-[var(--border-subtle)] cursor-pointer hover:bg-[var(--layer-2)] ${selected?.id === r.id ? 'bg-[var(--layer-2)]' : ''}`}>
                    <td className="px-3 py-2 font-mono text-[var(--text-tertiary)]">{r.ref}</td>
                    <td className="px-3 py-2 max-w-[260px] truncate" title={r.title}>{r.title}</td>
                    <td className="px-3 py-2 text-[var(--text-secondary)]">{r.entity_name}</td>
                    <td className="px-3 py-2 text-[var(--text-secondary)]">{r.owner}</td>
                    <td className="px-3 py-2"><BandChip band={r.inherent_band} score={r.inherent_score} /></td>
                    <td className="px-3 py-2"><BandChip band={r.residual_band} score={r.residual_score} /></td>
                    <td className="px-3 py-2 text-[10px] uppercase font-mono">{label(r.status)}</td>
                    <td className={`px-3 py-2 font-mono text-[10px] ${r.overdue ? 'text-[var(--danger)] font-bold' : 'text-[var(--text-secondary)]'}`}>{r.review_due}{r.overdue ? ' !' : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* RIGHT: detail or heat map */}
      <div className="w-[420px] shrink-0 flex flex-col min-h-0 bg-[var(--layer-1)] overflow-y-auto">
        {!selected && (
          <div className="p-4 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest"><Grid3x3 size={14} /> Heat map</div>
              <div className="flex text-[9px] font-bold uppercase border border-[var(--border-default)] rounded overflow-hidden">
                {['inherent', 'residual'].map((b) => (
                  <button key={b} onClick={() => setBasis(b)} className={`px-2 py-1 ${basis === b ? 'bg-[var(--accent)] text-white' : ''}`}>{b}</button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-[20px_repeat(5,1fr)] gap-1 text-[10px] font-mono">
              {[5, 4, 3, 2, 1].map((l) => (
                <React.Fragment key={l}>
                  <div className="flex items-center justify-center text-[var(--text-tertiary)]">{l}</div>
                  {[1, 2, 3, 4, 5].map((i) => {
                    const n = heat?.grid?.[l - 1]?.[i - 1] || 0;
                    const s = BAND_STYLE[l * i <= 4 ? 'low' : l * i <= 9 ? 'medium' : l * i <= 16 ? 'high' : 'critical'];
                    return (
                      <div key={i} className="aspect-square rounded-sm flex items-center justify-center font-bold border"
                        style={{ backgroundColor: s.bg, borderColor: n ? s.color : 'transparent', color: n ? s.color : 'var(--text-tertiary)' }}>
                        {n || ''}
                      </div>
                    );
                  })}
                </React.Fragment>
              ))}
              <div />
              {[1, 2, 3, 4, 5].map((i) => <div key={i} className="text-center text-[var(--text-tertiary)]">{i}</div>)}
            </div>
            <div className="text-[10px] text-[var(--text-tertiary)]">Rows: likelihood. Columns: impact. Open risks only. Select a risk to see its details and history.</div>
          </div>
        )}

        {selected && (
          <div className="p-4 flex flex-col gap-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-[10px] font-mono text-[var(--text-tertiary)]">{selected.ref} · {label(selected.category)} · {selected.entity_name}</div>
                <h3 className="text-sm font-bold mt-0.5">{selected.title}</h3>
              </div>
              <button onClick={() => setSelected(null)} aria-label="Close details"><X size={14} /></button>
            </div>
            <p className="text-xs text-[var(--text-secondary)] whitespace-pre-wrap">{selected.statement}</p>

            <div className="grid grid-cols-2 gap-2 text-[10px]">
              <div className="p-2 border border-[var(--border-default)] rounded"><div className="uppercase text-[var(--text-tertiary)] font-bold mb-1">Inherent</div>
                <BandChip band={selected.inherent_band} score={selected.inherent_score} /><div className="mt-1 font-mono">L{selected.inherent_likelihood} × I{selected.inherent_impact}</div></div>
              <div className="p-2 border border-[var(--border-default)] rounded"><div className="uppercase text-[var(--text-tertiary)] font-bold mb-1">Residual</div>
                <BandChip band={selected.residual_band} score={selected.residual_score} />{selected.residual_likelihood && <div className="mt-1 font-mono">L{selected.residual_likelihood} × I{selected.residual_impact}</div>}</div>
            </div>

            <dl className="grid grid-cols-[110px_1fr] gap-x-2 gap-y-1 text-[11px]">
              <dt className="text-[var(--text-tertiary)]">Owner</dt><dd>{selected.owner}</dd>
              <dt className="text-[var(--text-tertiary)]">Status</dt><dd className="uppercase font-mono text-[10px]">{label(selected.status)}</dd>
              <dt className="text-[var(--text-tertiary)]">Treatment</dt><dd>{label(selected.treatment)}{selected.target_date ? ` · by ${selected.target_date}` : ''}</dd>
              {selected.treatment_plan && (<><dt className="text-[var(--text-tertiary)]">Plan</dt><dd className="whitespace-pre-wrap">{selected.treatment_plan}</dd></>)}
              {selected.existing_controls && (<><dt className="text-[var(--text-tertiary)]">Controls</dt><dd className="whitespace-pre-wrap">{selected.existing_controls}</dd></>)}
              <dt className="text-[var(--text-tertiary)]">Review due</dt><dd className={selected.overdue ? 'text-[var(--danger)] font-bold' : ''}>{selected.review_due}{selected.overdue ? ' (overdue)' : ''}</dd>
              {selected.acceptance_expires_at && (<><dt className="text-[var(--text-tertiary)]">Accepted by</dt>
                <dd>{selected.accepted_by_owner} until {selected.acceptance_expires_at.slice(0, 10)}{selected.acceptance_expired ? ' (EXPIRED)' : ''}</dd></>)}
              {selected.pending_acceptance_by && (<><dt className="text-[var(--text-tertiary)]">Pending</dt>
                <dd className="text-[var(--warning)]">Acceptance for {selected.pending_acceptance_days} days proposed by {selected.pending_acceptance_by}; awaiting the owner's decision</dd></>)}
            </dl>

            {error && !mode && <div className="text-[11px] text-[var(--danger)] flex gap-1 items-start"><AlertTriangle size={12} className="mt-0.5" />{error}</div>}

            {canEdit && (
              <div className="flex flex-wrap gap-1.5">
                {selected.status !== 'closed' && <button onClick={startEdit} className="px-2 py-1 text-[10px] font-bold uppercase border border-[var(--border-default)] rounded">Edit / assess</button>}
                {selected.status !== 'closed' && selected.residual_band && !selected.pending_acceptance_by &&
                  <button onClick={() => { setForm({ days: selected.residual_band === 'high' ? 180 : 365, reason: '' }); setMode('propose'); setError(null); }}
                    className="px-2 py-1 text-[10px] font-bold uppercase border border-[var(--border-default)] rounded">Propose acceptance</button>}
                {canApprove && selected.pending_acceptance_by && selected.pending_acceptance_by !== user?.username &&
                  <button onClick={() => { setForm({ owner_name: '', reason: '' }); setMode('accept'); setError(null); }}
                    className="flex items-center gap-1 px-2 py-1 text-[10px] font-bold uppercase rounded bg-[var(--accent)] text-white"><CheckCircle2 size={11} /> Record owner's acceptance</button>}
                {selected.status !== 'closed'
                  ? <button onClick={() => closeOrReopen('close')} className="flex items-center gap-1 px-2 py-1 text-[10px] font-bold uppercase border border-[var(--border-default)] rounded"><Lock size={11} /> Close</button>
                  : <button onClick={() => closeOrReopen('reopen')} className="flex items-center gap-1 px-2 py-1 text-[10px] font-bold uppercase border border-[var(--border-default)] rounded"><Unlock size={11} /> Reopen</button>}
              </div>
            )}

            <div className="mt-2">
              <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-[var(--text-secondary)] mb-2"><History size={12} /> History (tamper-evident)</div>
              <ol className="flex flex-col gap-2">
                {[...(selected.events || [])].reverse().map((e) => (
                  <li key={e.id} className="border-l-2 border-[var(--border-emphasis)] pl-2 text-[11px]">
                    <div className="font-mono text-[10px] text-[var(--text-tertiary)]">{e.at?.slice(0, 16).replace('T', ' ')} UTC · {e.actor}</div>
                    <div className="font-bold text-[10px] uppercase">{label(e.event_type)}{e.accepted_by_owner ? ` by owner ${e.accepted_by_owner}` : ''}</div>
                    {e.reason && <div className="text-[var(--text-secondary)]">“{e.reason}”</div>}
                    {e.event_type !== 'CREATED' && Object.entries(e.changes || {}).map(([k, v]) => (
                      <div key={k} className="font-mono text-[10px] text-[var(--text-tertiary)] truncate" title={`${k}: ${v.before} → ${v.after}`}>{label(k)}: {String(v.before ?? '—')} → {String(v.after ?? '—')}</div>
                    ))}
                  </li>
                ))}
              </ol>
            </div>
          </div>
        )}
      </div>

      {mode === 'create' && modal('New risk', riskForm(false), submitCreate, 'Add risk')}
      {mode === 'edit' && modal(`Edit ${selected?.ref}`, riskForm(true), submitEdit, 'Save change')}
      {mode === 'entity' && modal('New entity', (
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2"><Field label="Name" hint="The process, application, asset or business unit a risk is about."><input className={inputCls} maxLength={200} value={form.e_name} onChange={set('e_name')} /></Field></div>
          <Field label="Type"><select className={inputCls} value={form.e_type} onChange={set('e_type')}>{ENTITY_TYPES.filter((t) => t !== 'vendor').map((t) => <option key={t} value={t}>{label(t)}</option>)}</select></Field>
          <Field label="Owner (optional)"><input className={inputCls} maxLength={200} value={form.e_owner} onChange={set('e_owner')} /></Field>
        </div>
      ), submitEntity, 'Add entity')}
      {mode === 'propose' && modal(`Propose accepting ${selected?.ref}`, (
        <div className="flex flex-col gap-3 text-xs">
          <p className="text-[var(--text-secondary)]">Residual risk is <b>{selected?.residual_band}</b>. Low and medium risks can be accepted for up to 365 days, high for up to 180, critical never. An admin records the owner's decision afterwards; it can't be the person proposing.</p>
          <Field label="Days"><input type="number" min={1} max={365} className={inputCls} value={form.days} onChange={set('days')} /></Field>
          <Field label="Why accepting is reasonable"><input className={inputCls} maxLength={1000} value={form.reason} onChange={set('reason')} /></Field>
        </div>
      ), submitPropose, 'Propose')}
      {mode === 'accept' && modal(`Record the owner's acceptance of ${selected?.ref}`, (
        <div className="flex flex-col gap-3 text-xs">
          <p className="text-[var(--text-secondary)]">ISO/IEC 27001 6.1.3 f: the <b>risk owner</b> accepts residual risk. Record it only once {selected?.owner} has agreed, and say how (meeting, signed email).</p>
          <Field label="Owner's name, as on the risk"><input className={inputCls} maxLength={200} value={form.owner_name} onChange={set('owner_name')} /></Field>
          <Field label="How the owner accepted"><input className={inputCls} maxLength={1000} value={form.reason} onChange={set('reason')} /></Field>
        </div>
      ), submitAccept, 'Record acceptance')}
    </div>
  );
}
