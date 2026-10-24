import { Suspense, lazy, memo, useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Auctions, Auth, Bids, watchAuction } from '../api.js';
import { homeFor, useAuth } from '../auth.jsx';
import { useWatch } from '../components/AuctionCard.jsx';
import { AnimatedMoney, Badge, CountdownBlocks, EmptyState, Field, Icon, Skeleton, fmtDateTime, initials, maskName, money, toLocalInput, useAsync, useCountdown, useEnded, useToast } from '../ui.jsx';

const Lot3D = lazy(() => import('../scene/Lot3D.jsx'));
const Trophy3D = lazy(() => import('../scene/Trophy3D.jsx'));

/** Final-minute drama: isolated so only this tiny component re-renders every second. */
function EndPhase({ end }) {
  const { ms } = useCountdown(end);
  if (ms <= 0 || ms > 60000) return null;
  const s = Math.ceil(ms / 1000);
  const text = s <= 3 ? 'Last chance!' : s <= 10 ? 'Going twice…' : s <= 30 ? 'Going once…' : 'Final minute';
  return <div className={`phase ${s <= 30 ? 'hot' : ''}`} role="status" aria-live="polite">{text} <span style={{ fontWeight: 500 }}>· a bid now extends the auction by 2 minutes</span></div>;
}

const Viewer = memo(function Viewer({ a }) {
  const imgs = a.product_images ?? [];
  const [mode, setMode] = useState(imgs.length ? 'photo' : '3d');
  const [i, setI] = useState(0);
  return (
    <div className="card clip">
      <div className="viewer">
        <div className="tabs chips">
          {imgs.length > 0 && <button className={`chip ${mode === 'photo' ? 'on' : ''}`} onClick={() => setMode('photo')}>Photo</button>}
          <button className={`chip ${mode === '3d' ? 'on' : ''}`} onClick={() => setMode('3d')}>3D view</button>
        </div>
        {mode === 'photo' && imgs[i] ? (
          <img src={imgs[i]} alt={a.product_name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <Suspense fallback={<Skeleton h="100%" r={0} />}><Lot3D image={imgs[0]} id={a.id} pulse={a.bid_count} /></Suspense>
        )}
        {mode === '3d' && <div className="faint small" style={{ position: 'absolute', bottom: 10, left: 0, right: 0, textAlign: 'center', pointerEvents: 'none' }}>Drag to rotate</div>}
      </div>
      {imgs.length > 1 && mode === 'photo' && (
        <div className="thumbs">{imgs.map((src, k) => <img key={src} src={src} alt="" className={k === i ? 'on' : ''} onClick={() => setI(k)} />)}</div>
      )}
    </div>
  );
});

// Buyers can suggest when an upcoming auction should run. It is advisory: only an admin decides the time.
function SuggestTime({ auction }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ preferred_start: '', note: '' });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr('');
    try {
      await Auctions.suggestTime(auction.id, { note: f.note, ...(f.preferred_start ? { preferred_start: new Date(f.preferred_start).toISOString() } : {}) });
      toast('Thanks! Your suggestion was sent to the admin.', 'ok'); setOpen(false); setF({ preferred_start: '', note: '' });
    } catch (x) { setErr(x.message); } finally { setBusy(false); }
  };
  if (!open) return <button type="button" className="btn ghost sm" onClick={() => setOpen(true)}><Icon name="clock" size={16} /> Suggest a better time</button>;
  return (
    <form onSubmit={submit} className="card pad" style={{ marginTop: 10, background: 'rgba(0,0,0,.25)' }}>
      <b>Suggest a time</b>
      <p className="faint small" style={{ margin: '2px 0 0' }}>An admin decides the final schedule.</p>
      <Field label="PREFERRED START (OPTIONAL)"><input type="datetime-local" min={toLocalInput(new Date())} value={f.preferred_start} onChange={(e) => setF({ ...f, preferred_start: e.target.value })} /></Field>
      <Field label="NOTE"><input value={f.note} maxLength={500} onChange={(e) => setF({ ...f, note: e.target.value })} placeholder="e.g. Weekend evenings suit most collectors" /></Field>
      {err && <div className="err" role="alert">{err}</div>}
      <div className="row" style={{ marginTop: 12 }}><button className="btn sm" disabled={busy}>{busy ? 'Sending…' : 'Send suggestion'}</button><button type="button" className="btn ghost sm" onClick={() => setOpen(false)}>Cancel</button></div>
    </form>
  );
}

