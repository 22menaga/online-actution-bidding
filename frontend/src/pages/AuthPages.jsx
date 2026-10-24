import { Suspense, lazy, useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Auth } from '../api.js';
import { homeFor, useAuth } from '../auth.jsx';
import { Field, Icon, useToast } from '../ui.jsx';

const AuthScene = lazy(() => import('../scene/AuthScene.jsx'));

function Split({ title, subtitle, children, art = true }) {
  const showArt = art && typeof matchMedia === 'function' && matchMedia('(min-width: 861px)').matches;
  return (
    <div className="auth">
      <div className="art">
        {showArt && <Suspense fallback={null}><AuthScene /></Suspense>}
        <div className="cap">
          <div className="eyebrow">Auction House</div>
          <h2 style={{ marginTop: 6 }}>Where collectors <span className="gold-text">win</span>.</h2>
          <p className="mute" style={{ margin: 0 }}>Verified sellers · live bidding · secure checkout</p>
        </div>
      </div>
      <div className="formside">
        <div className="card glow pad" style={{ width: '100%', maxWidth: 440, padding: 32 }}>
          <h1 style={{ fontSize: 32 }}>{title}</h1>
          {subtitle && <p className="mute">{subtitle}</p>}
          {children}
        </div>
      </div>
    </div>
  );
}

function PasswordInput({ value, onChange, autoComplete, minLength, id = 'pw' }) {
  const [show, setShow] = useState(false);
  return (
    <div style={{ position: 'relative' }}>
      <input id={id} type={show ? 'text' : 'password'} value={value} onChange={onChange} autoComplete={autoComplete} minLength={minLength} required style={{ paddingRight: 64 }} />
      <button type="button" className="chip" style={{ position: 'absolute', right: 8, top: 8, padding: '4px 10px' }} onClick={() => setShow(!show)} aria-label={show ? 'Hide password' : 'Show password'}>{show ? 'Hide' : 'Show'}</button>
    </div>
  );
}

const strength = (p) => [p.length >= 10, /[a-z]/.test(p) && /[A-Z]/.test(p), /\d/.test(p), /[^A-Za-z0-9]/.test(p)].filter(Boolean).length;

function Meter({ password }) {
  const n = strength(password);
  const colors = ['', 'var(--bad)', 'var(--gold2)', 'var(--gold1)', 'var(--ok)'];
  return (
    <div>
      <div className="pw-meter">{[1, 2, 3, 4].map((k) => <i key={k} style={{ background: k <= n ? colors[n] : undefined }} />)}</div>
      <div className="faint small" style={{ marginTop: 4 }}>{password ? ['Too short', 'Weak', 'Fair', 'Good', 'Strong'][n] : 'Use 10+ characters with a mix of letters, numbers and symbols'}</div>
    </div>
  );
}

export function Login() {
  const { login, profiles, switchTo, user } = useAuth();
  const [sp] = useSearchParams();
  const adding = sp.get('add') === '1';
  const nav = useNavigate();
  const loc = useLocation();
  const [f, setF] = useState({ username: '', password: '' });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr('');
    try {
      const me = await login(f.username.trim(), f.password);
      nav(adding ? homeFor(me.role) : (loc.state?.from ?? homeFor(me.role)), { replace: true });
    } catch (x) {
      setErr(x.message);
    } finally { setBusy(false); }
  };

  return (
    <Split title={adding ? 'Add another profile' : 'Welcome back'} subtitle={adding ? 'You stay signed in to your other profiles and can switch between them any time.' : 'Log in to your seller studio or your bidding account.'}>
      {!adding && !user && profiles.length > 0 && (
        <div style={{ marginBottom: 18 }}>
          <div className="faint small" style={{ marginBottom: 8 }}>Signed in on this device — continue instantly:</div>
          <div className="stack" style={{ marginTop: 0 }}>
            {profiles.map((p) => (
              <button type="button" key={p.id} className="pitem" style={{ border: '1px solid var(--line2)' }} onClick={async () => { const me = await switchTo(p.id); if (me) nav(homeFor(me.role), { replace: true }); }}>
                <span className="avatar sm">{p.username.slice(0, 2).toUpperCase()}</span><span className="grow" style={{ textAlign: 'left' }}>Continue as <b>{p.username}</b></span><span className={`rolechip ${p.role}`}>{p.role === 'SELLER' ? 'Seller' : p.role === 'ADMIN' ? 'Admin' : 'Bidder'}</span>
              </button>
            ))}
          </div>
          <div className="divider" />
        </div>
      )}
      <form onSubmit={submit}>
        <Field label="USERNAME"><input value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} autoComplete="username" autoFocus required /></Field>
        <Field label="PASSWORD"><PasswordInput value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} autoComplete="current-password" /></Field>
        {err && <div className="err" role="alert">{err}</div>}
        <button className="btn gold block lg" style={{ marginTop: 20 }} disabled={busy}>{busy ? 'Signing in…' : 'Log in'}</button>
      </form>
      <div className="row between small" style={{ marginTop: 18 }}>
        <Link to="/forgot-password" className="mute">Forgot password?</Link>
        <span className="mute">New here? <Link to="/register" className="gold-text" style={{ fontWeight: 700 }}>Create account</Link></span>
      </div>
      {import.meta.env.DEV && (
        <div className="banner info small" style={{ marginTop: 18, flexDirection: 'column' }}>
          <div><b>Local demo profiles</b> — one tap to sign in (password <b>DemoPass12345!</b>)</div>
          <div className="row">
            {[['demo_buyer', 'Bidder', 'BUYER'], ['demo_seller', 'Seller', 'SELLER'], ['demo_admin', 'Admin', 'ADMIN']].map(([u, label, role]) => (
              <button type="button" key={u} className="btn ghost sm" disabled={busy} onClick={async () => {
                setBusy(true); setErr('');
                try { const me = await login(u, 'DemoPass12345!'); nav(homeFor(me.role), { replace: true }); } catch (x) { setErr(x.message); } finally { setBusy(false); }
              }}><span className={`rolechip ${role}`}>{label}</span> {u}</button>
            ))}
          </div>
        </div>
      )}
    </Split>
  );
}

