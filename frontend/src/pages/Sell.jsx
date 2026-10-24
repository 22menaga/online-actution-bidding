import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Auctions, Auth, Products, Seller } from '../api.js';
import ListingForm from '../components/ListingForm.jsx';
import { Badge, Field, Icon, Skeleton, fmtDateTime, money, useAsync, useToast } from '../ui.jsx';

const iso = (local) => new Date(local).toISOString();

function VerificationForm() {
  const toast = useToast();
  const [f, setF] = useState({ legal_name: '', document_type: 'Business licence', document_reference: '' });
  const submit = async (e) => {
    e.preventDefault();
    try { await Seller.verify(f); toast('Verification submitted. An admin will review it.', 'ok'); } catch (x) { toast(x.message, 'err'); }
  };
  return (
    <form className="card pad" onSubmit={submit}>
      <h3>Seller verification</h3>
      <p className="mute small">Admin approval is required before you can create auctions.</p>
      <Field label="Legal name"><input value={f.legal_name} onChange={(e) => setF({ ...f, legal_name: e.target.value })} required /></Field>
      <Field label="Document type"><input value={f.document_type} onChange={(e) => setF({ ...f, document_type: e.target.value })} required /></Field>
      <Field label="Document reference"><input value={f.document_reference} onChange={(e) => setF({ ...f, document_reference: e.target.value })} required /></Field>
      <p><button className="btn">Submit for review</button></p>
    </form>
  );
}

function AuctionForm({ product, onDone }) {
  const toast = useToast();
  const [f, setF] = useState({ starting_price: product.ai_estimate?.suggested_start_price ?? product.starting_price, min_increment: '10', mode: 'twentyfour', requested_start_at: '', requested_end_at: '', seller_note: '' });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    const body = { product: product.id, starting_price: f.starting_price, min_increment: f.min_increment, seller_note: f.seller_note, is_24_7: f.mode === 'twentyfour' };
    if (f.mode === 'window' && f.requested_start_at && f.requested_end_at) { body.requested_start_at = iso(f.requested_start_at); body.requested_end_at = iso(f.requested_end_at); }
    try {
      await Auctions.create(body);
      toast('Request sent. An admin will review it and allocate the time.', 'ok');
      onDone();
    } catch (x) { toast(x.message, 'err'); }
  };
  return (
    <form onSubmit={submit} style={{ marginTop: 10 }}>
      <div className="row" style={{ alignItems: 'flex-end' }}>
        <div style={{ width: 120 }}><label>Start price</label><input type="number" step="0.01" min="0.01" value={f.starting_price} onChange={set('starting_price')} required /></div>
        <div style={{ width: 110 }}><label>Bid step</label><input type="number" step="0.01" min="0.01" value={f.min_increment} onChange={set('min_increment')} required /></div>
      </div>
      {product.ai_estimate && <p className="faint small" style={{ margin: '6px 0 0' }}>AI market estimate: {money(product.ai_estimate.estimated_low, 0)}–{money(product.ai_estimate.estimated_high, 0)} · suggested start {money(product.ai_estimate.suggested_start_price, 0)}</p>}
      <label>When would you like it to run?</label>
      <div className="chips">
        <button type="button" className={`chip ${f.mode === 'twentyfour' ? 'on' : ''}`} onClick={() => setF({ ...f, mode: 'twentyfour' })}>24/7 — let the admin choose</button>
        <button type="button" className={`chip ${f.mode === 'window' ? 'on' : ''}`} onClick={() => setF({ ...f, mode: 'window' })}>I have a preferred window</button>
      </div>
      {f.mode === 'window' && (
        <div className="row" style={{ marginTop: 8 }}>
          <div><label>Preferred start</label><input type="datetime-local" value={f.requested_start_at} onChange={set('requested_start_at')} required /></div>
          <div><label>Preferred end</label><input type="datetime-local" value={f.requested_end_at} onChange={set('requested_end_at')} required /></div>
        </div>
      )}
      <label>Note to the admin (optional)</label>
      <input value={f.seller_note} maxLength={500} onChange={set('seller_note')} placeholder="e.g. Collectors are online in the evenings" />
      <p className="faint small" style={{ margin: '8px 0 0' }}>This is a request only. Buyers can bid 24/7 once it is live, but an admin reviews your listing and sets the actual start and end time.</p>
      <p><button className="btn gold sm" style={{ marginTop: 10 }}>Send for scheduling</button></p>
    </form>
  );
}

