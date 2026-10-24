import { Suspense, lazy, startTransition, useEffect, useRef, useState } from 'react';
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { AuthProvider, ROLE_LABEL, homeFor, useAuth } from './auth.jsx';
import { Notifications as NotificationsApi, Wallet as WalletApi } from './api.js';
import { ErrorBoundary, Icon, OfflineBanner, ToastProvider, initials, injectStyles } from './ui.jsx';
import Home from './pages/Home.jsx';
import AuctionList from './pages/AuctionList.jsx';
import AuctionDetail from './pages/AuctionDetail.jsx';
import { Login, Register, ForgotPassword, ResetPassword, VerifyEmail } from './pages/AuthPages.jsx';
import Payments from './pages/Payments.jsx';
import Checkout from './pages/Checkout.jsx';
import Notifications from './pages/Notifications.jsx';
import MyBids from './pages/MyBids.jsx';
import Watchlist from './pages/Watchlist.jsx';
import Sell from './pages/Sell.jsx';
import Admin from './pages/Admin.jsx';
import Settings from './pages/Settings.jsx';
import Wallet from './pages/Wallet.jsx';

injectStyles();

const Backdrop3D = lazy(() => import('./scene/Backdrop3D.jsx'));

// Ambient 3D layer only where it is cheap: desktop-class screens and no reduced-motion preference.
const canShowBackdrop = () =>
  typeof matchMedia === 'function' && matchMedia('(min-width: 800px)').matches && !matchMedia('(prefers-reduced-motion: reduce)').matches;

// Pages that already render their own full-screen 3D scene don't also need the ambient backdrop.
const OWN_3D_ROUTES = new Set(['/', '/login', '/register', '/forgot-password']);

/** Route guard. `roles` limits who may enter; anyone else is sent to the home page of their own profile. */
function Protected({ children, roles }) {
  const { user, ready } = useAuth();
  const loc = useLocation();
  if (!ready) return null;
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname + loc.search }} replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  return children;
}

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo({ top: 0 }); }, [pathname]);
  return null;
}

function useUnread(user) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!user) { setN(0); return undefined; }
    const load = () => NotificationsApi.list().then((d) => setN(d.results.filter((x) => !x.read_at).length)).catch(() => {});
    load();
    const t = setInterval(load, 30000);
    window.addEventListener('notifications:changed', load);
    return () => { clearInterval(t); window.removeEventListener('notifications:changed', load); };
  }, [user]);
  return n;
}

function useCoinBalance(user) {
  const [bal, setBal] = useState(null);
  useEffect(() => {
    if (!user || user.role === 'ADMIN') { setBal(null); return undefined; }
    const load = () => WalletApi.get().then((d) => setBal(Number(d.balance))).catch(() => {});
    load();
    window.addEventListener('wallet:changed', load);
    const t = setInterval(load, 45000);
    return () => { window.removeEventListener('wallet:changed', load); clearInterval(t); };
  }, [user]);
  return bal;
}

function Logo() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#fbe7ae" /><stop offset="1" stopColor="#a8741c" /></linearGradient></defs>
      <path d="M6 22l9-9 3 3-9 9z M14 6l6-3 9 9-3 6z M3 29h14" fill="url(#lg)" stroke="url(#lg)" strokeWidth="1.2" strokeLinejoin="round" />
    </svg>
  );
}

