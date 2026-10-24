import { Link } from 'react-router-dom';
import { Bids } from '../api.js';
import { Badge, Countdown, EmptyState, Skeleton, money, useAsync } from '../ui.jsx';

export default function MyBids() {
  const { loading, data } = useAsync(Bids.mine, []);

  // One row per auction: the bidder's highest bid and whether it is still winning.
  const byAuction = new Map();
  (data?.results ?? []).forEach((b) => {
    const cur = byAuction.get(b.auction);
    if (!cur || Number(b.amount) > Number(cur.amount)) byAuction.set(b.auction, { ...b, count: (cur?.count ?? 0) + 1 });
    else cur.count += 1;
  });
  const rows = [...byAuction.values()];
  const winning = rows.filter((r) => r.is_leading && r.auction_status === 'LIVE').length;

  return (
    <div className="wrap page">
      <div className="eyebrow">Activity</div>
      <h1>My bids</h1>
      {loading ? <Skeleton h={220} r={16} /> : rows.length === 0 ? (
        <EmptyState icon="🔨" title="No bids yet" action={<Link to="/auctions" className="btn gold">Find something to bid on</Link>}>Your active and past bids will be tracked here.</EmptyState>
      ) : (
        <>
          <p className="mute">You are winning <b style={{ color: 'var(--ok)' }}>{winning}</b> of {rows.length} auctions.</p>
          <div className="card pad" style={{ overflowX: 'auto' }}>
            <table>
              <thead><tr><th>Item</th><th>Your top bid</th><th>Current</th><th>Position</th><th>Ends</th></tr></thead>
              <tbody>
                {rows.map((b) => (
                  <tr key={b.auction}>
                    <td><Link to={`/auctions/${b.auction}`} style={{ fontWeight: 600 }}>{b.product_name}</Link><div className="faint small">{b.count} bid{b.count === 1 ? '' : 's'} from you</div></td>
                    <td><b>{money(Number(b.amount))}</b></td>
                    <td className="price">{money(Number(b.current_highest_bid))}</td>
                    <td>{b.auction_status === 'LIVE' ? <Badge status={b.is_leading ? 'ok' : 'bad'}>{b.is_leading ? 'Winning' : 'Outbid'}</Badge> : <Badge status={b.auction_status} />}</td>
                    <td className="small mute">{b.auction_status === 'LIVE' ? <Countdown end={b.auction_end_at} /> : 'Closed'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
