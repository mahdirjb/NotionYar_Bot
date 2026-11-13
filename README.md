# NotionYar

NotionYar is a Telegram bot and installable web app for Life Tracker, daily habits,
Salah and Quran records backed by Notion.

## Android app

The `android/` project is a small native Android shell around the same production
web app. This keeps the backend, web login, Telegram integration and offline outbox
in one place while providing an installable Android experience. Build it with
Android Studio or `android\gradlew.bat assembleDebug`. The resulting APK uses
`https://notionyar.rjbzmhd.ir/` by default and accepts `-PwebAppUrl=...` for staging.

## Web access

The same application can be opened directly from a browser. Telegram users are
authenticated with Telegram `initData`; direct web users sign in with a secure,
signed, `HttpOnly` session cookie.

1. Copy `.env.example` values into the existing `.env` and replace placeholders.
2. Set the domain and host variables:

   ```dotenv
   # Optional: these can also be set from Telegram -> /admin
   WEB_LOGIN_USERNAME=your_username
   WEBAPP_URL=https://notionyar.example.com
   ALLOWED_HOSTS=notionyar.example.com
   CORS_ORIGINS=https://notionyar.example.com
   WEB_COOKIE_SECURE=true
   ALLOW_DEV_BYPASS=false
   ```

3. Start exactly one application process:

   ```powershell
   .\venv\Scripts\python.exe main.py
   ```

Do not run multiple Uvicorn workers. Every process starts Telegram polling and the
nightly scheduler, so multiple workers would duplicate bot updates and reminders.

## Domain and HTTPS

### Railway

1. Open the deployed service and go to `Settings -> Networking -> Public Networking`.
2. Choose `Custom Domain`, enter the domain, and select the port used by `$PORT`.
3. Add both DNS records Railway displays: the routing `CNAME` (or flattened
   `CNAME`/`ALIAS`/`ANAME` for an apex domain) and the ownership verification `TXT`.
4. After Railway verifies the domain and provisions HTTPS, set these service variables:

   ```dotenv
   WEBAPP_URL=https://app.example.com
   ALLOWED_HOSTS=app.example.com
   CORS_ORIGINS=https://app.example.com
   WEB_COOKIE_SECURE=true
   WEB_CREDENTIALS_FILE=/app/data/web_credentials.json
   # WEB_SESSION_SECRET is optional; the app generates and persists it automatically.
   ```

5. Add a Railway Volume mounted at `/app/data`. This keeps the generated session key
   and username/password changes made in the Admin panel across deploys and restarts.
6. Redeploy or restart the service. On startup, NotionYar updates Telegram's chat
   menu button to `WEBAPP_URL`, so the Mini App and browser use the same deployment.

The deployment health endpoint is `https://app.example.com/health` and should return
`{"status":"ok"}`. Use the exact public HTTP service port assigned to `$PORT` in
Railway's custom-domain target settings.

Railway does not publish a static IP for custom domains; do not create an `A` record
for it. If Cloudflare proxying is enabled, use `Full` SSL mode and keep the Railway
verification `TXT` record in place.

### Self-hosted server

For a server with a static IP, create an `A` or `AAAA` record for the chosen
subdomain. Keep the Python app bound to its internal port and place an HTTPS reverse
proxy in front of it. A minimal Caddy configuration is:

```caddyfile
notionyar.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

Caddy provisions and renews HTTPS automatically. HTTPS is required for secure web
cookies, Telegram Mini Apps and service workers outside `localhost`.

## Offline behavior

After the first successful online visit, the PWA caches its shell and recently read
API data. Create, update and delete requests made without a connection are stored in
IndexedDB, including a page-level fallback for the first visit before the Service
Worker takes control. They are replayed in order when the browser reconnects or when
the app becomes visible again. Temporary gateway errors are also queued, while
authentication requests are never stored offline. The header badge shows offline,
queued and syncing states and can be pressed to retry synchronization.

Web credentials can be created or changed from Telegram: open `/admin`, choose
`🔐 تنظیم ورود نسخه وب`, then send the username and password. The password message is
deleted after processing. The web admin panel can also change credentials later.
`WEB_SESSION_SECRET` is optional; if it is missing, a cryptographically random key is
created in `/app/data/web_session_secret.txt`. A Railway Volume mounted at `/app/data`
is required for that generated key and the credentials to survive a new deploy.
Password changes rotate the session version and invalidate older browser sessions.

Use the web logout button on shared devices. Logout clears cached API data and the
local mutation queue.

## Local web-login test

For local HTTP only, use `WEB_COOKIE_SECURE=false`. Restore it to `true` before
deploying behind HTTPS. `ALLOW_DEV_BYPASS=true` is only for isolated local testing.
