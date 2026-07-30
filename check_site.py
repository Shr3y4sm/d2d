#!/usr/bin/env python3
"""
Pre-flight diagnostic for a supplier site, BEFORE you invest time authoring
a custom webcmd adapter for it.

`webcmd browser <session> analyze <url>` classifies the anti-bot vendor (if
any), suggests real-data API candidates (sometimes there's a JSON endpoint
you can call directly instead of scraping HTML), tells you which of
webcmd's four navigation patterns (A/B/C/D) the site matches, points at the
nearest existing adapter to crib from, and recommends a next step.

Usage:
    python3 check_site.py https://robu.in
    python3 check_site.py https://www.mouser.in
"""
import sys
import subprocess


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 check_site.py <url>")
        sys.exit(1)

    url = sys.argv[1]
    session = "site_check"
    print(f"Analyzing {url} ...\n")

    res = subprocess.run(
        ["webcmd", "browser", session, "analyze", url],
        capture_output=True, text=True, timeout=60,
    )
    subprocess.run(["webcmd", "browser", session, "close"], capture_output=True, text=True, timeout=15)

    print(res.stdout or "(no output)")
    if res.stderr:
        print("---stderr---")
        print(res.stderr)

    if res.returncode != 0:
        print(f"\nExit code {res.returncode} — is webcmd installed and is a browser reachable "
              f"(local Chromium, or `webcmd setup` in Cloud mode)?")
        sys.exit(res.returncode)


if __name__ == "__main__":
    main()
