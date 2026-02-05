# DevOps Assignment

Dockerized Nginx setup with integration tests, HTTPS, rate limiting, and CI via GitHub Actions.

## What's in the project

Two Docker containers orchestrated with Docker Compose:

- **Nginx container** (built on Ubuntu 24.04):
  - Port 8080 — serves a custom HTML page over HTTP
  - Port 8443 — serves the same page over HTTPS (self-signed cert)
  - Port 8081 — always returns `403 Forbidden`
  - Rate limiting on ports 8080 and 8443 (5 req/s per IP)

- **Test container** (Python on Alpine):
  - Runs 5 integration tests that hit all the Nginx endpoints
  - Verifies HTTP responses, HTTPS, and rate limiting behavior
  - Exits with code 0 on success, 1 on failure

```
devops-assignment/
├── docker-compose.yml
├── nginx/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── sites/
│   │   ├── custom-html.conf      # port 8080
│   │   ├── https-html.conf       # port 8443
│   │   └── error-response.conf   # port 8081
│   └── html/
│       └── index.html
├── tests/
│   ├── Dockerfile
│   └── test_nginx.py
└── .github/
    └── workflows/
        └── ci.yml
```

## How to run

Make sure Docker is running, then:

```bash
docker compose up --build --abort-on-container-exit
```

This builds both images, starts Nginx, runs the tests, and stops everything once the tests finish.
Look for `RESULT: ALL TESTS PASSED` in the output.

To clean up afterwards:
```bash
docker compose down
```

If you want to poke around in the browser:
```bash
docker build -t nginx-custom ./nginx
docker run -p 8080:8080 -p 8081:8081 -p 8443:8443 nginx-custom
```
Then go to `http://localhost:8080`, `https://localhost:8443` (you'll get a cert warning, that's normal), or `http://localhost:8081`.

## Design choices

- **Ubuntu base for Nginx** — required by the assignment. I used `ubuntu:24.04` with a specific tag so builds are reproducible.
- **Python for tests** — I went with Python over Go because the test logic is simple HTTP requests and Python's `requests` library makes that very readable. Used `python:3-alpine` to keep the image small (~55MB instead of ~900MB for the full Python image).
- **`expose` instead of `ports`** in docker-compose — the tests talk to Nginx over Docker's internal network, so there's no reason to expose ports on the host.
- **Retry logic in the test script** instead of Docker healthchecks — `depends_on` only waits for the container to start, not for Nginx to actually be ready. I added a simple retry loop in the test script to handle this. Simpler than adding curl to the Nginx image just for a healthcheck.
- **403 for the error endpoint** — I picked 403 Forbidden because it's a clear, recognizable error code. Could have used any 4xx/5xx code.
- **Certificate generated at build time** — the self-signed cert is baked into the image so there's no generation overhead at runtime.
- **Single RUN layer** for apt-get in the Nginx Dockerfile — combining install and cleanup in one layer keeps the image smaller because Docker layers are additive (if you clean up in a separate layer, the deleted files still exist in the previous layer).

## HTTPS setup

Port 8443 serves the same content as 8080 but over TLS. The certificate is self-signed and generated during `docker build` with OpenSSL.

- Only TLS 1.2 and 1.3 are enabled (1.0 and 1.1 have known vulnerabilities)
- Browsers will show a warning because the cert isn't from a real CA — just click through it

The cert and key live at `/etc/nginx/ssl/selfsigned.crt` and `/etc/nginx/ssl/selfsigned.key` inside the container.

## Rate limiting

Rate limiting is set to **5 requests per second** per client IP, with a burst allowance of 10.

How it works:
- `limit_req_zone` in `nginx.conf` defines the shared memory zone that tracks request counts per IP
- `limit_req` in the site configs (ports 8080 and 8443) applies the actual limit
- `burst=10` lets clients briefly exceed the limit by up to 10 extra requests
- `nodelay` serves burst requests immediately instead of queuing them
- Requests beyond rate + burst get **HTTP 429 Too Many Requests**
- Port 8081 is not rate-limited (it just returns an error anyway)

### Changing the rate limit

To change the rate, edit the `rate=` value in `nginx/nginx.conf`:
```nginx
# default
limit_req_zone $binary_remote_addr zone=req_limit:10m rate=5r/s;

# example: 10 per second
limit_req_zone $binary_remote_addr zone=req_limit:10m rate=10r/s;
```

To change the burst, edit `limit_req` in `nginx/sites/custom-html.conf` and `nginx/sites/https-html.conf`:
```nginx
# default
limit_req zone=req_limit burst=10 nodelay;

# example: stricter, no burst
limit_req zone=req_limit;
```

Rebuild after changes: `docker compose up --build --abort-on-container-exit`

## CI pipeline

GitHub Actions workflow in `.github/workflows/ci.yml` runs on every push and every PR to main.

It does:
1. Checks out the code
2. Runs `docker compose up --build --abort-on-container-exit`
3. Based on the exit code, creates either a `succeeded` or `fail` file
4. Uploads it as a GitHub Actions artifact called `test-result`

## Troubleshooting

- **"Cannot connect to the Docker daemon"** — Docker Desktop isn't running, start it
- **Tests fail with connection errors** — Nginx might be slow to start. The test retries 10 times with 2s delays. Check `docker compose logs nginx` if it still fails
- **No 429 in rate limit test** — if requests are too slow (e.g. slow CI runner), they might all fit within the limit. Try bumping `RATE_LIMIT_REQUESTS` in `test_nginx.py`
- **Browser cert warning on :8443** — expected with self-signed certs, click through it
