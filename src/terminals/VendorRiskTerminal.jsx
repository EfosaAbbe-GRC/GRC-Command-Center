import React, { useState } from 'react';
import { Shield, AlertTriangle, CheckCircle2, Clock, ChevronRight, Plus, X, ShieldCheck, Bell, Download, Paperclip } from 'lucide-react';
import { useApiData } from '../hooks/useApiData';
import { StatusBadge } from '../components/StatusBadge';
import { api } from '../lib/api';
import { useAuth } from '../contexts/useAuth';
import { useWebSocket } from '../hooks/useWebSocket';

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
  not_applicable: <div className="w-3.5 h-3.5 rounded-sm" style={{ backgroundColor: 'var(--text-tertiary)' }} />,
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
  const { data: dueReassessments, refresh: refreshDue } = useApiData('/tprm/reassessments/due');
  const { data: expiringAcceptances, refresh: refreshExpiring } = useApiData('/tprm/acceptances/expiring');

  const [selected, setSelected] = useState(null);
  const [summary, setSummary] = useState(null);
  const [stages, setStages] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [expandedStage, setExpandedStage] = useState(null);
  const [acceptances, setAcceptances] = useState([]);
  const [signingStage, setSigningStage] = useState(null);
  const [showReassessPanel, setShowReassessPanel] = useState(false);
  const [stageEvidence, setStageEvidence] = useState({});
  const [uploadingEvidence, setUploadingEvidence] = useState(null);

  // Reassessment/expiring-acceptance status is time-based with no natural
  // mutation event of its own; GOVERNANCE bans setInterval polling, so this
  // re-fetches only on a WS nudge from a real TPRM action (see
  // _broadcast_reassessment_status in tprm.py) plus the initial mount fetch
  // above. A due date silently lapsing with no TPRM activity won't push live.
  useWebSocket(api.getAccessToken(), (message) => {
    if (message.type === 'TPRM_REASSESSMENT_STATUS') {
      refreshDue();
      refreshExpiring();
    }
  });

  const openIntegration = async (integ) => {
    setSelected(integ);
    setActionError(null);
    setExpandedStage(null);
    setStageEvidence({});
    const [s, st, ra] = await Promise.all([
      api.get(`/tprm/integrations/${integ.id}/summary`),
      api.get(`/tprm/integrations/${integ.id}/stages`),
      api.get(`/tprm/integrations/${integ.id}/risk-acceptances`),
    ]);
    setSummary(s);
    setStages(st);
    setAcceptances(ra);
  };

  const toggleStage = (stageId) => {
    const next = expandedStage === stageId ? null : stageId;
    setExpandedStage(next);
    if (next && !stageEvidence[next]) {
      api.get(`/tprm/integrations/${selected.id}/stages/${next}/evidence`)
        .then((ev) => setStageEvidence((prev) => ({ ...prev, [next]: ev })))
        .catch(() => {});
    }
  };

  const uploadEvidence = async (stageId, file) => {
    setUploadingEvidence(stageId);
    setActionError(null);
    try {
      await api.uploadFile(`/tprm/integrations/${selected.id}/stages/${stageId}/evidence`, file);
      const ev = await api.get(`/tprm/integrations/${selected.id}/stages/${stageId}/evidence`);
      setStageEvidence((prev) => ({ ...prev, [stageId]: ev }));
    } catch (err) {
      setActionError(err.message || 'Evidence upload failed');
    } finally {
      setUploadingEvidence(null);
    }
  };

  const updateStage = async (stageId, status) => {
    let evidence_notes;
    if (status === 'not_applicable') {
      const justification = window.prompt('Justification for marking this stage Not Applicable (required):');
      if (!justification || !justification.trim()) return;
      evidence_notes = justification.trim();
    }
    await api.post(`/tprm/integrations/${selected.id}/stages/${stageId}`, { status, evidence_notes });
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
            {(dueReassessments?.length > 0 || expiringAcceptances?.length > 0) && (
              <button
                onClick={() => setShowReassessPanel((v) => !v)}
                className="flex items-center gap-1 px-1.5 py-0.5 rounded-sm border text-[9px] font-bold uppercase font-mono"
                style={{ borderColor: 'var(--warning)', color: 'var(--warning)', backgroundColor: 'var(--warning-subtle)' }}
                title="Reassessment & risk-acceptance status"
              >
                <Bell size={10} />
                {dueReassessments?.length || 0} overdue · {expiringAcceptances?.length || 0} expiring
              </button>
            )}
          </div>
          <div className="flex items-center gap-1.5">
            {canSignoff && (
              <button
                onClick={() => api.downloadFile('/tprm/export', 'tprm_assessment_report.csv')}
                className="p-1.5 bg-[var(--layer-2)] hover:bg-[var(--layer-3)] border border-[var(--border-default)] rounded transition"
                title="Export TPRM Assessment Report (CSV)"
              >
                <Download size={14} />
              </button>
            )}
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
        </div>

        {showReassessPanel && (
          <div className="px-3 py-2 border-b border-[var(--border-default)] bg-[var(--layer-0)] text-[11px] space-y-2 max-h-48 overflow-y-auto shrink-0">
            {dueReassessments?.map((r) => (
              <div key={r.integration_id} className="flex justify-between gap-2">
                <span className="text-[var(--text-secondary)] truncate">{r.name}</span>
                <span className="text-[var(--warning)] font-mono shrink-0">{r.days_overdue}d overdue</span>
              </div>
            ))}
            {expiringAcceptances?.map((a) => (
              <div key={a.acceptance_id} className="flex justify-between gap-2">
                <span className="text-[var(--text-secondary)] truncate">{a.integration_name}</span>
                <span className="text-[var(--danger)] font-mono shrink-0">{a.days_expired}d expired</span>
              </div>
            ))}
          </div>
        )}

        {vendors?.length > 0 && (
          <div className="flex gap-1.5 px-3 py-2 border-b border-[var(--border-default)] overflow-x-auto shrink-0">
            {vendors.map((v) => {
              const tier = TIER_STYLE[v.overall_risk_tier] || TIER_STYLE.unscored;
              return (
                <div key={v.id}
                  className="flex items-center gap-1.5 px-2 py-1 rounded-sm border shrink-0"
                  style={{ borderColor: tier.color, backgroundColor: tier.bg }}
                  title={`${v.name} — ${v.overall_risk_tier}`}
                >
                  <span className="text-[10px] font-bold text-[var(--text-primary)] truncate max-w-[100px]">{v.name}</span>
                  <span className="text-[8px] font-bold uppercase font-mono" style={{ color: tier.color }}>
                    {v.overall_risk_tier}
                  </span>
                </div>
              );
            })}
          </div>
        )}

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
              {stages.map((stage) => {
                const isExpanded = expandedStage === stage.stage_id;
                return (
                  <div key={stage.stage_id}
                    className="rounded border border-[var(--border-default)] bg-[var(--layer-1)] overflow-hidden">
                    <div
                      className="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-[var(--layer-2)] transition"
                      onClick={() => toggleStage(stage.stage_id)}
                    >
                      <ChevronRight size={12} className={`text-[var(--text-tertiary)] transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                      <div className="w-6 text-center text-[10px] text-[var(--text-tertiary)] font-mono">{stage.stage_number}</div>
                      {STAGE_ICON[stage.status]}
                      <div className="flex-1 min-w-0">
                        <div className="text-[11px] text-[var(--text-secondary)] truncate">{stage.title}</div>
                      </div>
                      {canAssess && (
                        <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                          {['pass', 'gap', 'in_review', 'not_applicable'].map((s) => (
                            <button key={s} onClick={() => updateStage(stage.stage_id, s)}
                              className={`px-2 py-0.5 rounded-sm text-[9px] uppercase font-bold font-mono border transition ${stage.status === s ? 'border-[var(--accent)] text-[var(--accent)] bg-[var(--accent-subtle)]' : 'border-[var(--border-default)] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'}`}>
                              {s === 'in_review' ? 'review' : s === 'not_applicable' ? 'n/a' : s}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    {isExpanded && (
                      <div className="px-4 pb-3 pt-1 space-y-2 border-t border-[var(--border-subtle)] bg-[var(--layer-0)]">
                        <StageDetailField label="Guidance" value={stage.guidance} />
                        <StageDetailField label="Review Questions" value={stage.review_questions} />
                        <StageDetailField label="Evidence to Collect" value={stage.evidence_to_collect} />
                        {stage.evidence_notes && (
                          <StageDetailField label={`Notes${stage.reviewed_by ? ` — ${stage.reviewed_by}` : ''}`} value={stage.evidence_notes} />
                        )}
                        <div className="pt-1 border-t border-[var(--border-subtle)]">
                          <div className="text-[9px] font-bold text-[var(--text-tertiary)] uppercase tracking-widest mb-1">
                            Evidence ({(stageEvidence[stage.stage_id] || []).length})
                          </div>
                          {(stageEvidence[stage.stage_id] || []).map((ev) => (
                            <div key={ev.link_id} className="flex justify-between gap-2 text-[10px] text-[var(--text-secondary)] py-0.5">
                              <span className="truncate">{ev.filename}</span>
                              <span className="font-mono text-[var(--text-tertiary)] shrink-0">
                                {(ev.file_size_bytes / 1024).toFixed(1)}KB · {ev.file_hash.slice(0, 12)}… · {ev.linked_by}
                              </span>
                            </div>
                          ))}
                          {canAssess && (
                            <label className="mt-1 inline-flex items-center gap-1.5 px-2 py-1 bg-[var(--layer-2)] hover:bg-[var(--layer-3)] border border-[var(--border-default)] rounded text-[9px] font-bold uppercase tracking-wider cursor-pointer transition">
                              <Paperclip size={10} />
                              {uploadingEvidence === stage.stage_id ? 'Uploading…' : 'Attach Evidence'}
                              <input type="file" className="hidden" disabled={uploadingEvidence === stage.stage_id}
                                onChange={(e) => {
                                  const file = e.target.files?.[0];
                                  if (file) uploadEvidence(stage.stage_id, file);
                                  e.target.value = '';
                                }} />
                            </label>
                          )}
                        </div>
                        {stage.status === 'gap' && (() => {
                          const acc = acceptances.find((a) => a.stage_id === stage.stage_id);
                          if (acc) {
                            return (
                              <div className="pt-1 border-t border-[var(--border-subtle)]">
                                <div className="text-[9px] font-bold text-[var(--warning)] uppercase tracking-widest mb-0.5">Risk Accepted</div>
                                <div className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
                                  {acc.gap_description} — compensating control: {acc.compensating_control}
                                </div>
                                <div className="text-[9px] text-[var(--text-tertiary)] font-mono mt-1">
                                  Accepted by {acc.accepted_by} · expires {new Date(acc.expires_at).toLocaleDateString()}
                                </div>
                              </div>
                            );
                          }
                          if (canSignoff) {
                            return (
                              <button onClick={() => setSigningStage(stage)}
                                className="mt-1 px-3 py-1 bg-[var(--warning-subtle)] hover:bg-[var(--warning)] hover:text-black border border-[var(--warning)] text-[var(--warning)] rounded text-[9px] font-bold uppercase tracking-wider transition">
                                Sign Risk Acceptance
                              </button>
                            );
                          }
                          return <div className="text-[10px] text-[var(--text-tertiary)]">Gap open — awaiting admin risk acceptance</div>;
                        })()}
                      </div>
                    )}
                  </div>
                );
              })}
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

      {signingStage && (
        <RiskAcceptanceModal
          integrationId={selected.id}
          stage={signingStage}
          onClose={() => setSigningStage(null)}
          onSigned={async () => { setSigningStage(null); await openIntegration(selected); }}
        />
      )}
    </div>
  );
}

function StageDetailField({ label, value }) {
  return (
    <div>
      <div className="text-[9px] font-bold text-[var(--text-tertiary)] uppercase tracking-widest mb-0.5">{label}</div>
      <div className="text-[11px] text-[var(--text-secondary)] leading-relaxed">{value}</div>
    </div>
  );
}

function RiskAcceptanceModal({ integrationId, stage, onClose, onSigned }) {
  const [gapDescription, setGapDescription] = useState('');
  const [compensatingControl, setCompensatingControl] = useState('');
  const [expiresInDays, setExpiresInDays] = useState(365);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState(null);

  const submit = async () => {
    setErr(null);
    if (!gapDescription.trim() || !compensatingControl.trim()) {
      setErr('Gap description and compensating control are required');
      return;
    }
    setSubmitting(true);
    try {
      await api.post(`/tprm/integrations/${integrationId}/risk-acceptances`, {
        stage_id: stage.stage_id,
        gap_description: gapDescription,
        compensating_control: compensatingControl,
        expires_in_days: Number(expiresInDays) || 365,
      });
      onSigned();
    } catch (e) {
      setErr(e.message || 'Failed to sign risk acceptance');
    } finally {
      setSubmitting(false);
    }
  };

  const field = "w-full bg-[var(--layer-0)] border border-[var(--border-default)] px-3 py-2 rounded text-[11px] font-mono text-[var(--text-primary)] focus:border-[var(--accent)] outline-none";
  const label = "text-[9px] font-bold text-[var(--text-tertiary)] uppercase tracking-widest mb-1 block";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className="w-[480px] max-h-[90vh] overflow-y-auto bg-[var(--layer-1)] border border-[var(--border-emphasis)] rounded-lg shadow-2xl">
        <div className="h-12 border-b border-[var(--border-default)] flex items-center justify-between px-5 bg-[var(--layer-2)]">
          <span className="text-[11px] font-bold uppercase tracking-widest font-display">Sign Risk Acceptance — Stage {stage.stage_number}</span>
          <button onClick={onClose} className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"><X size={16} /></button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <span className={label}>Gap description</span>
            <textarea className={field} rows={3} placeholder="What's the gap?" value={gapDescription} onChange={(e) => setGapDescription(e.target.value)} />
          </div>
          <div>
            <span className={label}>Compensating control</span>
            <textarea className={field} rows={3} placeholder="What mitigates the risk in the meantime?" value={compensatingControl} onChange={(e) => setCompensatingControl(e.target.value)} />
          </div>
          <div>
            <span className={label}>Expires in (days)</span>
            <input type="number" className={field} value={expiresInDays} onChange={(e) => setExpiresInDays(e.target.value)} min={1} max={1095} />
          </div>
          {err && <div className="text-[10px] text-[var(--danger)] font-mono flex items-center gap-2"><AlertTriangle size={12} /> {err}</div>}
        </div>
        <div className="h-14 border-t border-[var(--border-default)] flex items-center justify-end gap-3 px-5 bg-[var(--layer-2)]">
          <button onClick={onClose} className="px-4 py-1.5 text-[10px] font-bold uppercase tracking-wider text-[var(--text-tertiary)] hover:text-[var(--text-primary)]">Cancel</button>
          <button onClick={submit} disabled={submitting}
            className="px-5 py-1.5 bg-[var(--accent-emphasis)] hover:bg-[var(--accent)] text-white rounded-md text-[10px] font-bold uppercase tracking-wider transition active:scale-95 disabled:opacity-50">
            {submitting ? 'Signing…' : 'Sign Acceptance'}
          </button>
        </div>
      </div>
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
                {vendors.map((v) => <option key={v.id} value={v.id}>{v.name} — {v.overall_risk_tier}</option>)}
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
