"""
cli.py

Interactive command-line interface for the URL shortener -- lets you create
short links, resolve them, and view analytics without spinning up the Flask
API. Persists to the same SQLite file across runs, so you can close the CLI
and reopen it later and your links are still there (the "recovery across
sessions" requirement).

Usage:
    python cli.py shorten "https://example.com/some/long/path"
    python cli.py resolve <code>
    python cli.py stats <code>
    python cli.py summary
    python cli.py repl              # interactive mode
"""

import argparse
import sys

from core.shortener import URLShortener
from storage.persistence import SQLiteStore
from analytics.tracker import AnalyticsTracker

DB_PATH = "url_shortener.db"


def make_shortener() -> URLShortener:
    return URLShortener(store=SQLiteStore(DB_PATH))


def cmd_shorten(shortener, args):
    code = shortener.shorten(args.url)
    print(f"short_code: {code}")
    print(f"short_url : http://localhost:5000/{code}")


def cmd_resolve(shortener, args):
    long_url = shortener.resolve(args.code)
    if long_url is None:
        print(f"No URL found for code '{args.code}'", file=sys.stderr)
        sys.exit(1)
    print(long_url)


def cmd_stats(shortener, args):
    tracker = AnalyticsTracker(shortener)
    stats = tracker.get_link_stats(args.code)
    if stats is None:
        print(f"No URL found for code '{args.code}'", file=sys.stderr)
        sys.exit(1)
    for k, v in stats.as_dict().items():
        print(f"{k:15}: {v}")


def cmd_summary(shortener, args):
    tracker = AnalyticsTracker(shortener)
    tracker.print_report()


def repl(shortener):
    print("URL Shortener REPL. Commands: shorten <url> | resolve <code> | stats <code> | summary | quit")
    tracker = AnalyticsTracker(shortener)
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()

        if cmd in ("quit", "exit"):
            break
        elif cmd == "shorten" and len(parts) == 2:
            print(shortener.shorten(parts[1]))
        elif cmd == "resolve" and len(parts) == 2:
            result = shortener.resolve(parts[1])
            print(result if result else "not found")
        elif cmd == "stats" and len(parts) == 2:
            stats = tracker.get_link_stats(parts[1])
            print(stats.as_dict() if stats else "not found")
        elif cmd == "summary":
            tracker.print_report()
        else:
            print("Unrecognized command.")


def main():
    parser = argparse.ArgumentParser(description="URL Shortener Simulator CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_shorten = sub.add_parser("shorten")
    p_shorten.add_argument("url")

    p_resolve = sub.add_parser("resolve")
    p_resolve.add_argument("code")

    p_stats = sub.add_parser("stats")
    p_stats.add_argument("code")

    sub.add_parser("summary")
    sub.add_parser("repl")

    args = parser.parse_args()
    shortener = make_shortener()

    try:
        if args.command == "shorten":
            cmd_shorten(shortener, args)
        elif args.command == "resolve":
            cmd_resolve(shortener, args)
        elif args.command == "stats":
            cmd_stats(shortener, args)
        elif args.command == "summary":
            cmd_summary(shortener, args)
        elif args.command == "repl":
            repl(shortener)
    finally:
        shortener.close()


if __name__ == "__main__":
    main()