export default function Sell() {
  const products = useAsync(Products.mine, []);
  const auctions = useAsync(() => Auctions.list({ ordering: '-created_at', mine: 1, status: '' }), []);
  const profile = useAsync(Auth.profile, []);
  const [open, setOpen] = useState(null);
  const toast = useToast();

  // studio numbers, computed from what the seller already has
  const mine = auctions.data?.results ?? [];
  const sold = mine.filter((a) => a.status === 'SOLD');
  const stats = [
    ['Live now', mine.filter((a) => a.status === 'LIVE').length, 'var(--ok)'],
    ['Awaiting admin', mine.filter((a) => a.status === 'PENDING_APPROVAL').length + (products.data?.results.filter((p) => p.status === 'PENDING_APPROVAL').length ?? 0), 'var(--gold1)'],
    ['Items sold', sold.length],
    ['Sales value', money(sold.reduce((n, a) => n + Number(a.current_highest_bid ?? 0), 0), 0)],
  ];

  const cancel = async (a) => {
    try { await Auctions.cancel(a.id); toast('Auction cancelled', 'ok'); auctions.reload(); } catch (x) { toast(x.message, 'err'); }
  };

  return (
    <div className="wrap" style={{ padding: '28px 20px' }}>
      <div className="eyebrow">Seller studio</div>
      <h1>Sell your items</h1>
      <p className="mute" style={{ maxWidth: 640 }}>Upload photos, let the AI estimate the market price, then send the listing for approval. Bidding happens on a separate bidder profile.</p>
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', margin: '18px 0 26px' }}>
        {stats.map(([label, value, tone]) => <div key={label} className="card kpi"><b style={tone ? { color: tone } : undefined}>{value}</b><span>{label}</span></div>)}
      </div>
      {profile.data && !profile.data.approved && (
        <div className="banner" style={{ marginBottom: 22 }}><Icon name="shield" /><div><b>Verification needed.</b> You can prepare listings now, but an admin must verify your identity before auctions can run. {profile.data.rejection_reason && <>Note from admin: {profile.data.rejection_reason}</>}</div></div>
      )}
      <div className="split" style={{ alignItems: 'start' }}>
        <div className="stack">
          <ListingForm onCreated={products.reload} />
          {profile.data && !profile.data.approved && <VerificationForm />}
        </div>
        <div className="stack">
          <div className="card pad">
            <h3>My products</h3>
            {products.loading && <Skeleton h={60} />}
            {products.data?.results.length === 0 && <p className="mute small">No products yet.</p>}
            {products.data?.results.map((p) => (
              <div key={p.id} style={{ borderBottom: '1px solid var(--line)', padding: '12px 0' }}>
                <div className="row between"><strong>{p.name}</strong><Badge status={p.status} /></div>
                {p.ai_estimate && <div className="small faint">AI estimate {money(p.ai_estimate.estimated_low, 0)}–{money(p.ai_estimate.estimated_high, 0)}</div>}
                {p.rejection_reason && <div className="small" style={{ color: 'var(--bad)' }}>Rejected: {p.rejection_reason}</div>}
                {p.auction_status && p.auction_status !== 'CANCELLED' && <div className="small mute" style={{ marginTop: 6 }}>Auction: <Badge status={p.auction_status} /></div>}
                {(p.status === 'APPROVED' || p.status === 'UNSOLD') && (!p.auction_status || ['CANCELLED', 'UNSOLD'].includes(p.auction_status)) && (open === p.id
                  ? <AuctionForm product={p} onDone={() => { setOpen(null); products.reload(); auctions.reload(); }} />
                  : <button className="btn ghost sm" style={{ marginTop: 8 }} onClick={() => setOpen(p.id)}>Create auction</button>)}
              </div>
            ))}
          </div>
          <div className="card pad">
            <h3>My auctions</h3>
            {auctions.loading && <Skeleton h={60} />}
            {auctions.data?.results.length === 0 && <p className="mute small">No auctions yet.</p>}
            {auctions.data?.results.map((a) => (
              <div key={a.id} className="row between" style={{ borderBottom: '1px solid var(--line)', padding: '12px 0' }}>
                <div>
                  <Link to={`/auctions/${a.id}`}><strong>{a.product_name}</strong></Link>
                  <div className="small mute">{money(a.current_highest_bid ?? a.starting_price)} · {a.bid_count} bids</div>
                  {a.status === 'PENDING_APPROVAL' && <div className="small" style={{ color: 'var(--gold1)' }}>Waiting for an admin to allocate your time{a.is_24_7 ? ' (you asked for 24/7)' : ''}</div>}
                  {a.start_at && <div className="small mute">Runs {fmtDateTime(a.start_at)} → {fmtDateTime(a.end_at)}{a.admin_note ? ` · admin: “${a.admin_note}”` : ''}</div>}
                  {a.status === 'CANCELLED' && a.admin_note && <div className="small" style={{ color: 'var(--bad)' }}>Not approved: {a.admin_note}</div>}
                </div>
                <div className="row">
                  <Badge status={a.status} />
                  {!a.bid_count && ['PENDING_APPROVAL', 'SCHEDULED'].includes(a.status) && <button className="btn ghost sm" onClick={() => cancel(a)}>Cancel</button>}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
