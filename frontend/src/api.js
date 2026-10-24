// API layer: JWT storage + silent refresh, pagination helper, bid WebSocket.
// Multi-profile token store.
//  - localStorage 'accounts': every signed-in profile on this device { [userId]: {id, username, role, access, refresh} }
//  - sessionStorage 'activeAccount': which profile THIS TAB uses (so tab A can be a seller while tab B is a bidder)
//  - localStorage 'lastAccount': what a brand-new tab starts with
const ACCOUNTS = 'accounts';
const ACTIVE = 'activeAccount';
const LAST = 'lastAccount';

const readAccounts = () => { try { return JSON.parse(localStorage.getItem(ACCOUNTS)) || {}; } catch { return {}; } };
const writeAccounts = (a) => localStorage.setItem(ACCOUNTS, JSON.stringify(a));

// This tab's profile. 'none' means this tab deliberately signed out: it must NOT silently pick up another stored profile.
function activeId() {
  const accounts = readAccounts();
  const raw = sessionStorage.getItem(ACTIVE);
  if (raw === 'none') return null;
  if (raw != null) { if (accounts[raw]) return raw; sessionStorage.setItem(ACTIVE, 'none'); return null; } // it was removed (e.g. in another tab)
  // brand-new tab: start with the profile used most recently on this device
  const id = [localStorage.getItem(LAST), Object.keys(accounts)[0]].find((x) => x != null && accounts[x]) ?? null;
  if (id != null) sessionStorage.setItem(ACTIVE, id);
  return id;
}

export const tokens = {
  get active() { return activeId(); },
  get access() { return readAccounts()[activeId()]?.access ?? null; },
  get refresh() { return readAccounts()[activeId()]?.refresh ?? null; },
  list() { return Object.values(readAccounts()); },
  /** silent token refresh: update the active profile's tokens */
  set({ access, refresh }) {
    const id = activeId(); const accounts = readAccounts();
    if (id == null || !accounts[id]) return;
    if (access) accounts[id].access = access;
    if (refresh) accounts[id].refresh = refresh;
    writeAccounts(accounts);
  },
  /** add (or replace) a signed-in profile and make it active in this tab */
  add(account) {
    const accounts = readAccounts();
    accounts[account.id] = account; writeAccounts(accounts);
    sessionStorage.setItem(ACTIVE, String(account.id)); localStorage.setItem(LAST, String(account.id));
  },
  switch(id) {
    if (!readAccounts()[id]) return;
    sessionStorage.setItem(ACTIVE, String(id)); localStorage.setItem(LAST, String(id));
  },
  remove(id) {
    const accounts = readAccounts(); delete accounts[id]; writeAccounts(accounts);
    if (String(sessionStorage.getItem(ACTIVE)) === String(id)) sessionStorage.setItem(ACTIVE, 'none');
    if (String(localStorage.getItem(LAST)) === String(id)) localStorage.removeItem(LAST);
  },
  /** sign out of this tab's profile only */
  clear() { const id = activeId(); if (id != null) this.remove(id); },
};

/** Server-synced clock: countdowns use the SERVER's time so a wrong device clock can never show a false "ended" or "time left". */
export const clock = {
  offset: 0,
  now: () => Date.now() + clock.offset,
  sync(serverIso) { const t = new Date(serverIso).getTime(); if (Number.isFinite(t)) clock.offset = t - Date.now(); },
};

export class ApiError extends Error {
  constructor(status, data) {
    super(describe(data) || `Request failed (${status})`);
    this.status = status;
    this.data = data;
  }
}

// Flattens DRF error shapes ({detail}, {field:[msgs]}, ["msg"]) into one readable line.
function describe(d) {
  if (!d) return '';
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) return d.map(describe).join(' ');
  if (d.detail) return describe(d.detail);
  return Object.entries(d).map(([k, v]) => `${k === 'non_field_errors' ? '' : k + ': '}${describe(v)}`).join(' ');
}

