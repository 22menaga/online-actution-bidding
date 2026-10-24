import { Link } from 'react-router-dom';
import { Auctions } from '../api.js';
import AuctionCard from '../components/AuctionCard.jsx';
import { CardSkeletons, EmptyState, useAsync } from '../ui.jsx';

export default function Watchlist() {
  const { loading, data, reload } = useAsync(Auctions.watchlist, []);
  return (
    <div className="wrap page">
      <div className="eyebrow">Saved</div>
      <h1>Watchlist</h1>
      {loading ? <CardSkeletons n={3} /> : data.results.length === 0 ? (
        <EmptyState icon="🤍" title="Your watchlist is empty" action={<Link to="/auctions" className="btn gold">Browse auctions</Link>}>Tap the heart on any lot to keep an eye on it.</EmptyState>
      ) : (
        <div className="grid">{data.results.map((a) => <AuctionCard key={a.id} a={a} onWatchChange={(on) => { if (!on) setTimeout(reload, 300); }} />)}</div>
      )}
    </div>
  );
}
