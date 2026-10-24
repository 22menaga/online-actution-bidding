# Advanced Online Auction & Bidding System

Production-oriented Django/DRF auction marketplace architecture for multiple sellers, buyers, concurrent auctions, real-time bid broadcasting, secure payment verification, notifications, messaging, audit logs, analytics, and PostgreSQL/Redis deployment.

> This repository is an engineering foundation, not a claim of 100% security or bug-free behavior. Before a public launch, run dependency/SAST/DAST scans, load/concurrency tests, payment-provider certification, infrastructure hardening, legal/privacy review, and a professional security assessment.

## Quick start (Windows)

Needs Python 3.13+ and Node.js 20+. Redis, Celery and PostgreSQL are **not** needed locally.

**Terminal 1 - backend** (first run: create the venv and install packages)

```powershell
cd D:\online_auction_bidding_system\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py start_local
```

After the first time, only the last line is needed. `start_local` migrates the database, seeds demo data, checks your payment keys, runs the auction clock and serves the API (port 8000, or the next free port if another program is using it).

**Terminal 2 - frontend**

```powershell
cd D:\online_auction_bidding_system\frontend
npm install        # first time only
npm run dev
```

Open **http://localhost:5173**. Start order does not matter, and the frontend finds the backend port automatically.
Logins (password `DemoPass12345!`): `demo_buyer`, `demo_buyer2`, `demo_seller`, `demo_admin`.