// Ask /health/ why the server is failing so the user sees the real cause (e.g. unapplied migrations).
async function serverProblem(status) {
  try {
    const h = await fetch('/health/');
    const text = (await h.text()).trim();
    if (!h.ok && text.startsWith('not ready')) return `The server is not ready: ${text.replace(/^not ready:\s*/, '')}`;
  } catch { /* fall through */ }
  return `The server hit an unexpected error (HTTP ${status}). Check the backend window for details, then try again.`;
}

let refreshing = null;
async function refreshAccess() {
  if (!tokens.refresh) return false;
  refreshing ??= fetch('/api/auth/token/refresh/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh: tokens.refresh }),
  })
    .then(async (r) => {
      if (!r.ok) return false;
      tokens.set(await r.json());
      return true;
    })
    .catch(() => false)
    .finally(() => { refreshing = null; });
  return refreshing;
}

export async function api(path, { method = 'GET', body, form, auth = true, retry = true } = {}) {
  const headers = {};
  if (auth && tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
  if (body) headers['Content-Type'] = 'application/json';
  let res;
  try {
    res = await fetch(`/api${path}`, { method, headers, body: form ?? (body ? JSON.stringify(body) : undefined) });
  } catch {
    throw new ApiError(0, { detail: 'Cannot reach the server. Check your internet connection and that the backend is running.' });
  }
  if (res.status === 401 && auth && headers.Authorization) {
    if (retry && tokens.refresh && (await refreshAccess())) return api(path, { method, body, form, auth, retry: false });
    // The saved sign-in is dead (expired / revoked / account reset). Drop it, and let public pages carry on as a visitor.
    window.dispatchEvent(new Event('auth:expired'));
    if (method === 'GET') return api(path, { method, auth: false, retry: false });
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401) window.dispatchEvent(new Event('auth:expired'));
    // An HTML/plain-text error page (no JSON body) means the server crashed or is misconfigured, not a normal API error.
    if (data === null && res.status >= 500) throw new ApiError(res.status, { detail: await serverProblem(res.status) });
    throw new ApiError(res.status, data);
  }
  return data;
}

const qs = (params) => {
  const p = new URLSearchParams();
  Object.entries(params ?? {}).forEach(([k, v]) => v !== '' && v != null && p.set(k, v));
  const s = p.toString();
  return s ? `?${s}` : '';
};

const num = (v) => (v == null ? null : Number(v));
const normAuction = (a) => {
  if (a.server_time) clock.sync(a.server_time);
  return {
  ...a,
  starting_price: num(a.starting_price),
  min_increment: num(a.min_increment),
  current_highest_bid: num(a.current_highest_bid),
  required_minimum: num(a.required_minimum),
  };
};

