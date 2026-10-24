import { useState } from 'react';
import { Wallet as WalletApi } from '../api.js';
import { openRazorpay } from '../razorpay.js';
import { useAuth } from '../auth.jsx';
import { coins } from '../components/PayModal.jsx';
import { Badge, EmptyState, Icon, Skeleton, fmtDateTime, money, useAsync, useToast, AnimatedMoney } from '../ui.jsx';
import { Payments as PaymentsApi } from '../api.js';

const PACKS = [100, 500, 1000, 2500, 5000];
const KIND = { TOPUP: ['Top-up', 'ok'], PURCHASE: ['Purchase', 'warn'], SALE: ['Sale', 'ok'], REFUND: ['Refund', 'ok'], ADJUSTMENT: ['Adjustment', ''] };

export default function Wallet() {
  const { user } = useAuth();
  const toast = useToast();
  const wallet = useAsync(WalletApi.get, []);
  const methods = useAsync(PaymentsApi.methods, []);
  const [amount, setAmount] = useState(1000);
  const [busy, setBusy] = useState('');
  const [err, setErr] = useState('');
  const w = wallet.data;
  const m = Object.fromEntries((methods.data?.methods ?? []).map((x) => [x.id, x]));
  const seller = user.role === 'SELLER';

  const done = async (msg) => { toast(msg, 'ok'); window.dispatchEvent(new Event('wallet:changed')); await wallet.reload(); };

  const buy = async (method) => {
    setBusy(method); setErr('');
    try {
      const t = await WalletApi.topup(Number(amount), method);
      if (method === 'fake') { await WalletApi.fakeTopup(t.topup_id, 'success'); }
      else { const resp = await openRazorpay(t); await WalletApi.verifyTopup(t.topup_id, resp); }
      await done(`${coins(amount)} coins added to your wallet`);
    } catch (x) { if (!x.dismissed) setErr(x.message); } finally { setBusy(''); }
  };

  return (
    <div className="wrap page" style={{ maxWidth: 980 }}>
      <div className="eyebrow">{seller ? 'Earnings' : 'Wallet'}</div>
      <h1>{seller ? 'Your coin earnings' : 'Your coin wallet'}</h1>

      <div className="split" style={{ alignItems: 'start' }}>
        <div className="stack">
          <div className="card glow pad" style={{ background: 'linear-gradient(135deg,rgba(42,31,92,.9),rgba(18,16,42,.95))' }}>
            <div className="faint small">COIN BALANCE</div>
            {wallet.loading && !w ? <Skeleton h={54} w="60%" /> : <div style={{ font: '700 52px var(--display)', lineHeight: 1.1 }}>🪙 <AnimatedMoney className="gold-text" value={Number(w?.balance ?? 0)} digits={0} format={(n) => coins(n)} /></div>}
            <div className="mute small">1 coin = {money(w?.coin_value ?? 1)}{seller && w?.platform_fee_percent > 0 ? ` · ${w.platform_fee_percent}% platform fee on sales` : ''}</div>
            {seller && <p className="faint small" style={{ margin: '12px 0 0' }}>You earn coins when a bidder pays for your item with coins. Coins can be used to buy items on a bidder profile.</p>}
          </div>

          {!seller && (
            <div className="card pad">
              <h3>Add coins</h3>
              <div className="chips">{PACKS.map((p) => <button key={p} type="button" className={`chip ${Number(amount) === p ? 'on' : ''}`} onClick={() => setAmount(p)}>{coins(p)}</button>)}</div>
              <label htmlFor="coins">OR ENTER AN AMOUNT ({w?.topup.min}–{coins(w?.topup.max)} coins)</label>
              <input id="coins" type="number" min={w?.topup.min} max={w?.topup.max} step="1" value={amount} onChange={(e) => setAmount(e.target.value)} />
              <div className="mute small" style={{ margin: '8px 0 14px' }}>You pay <b>{money(Number(amount || 0) * (w?.coin_value ?? 1))}</b></div>
              <div className="row">
                <button className="btn gold" disabled={!!busy || !m.razorpay?.available} onClick={() => buy('razorpay')}>{busy === 'razorpay' ? 'Opening…' : <><Icon name="lock" size={16} /> Pay with Razorpay</>}</button>
                {m.fake?.available && <button className="btn ghost" disabled={!!busy} onClick={() => buy('fake')}>{busy === 'fake' ? 'Adding…' : '🧪 Fake payment (test)'}</button>}
              </div>
              {m.razorpay?.test_mode && <p className="faint small" style={{ margin: '12px 0 0' }}><Badge status="warn">test mode</Badge> Razorpay card <b>4111 1111 1111 1111</b>, any future expiry and CVV, then “Success”, or UPI <b>success@razorpay</b>.</p>}
              {!m.razorpay?.available && !m.fake?.available && methods.data && <div className="banner" style={{ marginTop: 12 }}>No payment method is available right now. Ask the site owner to configure Razorpay.</div>}
              {err && <div className="err" role="alert">{err}</div>}
            </div>
          )}
        </div>

        <div className="card pad">
          <h3>History</h3>
          {wallet.loading && !w ? <Skeleton h={200} r={12} /> : w.transactions.length === 0 ? <EmptyState icon="🪙" title="No transactions yet">{seller ? 'Sales paid with coins will appear here.' : 'Top up coins to start paying with them.'}</EmptyState> : (
            <div>
              {w.transactions.map((t) => {
                const [label, tone] = KIND[t.kind] ?? [t.kind, ''];
                const up = Number(t.amount) > 0;
                return (
                  <div key={t.id} className="row between" style={{ padding: '10px 0', borderBottom: '1px solid var(--line)', flexWrap: 'nowrap' }}>
                    <div><div style={{ fontWeight: 600 }}>{t.description || label}</div><div className="faint small"><Badge status={tone}>{label}</Badge> {fmtDateTime(t.at)}</div></div>
                    <div style={{ textAlign: 'right' }}><b style={{ color: up ? 'var(--ok)' : 'var(--bad)' }}>{up ? '+' : ''}{coins(t.amount)}</b><div className="faint small">bal {coins(t.balance_after)}</div></div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
