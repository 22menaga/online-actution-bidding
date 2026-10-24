import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Payments as PaymentsApi } from '../api.js';
import PayModal from '../components/PayModal.jsx';
import { Badge, Confetti, EmptyState, Icon, Skeleton, money, useAsync, useToast } from '../ui.jsx';

export default function Payments() {
  const toast = useToast();
  const { loading, data, reload } = useAsync(PaymentsApi.list, []);
  const [celebrate, setCelebrate] = useState(false);
  const synced = useRef(false);

  // If the tab was closed after paying, ask the server to reconcile any open Razorpay orders once.
  useEffect(() => {
    if (!data || synced.current) return;
    synced.current = true;
    const open = data.results.filter((p) => p.status === 'PROCESSING' && p.provider === 'razorpay');
    if (!open.length) return;
    Promise.all(open.map((p) => PaymentsApi.sync(p.id).catch(() => p))).then((res) => {
      if (res.some((p) => p.status === 'SUCCESS')) { toast('Payment confirmed', 'ok'); window.dispatchEvent(new Event('notifications:changed')); reload(); }
    });
  }, [data]); // eslint-disable-line

  const [paying, setPaying] = useState(null);
  const onPaid = (method) => {
    setPaying(null);
    setCelebrate(true); setTimeout(() => setCelebrate(false), 5000);
    toast(method === 'coins' ? 'Paid with coins — thank you!' : 'Payment successful — thank you!', 'ok');
    window.dispatchEvent(new Event('notifications:changed')); window.dispatchEvent(new Event('wallet:changed'));
    reload();
  };

  const rows = data?.results ?? [];
  const due = rows.filter((p) => ['PENDING', 'PROCESSING'].includes(p.status));
  const paid = rows.filter((p) => p.status === 'SUCCESS');

  return (
    <div className="wrap page">
      <Confetti run={celebrate} />
      {paying && <PayModal payment={paying} onClose={() => setPaying(null)} onDone={onPaid} />}
      <div className="eyebrow">Orders</div>
      <h1>Payments</h1>
      {loading ? <Skeleton h={220} r={16} /> : rows.length === 0 ? (
        <EmptyState icon="🧾" title="Nothing to pay yet" action={<Link to="/auctions" className="btn gold">Browse auctions</Link>}>Win an auction and your invoice will appear here.</EmptyState>
      ) : (
        <>
          <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', marginBottom: 22 }}>
            <div className="card pad"><div className="faint small">AMOUNT DUE</div><div className="price" style={{ fontSize: 32 }}>{money(due.reduce((n, p) => n + Number(p.amount), 0))}</div><div className="mute small">{due.length} invoice{due.length === 1 ? '' : 's'}</div></div>
            <div className="card pad"><div className="faint small">TOTAL PAID</div><div className="price" style={{ fontSize: 32 }}>{money(paid.reduce((n, p) => n + Number(p.amount), 0))}</div><div className="mute small">{paid.length} completed</div></div>
          </div>
          <div className="card pad" style={{ overflowX: 'auto' }}>
            <table>
              <thead><tr><th>Item</th><th>Amount</th><th>Status</th><th>Date</th><th /></tr></thead>
              <tbody>
                {rows.map((p) => (
                  <tr key={p.id}>
                    <td><Link to={`/auctions/${p.auction}`} style={{ fontWeight: 600 }}>{p.product_name}</Link>{p.transaction_reference && <div className="faint small">Ref {p.transaction_reference}</div>}</td>
                    <td><b className="price">{money(Number(p.amount))}</b></td>
                    <td><Badge status={p.status} /></td>
                    <td className="small mute">{new Date(p.created_at).toLocaleDateString()}</td>
                    <td style={{ textAlign: 'right' }}>
                      {['PENDING', 'PROCESSING'].includes(p.status) && (
                        <button className="btn gold sm" onClick={() => setPaying(p)}><Icon name="lock" size={14} /> Pay now</button>
                      )}
                      {p.status === 'SUCCESS' && <span className="small mute">Paid {new Date(p.paid_at).toLocaleDateString()}</span>}
                      {p.status === 'FAILED' && <Link className="btn ghost sm" to={`/auctions/${p.auction}`}>View</Link>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="faint small" style={{ marginTop: 14 }}><Icon name="lock" size={13} /> Pay with coins, Razorpay (UPI, cards, netbanking, wallets) or a fake test payment. We never see your card details.</p>
        </>
      )}
    </div>
  );
}
