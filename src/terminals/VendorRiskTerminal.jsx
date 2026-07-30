import React, { useState } from 'react';
import { Shield, AlertTriangle, CheckCircle2, Clock, ChevronRight, Plus, X, ShieldCheck } from 'lucide-react';
import { useApiData } from '../hooks/useApiData';
import { StatusBadge } from '../components/StatusBadge';
import { api } from '../lib/api';
import { useAuth } from '../contexts/useAuth';

const TIER_STYLE = {
  critical: { color: 'var(--danger)', bg: 'var(--danger-subtle)' },
  high:     { color: 'var(--warning)', bg: 'var(--warning-subtle)' },
  medium:   { color: 'var(--accent)', bg: 'var(--accent-subtle)' },
  low:      { color: 'var(--success)', bg: 'var(--success-subtle)' },
  unscored: { color: 'var(--text-tertiary)', bg: 'var(--layer-2)' },
};

const STAGE_ICON = {
  pass: <CheckCircle2 size={14} style={{ color: 'var(--success)' }} />,
  gap: <AlertTriangle size={14} style={{ color: 'var(--danger)' }} />,
  in_review: <Clock size={14} style={{ color: 'var(--warning)' }} />,
  not_started: <div className="w-3.5 h-3.5 rounded-full border" style={{ borderColor: 'var(--border-emphasis)' }} />,
};

// Map backend integration status -> StatusBadge's uppercase config keys.
const STATUS_BADGE_KEY = {
  approved: 'COMPLETED',
  approved_with_exceptions: 'PARTIAL',
  under_assessment: 'REVIEW',
  blocked: 'FAILED',
  draft: 'QUEUED',
};

const EMPTY_FORM = {
  vendor_id: '', name: '', direction: 'egress', transfer_method: 'file',
  data_classification: 'PII', volume_per_transfer: 0, involves_regulated_data: 'none',
};

