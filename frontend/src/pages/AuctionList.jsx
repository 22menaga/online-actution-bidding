import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Auctions, Products } from '../api.js';
import AuctionCard from '../components/AuctionCard.jsx';
import { CardSkeletons, EmptyState, Icon, useAsync } from '../ui.jsx';

const STATUSES = [['LIVE', 'Live now'], ['SCHEDULED', 'Upcoming'], ['SOLD', 'Sold'], ['ALL', 'All']];

export default function AuctionList() {
  // Filters live in the URL so a refresh or a shared link restores the same view.
  const [params, setParams] = useSearchParams();
  const status = params.get('status') ?? 'LIVE';
  const category = params.get('category') ?? '';
  const order = params.get('ordering') ?? 'end_at';
  const page = Number(params.get('page') ?? 1);
  const [q, setQ] = useState(params.get('q') ?? '');
  const [search, setSearch] = useState(q);

  const set = (patch) => {
    const next = new URLSearchParams(params);
    Object.entries({ page: '', ...patch }).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    setParams(next, { replace: true });
  };

  useEffect(() => { const t = setTimeout(() => { setSearch(q); set({ q }); }, 300); return () => clearTimeout(t); }, [q]); // eslint-disable-line

  const cats = useAsync(Products.categories, []);
  const { loading, data, error, reload } = useAsync(
    () => Auctions.list({ search, status: status === 'ALL' ? '' : status, ordering: order, page, product__category: category }),
    [search, status, order, page, category],
  );

  return (
    <div className="wrap page">
      <div className="eyebrow">Marketplace</div>
      <h1>Auctions</h1>

      <div className="card pad" style={{ marginBottom: 22 }}>
        <div className="row" style={{ alignItems: 'stretch' }}>
          <div style={{ position: 'relative', flex: '1 1 260px' }}>
            <span style={{ position: 'absolute', left: 14, top: 13, color: 'var(--faint)' }}><Icon name="search" size={18} /></span>
            <input style={{ paddingLeft: 42 }} placeholder="Search watches, art, cameras…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search auctions" />
          </div>
          <select style={{ width: 200 }} value={order} onChange={(e) => set({ ordering: e.target.value === 'end_at' ? '' : e.target.value })} aria-label="Sort">
            <option value="end_at">Ending soonest</option>
            <option value="-current_highest_bid">Highest price</option>
            <option value="current_highest_bid">Lowest price</option>
            <option value="-bid_count">Most bids</option>
            <option value="-created_at">Newest</option>
          </select>
        </div>
        <div className="chips" style={{ marginTop: 14 }}>
          {STATUSES.map(([v, label]) => <button key={label} className={`chip ${status === v ? 'on' : ''}`} onClick={() => set({ status: v })}>{label}</button>)}
          <span style={{ width: 1, background: 'var(--line2)', margin: '0 4px' }} />
          <button className={`chip ${!category ? 'on' : ''}`} onClick={() => set({ category: '' })}>All categories</button>
          {cats.data?.results.map((c) => <button key={c.id} className={`chip ${String(c.id) === category ? 'on' : ''}`} onClick={() => set({ category: String(c.id) })}>{c.name}</button>)}
        </div>
      </div>

      {error && (
        <div className="banner" role="alert" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Could not load auctions: {error.message}</span>
          <button className="btn ghost sm" onClick={reload}>Try again</button>
        </div>
      )}
      {loading && !data ? <CardSkeletons /> : data && (data.results.length === 0 ? (
        <EmptyState icon="🔍" title="No auctions match" action={<button className="btn ghost" onClick={() => { setQ(''); setParams({}); }}>Clear filters</button>}>Try a different search or category.</EmptyState>
      ) : (
        <>
          <p className="mute small">{data.count} result{data.count === 1 ? '' : 's'}</p>
          <div className="grid">{data.results.map((a) => <AuctionCard key={a.id} a={a} />)}</div>
          <div className="row" style={{ marginTop: 32, justifyContent: 'center' }}>
            <button className="btn ghost sm" disabled={!data.previous} onClick={() => set({ page: String(page - 1) })}>← Previous</button>
            <span className="mute small">Page {page}</span>
            <button className="btn ghost sm" disabled={!data.next} onClick={() => set({ page: String(page + 1) })}>Next →</button>
          </div>
        </>
      ))}
    </div>
  );
}
