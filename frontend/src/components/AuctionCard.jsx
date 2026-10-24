import { Link, useNavigate } from 'react-router-dom';
import { Auctions } from '../api.js';
import { useAuth } from '../auth.jsx';
import { Badge, Countdown, Icon, Tilt, money, useNow, useToast } from '../ui.jsx';
import { useEffect, useState } from 'react';

/** Watch toggle shared by cards and the detail page. Persisted server-side per user. */
export function useWatch(auction, onChange) {
  const { user } = useAuth();
  const nav = useNavigate();
  const toast = useToast();
  const [watched, setWatched] = useState(!!auction.is_watched);
  const [busy, setBusy] = useState(false);
  useEffect(() => setWatched(!!auction.is_watched), [auction.id, auction.is_watched]); // data may arrive after mount
  const toggle = async (e) => {
    e?.preventDefault(); e?.stopPropagation();
    if (!user) return nav('/login', { state: { from: `/auctions/${auction.id}` } });
    if (busy) return;
    setBusy(true);
    const next = !watched;
    setWatched(next); // optimistic
    try {
      await (next ? Auctions.watch(auction.id) : Auctions.unwatch(auction.id));
      toast(next ? 'Added to your watchlist' : 'Removed from watchlist', 'ok');
      onChange?.(next);
    } catch (x) {
      setWatched(!next); toast(x.message, 'err');
    } finally { setBusy(false); }
  };
  return { watched, toggle };
}

export default function AuctionCard({ a, onWatchChange }) {
  const { watched, toggle } = useWatch(a, onWatchChange);
  const now = useNow(1000);
  const price = a.current_highest_bid ?? a.starting_price;
  const live = a.status === 'LIVE';
  const total = new Date(a.end_at) - new Date(a.start_at);
  const left = new Date(a.end_at) - now;
  const pct = live && total > 0 ? Math.max(0, Math.min(100, (left / total) * 100)) : 0;
  const hot = live && left > 0 && left < 3600000;
  return (
    <Tilt>
      <Link to={`/auctions/${a.id}`} className="card clip acard" aria-label={a.product_name}>
        <div className="shot">
          {a.product_images?.[0] ? <img src={a.product_images[0]} alt="" loading="lazy" /> : <div className="ph">🏺</div>}
          <span className="tag"><Badge status={a.status} /></span>
          <button type="button" className={`heartbtn heart ${watched ? 'on' : ''}`} onClick={toggle} aria-pressed={watched} aria-label={watched ? 'Remove from watchlist' : 'Add to watchlist'}>
            <Icon name="heart" size={18} />
          </button>
        </div>
        <div className="body">
          <div className="faint small" style={{ letterSpacing: '.08em', textTransform: 'uppercase' }}>{a.category_name}</div>
          <div style={{ fontWeight: 600, fontSize: 17, margin: '2px 0 10px', minHeight: 26 }}>{a.product_name}</div>
          <div className="row between" style={{ alignItems: 'flex-end' }}>
            <div>
              <div className="faint small">{a.current_highest_bid == null ? 'Starting at' : 'Current bid'}</div>
              <div className="price" style={{ fontSize: 24 }}>{money(price, 0)}</div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div className="faint small">{a.bid_count} bid{a.bid_count === 1 ? '' : 's'}</div>
              <div className="small" style={{ fontWeight: 600 }}>
                {a.status === 'SCHEDULED' ? `Starts ${new Date(a.start_at).toLocaleDateString()}` : live ? <><Icon name="clock" size={13} /> <Countdown end={a.end_at} /></> : 'Closed'}
              </div>
            </div>
          </div>
          {live && <div className={`meter ${hot ? 'hot' : ''}`}><i style={{ width: `${pct}%` }} /></div>}
        </div>
      </Link>
    </Tilt>
  );
}