export function Register() {
  const nav = useNavigate();
  const toast = useToast();
  const [sp] = useSearchParams();
  const adding = sp.get('add') === '1';
  const { login } = useAuth();
  const [f, setF] = useState({ username: '', email: '', password: '', role: sp.get('role') === 'SELLER' ? 'SELLER' : 'BUYER' });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr('');
    try {
      const res = await Auth.register({ ...f, username: f.username.trim(), email: f.email.trim() });
      if (res?.auto_verified) {
        const me = await login(f.username.trim(), f.password); // straight in, no second login step
        toast(me.role === 'SELLER' ? 'Seller profile created. Add your first item!' : 'Bidder profile created. Happy bidding!', 'ok');
        nav(homeFor(me.role), { replace: true });
      } else {
        toast('Account created! Check your email for the verification link, then log in.', 'ok');
        nav('/login');
      }
    } catch (x) { setErr(x.message); } finally { setBusy(false); }
  };

  return (
    <Split title={adding ? 'Create another profile' : 'Join Auction House'} subtitle={f.role === 'SELLER' ? 'A seller profile: list items, upload photos and get an AI market price estimate.' : 'A bidder profile: browse every item, bid live and buy.'}>
      <form onSubmit={submit}>
        <div className="chips" style={{ marginBottom: 4 }}>
          {[['BUYER', '🔨 Bidder — browse, bid & buy'], ['SELLER', '🏷️ Seller — list & sell']].map(([v, l]) => <button type="button" key={v} className={`chip ${f.role === v ? 'on' : ''}`} onClick={() => setF({ ...f, role: v })}>{l}</button>)}
        </div>
        <Field label="USERNAME"><input value={f.username} onChange={set('username')} autoComplete="username" required /></Field>
        <Field label="EMAIL"><input type="email" value={f.email} onChange={set('email')} autoComplete="email" required /></Field>
        <Field label="PASSWORD"><PasswordInput value={f.password} onChange={set('password')} autoComplete="new-password" minLength={10} /></Field>
        <Meter password={f.password} />
        {err && <div className="err" role="alert">{err}</div>}
        <button className="btn gold block lg" style={{ marginTop: 20 }} disabled={busy || f.password.length < 10}>{busy ? 'Creating account…' : 'Create account'}</button>
      </form>
      <p className="mute small" style={{ marginTop: 18 }}>Already registered? <Link to="/login" className="gold-text" style={{ fontWeight: 700 }}>Log in</Link></p>
    </Split>
  );
}

export function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault(); setBusy(true);
    try { await Auth.forgot(email.trim()); } catch { /* the API never reveals whether an account exists */ }
    setSent(true); setBusy(false);
  };
  return (
    <Split title="Reset password" subtitle="Enter your account email and we'll send a reset link.">
      {sent ? <div className="banner info"><Icon name="check" /> If an account exists for that address, a reset link is on its way.</div> : (
        <form onSubmit={submit}>
          <Field label="EMAIL"><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus /></Field>
          <button className="btn gold block lg" style={{ marginTop: 20 }} disabled={busy}>{busy ? 'Sending…' : 'Send reset link'}</button>
        </form>
      )}
      <p className="small" style={{ marginTop: 18 }}><Link to="/login" className="mute">← Back to log in</Link></p>
    </Split>
  );
}

export function ResetPassword() {
  const { uid, token } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const [password, setPassword] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr('');
    try {
      await Auth.reset(uid, token, password);
      toast('Password updated. Please log in.', 'ok'); nav('/login');
    } catch (x) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <Split title="Choose a new password">
      <form onSubmit={submit}>
        <Field label="NEW PASSWORD"><PasswordInput value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" minLength={10} /></Field>
        <Meter password={password} />
        {err && <div className="err" role="alert">{err}</div>}
        <button className="btn gold block lg" style={{ marginTop: 20 }} disabled={busy || password.length < 10}>{busy ? 'Saving…' : 'Update password'}</button>
      </form>
    </Split>
  );
}

export function VerifyEmail() {
  const { uid, token } = useParams();
  const { reload, user } = useAuth();
  const [state, setState] = useState('checking');
  useEffect(() => {
    Auth.verify(uid, token).then(() => { setState('ok'); if (user) reload(); }).catch(() => setState('bad'));
  }, [uid, token]); // eslint-disable-line
  return (
    <Split title={state === 'checking' ? 'Verifying…' : state === 'ok' ? 'Email verified 🎉' : 'Link expired'} art={false}>
      {state === 'ok' && <><p className="mute">Your account is ready — you can now place bids.</p><Link to={user ? '/auctions' : '/login'} className="btn gold block lg">{user ? 'Start bidding' : 'Log in'}</Link></>}
      {state === 'bad' && <><p className="mute">This verification link is invalid or has expired. Register again or request a new link.</p><Link to="/login" className="btn ghost block">Back to log in</Link></>}
    </Split>
  );
}
