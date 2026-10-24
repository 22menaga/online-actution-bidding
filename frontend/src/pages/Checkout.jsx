import { Suspense, lazy, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Payments as PaymentsApi } from '../api.js';
import { Confetti, EmptyState, Field, Icon, Skeleton, money, useAsync, useToast } from '../ui.jsx';

const Trophy3D = lazy(() => import('../scene/Trophy3D.jsx'));
const digits = (s) => s.replace(/\D/g, '');
const fmtCard = (s) => digits(s).slice(0, 16).replace(/(.{4})/g, '$1 ').trim();
const fmtExp = (s) => { const d = digits(s).slice(0, 4); return d.length > 2 ? `${d.slice(0, 2)}/${d.slice(2)}` : d; };

/** Test-mode checkout, only reachable when the backend runs with PAYMENTS_MOCK (no Razorpay keys, DEBUG). */
export default function Checkout() {
  const { id } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const { loading, data } = useAsync(PaymentsApi.list, []);
  const [card, setCard] = useState({ number: '4242 4242 4242 4242', exp: '12/34', cvc: '123', name: '' });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState('');

  const p = data?.results.find((x) => String(x.id) === id);
  if (loading) return <div className="wrap page" style={{ maxWidth: 620 }}><Skeleton h={380} r={16} /></div>;
  if (!p) return <div className="wrap page"><EmptyState icon="🧾" title="Invoice not found" action={<Link to="/payments" className="btn">Back to payments</Link>}>This invoice does not exist or belongs to another account.</EmptyState></div>;

  const payable = ['PENDING', 'PROCESSING'].includes(p.status);
  const valid = digits(card.number).length === 16 && /^\d\d\/\d\d$/.test(card.exp) && digits(card.cvc).length >= 3 && card.name.trim().length > 1;

  const pay = async (outcome) => {
    setBusy(true); setErr('');
    try {
      await PaymentsApi.mockPay(p.id, outcome);
      if (outcome === 'success') { setDone(true); window.dispatchEvent(new Event('notifications:changed')); setTimeout(() => nav('/payments'), 3200); }
      else setErr('The card was declined (simulated). Please try again.');
    } catch (x) { setErr(x.message); } finally { setBusy(false); }
  };

  if (done || p.status === 'SUCCESS') {
    return (
      <div className="wrap page center" style={{ maxWidth: 520 }}>
        <Confetti run={done} />
        <div className="card glow pad" style={{ padding: 40 }}>
          <Suspense fallback={<div style={{ fontSize: 56 }}>🎉</div>}><Trophy3D /></Suspense>
          <h1>Payment successful</h1>
          <p className="mute">Thank you! {p.product_name} is yours. The seller has been notified and will arrange handover.</p>
          <div className="price" style={{ fontSize: 34 }}>{money(Number(p.amount))}</div>
          <Link to="/payments" className="btn gold block lg" style={{ marginTop: 20 }}>View receipt</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="wrap page">
      <p><Link to="/payments" className="mute small">← Payments</Link></p>
      <div className="split">
        <form className="card glow pad" onSubmit={(e) => { e.preventDefault(); pay('success'); }}>
          <div className="banner info" style={{ marginBottom: 18 }}><Icon name="shield" /> Test mode — no real money is charged. Use the prefilled card.</div>
          <h2>Payment details</h2>
          <div className="checkout-card">
            <div className="faint small">CARD</div>
            <div style={{ font: '600 22px var(--display)', letterSpacing: '.12em', margin: '14px 0' }}>{card.number || '•••• •••• •••• ••••'}</div>
            <div className="row between small"><span>{card.name.toUpperCase() || 'CARDHOLDER'}</span><span>{card.exp || 'MM/YY'}</span></div>
          </div>
          <Field label="NAME ON CARD"><input value={card.name} onChange={(e) => setCard({ ...card, name: e.target.value })} autoComplete="cc-name" required /></Field>
          <Field label="CARD NUMBER"><input inputMode="numeric" value={card.number} onChange={(e) => setCard({ ...card, number: fmtCard(e.target.value) })} autoComplete="cc-number" required /></Field>
          <div className="row" style={{ alignItems: 'flex-start', flexWrap: 'nowrap' }}>
            <div style={{ flex: 1 }}><Field label="EXPIRY"><input value={card.exp} onChange={(e) => setCard({ ...card, exp: fmtExp(e.target.value) })} placeholder="MM/YY" autoComplete="cc-exp" required /></Field></div>
            <div style={{ flex: 1 }}><Field label="CVC"><input inputMode="numeric" value={card.cvc} onChange={(e) => setCard({ ...card, cvc: digits(e.target.value).slice(0, 4) })} autoComplete="cc-csc" required /></Field></div>
          </div>
          {err && <div className="err" role="alert">{err}</div>}
          <button className="btn gold block lg" style={{ marginTop: 22 }} disabled={busy || !valid || !payable}><Icon name="lock" size={18} /> {busy ? 'Processing…' : `Pay ${money(Number(p.amount))}`}</button>
          <button type="button" className="btn ghost block sm" style={{ marginTop: 10 }} disabled={busy || !payable} onClick={() => { toast('Simulating a declined card', 'warn'); pay('fail'); }}>Simulate declined card</button>
        </form>

        <div className="card pad sticky">
          <h3>Order summary</h3>
          <div className="row between"><span>{p.product_name}</span><b>{money(Number(p.amount))}</b></div>
          <div className="row between mute small" style={{ marginTop: 8 }}><span>Winning bid</span><span>{money(Number(p.amount))}</span></div>
          <div className="row between mute small"><span>Buyer fees</span><span>$0.00</span></div>
          <div className="divider" />
          <div className="row between"><b>Total due</b><b className="price" style={{ fontSize: 26 }}>{money(Number(p.amount))}</b></div>
          <p className="faint small" style={{ marginTop: 16 }}><Icon name="lock" size={13} /> Payments are recorded in an audit log. When Razorpay keys are configured this page is replaced by Razorpay Checkout.</p>
        </div>
      </div>
    </div>
  );
}
