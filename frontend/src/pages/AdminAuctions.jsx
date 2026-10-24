import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Admin as AdminApi } from '../api.js';
import { Badge, Countdown, EmptyState, Icon, Skeleton, fmtDateTime, money, useAsync } from '../ui.jsx';

const STATUSES = [['', 'All'], ['LIVE', 'Live'], ['PENDING_APPROVAL', 'Pending'], ['SCHEDULED', 'Scheduled'], ['SOLD', 'Sold'], ['UNSOLD', 'Unsold'], ['CANCELLED', 'Cancelled']];
const label = (s) => String(s || '').replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase());

/* ------------------------------------------------------------ small pieces */
function Stat({ label: l, value, tone, sub }) {
  return (
    <div className="card kpi">
      <b style={tone ? { color: tone } : undefined}>{value}</b>
      <span>{l}</span>
      {sub && <div className="faint small" style={{ marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function Section({ title, aside, children }) {
  return (
    <div className="card pad" style={{ background: 'rgba(0,0,0,.22)' }}>
      <div className="row between" style={{ marginBottom: 8 }}><h3 style={{ margin: 0, fontSize: 16 }}>{title}</h3>{aside}</div>
      {children}
    </div>
  );
}

const PersonLink = ({ id, name, go }) => (id ? <button type="button" className="plink" onClick={() => go({ type: 'person', id })}>{name}</button> : <>{name}</>);
const KV = ({ k, children }) => (<div className="kv"><span>{k}</span><div>{children ?? '—'}</div></div>);

/** Price over time: every bid is a point, so rapid bidding and jumps are obvious at a glance. */
function BidTrend({ bids, start }) {
  if (!bids.length) return <p className="faint small" style={{ margin: 0 }}>No bids yet.</p>;
  const W = 640, H = 150, P = 26;
  const amounts = bids.map((b) => Number(b.amount));
  const lo = Math.min(start, ...amounts), hi = Math.max(...amounts);
  const t0 = new Date(bids[0].at).getTime(), t1 = new Date(bids[bids.length - 1].at).getTime();
  const x = (b, i) => P + (bids.length === 1 ? (W - 2 * P) / 2 : ((t1 > t0 ? (new Date(b.at).getTime() - t0) / (t1 - t0) : i / (bids.length - 1)) * (W - 2 * P)));
  const y = (v) => H - P - (hi === lo ? 0.5 : (v - lo) / (hi - lo)) * (H - 2 * P);
  const pts = bids.map((b, i) => [x(b, i), y(Number(b.amount))]);
  const line = pts.map((p) => p.join(',')).join(' ');
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto' }} role="img" aria-label="Bid amounts over time">
      <defs><linearGradient id="trend" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#e0aa48" stopOpacity=".35" /><stop offset="1" stopColor="#e0aa48" stopOpacity="0" /></linearGradient></defs>
      <line x1={P} x2={W - P} y1={y(start)} y2={y(start)} stroke="rgba(255,92,154,.5)" strokeDasharray="4 4" />
      <text x={W - P} y={y(start) - 5} textAnchor="end" fill="#ff8fbd" fontSize="11">start {money(start, 0)}</text>
      <polygon points={`${pts[0][0]},${H - P} ${line} ${pts[pts.length - 1][0]},${H - P}`} fill="url(#trend)" />
      <polyline points={line} fill="none" stroke="#e0aa48" strokeWidth="2.5" strokeLinejoin="round" />
      {pts.map((p, i) => (<g key={bids[i].id}><circle cx={p[0]} cy={p[1]} r={i === pts.length - 1 ? 6 : 4} fill={i === pts.length - 1 ? '#ff5c9a' : '#fbe7ae'}><title>{`${bids[i].bidder} bid ${money(Number(bids[i].amount))}`}</title></circle></g>))}
      <text x={P} y={H - 6} fill="#6f6a88" fontSize="11">{fmtDateTime(bids[0].at)}</text>
      <text x={W - P} y={H - 6} fill="#6f6a88" fontSize="11" textAnchor="end">{fmtDateTime(bids[bids.length - 1].at)}</text>
      <text x={P} y={14} fill="#a7a2bd" fontSize="11">{money(hi, 0)}</text>
    </svg>
  );
}

/* ------------------------------------------------------------ detail panel */
export function AuctionDrawer({ id, onClose, onBack, go }) {
  const { loading, data: d, error } = useAsync(() => AdminApi.auctionDetail(id), [id]);
  useEffect(() => {
    const esc = (e) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', esc);
    const prev = document.body.style.overflow; document.body.style.overflow = 'hidden';
    return () => { document.removeEventListener('keydown', esc); document.body.style.overflow = prev; };
  }, [onClose]);

  const ended = d && d.schedule.end_at && new Date(d.schedule.end_at) < Date.now();
  const est = d?.ai_estimate;
  const estFlag = est && (Number(d.pricing.starting_price) > est.estimated_high ? 'above' : Number(d.pricing.starting_price) < est.estimated_low * 0.2 ? 'far below' : null);

  return (
    <div className="drawer-bg" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Auction details">
        <div className="row between" style={{ marginBottom: 14 }}>
          <span className="eyebrow">Auction #{id}</span>
          <div className="row">{onBack && <button className="btn ghost sm" onClick={onBack}>← Back</button>}<button className="btn ghost sm" onClick={onClose} aria-label="Close details"><Icon name="x" size={16} /> Close</button></div>
        </div>
        {loading && <div className="stack"><Skeleton h={120} r={14} /><Skeleton h={160} r={14} /><Skeleton h={220} r={14} /></div>}
        {error && <div className="banner" role="alert">Could not load this auction: {error.message}</div>}
        {d && (
          <div className="stack" style={{ marginTop: 0 }}>
            {/* header */}
            <div className="row" style={{ flexWrap: 'nowrap', alignItems: 'flex-start' }}>
              {d.product.images[0] ? <img src={d.product.images[0]} alt="" style={{ width: 132, height: 99, objectFit: 'cover', borderRadius: 12 }} /> : <div className="skel" style={{ width: 132, height: 99 }} />}
              <div className="grow">
                <div className="row"><Badge status={d.status} />{d.is_24_7 && <span className="badge ok">24/7 requested</span>}</div>
                <h2 style={{ margin: '6px 0 2px', fontSize: 26 }}>{d.product.name}</h2>
                <div className="mute small">{d.product.category} · {d.product.condition} · listed by <PersonLink id={d.seller.id} name={d.seller.username} go={go} /></div>
                <Link to={`/auctions/${d.id}`} className="small" style={{ color: 'var(--gold2)' }}>Open the public page →</Link>
              </div>
            </div>

            {/* the numbers */}
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(130px,1fr))', gap: 10 }}>
              <Stat label="Current bid" value={d.pricing.current_highest_bid != null ? money(d.pricing.current_highest_bid, 0) : '—'} tone="var(--gold1)" sub={`start ${money(d.pricing.starting_price, 0)} · step ${money(d.pricing.min_increment, 0)}`} />
              <Stat label="Bids" value={d.pricing.bid_count} sub={`${d.pricing.unique_bidders} bidder${d.pricing.unique_bidders === 1 ? '' : 's'}`} />
              <Stat label="Watchers" value={d.pricing.watchers} />
              <Stat label={ended ? 'Ended' : 'Time left'} value={d.schedule.end_at ? (ended ? fmtDateTime(d.schedule.end_at).split(',')[0] : <Countdown end={d.schedule.end_at} />) : '—'} />
            </div>

            {/* outcome */}
            <Section title="Outcome">
              <KV k="Leading bidder">{d.leader ? <PersonLink id={d.leader_id} name={d.leader} go={go} /> : 'No bids yet'}</KV>
              <KV k="Winner">{d.winner ? <b className="price" style={{ fontSize: 18 }}><PersonLink id={d.winner_id} name={d.winner} go={go} /></b> : d.status === 'UNSOLD' ? 'Unsold (no bids)' : 'Not decided yet'}</KV>
              <KV k="Payment">{d.payment ? <span className="row" style={{ gap: 10 }}><Badge status={d.payment.status} /> {money(d.payment.amount)} · {d.payment.provider}{d.payment.reference && <span className="faint small">ref {d.payment.reference}</span>}{d.payment.paid_at && <span className="faint small">paid {fmtDateTime(d.payment.paid_at)}</span>}</span> : d.status === 'SOLD' ? 'Invoice not created yet' : 'No payment (not sold)'}</KV>
            </Section>

            {/* bidding */}
            <Section title={`Bidding · ${d.bids.length} bid${d.bids.length === 1 ? '' : 's'}`}>
              <BidTrend bids={d.bids} start={Number(d.pricing.starting_price)} />
              {d.bids.length > 0 && (
                <div style={{ overflowX: 'auto', marginTop: 10 }}>
                  <table>
                    <thead><tr><th>#</th><th>Bidder</th><th>Amount</th><th>Raise</th><th>Time</th></tr></thead>
                    <tbody>
                      {[...d.bids].reverse().map((b, i) => (
                        <tr key={b.id} style={b.is_leader ? { color: 'var(--gold1)' } : undefined}>
                          <td className="faint">{d.bids.length - i}</td><td><PersonLink id={b.bidder_id} name={b.bidder} go={go} />{b.is_leader && <span className="badge ok" style={{ marginLeft: 8 }}>{d.status === 'SOLD' ? 'winner' : 'leading'}</span>}</td>
                          <td>{money(Number(b.amount))}</td><td className="mute">{b.increase != null ? `+${money(Number(b.increase))}` : 'opening bid'}</td><td className="small mute">{fmtDateTime(b.at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {d.bidders.length > 0 && (<>
                <div className="faint small" style={{ margin: '14px 0 6px', letterSpacing: '.1em', textTransform: 'uppercase' }}>Bidders (by highest bid)</div>
                {d.bidders.map((b) => (<div key={b.bidder} className="row between small" style={{ padding: '6px 0', borderBottom: '1px solid var(--line)' }}><span><PersonLink id={b.id} name={b.bidder} go={go} /> <span className="faint">{b.email}</span></span><span>{b.bids} bid{b.bids === 1 ? '' : 's'} · top <b>{money(Number(b.highest))}</b></span></div>))}
              </>)}
            </Section>

            {/* selling */}
            <Section title="Selling" aside={<Badge status={d.seller.verified ? 'ok' : 'warn'}>{d.seller.verified ? 'verified seller' : 'unverified'}</Badge>}>
              <KV k="Seller"><PersonLink id={d.seller.id} name={d.seller.username} go={go} /> · {d.seller.email}{d.seller.business_name && <> · {d.seller.business_name}</>}</KV>
              <KV k="Seller history">{d.seller.other_auctions} other auction{d.seller.other_auctions === 1 ? '' : 's'}, {d.seller.other_sold} sold · joined {fmtDateTime(d.seller.joined).split(',')[0]}</KV>
              <KV k="Reference price">{money(Number(d.product.reference_price))}</KV>
              <KV k="Description"><span className="mute">{d.product.description}</span></KV>
              {d.product.images.length > 1 && <div className="row" style={{ marginTop: 8 }}>{d.product.images.slice(1).map((src) => <img key={src} src={src} alt="" style={{ height: 64, borderRadius: 8 }} />)}</div>}
            </Section>

            {est && (
              <Section title="AI market estimate" aside={<Badge status={est.confidence === 'high' ? 'ok' : est.confidence === 'low' ? 'bad' : 'warn'}>{est.confidence} confidence</Badge>}>
                <KV k="Expected range"><b className="price" style={{ fontSize: 18 }}>{money(est.estimated_low, 0)} – {money(est.estimated_high, 0)}</b></KV>
                <KV k="vs starting price">{estFlag ? <span style={{ color: 'var(--gold1)' }}>⚠ Starting price {money(Number(d.pricing.starting_price), 0)} is {estFlag} the estimate</span> : <span style={{ color: 'var(--ok)' }}>✓ Starting price is in a sensible range</span>}</KV>
                {est.risks?.length > 0 && <KV k="Risks"><span className="mute">{est.risks.join(' · ')}</span></KV>}
              </Section>
            )}

            {/* schedule */}
            <Section title="Schedule">
              <KV k="Seller asked for">{d.is_24_7 ? '24/7 · admin chooses the time' : d.schedule.requested_start_at ? `${fmtDateTime(d.schedule.requested_start_at)} → ${fmtDateTime(d.schedule.requested_end_at)}` : 'No preference'}{d.schedule.seller_note && <span className="faint"> — “{d.schedule.seller_note}”</span>}</KV>
              <KV k="Allocated">{d.schedule.start_at ? <b>{fmtDateTime(d.schedule.start_at)} → {fmtDateTime(d.schedule.end_at)}</b> : <span style={{ color: 'var(--gold1)' }}>Not scheduled yet (waiting in the Scheduling queue)</span>}</KV>
              {d.schedule.scheduled_by && <KV k="Scheduled by">{d.schedule.scheduled_by} · {fmtDateTime(d.schedule.scheduled_at)}</KV>}
              {d.schedule.admin_note && <KV k="Admin note">{d.schedule.admin_note}</KV>}
              {d.time_suggestions.length > 0 && <KV k="Time suggestions">{d.time_suggestions.map((s, i) => <div key={i} className="small">{s.by} ({s.role.toLowerCase()}): {s.preferred_start ? fmtDateTime(s.preferred_start) : 'a different time'}{s.note && ` — “${s.note}”`} <Badge status={s.status === 'OPEN' ? 'warn' : 'ok'}>{s.status.toLowerCase()}</Badge></div>)}</KV>}
            </Section>

            {/* timeline */}
            <Section title="Activity log">
              {d.timeline.length === 0 ? <p className="faint small" style={{ margin: 0 }}>No recorded admin/seller actions yet.</p> : d.timeline.map((e, i) => (
                <div key={i} className="row between small" style={{ padding: '7px 0', borderBottom: '1px solid var(--line)', flexWrap: 'nowrap' }}>
                  <span><b>{label(e.action)}</b> <span className="faint">by {e.actor ?? 'system'}</span>{e.meta?.start_at && <span className="faint"> · {fmtDateTime(e.meta.start_at)} → {fmtDateTime(e.meta.end_at)}</span>}{e.meta?.reason && <span className="faint"> · “{e.meta.reason}”</span>}</span>
                  <span className="faint" style={{ whiteSpace: 'nowrap' }}>{fmtDateTime(e.at)}</span>
                </div>
              ))}
              <div className="faint small" style={{ marginTop: 8 }}>Created {fmtDateTime(d.created_at)}{d.closed_at && ` · closed ${fmtDateTime(d.closed_at)}`}</div>
            </Section>
          </div>
        )}
      </aside>
    </div>
  );
}

/* ------------------------------------------------------------ the tab */
export default function AdminAuctions({ go }) {
  const [status, setStatus] = useState('');
  const [q, setQ] = useState('');
  const [search, setSearch] = useState('');
  const [ordering, setOrdering] = useState('-created_at');
  const [page, setPage] = useState(1);

  useEffect(() => { const t = setTimeout(() => { setSearch(q); setPage(1); }, 300); return () => clearTimeout(t); }, [q]);
  const summary = useAsync(AdminApi.auctionSummary, []);
  const list = useAsync(() => AdminApi.auctionList({ status, q: search, ordering, page }), [status, search, ordering, page]);
  const s = summary.data;
  const counts = useMemo(() => s?.by_status ?? {}, [s]);

  return (
    <div className="stack">
      {s && (
        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: 12 }}>
          <Stat label="All auctions" value={s.total} />
          <Stat label="Live" value={counts.LIVE ?? 0} tone="var(--ok)" />
          <Stat label="Pending" value={counts.PENDING_APPROVAL ?? 0} tone="var(--gold1)" />
          <Stat label="Sold" value={counts.SOLD ?? 0} sub={money(s.sold_value, 0)} />
          <Stat label="Total bids" value={s.total_bids} />
          <Stat label="Paid" value={money(s.paid_value, 0)} sub={`${s.unpaid_sold} invoice${s.unpaid_sold === 1 ? '' : 's'} unpaid`} />
        </div>
      )}

      <div className="card pad">
        <div className="row" style={{ alignItems: 'stretch' }}>
          <div style={{ position: 'relative', flex: '1 1 240px' }}>
            <span style={{ position: 'absolute', left: 14, top: 13, color: 'var(--faint)' }}><Icon name="search" size={18} /></span>
            <input style={{ paddingLeft: 42 }} placeholder="Search item or seller…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search auctions" />
          </div>
          <select style={{ width: 210 }} value={ordering} onChange={(e) => { setOrdering(e.target.value); setPage(1); }} aria-label="Sort">
            <option value="-created_at">Newest first</option><option value="end_at">Ending soonest</option><option value="-current_highest_bid">Highest price</option><option value="-bid_count">Most bids</option>
          </select>
        </div>
        <div className="chips" style={{ marginTop: 12 }}>
          {STATUSES.map(([v, l]) => <button key={l} className={`chip ${status === v ? 'on' : ''}`} onClick={() => { setStatus(v); setPage(1); }}>{l}{v && counts[v] != null ? ` · ${counts[v]}` : ''}</button>)}
        </div>
      </div>

      {list.error && <div className="banner" role="alert">{list.error.message}</div>}
      {list.loading && !list.data ? <Skeleton h={320} r={16} /> : list.data && (list.data.results.length === 0 ? (
        <EmptyState icon="🔎" title="No auctions match">Try another status or search.</EmptyState>
      ) : (
        <div className="card pad" style={{ overflowX: 'auto' }}>
          <table className="clicky">
            <thead><tr><th>Item</th><th>Seller</th><th>Status</th><th>Price</th><th>Bids</th><th>Time</th><th>Winner / payment</th></tr></thead>
            <tbody>
              {list.data.results.map((r) => (
                <tr key={r.id} tabIndex={0} onClick={() => go({ type: 'auction', id: r.id })} onKeyDown={(e) => e.key === 'Enter' && go({ type: 'auction', id: r.id })} aria-label={`Open ${r.product_name}`}>
                  <td><div className="row" style={{ flexWrap: 'nowrap', gap: 10 }}>{r.image ? <img src={r.image} alt="" style={{ width: 52, height: 39, objectFit: 'cover', borderRadius: 8 }} /> : <span style={{ fontSize: 22 }}>🏺</span>}<div><b>{r.product_name}</b><div className="faint small">{r.category} · #{r.id}</div></div></div></td>
                  <td>{r.seller}</td>
                  <td><Badge status={r.status} /></td>
                  <td><b className="price">{money(Number(r.current_highest_bid ?? r.starting_price), 0)}</b>{r.current_highest_bid == null && <div className="faint small">start</div>}</td>
                  <td>{r.bid_count}<div className="faint small">{r.unique_bidders} bidder{r.unique_bidders === 1 ? '' : 's'}</div></td>
                  <td className="small">{r.status === 'LIVE' ? <Countdown end={r.end_at} /> : r.end_at ? fmtDateTime(r.end_at) : <span className="faint">not scheduled</span>}</td>
                  <td className="small">{r.winner ? <><b>{r.winner}</b><div>{r.payment_status && <Badge status={r.payment_status} />}</div></> : r.leader ? <span className="mute">leading: {r.leader}</span> : <span className="faint">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="row" style={{ marginTop: 14, justifyContent: 'center' }}>
            <button className="btn ghost sm" disabled={!list.data.previous} onClick={() => setPage(page - 1)}>← Previous</button>
            <span className="mute small">Page {page} · {list.data.count} auction{list.data.count === 1 ? '' : 's'}</span>
            <button className="btn ghost sm" disabled={!list.data.next} onClick={() => setPage(page + 1)}>Next →</button>
          </div>
        </div>
      ))}
    </div>
  );
}
