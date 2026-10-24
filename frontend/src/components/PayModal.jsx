import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Payments as PaymentsApi } from '../api.js';
import { openRazorpay } from '../razorpay.js';
import { Badge, Icon, Skeleton, money, useAsync } from '../ui.jsx';

export const coins = (n) => Number(n ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 2 });

/**
 * Payment-method chooser for one invoice. "Routes" the payment: coins from the wallet, Razorpay, or a fake test payment.
 * Every route ends the same way: the server confirms the payment, then onDone() refreshes the page.
 */
export default function PayModal({ payment, onClose, onDone }) {
  const { loading, data } = useAsync(PaymentsApi.methods, []);
  const [busy, setBusy] = useState(null);
  const [err, setErr] = useState('');
  const amount = Number(payment.amount);

  useEffect(() => {
    const esc = (e) => e.key === 'Escape' && !busy && onClose();
    document.addEventListener('keydown', esc);
    const prev = document.body.style.overflow; document.body.style.overflow = 'hidden';
    return () => { document.removeEventListener('keydown', esc); document.body.style.overflow = prev; };
  }, [onClose, busy]);

  const methods = Object.fromEntries((data?.methods ?? []).map((m) => [m.id, m]));
  const coinCost = data ? amount / data.coin_value : amount;
  const enough = methods.coins && Number(methods.coins.balance) >= coinCost;

  const run = async (id, fn) => {
    setBusy(id); setErr('');
    try { await fn(); onDone(id); } catch (x) { if (!x.dismissed) setErr(x.message); } finally { setBusy(null); }
  };

  const withCoins = () => run('coins', () => PaymentsApi.payCoins(payment.id));
  const withFake = () => run('fake', async () => { await PaymentsApi.checkout(payment.id, 'fake'); await PaymentsApi.mockPay(payment.id, 'success'); });
  const declineFake = () => run('fake-decline', async () => { await PaymentsApi.checkout(payment.id, 'fake'); await PaymentsApi.mockPay(payment.id, 'fail'); throw new Error('The fake card was declined (simulated). Choose a method to try again.'); });
  const withRazorpay = () => run('razorpay', async () => {
    const co = await PaymentsApi.checkout(payment.id, 'razorpay');
    const response = await openRazorpay(co); // Razorpay's own secure window
    await PaymentsApi.verify(payment.id, response); // server verifies the signature and amount before marking paid
  });

  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label="Choose how to pay">
        <div className="row between" style={{ marginBottom: 6 }}>
          <div><div className="eyebrow">Pay invoice #{payment.id}</div><h2 style={{ margin: '2px 0 0', fontSize: 24 }}>{payment.product_name}</h2></div>
          <button className="btn ghost sm" onClick={onClose} disabled={!!busy} aria-label="Close"><Icon name="x" size={16} /></button>
        </div>
        <div className="price" style={{ fontSize: 36, margin: '4px 0 14px' }}>{money(amount)}</div>

        {loading ? <Skeleton h={200} r={14} /> : (
          <div className="stack" style={{ marginTop: 0 }}>
            {/* coins */}
            <div className={`mcard ${enough ? '' : 'dim'}`}>
              <div className="row between" style={{ flexWrap: 'nowrap' }}>
                <div><b>🪙 Pay with coins</b><div className="small mute">Balance <b>{coins(methods.coins?.balance)}</b> coins · this costs <b>{coins(coinCost)}</b> coins</div></div>
                {enough
                  ? <button className="btn gold sm" disabled={!!busy} onClick={withCoins}>{busy === 'coins' ? 'Paying…' : 'Pay now'}</button>
                  : <Link to="/wallet" className="btn ghost sm" onClick={onClose}>Top up coins</Link>}
              </div>
              {!enough && <div className="small" style={{ color: 'var(--gold1)', marginTop: 6 }}>You need {coins(coinCost - Number(methods.coins?.balance ?? 0))} more coins. Top up in your wallet, then come back.</div>}
            </div>

            {/* razorpay */}
            <div className={`mcard ${methods.razorpay?.available ? '' : 'dim'}`}>
              <div className="row between" style={{ flexWrap: 'nowrap' }}>
                <div><b>💳 Razorpay</b> {methods.razorpay?.test_mode && <Badge status="warn">test mode</Badge>}<div className="small mute">UPI, cards, netbanking, wallets</div></div>
                <button className="btn sm" disabled={!!busy || !methods.razorpay?.available} onClick={withRazorpay}>{busy === 'razorpay' ? 'Opening…' : methods.razorpay?.available ? 'Pay with Razorpay' : 'Not set up'}</button>
              </div>
              {methods.razorpay?.test_mode && methods.razorpay?.available && (
                <div className="small faint" style={{ marginTop: 8 }}>Test mode: no real money. Card <b>4111 1111 1111 1111</b>, any future expiry, any CVV, then choose “Success”. Or UPI <b>success@razorpay</b>.</div>
              )}
            </div>

            {/* fake */}
            {methods.fake?.available && (
              <div className="mcard">
                <div className="row between" style={{ flexWrap: 'nowrap' }}>
                  <div><b>🧪 Fake payment</b> <Badge status="warn">test only</Badge><div className="small mute">Completes instantly, no money moves. For trying the flow.</div></div>
                  <div className="row" style={{ flexWrap: 'nowrap' }}>
                    <button className="btn ghost sm" disabled={!!busy} onClick={declineFake}>Decline</button>
                    <button className="btn gold sm" disabled={!!busy} onClick={withFake}>{busy === 'fake' ? 'Paying…' : 'Approve'}</button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
        {err && <div className="err" role="alert" style={{ marginTop: 12 }}>{err}</div>}
        <p className="faint small" style={{ margin: '14px 0 0' }}><Icon name="lock" size={13} /> Payments are confirmed by our server and recorded in an audit log.</p>
      </div>
    </div>
  );
}
