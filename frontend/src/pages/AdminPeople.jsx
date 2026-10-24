import { useEffect, useState } from 'react';
import { Admin as AdminApi } from '../api.js';
import { Badge, EmptyState, Icon, Skeleton, fmtDateTime, initials, money, useAsync, useToast } from '../ui.jsx';

const ROLE = { SELLER: 'Seller', BUYER: 'Bidder' };
const FILTERS = [['', '', 'Everyone'], ['SELLER', '', 'Sellers'], ['BUYER', '', 'Bidders'], ['', 'unverified', 'Needs verification'], ['', 'suspended', 'Suspended']];
const label = (s) => String(s || '').replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
const KV = ({ k, children }) => (<div className="kv"><span>{k}</span><div>{children ?? '—'}</div></div>);
const Num = ({ label: l, value, tone }) => (<div className="card kpi"><b style={tone ? { color: tone } : undefined}>{value}</b><span>{l}</span></div>);

function Section({ title, aside, children }) {
  return (
    <div className="card pad" style={{ background: 'rgba(0,0,0,.22)' }}>
      <div className="row between" style={{ marginBottom: 8 }}><h3 style={{ margin: 0, fontSize: 16 }}>{title}</h3>{aside}</div>
      {children}
    </div>
  );
}

const AuctionLink = ({ id, name, go }) => <button type="button" className="plink" onClick={() => go({ type: 'auction', id })}>{name}</button>;

