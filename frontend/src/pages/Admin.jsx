import { Suspense, lazy, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Admin as AdminApi } from '../api.js';
import AdminAuctions, { AuctionDrawer } from './AdminAuctions.jsx';
import AdminPeople, { PersonDrawer } from './AdminPeople.jsx';
import { ProductsReview, SellersReview } from './AdminReviews.jsx';
import { Badge, EmptyState, Field, Icon, Skeleton, fmtDateTime, money, toLocalInput, useAsync, useToast } from '../ui.jsx';

const StatBars3D = lazy(() => import('../scene/StatBars3D.jsx'));
const PRESETS = [['24 hours', 24], ['3 days', 72], ['7 days', 168], ['14 days', 336]];
const ICON = { ok: '✓', warn: '!', fail: '✕' };

function Kpi({ label, value, tone }) {
  return (<div className="card kpi"><b style={tone ? { color: tone } : undefined}>{value}</b><span>{label}</span></div>);
}

/* ------------------------------------------------------------ overview */
function Overview() {
  const { loading, data } = useAsync(AdminApi.overview, []);
  if (loading || !data) return <Skeleton h={300} r={16} />;
  const { queue, platform, security, money: m, recent_activity: activity, config } = data;
  const pay = config?.payments;
  const flagged = security.rapid_bidders.length + security.repeat_failed_payers.length;
  return (
    <div className="stack">
      {pay && !['ok', 'mock'].includes(pay.status) && (
        <div className="banner" role="alert"><Icon name="lock" /><div><b>Payments are not working:</b> {pay.detail} Buyers cannot pay until this is fixed.</div></div>
      )}
      {pay?.status === 'mock' && <div className="banner info"><Icon name="shield" /><div><b>Payments are in test mode.</b> {pay.detail}</div></div>}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))' }}>
        <Kpi label="Awaiting scheduling" value={queue.pending_auctions} tone={queue.pending_auctions ? 'var(--gold1)' : undefined} />
        <Kpi label="Time suggestions" value={queue.open_time_requests} />
        <Kpi label="Products to review" value={queue.pending_products} />
        <Kpi label="Sellers to verify" value={queue.pending_seller_verifications} />
        <Kpi label="Live now" value={platform.live_now} tone="var(--ok)" />
        <Kpi label="Bids (24h)" value={platform.bids_24h} />
        <Kpi label="Paid (gross)" value={money(m.gross_paid, 0)} />
        <Kpi label="Awaiting payment" value={money(m.awaiting_payment, 0)} />
      </div>

      <Suspense fallback={<Skeleton h={280} r={16} />}>
        <StatBars3D items={[{ label: 'SELLERS', value: queue.pending_seller_verifications }, { label: 'PRODUCTS', value: queue.pending_products }, { label: 'TO SCHEDULE', value: queue.pending_auctions }, { label: 'SUGGESTIONS', value: queue.open_time_requests }, { label: 'LIVE NOW', value: platform.live_now }]} />
      </Suspense>

      <div className="split" style={{ alignItems: 'start' }}>
        <div className="card pad">
          <div className="row between"><h3 style={{ margin: 0 }}>Security signals</h3><Badge status={flagged ? 'warn' : 'ok'}>{flagged ? `${flagged} to look at` : 'All clear'}</Badge></div>
          <div style={{ marginTop: 10 }}>
            {[
              ['Unverified email addresses', security.unverified_emails],
              ['Suspended accounts', security.suspended_users],
              ['Sellers not yet verified', security.unverified_sellers],
              ['New users (24h)', platform.new_users_24h],
              ['Admin actions (24h)', security.admin_actions_24h],
              ['Failed payments (all time)', m.failed_payments],
            ].map(([l, v]) => (<div key={l} className="row between" style={{ padding: '8px 0', borderBottom: '1px solid var(--line)' }}><span className="mute">{l}</span><b>{v}</b></div>))}
          </div>
          {security.rapid_bidders.length > 0 && (
            <div className="banner" style={{ marginTop: 14 }}><Icon name="bolt" /><div><b>Rapid bidding (10 min):</b> {security.rapid_bidders.map((b) => `${b.bidder__username} (${b.n} bids)`).join(', ')}</div></div>
          )}
          {security.repeat_failed_payers.length > 0 && (
            <div className="banner" style={{ marginTop: 10 }}><Icon name="lock" /><div><b>Repeated failed payments (7 days):</b> {security.repeat_failed_payers.map((b) => `${b.buyer__username} (${b.n})`).join(', ')}</div></div>
          )}
        </div>
        <div className="card pad">
          <h3>Recent activity</h3>
          {activity.length === 0 ? <p className="mute small">Nothing yet.</p> : activity.map((e) => (
            <div key={e.id} className="row between small" style={{ padding: '7px 0', borderBottom: '1px solid var(--line)', flexWrap: 'nowrap' }}>
              <span><b>{e.action.replace(/_/g, ' ').toLowerCase()}</b> <span className="faint">by {e.actor ?? 'system'} · {e.object}</span></span>
              <span className="faint" style={{ whiteSpace: 'nowrap' }}>{fmtDateTime(e.at)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ allocate / review */
function Report({ report }) {
  if (!report) return <Skeleton h={120} r={12} />;
  return (
    <div>
      <div className="row between" style={{ marginBottom: 6 }}>
        <b>Review report</b>
        <Badge status={report.overall === 'ok' ? 'ok' : report.overall === 'warn' ? 'warn' : 'bad'}>{report.overall === 'ok' ? 'No concerns' : report.overall === 'warn' ? 'Review warnings' : 'Blocking issues'}</Badge>
      </div>
      {report.checks.map((c) => (
        <div key={c.key} className={`check ${c.status}`}>
          <span className="ic">{ICON[c.status]}</span>
          <div><div style={{ fontWeight: 600, fontSize: 14 }}>{c.label}</div><div className="mute small">{c.detail}</div></div>
        </div>
      ))}
    </div>
  );
}

function AllocateForm({ auction, onDone, mode }) {
  const toast = useToast();
  const req = auction.requested_start_at && auction.requested_end_at;
  const initialStart = auction.start_at ?? auction.requested_start_at ?? new Date(Date.now() + 15 * 60000);
  const initialEnd = auction.end_at ?? auction.requested_end_at ?? new Date(new Date(initialStart).getTime() + (auction.is_24_7 ? 168 : 24) * 3600000);
  const [start, setStart] = useState(toLocalInput(initialStart));
  const [end, setEnd] = useState(toLocalInput(initialEnd));
  const [note, setNote] = useState(auction.admin_note ?? '');
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState('');

  // Re-run the capacity part of the report whenever the admin changes the window.
  useEffect(() => {
    if (mode === 'reschedule') return undefined;
    const t = setTimeout(() => {
      const ok = start && end && new Date(end) > new Date(start);
      AdminApi.review(auction.id, ok ? new Date(start).toISOString() : '', ok ? new Date(end).toISOString() : '').then(setReport).catch(() => {});
    }, 400);
    return () => clearTimeout(t);
  }, [auction.id, start, end, mode]);

  const applyPreset = (hours) => { const s = new Date(start || Date.now()); setEnd(toLocalInput(new Date(s.getTime() + hours * 3600000))); };

  const submit = async (e) => {
    e.preventDefault(); setErr(''); setBusy(true);
    try {
      const body = { start_at: new Date(start).toISOString(), end_at: new Date(end).toISOString(), note };
      await (mode === 'reschedule' ? AdminApi.reschedule : AdminApi.approve)(auction.id, body);
      toast(mode === 'reschedule' ? 'Auction rescheduled' : 'Approved and scheduled. The seller has been notified.', 'ok');
      onDone();
    } catch (x) { setErr(x.message); } finally { setBusy(false); }
  };

  const doReject = async () => {
    setBusy(true); setErr('');
    try { await AdminApi.reject(auction.id, reason); toast('Rejected. The seller has been notified.', 'ok'); onDone(); } catch (x) { setErr(x.message); } finally { setBusy(false); }
  };

  return (
    <div className="split" style={{ alignItems: 'start', marginTop: 16 }}>
      {mode !== 'reschedule' && <div>{<Report report={report} />}</div>}
      <form onSubmit={submit}>
        <b>Allocate the time</b>
        <p className="faint small" style={{ margin: '2px 0 0' }}>Buyers bid 24/7 while the auction is live. You decide when it runs.</p>
        <div className="row" style={{ alignItems: 'flex-start', flexWrap: 'nowrap' }}>
          <div style={{ flex: 1 }}><Field label="STARTS"><input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} required /></Field></div>
          <div style={{ flex: 1 }}><Field label="ENDS"><input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} required /></Field></div>
        </div>
        <div className="chips" style={{ marginTop: 10 }}>{PRESETS.map(([l, h]) => <button type="button" key={l} className="chip" onClick={() => applyPreset(h)}>{l}</button>)}{req && <button type="button" className="chip" onClick={() => { setStart(toLocalInput(auction.requested_start_at)); setEnd(toLocalInput(auction.requested_end_at)); }}>Seller&apos;s request</button>}</div>
        <Field label="NOTE TO SELLER (OPTIONAL)"><input value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Weekend slot for better visibility" /></Field>
        {err && <div className="err" role="alert">{err}</div>}
        <div className="row" style={{ marginTop: 16 }}>
          <button className="btn gold" disabled={busy}>{busy ? 'Saving…' : mode === 'reschedule' ? 'Save new time' : 'Approve & schedule'}</button>
          {mode !== 'reschedule' && <button type="button" className="btn ghost" onClick={() => setRejecting(!rejecting)}>Reject…</button>}
        </div>
        {rejecting && (
          <div style={{ marginTop: 12 }}>
            <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason shown to the seller" maxLength={500} />
            <button type="button" className="btn pink sm" style={{ marginTop: 8 }} disabled={busy || !reason.trim()} onClick={doReject}>Confirm rejection</button>
          </div>
        )}
      </form>
    </div>
  );
}

function RequestSummary({ a }) {
  return (
    <div className="small mute" style={{ marginTop: 4 }}>
      Seller asks for: {a.is_24_7 ? <b style={{ color: 'var(--gold1)' }}>24/7 · admin chooses the time</b> : a.requested_start_at ? <b>{fmtDateTime(a.requested_start_at)} → {fmtDateTime(a.requested_end_at)}</b> : <b>no preference</b>}
      {a.seller_note && <> · “{a.seller_note}”</>}
    </div>
  );
}

function Queue({ onChange }) {
  const { loading, data, reload } = useAsync(() => AdminApi.auctions('PENDING_APPROVAL'), []);
  const [open, setOpen] = useState(null);
  if (loading) return <Skeleton h={200} r={16} />;
  if (!data.length) return <EmptyState icon="✅" title="Nothing waiting">New seller listings will appear here for you to review and schedule.</EmptyState>;
  return (
    <div className="stack">
      {data.map((a) => (
        <div key={a.id} className="card glow pad">
          <div className="row between">
            <div className="row" style={{ flexWrap: 'nowrap' }}>
              {a.product_images?.[0] ? <img src={a.product_images[0]} alt="" style={{ width: 72, height: 54, objectFit: 'cover', borderRadius: 10 }} /> : <span style={{ fontSize: 32 }}>🏺</span>}
              <div><b style={{ fontSize: 17 }}>{a.product_name}</b> <span className="faint small">· {a.category_name}</span>
                <div className="small mute">by {a.seller_name} · start {money(a.starting_price)} · step {money(a.min_increment)}</div>
                <RequestSummary a={a} /></div>
            </div>
            <button className="btn ghost sm" onClick={() => setOpen(open === a.id ? null : a.id)}>{open === a.id ? 'Close' : 'Review & schedule'}</button>
          </div>
          {open === a.id && <AllocateForm auction={a} onDone={() => { setOpen(null); reload(); onChange(); }} />}
        </div>
      ))}
    </div>
  );
}

function Upcoming({ onChange }) {
  const { loading, data, reload } = useAsync(() => AdminApi.auctions('SCHEDULED'), []);
  const [open, setOpen] = useState(null);
  if (loading) return <Skeleton h={200} r={16} />;
  if (!data.length) return <EmptyState icon="📅" title="No upcoming auctions">Approved auctions waiting for their start time appear here.</EmptyState>;
  return (
    <div className="stack">
      {data.map((a) => (
        <div key={a.id} className="card pad">
          <div className="row between">
            <div><Link to={`/auctions/${a.id}`} style={{ fontWeight: 700 }}>{a.product_name}</Link> <Badge status={a.status} />
              <div className="small mute">{fmtDateTime(a.start_at)} → {fmtDateTime(a.end_at)} · {a.bid_count} bids</div></div>
            {a.bid_count === 0 ? <button className="btn ghost sm" onClick={() => setOpen(open === a.id ? null : a.id)}>{open === a.id ? 'Close' : 'Reschedule'}</button> : <span className="faint small">Locked (has bids)</span>}
          </div>
          {open === a.id && <AllocateForm auction={a} mode="reschedule" onDone={() => { setOpen(null); reload(); onChange(); }} />}
        </div>
      ))}
    </div>
  );
}

function Suggestions({ onChange }) {
  const toast = useToast();
  const { loading, data, reload } = useAsync(() => AdminApi.timeRequests('OPEN'), []);
  if (loading) return <Skeleton h={160} r={16} />;
  const rows = data.results;
  if (!rows.length) return <EmptyState icon="💡" title="No open suggestions">When buyers suggest a better time for an upcoming auction, it shows up here.</EmptyState>;
  const resolve = async (r, status) => { try { await AdminApi.resolveRequest(r.id, status); toast(`Marked ${status.toLowerCase()}`, 'ok'); reload(); onChange(); } catch (x) { toast(x.message, 'err'); } };
  return (
    <div className="stack">
      {rows.map((r) => (
        <div key={r.id} className="card pad">
          <div className="row between">
            <div>
              <b>{r.product_name}</b> <span className="badge">{r.requester_role}</span>
              <div className="small mute">{r.requester_name} suggests {r.preferred_start ? <b>{fmtDateTime(r.preferred_start)}{r.preferred_end ? ` → ${fmtDateTime(r.preferred_end)}` : ''}</b> : 'a different time'}{r.note && <> — “{r.note}”</>}</div>
              <div className="faint small">Currently {fmtDateTime(r.current_start_at)} → {fmtDateTime(r.current_end_at)}</div>
            </div>
            <div className="row">
              <Link to={`/auctions/${r.auction}`} className="btn ghost sm">Open</Link>
              <button className="btn sm" onClick={() => resolve(r, 'ACCEPTED')}>Accept</button>
              <button className="btn ghost sm" onClick={() => resolve(r, 'DISMISSED')}>Dismiss</button>
            </div>
          </div>
        </div>
      ))}
      <p className="faint small">Accepting records your decision; use the Upcoming tab to change the actual time.</p>
    </div>
  );
}

/* ------------------------------------------------------------ page */
export default function Admin() {
  const [tab, setTab] = useState('auctions');
  const [stack, setStack] = useState([]); // open detail panels; Back pops, Close clears
  const go = (p) => setStack((s) => [...s, p]);
  const back = () => setStack((s) => s.slice(0, -1));
  const close = () => setStack([]);
  const top = stack[stack.length - 1];
  const [tick, setTick] = useState(0);
  const { data } = useAsync(AdminApi.overview, [tick]);
  const bump = () => setTick((t) => t + 1);
  const q = data?.queue;
  const tabs = [['auctions', 'All auctions'], ['people', 'People'], ['sellers', 'Seller verification', q?.pending_seller_verifications], ['products', 'Product approvals', q?.pending_products], ['queue', 'Scheduling queue', q?.pending_auctions], ['upcoming', 'Upcoming'], ['suggestions', 'Time suggestions', q?.open_time_requests], ['overview', 'Security & data']];
  return (
    <div className="wrap page">
      <div className="eyebrow">Admin</div>
      <h1>Control room</h1>
      <p className="mute" style={{ maxWidth: 680 }}>Auctions run around the clock for buyers. Sellers and buyers can only <b>request</b> a time — you review each listing and decide exactly when it goes live.</p>
      <div className="tabs2" role="tablist">
        {tabs.map(([k, l, n]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}{n ? <span className="n">{n}</span> : null}</button>)}
      </div>
      {tab === 'auctions' && <AdminAuctions go={go} />}
      {tab === 'people' && <AdminPeople go={go} />}
      {top?.type === 'auction' && <AuctionDrawer key={`a${top.id}`} id={top.id} onClose={close} onBack={stack.length > 1 ? back : null} go={go} />}
      {top?.type === 'person' && <PersonDrawer key={`p${top.id}`} id={top.id} onClose={close} onBack={stack.length > 1 ? back : null} go={go} />}
      {tab === 'sellers' && <SellersReview onChange={bump} />}
      {tab === 'products' && <ProductsReview onChange={bump} />}
      {tab === 'queue' && <Queue onChange={bump} />}
      {tab === 'upcoming' && <Upcoming onChange={bump} />}
      {tab === 'suggestions' && <Suggestions onChange={bump} />}
      {tab === 'overview' && <Overview key={tick} />}
    </div>
  );
}