const BidHistory = memo(function BidHistory({ history }) {
  return (
    <div className="card pad">
      <div className="row between"><h3 style={{ margin: 0 }}>Bid history</h3><span className="faint small">{history.length} shown</span></div>
      {history.length === 0 ? <p className="mute small" style={{ marginTop: 14 }}>No bids yet — be the first to bid.</p> : (
        <div style={{ marginTop: 8 }}>
          {history.slice(0, 12).map((b, idx) => (
            <div key={b.id} className={`bidrow ${idx === 0 ? 'top' : ''}`}>
              <span className="avatar">{initials(b.bidder_name)}</span>
              <div className="grow"><div style={{ fontWeight: 600 }}>{b.bidder_name}</div><div className="faint small">{new Date(b.created_at).toLocaleString()}</div></div>
              <b className={idx === 0 ? 'price' : ''} style={{ fontSize: 17 }}>{money(Number(b.amount))}</b>
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

export default function AuctionDetail() {
  const { id } = useParams();
  const { user, reload: reloadUser, profiles, switchTo } = useAuth();
  const toast = useToast();
  const nav = useNavigate();

  const { loading, data: initial, error } = useAsync(() => Auctions.get(id), [id]);
  const [a, setA] = useState(null);
  const [history, setHistory] = useState([]);
  const [conn, setConn] = useState('connecting');
  const [flash, setFlash] = useState(false);
  const [amount, setAmount] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [confirm, setConfirm] = useState(false);
  const [placed, setPlaced] = useState(false); // brief "Bid placed" success state on the button
  const [resending, setResending] = useState(false);
  const [viewers, setViewers] = useState(null);
  const edited = useRef(false); // true once the bidder typed their own amount
  const me = useRef(null);
  me.current = user;

  useEffect(() => { if (initial) setA(initial); }, [initial]);
  useEffect(() => { Auctions.bids(id).then((d) => setHistory(d.results)).catch(() => {}); }, [id]);

  // Authoritative re-sync (reconnect, polling, after our own bid, when the timer hits zero).
  const refresh = useCallback(async () => {
    try {
      const [fresh, bids] = await Promise.all([Auctions.get(id), Auctions.bids(id)]);
      setA(fresh); setHistory(bids.results);
    } catch { /* keep the stale view */ }
  }, [id]);

  // Live bid stream.
  useEffect(() => watchAuction(id, (m) => {
    if (m.event === 'viewers') { setViewers(m.count); return; }
    if (m.event === 'status') { // the auction went live or closed: update at once, no refresh needed
      if (m.status === 'LIVE') toast('🔔 This auction is now live — bidding is open!', 'ok');
      else if (m.status === 'SOLD') toast(me.current && m.winner && me.current.username && maskName(me.current.username) === m.winner ? '🎉 You won this auction!' : `🔨 Sold${m.price ? ` for ${money(Number(m.price))}` : ''}`, 'ok');
      else if (m.status === 'UNSOLD') toast('This auction ended without a winning bid.');
      refresh();
      return;
    }
    if (!m.amount) return;
    const mine = me.current && m.bidder_id === me.current.id;
    setA((cur) => {
      if (!cur) return cur;
      if (cur.is_leading && !mine) toast(`You've been outbid on ${cur.product_name} — now ${money(Number(m.amount))}`, 'warn');
      return {
        ...cur,
        current_highest_bid: Number(m.amount),
        required_minimum: Number(m.amount) + cur.min_increment,
        bid_count: m.bid_count,
        end_at: m.end_at ?? cur.end_at,
        leader_name: m.bidder,
        is_leading: !!mine,
      };
    });
    setHistory((h) => [{ id: m.bid_id, bidder_name: m.bidder, amount: m.amount, created_at: new Date().toISOString() }, ...h.filter((x) => x.id !== m.bid_id)]);
    setFlash(true); setTimeout(() => setFlash(false), 900);
    if (m.extended) toast('⏱ Anti-sniping: the auction was extended by 2 minutes', 'warn');
  }, setConn), [id, toast]);

  // Poll when the socket is not live (anonymous visitors, outages).
  useEffect(() => {
    if (conn === 'live') return undefined;
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [conn, refresh]);

  const ended = useEnded(a?.end_at);
  const finalised = useRef(false);
  useEffect(() => { // when the clock reaches zero, fetch the final result (sold / unsold, winner)
    if (a && ended && a.status === 'LIVE' && !finalised.current) { finalised.current = true; setTimeout(refresh, 2500); setTimeout(refresh, 8000); }
  }, [ended, a, refresh]);

  // Keep the suggested bid at the live minimum unless the bidder is typing their own.
  useEffect(() => { if (a && !edited.current) setAmount(String(a.required_minimum ?? a.starting_price)); }, [a?.required_minimum, a?.starting_price]); // eslint-disable-line

  const watch = useWatch(a ?? {});
  const wasLeading = useRef(false); // true once this bidder has led in this session
  useEffect(() => { if (a?.is_leading) wasLeading.current = true; }, [a?.is_leading]);

  if (loading) return <div className="wrap page"><div className="split"><Skeleton h={420} r={16} /><div className="stack"><Skeleton h={40} /><Skeleton h={140} /><Skeleton h={220} /></div></div></div>;
  if (error || !a) return <div className="wrap page"><EmptyState icon="🧭" title="Auction not found" action={<Link to="/auctions" className="btn">Browse auctions</Link>}>It may have been removed or is not public yet.</EmptyState></div>;

  const min = a.required_minimum ?? a.starting_price;
  const isLive = a.status === 'LIVE' && !ended;
  const isSeller = user && a.seller === user.id;
  const iWon = user && a.winner === user.id;
  const val = Number(amount);
  const resend = async () => {
    setResending(true);
    try { const r = await Auth.resendVerification(); toast(r.detail, 'ok'); } catch (x) { toast(x.message, 'err'); } finally { setResending(false); }
  };
  const blocker = !user ? null
    : !user.email_verified ? 'Verify your email address before bidding.'
    : user.is_suspended ? 'Your account is suspended.'
    : user.role !== 'BUYER' ? 'This is a seller / admin profile. Bidding is done from a bidder profile.'
    : isSeller ? 'You cannot bid on your own auction.' : null;
  const bigJump = val > min * 2 && min > 0;

  const place = async (e) => {
    e.preventDefault();
    setErr('');
    if (!user) return nav('/login', { state: { from: `/auctions/${id}` } });
    if (!(val >= min)) return setErr(`Minimum bid is ${money(min)}.`);
    if (bigJump && !confirm) return setConfirm(true); // guard against an extra-zero typo
    setBusy(true);
    try {
      const bid = await Bids.place(a.id, val, confirm);
      edited.current = false; setConfirm(false);
      // Show the result immediately from the response; the live stream / a background refresh confirm it.
      const amt = Number(bid.amount);
      setA((cur) => cur && (cur.current_highest_bid === amt ? { ...cur, is_leading: true } : {
        ...cur, current_highest_bid: amt, required_minimum: amt + cur.min_increment, bid_count: cur.bid_count + 1, is_leading: true, leader_name: maskName(user.username),
      }));
      setHistory((h) => (h.some((x) => x.id === bid.id) ? h : [{ id: bid.id, bidder_name: maskName(user.username), amount: bid.amount, created_at: bid.created_at }, ...h]));
      setFlash(true); setTimeout(() => setFlash(false), 900);
      setPlaced(true); setTimeout(() => setPlaced(false), 1800);
      toast(`Bid of ${money(val)} placed — you're in the lead`, 'ok');
      refresh(); // background re-sync (not awaited, so the UI never waits on it)
    } catch (x) {
      setErr(x.message); setConfirm(false);
      refresh(); // someone may have outbid us in the meantime
    } finally { setBusy(false); }
  };

  const share = async () => {
    try { await navigator.clipboard.writeText(location.href); toast('Link copied to clipboard', 'ok'); } catch { toast(location.href); }
  };

  return (
    <div className="wrap page">
      <p><Link to="/auctions" className="mute small">← All auctions</Link></p>
      <div className="detail">
        <div className="d-view"><Viewer a={a} key={a.id} /></div>
        <div className="stack d-info">
          <div className="card pad">
            <h3>About this lot</h3>
            <p className="mute" style={{ whiteSpace: 'pre-wrap' }}>{a.product_description}</p>
            <div className="divider" />
            <div className="row" style={{ gap: 28 }}>
              <div><div className="faint small">CONDITION</div><b>{a.product_condition}</b></div>
              <div><div className="faint small">CATEGORY</div><b>{a.category_name}</b></div>
              <div><div className="faint small">SELLER</div><b>{a.seller_name}</b> <span className="badge ok" title="Seller identity verified"><Icon name="shield" size={12} /> verified</span></div>
            </div>
          </div>
          <BidHistory history={history} />
        </div>

        <div className="d-bid">
          <div className={`card glow pad ${flash ? 'flash' : ''}`}>
            <div className="row between"><span className="eyebrow">{a.category_name}</span><Badge status={a.status} /></div>
            <h1 style={{ fontSize: 30, margin: '8px 0 14px' }}>{a.product_name}</h1>
            <div className="faint small">{a.current_highest_bid == null ? 'Starting price' : 'Current bid'}</div>
            <AnimatedMoney className="price" style={{ fontSize: 46, display: 'block', lineHeight: 1.1 }} value={a.current_highest_bid ?? a.starting_price} />
            <div className="row between small mute" style={{ margin: '6px 0 16px' }}>
              <span>{a.bid_count} bid{a.bid_count === 1 ? '' : 's'}{a.leader_name ? ` · led by ${a.is_leading ? 'you' : a.leader_name}` : ''}</span>
              <span className="row" style={{ gap: 8 }}>{viewers > 1 && <span className="viewers" title="People watching this auction right now"><i />{viewers} watching</span>}<span><span className={`dot ${conn === 'live' ? 'live' : ''}`} />{conn === 'live' ? 'Live' : conn === 'anonymous' ? 'Log in for live updates' : conn === 'toomany' ? 'Too many open tabs' : 'Refreshing every 5s'}</span></span>
            </div>

            {a.status === 'PENDING_APPROVAL'
              ? <div className="banner info"><Icon name="clock" /> Waiting for an admin to review this listing and allocate its time.</div>
              : a.status === 'SCHEDULED'
              ? <div className="banner info"><Icon name="clock" /> Opens {fmtDateTime(a.start_at)}</div>
              : <><div className="faint small" style={{ marginBottom: 6 }}>{isLive ? 'ENDS IN' : 'ENDED'}</div><CountdownBlocks end={a.end_at} />{isLive && <EndPhase end={a.end_at} />}</>}

            <div className="divider" />

            {user && a.is_leading && isLive && <div className="state win" style={{ marginBottom: 14 }}><Icon name="check" /> You're the highest bidder</div>}
            {user && !a.is_leading && isLive && wasLeading.current && <div className="state lose" style={{ marginBottom: 14 }}>You've been outbid — raise your bid to take the lead</div>}

            {isLive && user && user.role !== 'BUYER' ? (
              <div className="banner info" style={{ flexDirection: 'column' }}>
                <div><b>This is a {user.role === 'SELLER' ? 'seller' : 'admin'} profile.</b> Bidding is done from a bidder profile.</div>
                <div className="row">
                  {profiles.filter((p) => p.role === 'BUYER').map((p) => <button type="button" key={p.id} className="btn sm" onClick={async () => { const me = await switchTo(p.id); if (me) toast(`Now bidding as ${me.username}`, 'ok'); }}>Switch to {p.username}</button>)}
                  <Link to="/register?add=1&role=BUYER" className="btn ghost sm">Create a bidder profile</Link>
                </div>
              </div>
            ) : isLive ? (
              <form onSubmit={place} noValidate>
                {user && !user.email_verified ? (
                  <div className="banner" style={{ marginBottom: 12, flexDirection: 'column' }}>
                    <div><b>{blocker}</b> We sent a link to {user.email}. In local development the link is printed in the backend terminal.</div>
                    <div className="row">
                      <button type="button" className="btn ghost sm" disabled={resending} onClick={resend}>{resending ? 'Sending…' : 'Resend email'}</button>
                      <button type="button" className="btn sm" onClick={reloadUser}>I verified — refresh</button>
                    </div>
                  </div>
                ) : blocker && user?.role !== 'BUYER' ? (
                  <div className="banner info" style={{ marginBottom: 12, flexDirection: 'column' }}>
                    <div><b>{blocker}</b></div>
                    <div className="row">
                      {profiles.filter((p) => p.role === 'BUYER').map((p) => <button type="button" key={p.id} className="btn sm" onClick={async () => { const me = await switchTo(p.id); if (me) toast(`Now bidding as ${me.username}`, 'ok'); }}>Switch to {p.username}</button>)}
                      <Link to="/register?add=1&role=BUYER" className="btn ghost sm">Create a bidder profile</Link>
                    </div>
                  </div>
                ) : blocker && <div className="banner" style={{ marginBottom: 12 }}>{blocker}</div>}
                <label htmlFor="bid" style={{ marginTop: 0 }}>YOUR BID · minimum {money(min)} · step {money(a.min_increment)}</label>
                <div className="row" style={{ flexWrap: 'nowrap' }}>
                  <div style={{ position: 'relative', flex: 1 }}>
                    <span style={{ position: 'absolute', left: 14, top: 12, color: 'var(--gold2)', fontWeight: 700 }}>₹</span>
                    <input id="bid" inputMode="decimal" type="number" step="0.01" min={min} style={{ paddingLeft: 28, fontSize: 18, fontWeight: 700 }} value={amount} disabled={!!blocker}
                      onChange={(e) => { edited.current = true; setConfirm(false); setAmount(e.target.value); }} />
                  </div>
                  <button className={`btn ${placed ? 'ok' : confirm ? 'pink' : 'gold'}`} disabled={busy || !!blocker} style={{ whiteSpace: 'nowrap', minWidth: 130 }}>
                    {busy ? 'Placing…' : placed ? <><Icon name="check" size={18} /> Bid placed</> : confirm ? 'Confirm bid' : <><Icon name="gavel" size={18} /> Place bid</>}
                  </button>
                </div>
                <div className="chips" style={{ marginTop: 10 }}>
                  {[0, 1, 2, 5].map((k) => (
                    <button type="button" key={k} className="chip" disabled={!!blocker} onClick={() => { edited.current = true; setConfirm(false); setAmount(String(+(min + k * a.min_increment).toFixed(2))); }}>
                      {k === 0 ? `Min ${money(min, 0)}` : `+${money(k * a.min_increment, 0)}`}
                    </button>
                  ))}
                </div>
                {confirm && <div className="banner" style={{ marginTop: 12 }}>That is more than double the minimum bid. Tap “Confirm bid” to place {money(val)}.</div>}
                {err && <div className="err" role="alert">{err}</div>}
                {!user && <p className="mute small" style={{ marginTop: 12 }}>You'll be asked to log in or join free to bid.</p>}
                <p className="faint small" style={{ marginTop: 12 }}><Icon name="shield" size={13} /> Bids are binding. Late bids automatically extend the auction by 2 minutes.</p>
              </form>
            ) : (
              <div className="stack">
                <p className="mute" style={{ margin: 0 }}>
                  {a.status === 'SOLD' ? (iWon ? '🎉 Congratulations — you won this auction!' : `Sold for ${money(a.current_highest_bid)}.`)
                    : a.status === 'UNSOLD' ? 'This auction ended without a winning bid.'
                    : a.status === 'SCHEDULED' ? 'Bidding opens when the auction starts.'
                    : a.status === 'LIVE' ? 'Finalising results…' : 'Bidding is closed.'}
                </p>
                {iWon && <Suspense fallback={null}><Trophy3D height={190} /></Suspense>}
                {iWon && <Link to="/payments" className="btn gold block lg">Complete payment · {money(a.current_highest_bid)}</Link>}
              </div>
            )}

            {a.status === 'SCHEDULED' && user && !isSeller && user.role !== 'ADMIN' && a.bid_count === 0 && <div style={{ marginTop: 14 }}><SuggestTime auction={a} /></div>}
            <div className="row" style={{ marginTop: 18 }}>
              <button type="button" className={`btn ghost sm ${watch.watched ? 'pink' : ''}`} onClick={watch.toggle}><Icon name="heart" size={16} /> {watch.watched ? 'Watching' : 'Watch'}</button>
              <button type="button" className="btn ghost sm" onClick={share}><Icon name="share" size={16} /> Share</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
