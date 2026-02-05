#!/usr/bin/env python3
"""
Integration tests for the Nginx container.

Sends HTTP requests to each Nginx server block and verifies:
  - Port 8080 returns 200 with the expected HTML
  - Port 8081 returns 403
  - Port 8443 returns 200 over HTTPS
  - Rate limiting triggers 429 on ports 8080 and 8443

Exit code 0 = all passed, 1 = something failed.
"""

import sys
import time
import requests
import urllib3

# Suppress the warning that shows up on every verify=False request
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Config ---
# These need to match the nginx config and docker-compose service name
NGINX_HOST = "nginx"
PORT_HTML = 8080
PORT_ERROR = 8081
PORT_HTTPS = 8443

MAX_RETRIES = 10
RETRY_DELAY = 2

EXPECTED_ERROR_CODE = 403
EXPECTED_CONTENT = "Hello from Nginx!"
RATE_LIMIT_REQUESTS = 20
RATE_LIMIT_CODE = 429


def wait_for_nginx():
    """Keep trying to connect until nginx is up.
    depends_on in compose only waits for the container to start,
    not for nginx to actually be ready to serve."""
    url = f"http://{NGINX_HOST}:{PORT_HTML}/"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            requests.get(url, timeout=2)
            print(f"Nginx is ready (attempt {attempt}/{MAX_RETRIES})")
            return True
        except requests.exceptions.ConnectionError:
            print(f"Waiting for Nginx... (attempt {attempt}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
    print("ERROR: Nginx did not become ready in time.")
    return False


def test_custom_html():
    """Check that port 8080 returns 200 and contains our HTML."""
    url = f"http://{NGINX_HOST}:{PORT_HTML}/"
    print(f"\n--- Test: Custom HTML (GET {url}) ---")

    resp = requests.get(url, timeout=5)

    if resp.status_code != 200:
        print(f"FAIL: Expected 200, got {resp.status_code}")
        return False
    print(f"PASS: Status code is {resp.status_code}")

    if EXPECTED_CONTENT not in resp.text:
        print(f"FAIL: '{EXPECTED_CONTENT}' not found in response")
        print(f"  Got: {resp.text[:200]}")
        return False
    print(f"PASS: Response contains '{EXPECTED_CONTENT}'")

    return True


def test_error_response():
    """Check that port 8081 returns 403."""
    url = f"http://{NGINX_HOST}:{PORT_ERROR}/"
    print(f"\n--- Test: Error Response (GET {url}) ---")

    resp = requests.get(url, timeout=5)

    if resp.status_code != EXPECTED_ERROR_CODE:
        print(f"FAIL: Expected {EXPECTED_ERROR_CODE}, got {resp.status_code}")
        return False
    print(f"PASS: Status code is {resp.status_code}")

    return True


def test_https_html():
    """Check that port 8443 (HTTPS) returns 200 with the HTML.
    verify=False because the cert is self-signed."""
    url = f"https://{NGINX_HOST}:{PORT_HTTPS}/"
    print(f"\n--- Test: HTTPS Custom HTML (GET {url}) ---")

    resp = requests.get(url, timeout=5, verify=False)

    if resp.status_code != 200:
        print(f"FAIL: Expected 200, got {resp.status_code}")
        return False
    print(f"PASS: Status code is {resp.status_code}")

    if EXPECTED_CONTENT not in resp.text:
        print(f"FAIL: '{EXPECTED_CONTENT}' not found in response")
        print(f"  Got: {resp.text[:200]}")
        return False
    print(f"PASS: Response contains '{EXPECTED_CONTENT}'")

    return True


def test_rate_limiting(port, scheme="http"):
    """Send a bunch of rapid requests and check that some get 429.
    We don't assert exact counts because timing varies across environments,
    just that both 200 and 429 show up."""
    url = f"{scheme}://{NGINX_HOST}:{port}/"
    verify_ssl = (scheme != "https")
    print(f"\n--- Test: Rate Limiting ({scheme.upper()} port {port}) ---")
    print(f"Sending {RATE_LIMIT_REQUESTS} rapid requests to {url}")

    codes = []
    for i in range(RATE_LIMIT_REQUESTS):
        try:
            resp = requests.get(url, timeout=5, verify=verify_ssl)
            codes.append(resp.status_code)
        except requests.exceptions.RequestException as e:
            print(f"  Request {i+1} failed: {e}")
            codes.append(0)

    ok = codes.count(200)
    limited = codes.count(RATE_LIMIT_CODE)
    other = len(codes) - ok - limited

    print(f"Results: {ok} x 200, {limited} x 429, {other} x other")

    passed = True
    if ok == 0:
        print("FAIL: No 200 responses (endpoint might be down)")
        passed = False
    else:
        print(f"PASS: Got {ok} successful responses")

    if limited == 0:
        print("FAIL: No 429 responses (rate limiting might not be working)")
        passed = False
    else:
        print(f"PASS: Got {limited} rate-limited responses")

    if other > 0:
        print(f"WARNING: {other} requests returned unexpected status codes")

    return passed


def main():
    print("=" * 60)
    print("Starting Nginx integration tests")
    print("=" * 60)

    if not wait_for_nginx():
        print("\nRESULT: FAIL (Nginx not reachable)")
        sys.exit(1)

    results = []
    results.append(("Custom HTML (port 8080)", test_custom_html()))
    results.append(("Error Response (port 8081)", test_error_response()))
    results.append(("HTTPS Custom HTML (port 8443)", test_https_html()))

    # Wait for the rate limiter to reset before testing it.
    # The tests above already made requests that count against the limit,
    # and both ports share the same zone, so we need the counters to drain.
    print("\nWaiting 3s for rate limiter to reset...")
    time.sleep(3)

    results.append(("Rate Limiting HTTP (port 8080)", test_rate_limiting(PORT_HTML, "http")))

    # Wait again between rate limit tests since they share the same zone
    print("\nWaiting 3s for rate limiter to reset...")
    time.sleep(3)

    results.append(("Rate Limiting HTTPS (port 8443)", test_rate_limiting(PORT_HTTPS, "https")))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\nRESULT: ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("\nRESULT: SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
