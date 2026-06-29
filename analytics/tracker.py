"""
analytics/tracker.py

Thin reporting layer over storage/persistence.py's click-count columns.
Click recording itself happens inside URLShortener.resolve() (so every
lookup is automatically tracked); this module is just for *reading* that
data back out in useful shapes -- per-link stats, leaderboards, and a
simple human-readable summary report.
"""

import time
from dataclasses import dataclass
from typing import Optional, List, Dict


@dataclass
class LinkStats:
    short_code: str
    long_url: str
    created_at: float
    click_count: int
    last_accessed: Optional[float]

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    def as_dict(self) -> Dict:
        return {
            "short_code": self.short_code,
            "long_url": self.long_url,
            "created_at": self.created_at,
            "click_count": self.click_count,
            "last_accessed": self.last_accessed,
            "age_seconds": round(self.age_seconds, 1),
        }


class AnalyticsTracker:
    def __init__(self, shortener):
        self.shortener = shortener

    def get_link_stats(self, short_code: str) -> Optional[LinkStats]:
        row = self.shortener.stats_for(short_code)
        if row is None:
            return None
        return LinkStats(**row)

    def leaderboard(self, n: int = 10) -> List[LinkStats]:
        rows = self.shortener.top_urls(n)
        return [LinkStats(**row) for row in rows]

    def summary(self) -> Dict:
        overview = self.shortener.overview()
        top = self.leaderboard(5)
        return {
            "total_urls": overview["total_urls"],
            "total_clicks": overview["total_clicks"],
            "avg_clicks_per_url": round(
                overview["total_clicks"] / overview["total_urls"], 2
            ) if overview["total_urls"] else 0.0,
            "top_5_links": [s.as_dict() for s in top],
        }

    def print_report(self):
        summary = self.summary()
        print("=" * 50)
        print("URL SHORTENER -- ANALYTICS SUMMARY")
        print("=" * 50)
        print(f"Total shortened URLs : {summary['total_urls']}")
        print(f"Total clicks         : {summary['total_clicks']}")
        print(f"Avg clicks per URL   : {summary['avg_clicks_per_url']}")
        print("\nTop links:")
        for link in summary["top_5_links"]:
            print(f"  /{link['short_code']:<10} -> {link['long_url'][:50]:<50} "
                  f"({link['click_count']} clicks)")
        print("=" * 50)