export default function VendorRiskTerminal() {
  const { user } = useAuth();
  const role = user?.role;
  const canAssess = role === 'analyst' || role === 'admin';
  const canSignoff = role === 'admin';

  const { data: integrations, loading, refresh } = useApiData('/tprm/integrations');
  const { data: vendors } = useApiData('/tprm/vendors');

  const [selected, setSelected] = useState(null);
  const [summary, setSummary] = useState(null);
  const [stages, setStages] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [actionError, setActionError] = useState(null);

  const openIntegration = async (integ) => {
    setSelected(integ);
    setActionError(null);
    const [s, st] = await Promise.all([
      api.get(`/tprm/integrations/${integ.id}/summary`),
      api.get(`/tprm/integrations/${integ.id}/stages`),
    ]);
    setSummary(s);
    setStages(st);
  };

  const updateStage = async (stageId, status) => {
    await api.post(`/tprm/integrations/${selected.id}/stages/${stageId}`, { status });
    openIntegration(selected);
  };

  const approve = async () => {
    setActionError(null);
    try {
      await api.post(`/tprm/integrations/${selected.id}/approve`, {});
      await openIntegration(selected);
      refresh();
    } catch (err) {
      setActionError(err.message || 'Approval blocked');
    }
  };

  return (
    <div className="flex-1 flex bg-[var(--layer-0)] text-[var(--text-primary)] overflow-hidden h-full">
      {/* LEFT: integration list */}
      <div className="w-[380px] border-r border-[var(--border-default)] flex flex-col min-h-0 bg-[var(--layer-1)]">
        <div className="h-14 border-b border-[var(--border-default)] flex items-center justify-between px-4 shrink-0">
          <div className="flex items-center gap-2">
            <Shield size={16} className="text-[var(--accent)]" />
            <h2 className="text-[11px] font-bold tracking-widest uppercase font-display">Vendor Risk Assessments</h2>
          </div>
          {canAssess && (
            <button
              onClick={() => { setShowCreate(true); setActionError(null); }}
              className="p-1.5 bg-[var(--layer-2)] hover:bg-[var(--layer-3)] border border-[var(--border-default)] rounded transition"
              title="New Integration"
            >
              <Plus size={14} />
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto min-h-0 scrollbar-thin scrollbar-thumb-[var(--layer-4)]">
          {loading && <div className="p-4 text-[10px] text-[var(--text-tertiary)] font-mono uppercase tracking-widest animate-pulse">Loading integrations…</div>}
          {!loading && integrations?.length === 0 && (
            <div className="p-4 text-[10px] text-[var(--text-tertiary)]">No integrations tracked yet. Add one to begin an assessment.</div>
          )}
          {integrations?.map((integ) => {
            const tier = TIER_STYLE[integ.computed_risk_tier] || TIER_STYLE.unscored;
            return (
              <button
                key={integ.id}
                onClick={() => openIntegration(integ)}
                className={`w-full text-left px-4 py-3 border-b border-[var(--border-subtle)] hover:bg-[var(--layer-2)] transition flex items-center justify-between ${selected?.id === integ.id ? 'bg-[var(--layer-2)]' : ''}`}
              >
                <div className="min-w-0">
                  <div className="text-[12px] text-[var(--text-primary)] truncate font-bold">{integ.name}</div>
                  <div className="text-[9px] text-[var(--text-tertiary)] uppercase tracking-widest mt-0.5 font-mono">
                    {integ.direction} · {integ.transfer_method}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="px-2 py-0.5 rounded-sm text-[9px] font-bold uppercase font-mono border"
                    style={{ color: tier.color, backgroundColor: tier.bg, borderColor: tier.color }}>
                    {integ.computed_risk_tier}
                  </span>
                  <ChevronRight size={14} className="text-[var(--text-tertiary)]" />
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* RIGHT: detail */}
      <div className="flex-1 flex flex-col min-w-0 bg-[var(--layer-0)]">
        {!selected && (
          <div className="flex-1 flex items-center justify-center text-[var(--text-tertiary)] text-[11px] font-mono uppercase tracking-widest">
            Select an integration to review its assessment
          </div>
        )}

        {selected && summary && (
          <>
            <div className="h-14 border-b border-[var(--border-default)] flex items-center justify-between px-6 bg-[var(--layer-1)] shrink-0">
              <div>
                <h3 className="text-[var(--text-primary)] font-bold text-xs font-display tracking-wide">{selected.name}</h3>
                <div className="text-[9px] text-[var(--text-tertiary)] uppercase tracking-widest font-mono mt-0.5">
                  {summary.completed_stages}/{summary.total_stages} stages reviewed
                  {summary.open_gaps > 0 && (
                    <span className="text-[var(--danger)] ml-2">· {summary.open_gaps} open gap(s)</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge status={STATUS_BADGE_KEY[summary.status] || 'QUEUED'} variant="large" />
                {canSignoff && (
                  <button
                    onClick={approve}
                    className="flex items-center gap-2 px-4 py-1.5 bg-[var(--accent-emphasis)] hover:bg-[var(--accent)] text-white rounded-md text-[10px] font-bold uppercase tracking-wider transition active:scale-95"
                  >
                    <ShieldCheck size={13} strokeWidth={2.5} /> Approve
                  </button>
                )}
              </div>
            </div>

            {actionError && (
              <div className="px-6 py-2 bg-[var(--danger-subtle)] border-b border-[var(--danger)] text-[10px] text-[var(--danger)] font-mono flex items-center gap-2">
                <AlertTriangle size={12} /> {actionError}
              </div>
            )}

            <div className="flex-1 overflow-y-auto p-6 space-y-1 scrollbar-thin scrollbar-thumb-[var(--layer-4)]">
              {stages.map((stage) => (
                <div key={stage.stage_id}
                  className="flex items-center gap-3 px-3 py-2 rounded border border-[var(--border-default)] bg-[var(--layer-1)]">
                  <div className="w-6 text-center text-[10px] text-[var(--text-tertiary)] font-mono">{stage.stage_number}</div>
                  {STAGE_ICON[stage.status]}
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] text-[var(--text-secondary)] truncate">{stage.title}</div>
                  </div>
                  {canAssess && (
                    <div className="flex gap-1">
                      {['pass', 'gap', 'in_review'].map((s) => (
                        <button key={s} onClick={() => updateStage(stage.stage_id, s)}
                          className={`px-2 py-0.5 rounded-sm text-[9px] uppercase font-bold font-mono border transition ${stage.status === s ? 'border-[var(--accent)] text-[var(--accent)] bg-[var(--accent-subtle)]' : 'border-[var(--border-default)] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'}`}>
                          {s === 'in_review' ? 'review' : s}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {showCreate && (
        <CreateIntegrationModal
          vendors={vendors || []}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); refresh(); }}
        />
      )}
    </div>
  );
}

function CreateIntegrationModal({ vendors, onClose, onCreated }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [newVendor, setNewVendor] = useState(vendors.length === 0);
  const [vendorName, setVendorName] = useState('');
  const [vendorEmail, setVendorEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState(null);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async () => {
    setErr(null);
    setSubmitting(true);
    try {
      let vendorId = form.vendor_id;
      if (newVendor) {
        if (!vendorName.trim()) throw new Error('Vendor name is required');
        const v = await api.post('/tprm/vendors', { name: vendorName, contact_email: vendorEmail || null });
        vendorId = v.id;
      }
      if (!vendorId) throw new Error('Select or create a vendor');
      if (!form.name.trim()) throw new Error('Integration name is required');
      await api.post('/tprm/integrations', {
        vendor_id: vendorId,
        name: form.name,
        direction: form.direction,
        transfer_method: form.transfer_method,
        data_classification: form.data_classification,
        volume_per_transfer: Number(form.volume_per_transfer) || 0,
        involves_regulated_data: form.involves_regulated_data,
      });
      onCreated();
    } catch (e) {
      setErr(e.message || 'Create failed');
    } finally {
      setSubmitting(false);
    }
  };

  const field = "w-full bg-[var(--layer-0)] border border-[var(--border-default)] px-3 py-2 rounded text-[11px] font-mono text-[var(--text-primary)] focus:border-[var(--accent)] outline-none";
  const label = "text-[9px] font-bold text-[var(--text-tertiary)] uppercase tracking-widest mb-1 block";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className="w-[520px] max-h-[90vh] overflow-y-auto bg-[var(--layer-1)] border border-[var(--border-emphasis)] rounded-lg shadow-2xl">
        <div className="h-12 border-b border-[var(--border-default)] flex items-center justify-between px-5 bg-[var(--layer-2)]">
          <span className="text-[11px] font-bold uppercase tracking-widest font-display">New Integration</span>
          <button onClick={onClose} className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"><X size={16} /></button>
        </div>

        <div className="p-5 space-y-4">
          {/* Vendor */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className={label}>Vendor</span>
              <button onClick={() => setNewVendor((v) => !v)}
                className="text-[9px] text-[var(--accent)] uppercase tracking-widest font-bold">
                {newVendor ? 'Pick existing' : '+ New vendor'}
              </button>
            </div>
            {newVendor ? (
              <div className="space-y-2">
                <input className={field} placeholder="Vendor name" value={vendorName} onChange={(e) => setVendorName(e.target.value)} />
                <input className={field} placeholder="Contact email (optional)" value={vendorEmail} onChange={(e) => setVendorEmail(e.target.value)} />
              </div>
            ) : (
              <select className={field} value={form.vendor_id} onChange={set('vendor_id')}>
                <option value="">— select vendor —</option>
                {vendors.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
              </select>
            )}
          </div>

          <div>
            <span className={label}>Integration name</span>
            <input className={field} placeholder="e.g. Daily customer enrichment feed" value={form.name} onChange={set('name')} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <span className={label}>Direction</span>
              <select className={field} value={form.direction} onChange={set('direction')}>
                <option value="egress">Egress (data leaving)</option>
                <option value="ingress">Ingress (data arriving)</option>
              </select>
            </div>
            <div>
              <span className={label}>Transfer method</span>
              <select className={field} value={form.transfer_method} onChange={set('transfer_method')}>
                <option value="file">File</option>
                <option value="api">API</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <span className={label}>Data classification</span>
              <select className={field} value={form.data_classification} onChange={set('data_classification')}>
                {['PII', 'PHI', 'financial', 'credentials', 'public'].map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <span className={label}>Volume / transfer</span>
              <input type="number" className={field} value={form.volume_per_transfer} onChange={set('volume_per_transfer')} />
            </div>
          </div>

          <div>
            <span className={label}>Regulated data</span>
            <input className={field} placeholder='e.g. "HIPAA, GDPR" or "none"' value={form.involves_regulated_data} onChange={set('involves_regulated_data')} />
          </div>

          {err && <div className="text-[10px] text-[var(--danger)] font-mono flex items-center gap-2"><AlertTriangle size={12} /> {err}</div>}
        </div>

        <div className="h-14 border-t border-[var(--border-default)] flex items-center justify-end gap-3 px-5 bg-[var(--layer-2)]">
          <button onClick={onClose} className="px-4 py-1.5 text-[10px] font-bold uppercase tracking-wider text-[var(--text-tertiary)] hover:text-[var(--text-primary)]">Cancel</button>
          <button onClick={submit} disabled={submitting}
            className="px-5 py-1.5 bg-[var(--accent-emphasis)] hover:bg-[var(--accent)] text-white rounded-md text-[10px] font-bold uppercase tracking-wider transition active:scale-95 disabled:opacity-50">
            {submitting ? 'Creating…' : 'Create & Assess'}
          </button>
        </div>
      </div>
    </div>
  );
}
