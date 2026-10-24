import { useState } from 'react';
import { Admin as AdminApi } from '../api.js';
import { Badge, EmptyState, Skeleton, fmtDateTime, money, useAsync, useToast } from '../ui.jsx';

/** Inline approve / reject with a required reason on rejection. */
function Decision({ onApprove, onReject, approveLabel = 'Approve', busy }) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState('');
  return (
    <div style={{ minWidth: 220 }}>
      <div className="row">
        <button className="btn gold sm" disabled={busy} onClick={onApprove}>{approveLabel}</button>
        <button className="btn ghost sm" disabled={busy} onClick={() => setRejecting(!rejecting)}>Reject…</button>
      </div>
      {rejecting && (
        <div style={{ marginTop: 8 }}>
          <input value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} placeholder="Reason shown to the seller" />
          <button className="btn pink sm" style={{ marginTop: 8 }} disabled={busy || !reason.trim()} onClick={() => onReject(reason.trim())}>Confirm rejection</button>
        </div>
      )}
    </div>
  );
}

export function ProductsReview({ onChange }) {
  const toast = useToast();
  const { loading, data, reload } = useAsync(AdminApi.pendingProducts, []);
  const [busy, setBusy] = useState(false);
  if (loading) return <Skeleton h={180} r={16} />;
  if (!data.length) return <EmptyState icon="📦" title="No products waiting">Items sellers submit for approval appear here.</EmptyState>;
  const act = async (p, decision, reason = '') => {
    setBusy(true);
    try { await AdminApi.reviewProduct(p.id, decision, reason); toast(decision === 'APPROVED' ? 'Product approved' : 'Product rejected', 'ok'); await reload(); onChange(); } catch (x) { toast(x.message, 'err'); } finally { setBusy(false); }
  };
  return (
    <div className="stack">
      {data.map((p) => (
        <div key={p.id} className="card pad">
          <div className="row between" style={{ alignItems: 'flex-start' }}>
            <div className="row" style={{ flexWrap: 'nowrap', alignItems: 'flex-start' }}>
              {p.images?.[0] ? <img src={p.images[0].image} alt="" style={{ width: 96, height: 72, objectFit: 'cover', borderRadius: 10 }} /> : <div className="skel" style={{ width: 96, height: 72 }} />}
              <div>
                <b style={{ fontSize: 17 }}>{p.name}</b> <span className="faint small">· {p.category_name} · {p.condition}</span>
                <div className="small mute">by {p.seller_name} · reference {money(Number(p.starting_price))} · {p.images?.length ?? 0} photo(s)</div>
                {p.ai_estimate && (() => { const e = p.ai_estimate; const off = Number(p.starting_price) > e.estimated_high * 1.5 || Number(p.starting_price) < e.estimated_low * 0.5; return <div className="small" style={{ color: off ? 'var(--gold1)' : 'var(--ok)', marginTop: 2 }}>{off ? '⚠' : '✓'} AI estimate {money(e.estimated_low, 0)}–{money(e.estimated_high, 0)} ({e.confidence} confidence){off ? ' — the seller\'s reference price is far outside this range' : ''}</div>; })()}
                <p className="mute small" style={{ margin: '6px 0 0', maxWidth: 560 }}>{p.description}</p>
                {(!p.images?.length || (p.description ?? '').length < 30) && <div className="small" style={{ color: 'var(--gold1)', marginTop: 6 }}>⚠ Thin listing: {!p.images?.length ? 'no photos' : 'very short description'}</div>}
              </div>
            </div>
            <Decision busy={busy} onApprove={() => act(p, 'APPROVED')} onReject={(r) => act(p, 'REJECTED', r)} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function SellersReview({ onChange }) {
  const toast = useToast();
  const { loading, data, reload } = useAsync(AdminApi.sellerVerifications, []);
  const [busy, setBusy] = useState(false);
  if (loading) return <Skeleton h={180} r={16} />;
  const pending = data.filter((v) => v.status === 'PENDING');
  if (!pending.length) return <EmptyState icon="🪪" title="No verifications waiting">Seller identity submissions appear here.</EmptyState>;
  const act = async (v, decision, notes = '') => {
    setBusy(true);
    try { await AdminApi.reviewSeller(v.id, decision, notes); toast(decision === 'APPROVED' ? 'Seller approved' : 'Seller rejected', 'ok'); await reload(); onChange(); } catch (x) { toast(x.message, 'err'); } finally { setBusy(false); }
  };
  return (
    <div className="stack">
      {pending.map((v) => (
        <div key={v.id} className="card pad">
          <div className="row between" style={{ alignItems: 'flex-start' }}>
            <div>
              <b style={{ fontSize: 17 }}>{v.legal_name}</b> <Badge status="PENDING" />
              <div className="small mute">Account {v.seller_name} · {v.seller_email}</div>
              <div className="small mute">{v.document_type} · ref <b>{v.document_reference}</b> · submitted {fmtDateTime(v.created_at)}</div>
              <p className="faint small" style={{ margin: '6px 0 0' }}>Check the document against the legal name before approving. Approving lets this seller list products and create auctions.</p>
            </div>
            <Decision busy={busy} approveLabel="Verify seller" onApprove={() => act(v, 'APPROVED')} onReject={(r) => act(v, 'REJECTED', r)} />
          </div>
        </div>
      ))}
    </div>
  );
}
