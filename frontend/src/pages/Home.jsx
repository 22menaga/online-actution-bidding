import { Suspense, lazy, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Auctions } from '../api.js';
import AuctionCard from '../components/AuctionCard.jsx';
import { CardSkeletons, Icon, Tilt, money, useAsync } from '../ui.jsx';

const Hero3D = lazy(() => import('../scene/Hero3D.jsx')); // keeps three.js out of the main bundle
const MarketSkyline = lazy(() => import('../scene/MarketSkyline.jsx'));

const STEPS = [
  ['01', 'bolt', 'Find a lot', 'Browse verified listings with real photos, condition notes and live prices.'],
  ['02', 'gavel', 'Bid with confidence', 'Every bid is checked on the server, timestamped and shown instantly to all bidders.'],
  ['03', 'lock', 'Win and pay securely', 'Pay through encrypted checkout. Your receipt and the seller handover are tracked for you.'],
];

export default function Home() {
  const nav = useNavigate();
  const [selected, setSelected] = useState(0);
  const { loading, data, error, reload } = useAsync(() => Auctions.list({ status: 'LIVE', ordering: 'end_at' }), []);
  const live = data?.results ?? [];
  const totalBids = live.reduce((n, a) => n + (a.bid_count ?? 0), 0);
  const wide = typeof matchMedia === 'function' && matchMedia('(min-width: 640px)').matches;

  return (
    <>
      <section className="hero">
        {live.length > 0 && wide && (
          <Suspense fallback={null}>
            <Hero3D auctions={live.slice(0, 8)} selected={selected} onSelect={setSelected} onOpen={(a) => nav(`/auctions/${a.id}`)} />
          </Suspense>
        )}
        <div className="copy">
          <div className="wrap">
            <div>
              <div className="eyebrow">Live online auctions · open 24/7</div>
              <h1>Rare finds. <span className="gold-text">Real-time</span> bidding.</h1>
              <p className="mute" style={{ fontSize: 17, maxWidth: 480 }}>Bid on antiques, art, jewellery and collectibles from verified sellers. Watch the price move live and never lose a lot to a last-second snipe.</p>
              <div className="row" style={{ marginTop: 22 }}>
                <Link to="/auctions" className="btn gold lg">Explore live auctions</Link>
                <Link to="/register" className="btn ghost lg">Create free account</Link>
              </div>
              <div className="stats">
                <div><b className="gold-text">{live.length}</b><span>Live lots</span></div>
                <div><b className="gold-text">{totalBids}</b><span>Bids placed</span></div>
                <div><b className="gold-text">{totalBids > 0 ? money(live.reduce((m, a) => Math.max(m, a.current_highest_bid ?? 0), 0), 0) : '—'}</b><span>Top bid</span></div>
              </div>
            </div>
          </div>
        </div>
        {live.length > 0 && wide && <div className="hint">Drag to spin · click a card to bring it forward · click again to open</div>}
      </section>

      <div className="wrap page">
        <div className="row between" style={{ marginBottom: 18 }}>
          <div><div className="eyebrow">Closing soon</div><h2 style={{ margin: 0 }}>Ending soon</h2></div>
          <Link to="/auctions" className="btn ghost sm">View all →</Link>
        </div>
        {error ? (
          <div className="banner" role="alert" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <span>Could not load live auctions: {error.message}</span>
            <button className="btn ghost sm" onClick={reload}>Try again</button>
          </div>
        ) : loading ? <CardSkeletons n={4} /> : live.length === 0 ? (
          <div className="card empty"><div className="ico">🔔</div><h3>No live auctions right now</h3><p className="mute">New lots go live every day — check back soon.</p></div>
        ) : <div className="grid">{live.slice(0, 8).map((a) => <AuctionCard key={a.id} a={a} />)}</div>}

        {live.length > 1 && wide && (
          <div style={{ marginTop: 64 }}>
            <div className="row between" style={{ marginBottom: 14 }}>
              <div><div className="eyebrow">Market skyline</div><h2 style={{ margin: 0 }}>Live prices at a glance</h2></div>
              <span className="faint small">Taller = higher bid · <span style={{ color: 'var(--pink)' }}>pink</span> = ends within the hour · click a tower to open it</span>
            </div>
            <div className="card clip" style={{ height: 420 }}>
              <Suspense fallback={null}><MarketSkyline auctions={live} onOpen={(a) => nav(`/auctions/${a.id}`)} /></Suspense>
            </div>
          </div>
        )}

        <div style={{ marginTop: 72 }}>
          <div className="center" style={{ marginBottom: 28 }}><div className="eyebrow">How it works</div><h2>Three steps to your next treasure</h2></div>
          <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))' }}>
            {STEPS.map(([n, icon, title, copy]) => (
              <Tilt key={n} max={5}>
                <div className="card glow step">
                  <div className="row between"><span className="gold-text n">{n}</span><span style={{ color: 'var(--gold2)' }}><Icon name={icon} size={30} /></span></div>
                  <h3>{title}</h3><p className="mute" style={{ margin: 0 }}>{copy}</p>
                </div>
              </Tilt>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