export const Auth = {
  /** Returns the signed-in user. Stores the profile alongside any others already signed in on this device. */
  async login(username, password) {
    const t = await api('/auth/token/', { method: 'POST', body: { username, password }, auth: false });
    const res = await fetch('/api/accounts/me/', { headers: { Authorization: `Bearer ${t.access}` } });
    if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => null));
    const me = await res.json();
    tokens.add({ id: me.id, username: me.username, role: me.role, access: t.access, refresh: t.refresh });
    return me;
  },
  /** Best-effort: tell the server to revoke a refresh token so a stolen copy stops working. */
  revoke(refresh) { if (refresh) fetch('/api/auth/logout/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh }), keepalive: true }).catch(() => {}); },
  profile: () => api('/accounts/profile/'),
  updateProfile: (patch) => api('/accounts/profile/', { method: 'PATCH', body: patch }),
  register: (b) => api('/accounts/register/', { method: 'POST', body: b, auth: false }),
  me: () => api('/accounts/me/'),
  resendVerification: () => api('/accounts/resend-verification/', { method: 'POST', body: {} }),
  verify: (uid, token) => api(`/accounts/verify/${uid}/${token}/`, { auth: false }),
  forgot: (email) => api('/accounts/password-reset/', { method: 'POST', body: { email }, auth: false }),
  reset: (uid, token, password) => api(`/accounts/password-reset/${uid}/${token}/`, { method: 'POST', body: { password }, auth: false }),
};

export const Auctions = {
  async list(params) {
    const d = await api(`/auctions/auctions/${qs(params)}`);
    return { ...d, results: d.results.map(normAuction) };
  },
  async get(id) {
    return normAuction(await api(`/auctions/auctions/${id}/`));
  },
  bids: (id) => api(`/bidding/auctions/${id}/bids/`, { auth: false }),
  watch: (id) => api(`/auctions/auctions/${id}/watch/`, { method: 'POST' }),
  unwatch: (id) => api(`/auctions/auctions/${id}/watch/`, { method: 'DELETE' }),
  async watchlist() {
    const d = await api('/auctions/auctions/watchlist/');
    return { ...d, results: d.results.map(normAuction) };
  },
  create: (b) => api('/auctions/auctions/', { method: 'POST', body: b }),
  cancel: (id) => api(`/auctions/auctions/${id}/cancel/`, { method: 'POST' }),
  suggestTime: (id, body) => api(`/auctions/auctions/${id}/suggest-time/`, { method: 'POST', body }),
};

// Admin-only: scheduling queue, review reports, time suggestions and the security/data overview.
export const Admin = {
  overview: () => api('/dashboard/overview/'),
  auctionSummary: () => api('/dashboard/auctions/summary/'),
  auctionList: (params) => api(`/dashboard/auctions/${qs(params)}`),
  auctionDetail: (id) => api(`/dashboard/auctions/${id}/`),
  personList: (params) => api(`/dashboard/people/${qs(params)}`),
  personDetail: (id) => api(`/dashboard/people/${id}/`),
  suspendPerson: (id, suspended, reason = '') => api(`/dashboard/people/${id}/suspend/`, { method: 'POST', body: { suspended, reason } }),
  async auctions(status) {
    const d = await api(`/auctions/auctions/${qs({ status, ordering: 'created_at', page_size: 100 })}`);
    return d.results.map(normAuction);
  },
  review: (id, start, end) => api(`/auctions/auctions/${id}/review/${qs({ start_at: start, end_at: end })}`),
  approve: (id, body) => api(`/auctions/auctions/${id}/approve/`, { method: 'POST', body }),
  reschedule: (id, body) => api(`/auctions/auctions/${id}/reschedule/`, { method: 'POST', body }),
  reject: (id, reason) => api(`/auctions/auctions/${id}/reject/`, { method: 'POST', body: { reason } }),
  async pendingProducts() {
    const d = await api('/products/products/?status=PENDING_APPROVAL');
    return d.results;
  },
  reviewProduct: (id, decision, reason = '') => api(`/products/products/${id}/review/`, { method: 'POST', body: { decision, reason } }),
  async sellerVerifications() {
    const d = await api('/accounts/seller-verifications/');
    return d.results;
  },
  reviewSeller: (id, decision, notes = '') => api(`/accounts/seller-verifications/${id}/review/`, { method: 'POST', body: { decision, notes } }),
  timeRequests: (status = 'OPEN') => api(`/auctions/time-requests/${qs({ status })}`),
  resolveRequest: (id, status) => api(`/auctions/time-requests/${id}/resolve/`, { method: 'POST', body: { status } }),
};

export const Bids = {
  mine: () => api('/bidding/bids/'),
  place: (auction, amount, confirmLarge = false) =>
    api('/bidding/bids/', {
      method: 'POST',
      // client_reference makes a retried request idempotent on the server; confirm_large answers the server's typo guard
      body: { auction, amount: Number(amount).toFixed(2), client_reference: crypto.randomUUID(), ...(confirmLarge ? { confirm_large: true } : {}) },
    }),
};

export const Payments = {
  list: () => api('/payments/'),
  methods: () => api('/payments/methods/'),
  checkout: (id, method) => api(`/payments/${id}/checkout/`, { method: 'POST', body: method ? { method } : {} }),
  payCoins: (id) => api(`/payments/${id}/pay-coins/`, { method: 'POST', body: {} }),
  sync: (id) => api(`/payments/${id}/sync/`, { method: 'POST' }),
  verify: (id, r) => api(`/payments/${id}/verify/`, { method: 'POST', body: { razorpay_order_id: r.razorpay_order_id, razorpay_payment_id: r.razorpay_payment_id, razorpay_signature: r.razorpay_signature } }),
  mockPay: (id, outcome = 'success') => api(`/payments/${id}/mock-pay/`, { method: 'POST', body: { outcome } }),
};

// In-app coin wallet: balance + ledger, buying coins (Razorpay or fake test payment).
export const Wallet = {
  get: () => api('/payments/wallet/'),
  topup: (coins, method) => api('/payments/wallet/topup/', { method: 'POST', body: { coins, method } }),
  verifyTopup: (id, r) => api(`/payments/wallet/topup/${id}/verify/`, { method: 'POST', body: { razorpay_order_id: r.razorpay_order_id, razorpay_payment_id: r.razorpay_payment_id, razorpay_signature: r.razorpay_signature } }),
  fakeTopup: (id, outcome = 'success') => api(`/payments/wallet/topup/${id}/fake-pay/`, { method: 'POST', body: { outcome } }),
};

export const Notifications = {
  list: () => api('/notifications/'),
  read: (id) => api(`/notifications/${id}/read/`, { method: 'PATCH', body: {} }),
};

export const Products = {
  categories: () => api('/products/categories/', { auth: false }),
  mine: () => api('/products/products/'),
  aiStatus: () => api('/products/ai-estimate/status/'),
  // photos -> AI market-value estimate (multipart). `hint` is the seller's own description.
  aiEstimate: (files, hint = '') => {
    const f = new FormData();
    files.forEach((file) => f.append('images', file));
    if (hint) f.append('hint', hint.slice(0, 300));
    return api('/products/ai-estimate/', { method: 'POST', form: f });
  },
  create: (b) => api('/products/products/', { method: 'POST', body: b }),
  submit: (id) => api(`/products/products/${id}/submit/`, { method: 'POST' }),
  image: (id, file) => {
    const f = new FormData();
    f.append('image', file);
    f.append('alt_text', file.name);
    return api(`/products/products/${id}/image/`, { method: 'POST', form: f });
  },
};

export const Seller = {
  verify: (b) => api('/accounts/seller-verifications/', { method: 'POST', body: b }),
};

/**
 * Subscribe to live bid events. The server requires a JWT, sent as a WebSocket subprotocol.
 * Reconnects with backoff; returns an unsubscribe function.
 */
export function watchAuction(id, onEvent, onStatus = () => {}) {
  if (!tokens.access) { onStatus('anonymous'); return () => {}; }
  let ws; let closed = false; let attempt = 0; let timer; let beat;
  const connect = () => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/ws/auctions/${id}/`, ['jwt', tokens.access]);
    ws.onopen = () => { attempt = 0; onStatus('live'); clearInterval(beat); beat = setInterval(() => { if (ws.readyState === 1) ws.send('{"type":"ping"}'); }, 25000); };
    ws.onmessage = (e) => { try { onEvent(JSON.parse(e.data)); } catch { /* ignore */ } };
    ws.onclose = (e) => {
      clearInterval(beat);
      if (closed) return;
      onStatus(e.code === 4401 || e.code === 4403 ? 'denied' : e.code === 4429 ? 'toomany' : 'reconnecting');
      if (e.code === 4403 || e.code === 4429) return;
      timer = setTimeout(connect, Math.min(15000, 1000 * 2 ** attempt++));
    };
  };
  connect();
  return () => { closed = true; clearTimeout(timer); clearInterval(beat); ws?.close(); };
}