function ProfileMenu() {
  const { user, profiles, switchTo, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const nav = useNavigate();
  useEffect(() => {
    const away = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', away);
    return () => document.removeEventListener('mousedown', away);
  }, []);
  const others = profiles.filter((p) => String(p.id) !== String(user.id));
  const go = async (id) => { setOpen(false); const me = await switchTo(id); if (me) nav(homeFor(me.role)); };
  return (
    <div className="pmenu" ref={ref}>
      <button className="pbtn" onClick={() => setOpen(!open)} aria-haspopup="menu" aria-expanded={open}>
        <span className="avatar">{initials(user.username)}</span>
        <span className="pname">{user.username}</span>
        <span className={`rolechip ${user.role}`}>{ROLE_LABEL[user.role]}</span>
      </button>
      {open && (
        <div className="pdrop" role="menu">
          <div className="phead"><span className="avatar">{initials(user.username)}</span><div><b>{user.username}</b><div className="faint small">{user.email}</div></div></div>
          {others.length > 0 && <div className="plabel">Switch profile</div>}
          {others.map((p) => (
            <button key={p.id} className="pitem" role="menuitem" onClick={() => go(p.id)}>
              <span className="avatar sm">{initials(p.username)}</span><span className="grow" style={{ textAlign: 'left' }}>{p.username}</span><span className={`rolechip ${p.role}`}>{ROLE_LABEL[p.role]}</span>
            </button>
          ))}
          <Link to="/login?add=1" className="pitem" role="menuitem" onClick={() => setOpen(false)}><Icon name="share" size={16} /> <span className="grow">Add another profile</span></Link>
          <Link to="/settings" className="pitem" role="menuitem" onClick={() => setOpen(false)}><Icon name="shield" size={16} /> <span className="grow">Profile &amp; settings</span></Link>
          <button className="pitem" role="menuitem" onClick={() => { setOpen(false); startTransition(() => { nav('/'); logout(); }); /* one transition: no flash through a protected page */ }}><Icon name="x" size={16} /> <span className="grow" style={{ textAlign: 'left' }}>Sign out of this profile</span></button>
        </div>
      )}
    </div>
  );
}

function Nav() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const unread = useUnread(user);
  const balance = useCoinBalance(user);
  useEffect(() => setOpen(false), [loc.pathname]);
  const cls = ({ isActive }) => `link${isActive ? ' active' : ''}`;
  const role = user?.role;
  return (
    <nav className="nav" aria-label="Main">
      <div className="wrap">
        <Link to={user ? homeFor(role) : '/'} className="brand"><Logo /> <span>Auction <span className="gold-text">House</span></span></Link>
        {role && <span className={`rolechip ${role}`} style={{ marginLeft: -10 }}>{ROLE_LABEL[role]}</span>}
        <button className="burger" aria-label="Toggle menu" aria-expanded={open} onClick={() => setOpen(!open)}><Icon name={open ? 'x' : 'menu'} size={24} /></button>
        <div className={`links ${open ? 'open' : ''}`}>
          {/* Seller studio: sell, manage, get paid. Bidder: browse, bid, buy. Admin: run the marketplace. */}
          {role === 'SELLER' && (<>
            <NavLink to="/sell" className={cls}>Studio</NavLink>
            <NavLink to="/wallet" className={cls}>Earnings</NavLink>
            <NavLink to="/auctions" className={cls}>Marketplace</NavLink>
          </>)}
          {role === 'BUYER' && (<>
            <NavLink to="/auctions" className={cls}>Browse</NavLink>
            <NavLink to="/watchlist" className={cls}>Watchlist</NavLink>
            <NavLink to="/my-bids" className={cls}>My bids</NavLink>
            <NavLink to="/payments" className={cls}>Payments</NavLink>
            <NavLink to="/wallet" className={cls}>Wallet</NavLink>
          </>)}
          {role === 'ADMIN' && (<>
            <NavLink to="/admin" className={cls}>Admin</NavLink>
            <NavLink to="/auctions" className={cls}>Auctions</NavLink>
          </>)}
          {!user && <NavLink to="/auctions" className={cls}>Auctions</NavLink>}
          <span className="grow" />
          {user ? (
            <>
              {balance != null && <Link to="/wallet" className="coinpill" title="Your coin balance">🪙 {Number(balance).toLocaleString('en-IN', { maximumFractionDigits: 2 })}</Link>}
              <NavLink to="/notifications" className="bell" aria-label={`Alerts${unread ? `, ${unread} unread` : ''}`}>
                <Icon name="bell" />{unread > 0 && <span className="count">{unread > 9 ? '9+' : unread}</span>}
              </NavLink>
              <ProfileMenu />
            </>
          ) : (
            <div className="row" style={{ gap: 8 }}>
              <NavLink to="/login" className={cls}>Log in</NavLink>
              <Link to="/register" className="btn gold sm">Join free</Link>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}

function Footer() {
  return (
    <footer className="foot">
      <div className="wrap row between">
        <span>© {new Date().getFullYear()} Auction House. Bids are binding. Payments are processed securely.</span>
        <span className="row" style={{ gap: 16 }}><span><Icon name="shield" size={14} /> Verified sellers</span><span><Icon name="lock" size={14} /> Encrypted checkout</span><Link to="/login?add=1" className="mute" style={{ textDecoration: 'underline' }}>Staff / admin login</Link></span>
      </div>
    </footer>
  );
}

function RouteBoundary({ children }) {
  const { pathname } = useLocation();
  return <ErrorBoundary resetKey={pathname}>{children}</ErrorBoundary>;
}

function NotFound() {
  const { user } = useAuth();
  return (
    <div className="wrap page center" style={{ maxWidth: 560 }}>
      <div className="card glow pad" style={{ padding: 40 }}>
        <div style={{ font: '700 72px var(--display)' }} className="gold-text">404</div>
        <h2>This page isn't here</h2>
        <p className="mute">The link may be old, or the auction may have been removed.</p>
        <div className="row" style={{ justifyContent: 'center' }}><Link to="/auctions" className="btn gold">Browse auctions</Link>{user && <Link to={homeFor(user.role)} className="btn ghost">Go to my home</Link>}</div>
      </div>
    </div>
  );
}

function BackdropGate() {
  const { pathname } = useLocation();
  const [hidden, setHidden] = useState(document.hidden);
  useEffect(() => {
    const on = () => setHidden(document.hidden);
    document.addEventListener('visibilitychange', on);
    return () => document.removeEventListener('visibilitychange', on);
  }, []);
  if (OWN_3D_ROUTES.has(pathname)) return null;
  return <Suspense fallback={null}><Backdrop3D paused={hidden} /></Suspense>;
}

export default function App() {
  const [backdrop] = useState(canShowBackdrop);
  useEffect(() => { document.title = 'Auction House · Live online auctions'; }, []);
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <ToastProvider>
          {backdrop && <BackdropGate />}
          <ScrollToTop />
          <a href="#main" className="skip">Skip to content</a>
          <Nav />
          <OfflineBanner />
          <main id="main">
            <RouteBoundary>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/auctions" element={<AuctionList />} />
              <Route path="/auctions/:id" element={<AuctionDetail />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/reset-password/:uid/:token" element={<ResetPassword />} />
              <Route path="/verify/:uid/:token" element={<VerifyEmail />} />
              <Route path="/watchlist" element={<Protected roles={['BUYER']}><Watchlist /></Protected>} />
              <Route path="/my-bids" element={<Protected roles={['BUYER']}><MyBids /></Protected>} />
              <Route path="/payments" element={<Protected roles={['BUYER']}><Payments /></Protected>} />
              <Route path="/checkout/:id" element={<Protected roles={['BUYER']}><Checkout /></Protected>} />
              <Route path="/notifications" element={<Protected><Notifications /></Protected>} />
              <Route path="/sell" element={<Protected roles={['SELLER']}><Sell /></Protected>} />
              <Route path="/settings" element={<Protected><Settings /></Protected>} />
              <Route path="/wallet" element={<Protected roles={['BUYER', 'SELLER']}><Wallet /></Protected>} />
              <Route path="/admin" element={<Protected roles={['ADMIN']}><Admin /></Protected>} />
              <Route path="*" element={<NotFound />} />
            </Routes>
            </RouteBoundary>
          </main>
          <Footer />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