/* ------------------------------------------------------------ profile panel */
export function PersonDrawer({ id, onClose, onBack, go }) {
  const toast = useToast();
  const { loading, data: d, error, reload } = useAsync(() => AdminApi.personDetail(id), [id]);
  const [reason, setReason] = useState('');
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const esc = (e) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', esc);
    const prev = document.body.style.overflow; document.body.style.overflow = 'hidden';
    return () => { document.removeEventListener('keydown', esc); document.body.style.overflow = prev; };
  }, [onClose]);

  const setSuspended = async (suspended) => {
    setBusy(true);
    try { await AdminApi.suspendPerson(id, suspended, reason); toast(suspended ? 'Account suspended' : 'Account restored', 'ok'); setAsking(false); setReason(''); await reload(); } catch (x) { toast(x.message, 'err'); } finally { setBusy(false); }
  };

  const s = d?.selling, b = d?.bidding;
  return (
    <div className="drawer-bg" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Person details">
        <div className="row between" style={{ marginBottom: 14 }}>
          <span className="eyebrow">{d ? ROLE[d.role] : 'Profile'} profile</span>
          <div className="row">{onBack && <button className="btn ghost sm" onClick={onBack}>← Back</button>}<button className="btn ghost sm" onClick={onClose} aria-label="Close details"><Icon name="x" size={16} /> Close</button></div>
        </div>
        {loading && <div className="stack"><Skeleton h={110} r={14} /><Skeleton h={200} r={14} /><Skeleton h={240} r={14} /></div>}
        {error && <div className="banner" role="alert">Could not load this profile: {error.message}</div>}
        {d && (
          <div className="stack" style={{ marginTop: 0 }}>
            <div className="row" style={{ flexWrap: 'nowrap', alignItems: 'flex-start', gap: 16 }}>
              <span className="avatar" style={{ width: 64, height: 64, fontSize: 22 }}>{initials(d.username)}</span>
              <div className="grow">
                <div className="row"><span className={`rolechip ${d.role}`}>{ROLE[d.role]}</span>
                  <Badge status={d.email_verified ? 'ok' : 'warn'}>{d.email_verified ? 'email verified' : 'email not verified'}</Badge>
                  {d.role === 'SELLER' && <Badge status={d.profile.approved ? 'ok' : 'warn'}>{d.profile.approved ? 'verified seller' : 'seller not verified'}</Badge>}
                  {d.is_suspended && <Badge status="bad">suspended</Badge>}</div>
                <h2 style={{ margin: '6px 0 2px', fontSize: 26 }}>{d.username}</h2>
                <div className="mute small">{d.email}</div>
              </div>
            </div>

            <Section title="Account & contact">
              <KV k="Joined">{fmtDateTime(d.joined)}</KV>
              <KV k="Last login">{d.last_login ? fmtDateTime(d.last_login) : 'Never'}</KV>
              {d.role === 'SELLER' && <KV k="Business">{d.profile.business_name || <span className="faint">not provided</span>}</KV>}
              <KV k="Phone">{d.profile.phone || <span className="faint">not provided</span>}</KV>
              <KV k={d.role === 'SELLER' ? 'Pickup address' : 'Delivery address'}>{d.profile.address ? <span style={{ whiteSpace: 'pre-wrap' }}>{d.profile.address}</span> : <span className="faint">not provided</span>}</KV>
              <KV k="Watchlist">{d.watchlist} item{d.watchlist === 1 ? '' : 's'}</KV>
              {d.role === 'SELLER' && d.profile.rejection_reason && <KV k="Last rejection note"><span style={{ color: 'var(--bad)' }}>{d.profile.rejection_reason}</span></KV>}
            </Section>

            {/* ---------------- seller view */}
            {s && (<>
              <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(120px,1fr))', gap: 10 }}>
                <Num label="Listed" value={s.totals.listed} /><Num label="Live" value={s.totals.live} tone="var(--ok)" /><Num label="Sold" value={s.totals.sold} />
                <Num label="Bids received" value={s.totals.total_bids_received} /><Num label="Sales value" value={money(Number(s.totals.sales_value), 0)} tone="var(--gold1)" /><Num label="Paid to date" value={money(Number(s.totals.paid_value), 0)} />
              </div>
              <Section title={`Identity verification · ${s.verifications.length} submission${s.verifications.length === 1 ? '' : 's'}`}>
                {s.verifications.length === 0 ? <p className="faint small" style={{ margin: 0 }}>No documents submitted.</p> : s.verifications.map((v, i) => (
                  <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--line)' }}>
                    <div className="row between"><b>{v.legal_name}</b><Badge status={v.status === 'APPROVED' ? 'ok' : v.status === 'REJECTED' ? 'bad' : 'warn'}>{v.status.toLowerCase()}</Badge></div>
                    <div className="small mute">{v.document_type} · ref {v.document_reference} · submitted {fmtDateTime(v.submitted)}{v.reviewed && ` · reviewed ${fmtDateTime(v.reviewed)}`}</div>
                    {v.notes && <div className="small" style={{ color: 'var(--gold1)' }}>Note: {v.notes}</div>}
                  </div>
                ))}
              </Section>
              <Section title={`Auctions · ${s.auctions.length}`}>
                {s.auctions.length === 0 ? <p className="faint small" style={{ margin: 0 }}>No auctions yet.</p> : (
                  <div style={{ overflowX: 'auto' }}><table><thead><tr><th>Item</th><th>Status</th><th>Price</th><th>Bids</th><th>Winner / payment</th></tr></thead><tbody>
                    {s.auctions.map((a) => (<tr key={a.id}><td><AuctionLink id={a.id} name={a.name} go={go} /></td><td><Badge status={a.status} /></td><td><b className="price">{money(Number(a.current_bid ?? a.starting_price), 0)}</b></td><td>{a.bids}</td><td className="small">{a.winner ? <>{a.winner} {a.payment_status && <Badge status={a.payment_status} />}</> : <span className="faint">—</span>}</td></tr>))}
                  </tbody></table></div>
                )}
              </Section>
              <Section title={`Products · ${s.products.length}`}>
                {s.products.map((p) => (<div key={p.id} className="row between small" style={{ padding: '7px 0', borderBottom: '1px solid var(--line)' }}><span><b>{p.name}</b> <span className="faint">{p.category} · reference {money(Number(p.reference_price), 0)}{p.ai_low != null && ` · AI ${money(p.ai_low, 0)}–${money(p.ai_high, 0)}`}</span></span><Badge status={p.status} /></div>))}
              </Section>
            </>)}

            {/* ---------------- bidder view */}
            {b && (<>
              <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(120px,1fr))', gap: 10 }}>
                <Num label="Bids placed" value={b.totals.bids} /><Num label="Auctions joined" value={b.totals.auctions_bid_on} /><Num label="Leading now" value={b.totals.leading_now} tone="var(--ok)" />
                <Num label="Won" value={b.totals.wins} tone="var(--gold1)" /><Num label="Paid" value={money(Number(b.totals.paid), 0)} /><Num label="Unpaid" value={money(Number(b.totals.unpaid), 0)} tone={b.totals.unpaid > 0 ? 'var(--bad)' : undefined} />
              </div>
              {b.totals.failed_payments > 0 && <div className="banner"><Icon name="lock" /> {b.totals.failed_payments} failed payment{b.totals.failed_payments === 1 ? '' : 's'} on this account.</div>}
              {b.leading_now.length > 0 && <Section title="Currently leading">{b.leading_now.map((a) => (<div key={a.id} className="row between small" style={{ padding: '6px 0', borderBottom: '1px solid var(--line)' }}><AuctionLink id={a.id} name={a.name} go={go} /><b className="price">{money(Number(a.bid), 0)}</b></div>))}</Section>}
              <Section title={`Won auctions · ${b.wins.length}`}>
                {b.wins.length === 0 ? <p className="faint small" style={{ margin: 0 }}>Nothing won yet.</p> : b.wins.map((a) => (<div key={a.id} className="row between small" style={{ padding: '6px 0', borderBottom: '1px solid var(--line)' }}><AuctionLink id={a.id} name={a.name} go={go} /><span><b className="price">{money(Number(a.price), 0)}</b> <span className="faint">{a.closed_at && fmtDateTime(a.closed_at)}</span></span></div>))}
              </Section>
              <Section title={`Payments · ${b.payments.length}`}>
                {b.payments.length === 0 ? <p className="faint small" style={{ margin: 0 }}>No invoices.</p> : (
                  <div style={{ overflowX: 'auto' }}><table><thead><tr><th>Item</th><th>Amount</th><th>Status</th><th>Reference</th></tr></thead><tbody>
                    {b.payments.map((p) => (<tr key={p.id}><td><AuctionLink id={p.auction} name={p.name} go={go} /></td><td><b className="price">{money(Number(p.amount), 0)}</b></td><td><Badge status={p.status} /></td><td className="small faint">{p.reference || p.provider}{p.paid_at && ` · ${fmtDateTime(p.paid_at)}`}</td></tr>))}
                  </tbody></table></div>
                )}
              </Section>
              <Section title={`Recent bids · ${b.recent_bids.length}${b.totals.bids > b.recent_bids.length ? ` of ${b.totals.bids}` : ''}`}>
                {b.recent_bids.length === 0 ? <p className="faint small" style={{ margin: 0 }}>No bids yet.</p> : b.recent_bids.map((r, i) => (<div key={i} className="row between small" style={{ padding: '6px 0', borderBottom: '1px solid var(--line)', flexWrap: 'nowrap' }}><span><AuctionLink id={r.auction} name={r.name} go={go} /> <Badge status={r.auction_status} /></span><span style={{ whiteSpace: 'nowrap' }}><b>{money(Number(r.amount), 0)}</b> <span className="faint">{fmtDateTime(r.at)}</span></span></div>))}
              </Section>
            </>)}

            {d.wallet && (
              <Section title="Coin wallet" aside={<span className="coinpill">🪙 {Number(d.wallet.balance).toLocaleString('en-IN', { maximumFractionDigits: 2 })}</span>}>
                {d.wallet.transactions.length === 0 ? <p className="faint small" style={{ margin: 0 }}>No coin activity.</p> : d.wallet.transactions.map((t, i) => (
                  <div key={i} className="row between small" style={{ padding: '6px 0', borderBottom: '1px solid var(--line)', flexWrap: 'nowrap' }}>
                    <span><b>{label(t.kind)}</b> <span className="faint">{t.description}</span></span>
                    <span style={{ whiteSpace: 'nowrap' }}><b style={{ color: Number(t.amount) > 0 ? 'var(--ok)' : 'var(--bad)' }}>{Number(t.amount) > 0 ? '+' : ''}{Number(t.amount).toLocaleString('en-IN')}</b> <span className="faint">{fmtDateTime(t.at)}</span></span>
                  </div>
                ))}
              </Section>
            )}

            <Section title="Recent account activity">
              {d.security.length === 0 ? <p className="faint small" style={{ margin: 0 }}>No recorded actions.</p> : d.security.map((e, i) => (<div key={i} className="row between small" style={{ padding: '6px 0', borderBottom: '1px solid var(--line)', flexWrap: 'nowrap' }}><span><b>{label(e.action)}</b> <span className="faint">{e.object}{e.ip && ` · ${e.ip}`}</span></span><span className="faint" style={{ whiteSpace: 'nowrap' }}>{fmtDateTime(e.at)}</span></div>))}
            </Section>

            <Section title="Account control" aside={d.is_suspended ? <Badge status="bad">suspended</Badge> : <Badge status="ok">active</Badge>}>
              <p className="mute small" style={{ marginTop: 0 }}>A suspended account cannot bid, list items or pay. The reason is saved in the audit log and the user is notified.</p>
              {d.is_suspended ? (
                <button className="btn gold sm" disabled={busy} onClick={() => setSuspended(false)}>{busy ? 'Working…' : 'Restore account'}</button>
              ) : asking ? (
                <div>
                  <input value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} placeholder="Reason (required)" autoFocus />
                  <div className="row" style={{ marginTop: 8 }}><button className="btn pink sm" disabled={busy || !reason.trim()} onClick={() => setSuspended(true)}>Confirm suspension</button><button className="btn ghost sm" onClick={() => setAsking(false)}>Cancel</button></div>
                </div>
              ) : <button className="btn ghost sm" onClick={() => setAsking(true)}>Suspend account…</button>}
            </Section>
          </div>
        )}
      </aside>
    </div>
  );
}