Shortcut: from this folder in PowerShell run `.\run-all.bat` (note the `.\`), or double-click it.
Do **not** run `uvicorn app.main:app` here - that is a different project. This site is Django and is started with `start_local`.

Check the payment keys any time: `cd backend; .\.venv\Scripts\python.exe manage.py check_payments`.
Run the tests: `cd backend; .\.venv\Scripts\python.exe -m pytest`.

## Stack

- Python 3.13+
- Django 5.1
- Django REST Framework + SimpleJWT
- PostgreSQL 17 production database
- Redis 7 for Channels/Celery
- Django Channels/WebSockets
- Celery + Celery Beat for auction lifecycle/background work
- Bootstrap 5 responsive templates
- Razorpay payments (Orders API + Checkout.js) with server-side HMAC signature verification and signed webhooks
- WhiteNoise for static assets; use object storage/CDN for production media

## Architecture

`accounts` handles identity, roles, seller verification and account security.

`products` handles categories, products, images and approval workflow.

`auctions` owns auction state, schedules and winner/close lifecycle.

`bidding` owns transactional bids and WebSocket fan-out.

`payments` owns payment records, checkout creation and server-side webhook verification.

`notifications` provides durable in-app notifications and an email-ready service boundary.

`messaging` provides authorized buyer/seller conversations and reports.

`audit` provides append-only operational audit records exposed only to admins.

`dashboard` provides admin analytics and web shell pages.

The browser never receives database credentials and never writes directly to PostgreSQL. Sensitive operations are server-side API/service operations.

## Requirements

- Python 3.13+
- PostgreSQL 15+ (17 recommended)
- Redis 7+
- Docker Desktop with the Linux container engine (for the local container deployment below)
- A configured SMTP service only if real account-verification/reset email delivery is needed
- A Razorpay account (test keys are fine) only if real checkout is enabled

## Local Docker Desktop deployment

This starts the complete application stack on this desktop: Django/ASGI, PostgreSQL,
Redis, a Celery worker, and Celery Beat. The web port is bound to `127.0.0.1`, so
the service is not exposed to other computers on the network.

From PowerShell at the project root:

```powershell
.\scripts\docker-up.ps1
```

On the first run, the script creates a private, git-ignored `.env.docker` file
with random Django and PostgreSQL secrets, builds the image, applies migrations,
collects static files, and starts the containers. Open
<http://localhost:8000/> after the `web` container reports healthy.

#### Marketplace workflow

- Buyers browse products at `/products/`, place bids on live auctions, and
  review bids and winning-auction payments from their dashboard.
- Sellers use `/seller-dashboard/` to submit products for review, submit seller
  verification, and schedule approved products for auction approval. Admins
  review these submissions from `/admin-dashboard/`.
- Bidding requires a verified email and an active account. With the local
  console email backend, verification links are written to the `web` container
  logs.
- Default product categories are installed by a data migration, so new seller
  accounts can create listings immediately.
- Razorpay checkout requires valid Razorpay credentials; without them, checkout
  reports that it is unavailable instead of failing with a server error.

Useful commands:

```powershell
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs -f web worker beat
docker compose --env-file .env.docker exec web python manage.py createsuperuser
docker compose --env-file .env.docker run --rm web python manage.py test
docker compose --env-file .env.docker exec backup ls -lh /backups
docker compose --env-file .env.docker down
```

PostgreSQL, Redis, and uploaded media are stored in named Docker volumes and
survive container rebuilds and `down`. To permanently remove the database, Redis data, PostgreSQL backups, and uploaded
media, use `docker compose --env-file .env.docker down --volumes`. That command
is destructive.

The `backup` service creates a PostgreSQL custom-format dump immediately on
startup and every 24 hours, verifies each dump by restoring it into a temporary
database, and retains the latest 14 days of dumps in the `postgres_backups`
volume. Check its progress with:

```powershell
docker compose --env-file .env.docker logs backup
docker compose --env-file .env.docker exec backup ls -lh /backups
```

Run a one-time backup and restore verification on demand with:

```powershell
docker compose --env-file .env.docker run --rm -e BACKUP_ONCE=1 backup
```

#### Optional encrypted S3 copy

The backup service uploads verified dumps to S3 only when `S3_BACKUP_BUCKET` is
configured. It explicitly requests S3-managed server-side encryption (SSE-S3,
`AES256`) and checks the resulting object's encryption metadata. To enable it:

1. Create a private S3 bucket in your chosen AWS region. Keep Block Public Access
   enabled, enable bucket versioning, and add an S3 lifecycle policy appropriate
   to your recovery requirements.
2. Create an IAM identity restricted to this bucket/prefix. It needs permission
   to upload and inspect objects (`s3:PutObject` and `s3:GetObject`); it should
   not have bucket-wide or account-wide administrative permissions. On AWS
   compute, prefer an instance/task role. For Docker Desktop, use dedicated
   limited-scope IAM access keys and rotate them regularly.
3. Edit the private, git-ignored `.env.docker` file and set:

   ```dotenv
   S3_BACKUP_BUCKET=your-private-bucket-name
   S3_BACKUP_PREFIX=auction-postgres
   AWS_REGION=your-bucket-region
   AWS_ACCESS_KEY_ID=your-limited-scope-access-key
   AWS_SECRET_ACCESS_KEY=your-limited-scope-secret
   ```

   Keep the key values private; do not paste them into chat or commit them.
   Leave access-key variables unset when using an AWS instance/task role.
4. Recreate the backup service to load the settings, then run and verify one
   upload:

   ```powershell
   docker compose --env-file .env.docker up -d --build backup
   docker compose --env-file .env.docker run --rm -e BACKUP_ONCE=1 backup
   docker compose --env-file .env.docker logs --tail 30 backup
   ```

   The run must report successful restore validation and S3 encryption
   verification. Confirm the object appears in the intended bucket/prefix and
   test downloading and restoring it into an isolated database. If upload or
   encryption verification fails, the scheduled job reports failure and keeps
   the local dump for recovery/retry.

This local backup volume is on the same desktop as the database: it is not an
off-site disaster-recovery copy and is not encrypted by this application.
Protect the Docker host and volume, and for production export backups through a
restricted process to encrypted off-site storage with separate credentials.
Before restoring over any existing database, take and verify a separate
precautionary backup and follow a reviewed recovery procedure.

The local container uses the console email backend; verification and reset links
appear in `docker compose --env-file .env.docker logs web`. Before enabling real
email delivery, configure the SMTP variables in `.env.docker` and change
`EMAIL_BACKEND` to `django.core.mail.backends.smtp.EmailBackend`.

To test real Razorpay checkout locally, use Razorpay **test-mode** keys only:

1. In the private `.env.docker` (or `backend/.env` for the non-Docker setup), set
   `RAZORPAY_KEY_ID` (`rzp_test_...`) and `RAZORPAY_KEY_SECRET`.
2. Optional, for server-to-server confirmation: in the Razorpay Dashboard add a
   webhook for `payment.captured`, `order.paid` and `payment.failed` pointing at
   `https://<public-url>/api/payments/webhook/razorpay/` and put its secret in
   `RAZORPAY_WEBHOOK_SECRET`. (The browser flow already verifies signatures
   server-side without it.)
3. Recreate the web service so it reads those variables:

   ```powershell
   docker compose --env-file .env.docker up -d --force-recreate web
   ```

Checkout reports "not configured" until valid keys are set. Never put provider
secrets in source control or chat. Use Razorpay's published test cards/UPI IDs in
test mode; do not use real card details for local testing.

This localhost deployment uses HTTP and is intended for a single desktop. Do not
bind it to a LAN interface or expose it to the internet as-is. Remote access
requires a TLS-terminating reverse proxy, an appropriate trusted-origin/host
configuration, secure cookies, and a security review.

## Local Python development

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .venv\\Scripts\\Activate.ps1

pip install -r requirements-dev.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py runserver
```

Run PostgreSQL/Redis locally, configure `.env`, and run the Django development server
when you are not using Docker. The development server is not for production use.
Run tests with `python -m pytest` or `python manage.py test`.

For live auction lifecycle processing, run a worker and beat scheduler:

```bash
celery -A config worker -l INFO
celery -A config beat -l INFO
```

The lifecycle task runs every 10 seconds, moves scheduled auctions into `LIVE`, and closes expired auctions transactionally.

## PostgreSQL

Create a database and role, then set:

```text
DATABASE_URL=postgresql://auction_user:strong-password@db-host:5432/auction_db
```

Do not commit credentials.

## Environment variables

See `.env.example`. Production should supply at minimum:

- `SECRET_KEY`
- `DEBUG=False`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL`
- `REDIS_URL`
- Celery broker/result URLs
- SMTP credentials
- Razorpay key secret and webhook secret

## API overview

- `POST /api/accounts/register/`
- `POST /api/auth/token/`
- `POST /api/auth/token/refresh/`
- `GET/PATCH /api/accounts/me/`
- `GET/POST /api/accounts/seller-verifications/`
- `POST /api/accounts/seller-verifications/{id}/review/` (admin)
- `GET/POST /api/products/products/`
- `POST /api/products/products/{id}/submit/`
- `POST /api/products/products/{id}/review/` (admin)
- `GET/POST /api/auctions/auctions/`
- `POST /api/auctions/auctions/{id}/approve/` (admin)
- `POST /api/bidding/bids/`
- `GET /api/payments/`
- `POST /api/payments/{id}/checkout/`
- `POST /api/payments/webhook/razorpay/`
- `GET /api/notifications/`
- `GET/POST /api/messaging/conversations/`
- `POST /api/messaging/conversations/{id}/message/`
- `GET/POST/PATCH /api/messaging/reports/`
- `GET /api/dashboard/analytics/` (admin)
- `GET /api/audit/` (admin)
- WebSocket: `ws://host/ws/auctions/{auction_id}/`

Product and auction writes are role-restricted: sellers create products and auctions, admins review products and approve auctions, and buyers have read-only access to public listings. Sellers can edit or delete products only while they are drafts or rejected, and can change or delete auctions only before they start and before any bids exist. Repeated checkout requests reuse the current Razorpay session rather than replacing its ID.

## Real-time bidding model

Clients subscribe to an auction WebSocket to receive bid events. Bid submission itself is authenticated REST API traffic. The service:

1. Locks the auction row with `select_for_update()`.
2. Rechecks account eligibility and auction status/time.
3. Rejects seller self-bidding.
4. Recalculates the minimum acceptable bid from server-side state.
5. Rejects duplicate client references.
6. Inserts the bid and updates the leader in one transaction.
7. Creates notifications and an audit event.
8. Broadcasts the resulting authoritative event through Channels.

This prevents clients from setting the authoritative price and substantially reduces race-condition risk. High-scale deployments should also load-test lock contention and consider partitioning/sharding strategies after measuring real traffic.

## Payment security

The browser never determines payment success. The server creates a provider checkout session and marks a payment successful only after a signed provider webhook is verified. Card number, CVV, PIN and banking credentials are never stored.

Set `RAZORPAY_WEBHOOK_SECRET` and expose the webhook endpoint over HTTPS. Replace the example localhost success/cancel URLs with configured application URLs before production.

## Media security

Product images are validated for size and MIME type at the serializer boundary. For production, store media in private/object storage with controlled delivery, antivirus/content scanning, image re-encoding, quotas and CDN delivery. Never trust file extensions alone.

## Security checklist

- [ ] Strong random production `SECRET_KEY`
- [ ] `DEBUG=False`
- [ ] Strict `ALLOWED_HOSTS`
- [ ] HTTPS and HSTS
- [ ] Secure/HTTP-only cookies
- [ ] CSRF protection
- [ ] Secure CORS allowlist
- [ ] PostgreSQL least-privilege credentials
- [ ] Redis not publicly exposed
- [ ] Database backups encrypted and tested
- [ ] Object-storage media access controlled
- [ ] Dependency vulnerability scans
- [ ] SAST/DAST and penetration testing
- [ ] Rate-limit tuning under load
- [ ] Payment webhook secret rotation procedure
- [ ] Admin MFA/SSO through infrastructure or an identity provider
- [ ] Centralized logs and alerting
- [ ] Incident response and audit retention policy
- [ ] Privacy/data-retention/legal review

## Testing

Run:

```bash
python manage.py test
```

or, when pytest-django is installed/configured:

```bash
pytest
```

The repository includes tests for registration, role restrictions on product and auction workflows, product visibility, bid validation, seller self-bidding, auction close/payment creation, repeated checkout behavior, and server-side payment webhook state changes. Add integration/load tests using PostgreSQL + Redis before production, especially for concurrent bids.

## Production deployment

A typical deployment is:

`Internet → CDN/WAF → TLS reverse proxy/load balancer → Gunicorn/Daphne → Django/Channels → PostgreSQL + Redis`

Run ASGI-capable workers for WebSockets (for example Daphne/Uvicorn) and keep Celery worker/beat as separate processes. Use a managed PostgreSQL service and Redis where appropriate.

Static files can be collected to `STATIC_ROOT`. Production media should generally be S3-compatible/object storage rather than a container filesystem.

Run migrations as a controlled release step:

```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

### Example: public HTTPS in front of the existing local Docker stack

The Compose stack in this repository is still a single-host deployment. Its web
port is bound to `127.0.0.1:8000`; PostgreSQL and Redis are not published. A host
reverse proxy can terminate TLS and proxy to that loopback port. This is an
example starting point, not a substitute for a security review or a highly
available production architecture.

1. Point the production DNS name (for example, `auction.example.com`) to the
   host. Restrict the host firewall to the ports you actually need; normally
   public TCP 80/443 for ACME/TLS and HTTP-to-HTTPS redirection. Do not publish
   the Django, PostgreSQL, or Redis ports to the public network.
2. Obtain and renew a trusted TLS certificate. Configure Nginx (or an equivalent
   proxy) to redirect HTTP to HTTPS and forward the original host and scheme.
   The `/ws/` route must support WebSocket upgrades:

   ```nginx
   # Add this map inside Nginx's http {} context (for example, nginx.conf).
   map $http_upgrade $connection_upgrade {
       default upgrade;
       ''      close;
   }

   # Put the following server blocks in the site's Nginx configuration.
   server {
       listen 80;
       server_name auction.example.com;
       return 301 https://$host$request_uri;
   }

   server {
       listen 443 ssl;
       server_name auction.example.com;
       ssl_certificate     /etc/letsencrypt/live/auction.example.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/auction.example.com/privkey.pem;

       location /ws/ {
           proxy_pass http://127.0.0.1:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection $connection_upgrade;
           proxy_set_header Host $host;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_read_timeout 3600s;
           proxy_buffering off;
       }

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

   If the proxy runs in another container, do not use `127.0.0.1` as its
   upstream: put the proxy and web service on a private Docker network, address
   the web service by its Compose service name, and publish only the proxy.
3. Set production values in a private secrets/environment store, not in source
   control. For this application's existing settings, the deployment should
   include:

   ```dotenv
   DEBUG=False
   SECRET_KEY=<unique-random-secret-of-at-least-50-characters>
   ALLOWED_HOSTS=auction.example.com
   CSRF_TRUSTED_ORIGINS=https://auction.example.com
   CORS_ALLOWED_ORIGINS=https://auction.example.com
   BASE_URL=https://auction.example.com
   SECURE_SSL_REDIRECT=True
   SESSION_COOKIE_SECURE=True
   CSRF_COOKIE_SECURE=True
   SECURE_HSTS_SECONDS=0
   SECURE_HSTS_INCLUDE_SUBDOMAINS=False
   SECURE_HSTS_PRELOAD=False
   ```

   Keep `SECURE_PROXY_SSL_HEADER` configured only when the trusted proxy
   overwrites `X-Forwarded-Proto` and direct untrusted clients cannot reach
   Django. The project already sets it to `("HTTP_X_FORWARDED_PROTO", "https")`.
   Use a unique production database password and separate production PostgreSQL
   and Redis services/credentials; do not reuse the local `.env.docker` secrets.
   Configure SMTP and Razorpay secrets separately, and register the Razorpay webhook
   at `https://auction.example.com/api/payments/webhook/razorpay/`.
4. Roll out HSTS only after HTTPS, redirects, subdomains, and recovery access
   have been verified. The example starts with HSTS disabled; then set a short
   `SECURE_HSTS_SECONDS` value and increase it deliberately. Enable
   `SECURE_HSTS_INCLUDE_SUBDOMAINS` only if every
   subdomain is permanently HTTPS, and do not enable `SECURE_HSTS_PRELOAD`
   without understanding the difficult-to-reverse browser preload consequences.
5. Run deployment checks and verify the actual public endpoints:

   ```bash
   python manage.py check --deploy
   curl -I http://auction.example.com/
   curl -I https://auction.example.com/health/
   ```

   Confirm HTTP redirects to HTTPS, static assets load, login/CSRF flows work,
   and live bidding uses `wss://auction.example.com/ws/auctions/<id>/`. Test
   certificate renewal, backups/restores, monitoring, and incident procedures
   before inviting users.

## Backup/recovery

- The local Docker stack produces daily PostgreSQL dumps and verifies them by
  restoring into a temporary database; those local dumps are not encrypted or
  off-site.
- Production: use encrypted off-site backups plus point-in-time recovery where
  supported, with credentials and retention managed separately from the app.
- Test full restore procedures regularly in an isolated environment.
- Back up object-storage media according to retention requirements.
- Keep infrastructure configuration and migration history in version control.
- Define RPO/RTO targets before launch.

## Important production boundaries

Real production readiness still requires:

- Real payment-provider credentials and webhook configuration.
- Production SMTP/provider configuration.
- PostgreSQL/Redis sizing and HA design.
- Object storage/CDN configuration.
- WAF, monitoring, alerting and secrets management.
- Load testing for concurrent auctions and WebSocket fan-out.
- Formal security and privacy review.
- Payment, tax, KYC/verification, marketplace and consumer-law review for the target jurisdiction.

The code deliberately does not contain production secrets.

## React frontend (`frontend/`)

Vite + React + react-router, with a three.js (react-three-fiber) 3D landing scene. Plain JS/JSX, no stylesheet files. `/api`, `/ws` and `/media` are proxied to the backend on port 8000.

Backend rules added for the UI: anti-sniping (a bid in the last `ANTI_SNIPE_WINDOW_SECONDS` extends the auction by `ANTI_SNIPE_EXTENSION_SECONDS`), the current leader cannot raise their own bid, public masked bid history at `/api/bidding/auctions/<id>/bids/`, and `POST /api/payments/<id>/verify/` (checks Razorpay's signature, then re-confirms amount/currency with Razorpay) and `/sync/` (reconciles an open order). Set `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` (and `RAZORPAY_WEBHOOK_SECRET` for webhooks pointing at `/api/payments/webhook/razorpay/`) in `backend/.env`. Amounts are in INR. With no keys and `DEBUG=True`, a demo checkout page is used instead (`PAYMENTS_MOCK`).

## Scheduling: who decides when an auction runs

Auctions run **24/7** for buyers once they are LIVE. *When* each one runs is decided only by an admin:

- **Seller** submits a listing with a *request*: "24/7 - let the admin choose" or a preferred window, plus a note. Seller-supplied times are never the schedule (`start_at`/`end_at` are read-only for everyone except via the admin endpoints).
- **Admin** opens **Admin > Scheduling queue**, reads the review report (seller identity/email/standing, account age, track record, listing completeness, price and bid-step sanity, duplicates, capacity in the chosen window), then **approves with a start/end** or **rejects with a reason**. Rules are enforced server-side: min `AUCTION_MIN_DURATION_MINUTES` (10), max `AUCTION_MAX_DURATION_DAYS` (30), no past start, and at most `AUCTION_MAX_CONCURRENT` (100) auctions overlapping any window. Scheduled auctions can be rescheduled until they receive a bid.
- **Buyers** can *suggest* a better time on an upcoming auction. It lands in the admin's **Time suggestions** inbox; only the admin changes the schedule.
- **Security & data** tab (`GET /api/dashboard/overview/`): queue sizes, live volume, unverified emails/sellers, suspended users, rapid-bidding and repeat-failed-payment flags, money totals, and the latest audit events. Every approval, rejection and reschedule is written to the audit log and notifies the seller.

If port 8000 is used by another program, run both scripts with `$env:BACKEND_PORT=8001` set first.

## AI price estimate from photos (sellers)

When listing an item the seller drops 1-4 photos into the form and clicks **Estimate market value with AI**. The backend re-validates and downsizes each image, sends it to Claude (vision + structured output) and returns the item name, category, condition, description and an expected resale/auction price range in INR, plus a suggested starting price (60% of the low estimate). The result is saved with the product so the admin sees it in **Admin > Products** and in the auction review report (warns when the starting price is far from the estimate).

- Enable it: add `ANTHROPIC_API_KEY=...` to `backend/.env` and restart. Without a key the button is hidden and listing works as before. Model: `AI_VALUATION_MODEL` (default `claude-opus-5-5`).
- Limits: sellers only, 15 estimates per hour per user, 5MB per photo, JPEG/PNG/WebP. Each estimate costs a few US cents.
- It is an estimate from photos only (no live market data) and is labelled as such in the UI. It never sets a price by itself.

## Local development notes

- New accounts are verified automatically when `DEBUG=True` (`AUTO_VERIFY_EMAIL`), because there is no inbox locally. In production the emailed link is required, and signed-in users can use **Resend email** on the bid panel.

## Separate seller and bidder profiles

A person can hold a **Seller** profile and a **Bidder** profile at the same time and use them in different browser tabs.

- **Seller studio** (`/sell`): green theme, stats, photo upload with AI market price, listings, auction requests, business profile and verification. Sellers cannot bid.
- **Bidder** (`/auctions`): gold theme, browse all items, bid, watchlist, my bids, payments, delivery details. Only bidder accounts can place bids (enforced by the API).
- **Profile menu** (top right): switch profile instantly, add another profile, settings, sign out of this profile only. Each tab remembers its own profile; other signed-in profiles stay signed in.
- Signing in or creating an account lands you on the home page of that profile straight away.

## Coins, wallet and payment routing

- **Coin wallet:** every bidder and seller has a coin balance (1 coin = ₹1, `COIN_VALUE`). Each change is a ledger row written in the same database transaction as the balance, so balances cannot drift or be double-spent.
- **Add coins:** bidders top up on **Wallet** with Razorpay or a **fake test payment** (`FAKE_PAYMENTS_ENABLED`, on by default in local development, off in production). Razorpay top-ups are verified by signature and by the webhook, and credit coins exactly once.
- **Pay an invoice:** "Pay now" opens a chooser that routes the payment: **coins**, **Razorpay**, or **fake payment**. Paying with coins debits the bidder and credits the seller (minus `PLATFORM_FEE_PERCENT`, default 0).
- **Sellers** see their coin earnings on **Earnings**. Admins see any person's wallet in **Admin > People**.
- Endpoints: `GET /api/payments/wallet/`, `GET /api/payments/methods/`, `POST /api/payments/wallet/topup/`, `POST /api/payments/<id>/pay-coins/`.
- SQLite is now opened in WAL mode with immediate write locks, which fixes occasional "database is locked" errors when requests and the auction clock write at the same time.

## Security hardening and live auction

**Accounts and tokens**
- Login is rate limited per IP and **locks after 5 failed attempts** for a username from one IP (15 minutes, `LOGIN_LOCK_THRESHOLD` / `LOGIN_LOCK_MINUTES`); 30 failures from anywhere lock the account's logins. Wrong password and unknown user give the same answer. Failures and locks are written to the audit log.
- Access tokens last 15 minutes and refresh silently. Refresh tokens **rotate** and the old one is blacklisted on use; **signing out revokes** the refresh token (`POST /api/auth/logout/`). `last_login` is recorded for admins.

**Bidding abuse**
- Per-user (40/min) and per-lot (15/min) bid throttles. A bid above 10x the current price must be explicitly confirmed (`confirm_large`), which guards against extra-zero typos. Only bidder accounts can bid. A leader cannot outbid themselves. Late bids extend the auction (anti-sniping). Bids and payments are idempotent and written in locked transactions.

**Live auction**
- WebSocket: JWT in the subprotocol, **Origin checked** (cross-site pages refused), suspended users refused, **max 10 connections per user**, size-limited frames, heartbeat. It pushes bids, "went live / sold" status changes and a live **"N watching"** count. Countdowns use the **server clock** (`server_time`), so a wrong device clock cannot show a false end. The last minute shows "Final minute / Going once / Going twice / Last chance".

**Uploads and transport**
- Photos are opened with Pillow (a renamed script is refused), size/pixel capped, re-encoded (strips EXIF/GPS and appended payloads) and stored under a random name. API responses are `no-store` with a strict CSP; Permissions-Policy and COOP are set. In production use HTTPS (`SECURE_SSL_REDIRECT`, HSTS are on when `DEBUG=False`), a shared Redis cache (lockouts/throttles), PostgreSQL and a real `SECRET_KEY`.

**Testing safely:** set `SQLITE_PATH` to a scratch file for demos/E2E so your real `db.sqlite3` is never touched.
