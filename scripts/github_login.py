"""Bounded device-flow recovery for the already authorized GitHub CLI app.

Uses the public client ID from cli/cli internal/authflow/flow.go and GitHub's
documented device protocol. Credentials go to gh on stdin, never a file/log.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPRedirectHandler, Request

ROOT = Path(__file__).resolve().parent.parent
CLIENT_ID = "178c6fc778ccc68e1d6a"
ACCOUNT = "OQTI2JWL80"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url, form=None, token=None):
    headers = {"Accept": "application/json", "User-Agent": "morning-news-cards-login-recovery"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = urlencode(form).encode() if form is not None else None
    with build_opener(NoRedirect()).open(Request(url, data=data, headers=headers), timeout=20) as reply:
        return json.loads(reply.read(100_000))


def main():
    print("1/4 GitHub device authorization request", flush=True)
    code = request("https://github.com/login/device/code", {
        "client_id": CLIENT_ID, "scope": "repo read:org gist workflow",
    })
    if not all(k in code for k in ("device_code", "user_code", "expires_in", "interval")):
        raise ValueError("Invalid device response")
    print("Verification URL: https://github.com/login/device", flush=True)
    print("One-time code: " + code["user_code"], flush=True)
    print("2/4 Waiting for browser approval (bounded network requests)", flush=True)
    deadline = time.monotonic() + min(int(code["expires_in"]), 600)
    interval = max(5, int(code["interval"]))
    last_notice = 0
    failures = 0
    token = None
    while time.monotonic() < deadline:
        time.sleep(interval)
        try:
            response = request("https://github.com/login/oauth/access_token", {
                "client_id": CLIENT_ID,
                "device_code": code["device_code"],
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            })
            failures = 0
        except (URLError, TimeoutError, OSError):
            failures += 1
            print("Authorization response timeout/network failure", flush=True)
            if failures >= 3:
                return 2
            continue
        if response.get("access_token"):
            token = response["access_token"]
            break
        error = response.get("error")
        if error == "slow_down":
            interval += 5
        elif error != "authorization_pending":
            print("Authorization stopped: " + (error if error in {
                "access_denied", "expired_token", "incorrect_device_code", "incorrect_client_credentials",
            } else "unexpected_response"), flush=True)
            return 2
        if time.monotonic() - last_notice >= 30:
            print("GitHub reply: authorization_pending", flush=True)
            last_notice = time.monotonic()
    if not token:
        print("Authorization window expired", flush=True)
        return 2
    print("3/4 Authorization received; validating account", flush=True)
    user = request("https://api.github.com/user", token=token)
    if user.get("login", "").lower() != ACCOUNT.lower():
        print("Wrong account; required account: " + ACCOUNT, flush=True)
        return 2
    print("Account verified: " + ACCOUNT, flush=True)
    print("4/4 Saving authorization through official GitHub CLI", flush=True)
    env = os.environ.copy()
    env["GH_CONFIG_DIR"] = str(ROOT / ".local" / "gh-config")
    env["GODEBUG"] = "http2client=0"
    for key in ("GH_TOKEN", "GITHUB_TOKEN"):
        env.pop(key, None)
    gh = ROOT / ".local" / "tools" / "github-cli" / "bin" / "gh.exe"
    try:
        result = subprocess.run([str(gh), "auth", "login", "--hostname", "github.com",
                                 "--git-protocol", "https", "--with-token"],
                                input=token + "\n", text=True, capture_output=True,
                                timeout=40, env=env)
    except subprocess.TimeoutExpired:
        print("CLI credential storage/account check timed out", flush=True)
        return 2
    if result.returncode:
        # Do not print raw output: it may echo credential-bearing headers.
        print("CLI credential setup failed", flush=True)
        return 2
    print("GitHub connection completed", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except HTTPError as exc:
        print("Stopped at HTTP " + str(exc.code), flush=True)
        sys.exit(2)
    except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
        print("Connection stopped; no credential values were logged", flush=True)
        sys.exit(2)