/* ------------------------------------------------------------ the tab */
export default function AdminPeople({ go }) {
  const [f, setF] = useState(0);
  const [q, setQ] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  useEffect(() => { const t = setTimeout(() => { setSearch(q); setPage(1); }, 300); return () => clearTimeout(t); }, [q]);
  const [role, state] = FILTERS[f];
  const { loading, data, error } = useAsync(() => AdminApi.personList({ role, state, q: search, page }), [role, state, search, page]);

  return (
    <div className="stack">
      <div className="card pad">
        <div style={{ position: 'relative' }}>
          <span style={{ position: 'absolute', left: 14, top: 13, color: 'var(--faint)' }}><Icon name="search" size={18} /></span>
          <input style={{ paddingLeft: 42 }} placeholder="Search by username or email…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search people" />
        </div>
        <div className="chips" style={{ marginTop: 12 }}>{FILTERS.map(([, , l], i) => <button key={l} className={`chip ${f === i ? 'on' : ''}`} onClick={() => { setF(i); setPage(1); }}>{l}</button>)}</div>
      </div>
      {error && <div className="banner" role="alert">{error.message}</div>}
      {loading && !data ? <Skeleton h={300} r={16} /> : data && (data.results.length === 0 ? <EmptyState icon="👥" title="No one matches">Try another filter or search.</EmptyState> : (
        <div className="card pad" style={{ overflowX: 'auto' }}>
          <table className="clicky">
            <thead><tr><th>Person</th><th>Type</th><th>Status</th><th>Activity</th><th>Joined</th><th>Last login</th></tr></thead>
            <tbody>
              {data.results.map((u) => (
                <tr key={u.id} tabIndex={0} onClick={() => go({ type: 'person', id: u.id })} onKeyDown={(e) => e.key === 'Enter' && go({ type: 'person', id: u.id })} aria-label={`Open ${u.username}`}>
                  <td><div className="row" style={{ flexWrap: 'nowrap', gap: 10 }}><span className="avatar sm">{initials(u.username)}</span><div><b>{u.username}</b><div className="faint small">{u.email}</div></div></div></td>
                  <td><span className={`rolechip ${u.role}`}>{ROLE[u.role]}</span></td>
                  <td className="small"><div className="row" style={{ gap: 6 }}>{u.is_suspended && <Badge status="bad">suspended</Badge>}{!u.email_verified && <Badge status="warn">email?</Badge>}{u.role === 'SELLER' && !u.seller_verified && <Badge status="warn">unverified</Badge>}{!u.is_suspended && u.email_verified && (u.role !== 'SELLER' || u.seller_verified) && <Badge status="ok">good</Badge>}</div></td>
                  <td className="small">{u.role === 'SELLER' ? <>{u.listings} listed · <b>{u.sold}</b> sold</> : <>{u.bids} bids · <b>{u.wins}</b> won</>}</td>
                  <td className="small mute">{fmtDateTime(u.joined)}</td>
                  <td className="small mute">{u.last_login ? fmtDateTime(u.last_login) : 'never'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="row" style={{ marginTop: 14, justifyContent: 'center' }}>
            <button className="btn ghost sm" disabled={!data.previous} onClick={() => setPage(page - 1)}>← Previous</button>
            <span className="mute small">Page {page} · {data.count} {data.count === 1 ? 'person' : 'people'}</span>
            <button className="btn ghost sm" disabled={!data.next} onClick={() => setPage(page + 1)}>Next →</button>
          </div>
        </div>
      ))}
    </div>
  );
}
