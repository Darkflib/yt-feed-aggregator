"""Feed aggregation module for YouTube RSS feeds."""

from .aggregator import aggregate_feeds, decode_cursor, is_short, make_cursor

__all__ = ["aggregate_feeds", "decode_cursor", "is_short", "make_cursor"]
