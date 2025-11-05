"""Tests for feed aggregator functionality."""

from datetime import datetime, timezone

import pytest

from app.feed import aggregate_feeds, decode_cursor, is_short, make_cursor
from app.rss.models import FeedItem


def make_item(
    video_id: str,
    published: datetime,
    is_short: bool = False,
    channel_id: str = "UC_test",
) -> FeedItem:
    """Helper to create a FeedItem for testing."""
    path = "/shorts/" if is_short else "/watch?v="
    return FeedItem(
        video_id=video_id,
        channel_id=channel_id,
        title=f"Video {video_id}",
        link=f"https://www.youtube.com{path}{video_id}",
        published=published,
    )


class TestIsShort:
    """Tests for is_short function."""

    def test_regular_video(self):
        """Regular YouTube videos should return False."""
        item = make_item("abc123", datetime.now(timezone.utc), is_short=False)
        assert is_short(item) is False

    def test_short_video(self):
        """YouTube Shorts should return True."""
        item = make_item("xyz789", datetime.now(timezone.utc), is_short=True)
        assert is_short(item) is True

    def test_case_insensitive(self):
        """Shorts detection should be case-insensitive."""
        item = FeedItem(
            video_id="test",
            channel_id="UC_test",
            title="Test",
            link="https://www.youtube.com/SHORTS/test123",
            published=datetime.now(timezone.utc),
        )
        assert is_short(item) is True


class TestCursorOperations:
    """Tests for cursor encoding and decoding."""

    def test_make_and_decode_cursor(self):
        """Cursor should encode and decode correctly."""
        item = make_item("video123", datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc))
        cursor = make_cursor(item)

        # Cursor should be a non-empty string
        assert isinstance(cursor, str)
        assert len(cursor) > 0

        # Decode should return the same values
        timestamp, video_id = decode_cursor(cursor)
        assert timestamp == int(item.published.timestamp())
        assert video_id == item.video_id

    def test_cursor_deterministic(self):
        """Same item should produce same cursor."""
        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        item1 = make_item("video123", dt)
        item2 = make_item("video123", dt)

        cursor1 = make_cursor(item1)
        cursor2 = make_cursor(item2)
        assert cursor1 == cursor2


class TestAggregateFeedsBasic:
    """Basic tests for aggregate_feeds function."""

    def test_empty_feeds(self):
        """Empty feeds should return empty results."""
        result = aggregate_feeds([])
        assert result["items"] == []
        assert result["next_cursor"] is None

    def test_empty_feed_list(self):
        """List with empty feeds should return empty results."""
        result = aggregate_feeds([[], []])
        assert result["items"] == []
        assert result["next_cursor"] is None

    def test_single_feed(self):
        """Single feed should be returned sorted."""
        dt1 = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2024, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        dt3 = datetime(2024, 1, 14, 12, 0, 0, tzinfo=timezone.utc)

        feed = [
            make_item("video1", dt1),
            make_item("video2", dt2),
            make_item("video3", dt3),
        ]

        result = aggregate_feeds([feed], limit=10)
        items = result["items"]

        # Should be sorted by date descending
        assert len(items) == 3
        assert items[0].video_id == "video2"  # newest
        assert items[1].video_id == "video1"
        assert items[2].video_id == "video3"  # oldest

    def test_multiple_feeds_merge_and_sort(self):
        """Multiple feeds should be merged and sorted by date."""
        dt1 = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2024, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        dt3 = datetime(2024, 1, 14, 12, 0, 0, tzinfo=timezone.utc)
        dt4 = datetime(2024, 1, 17, 12, 0, 0, tzinfo=timezone.utc)

        feed1 = [
            make_item("video1", dt1, channel_id="UC_1"),
            make_item("video2", dt2, channel_id="UC_1"),
        ]
        feed2 = [
            make_item("video3", dt3, channel_id="UC_2"),
            make_item("video4", dt4, channel_id="UC_2"),
        ]

        result = aggregate_feeds([feed1, feed2], limit=10)
        items = result["items"]

        # Should be sorted by date descending across all feeds
        assert len(items) == 4
        assert items[0].video_id == "video4"  # Jan 17 - newest
        assert items[1].video_id == "video2"  # Jan 16
        assert items[2].video_id == "video1"  # Jan 15
        assert items[3].video_id == "video3"  # Jan 14 - oldest


class TestShortsFiltering:
    """Tests for Shorts filtering functionality."""

    def test_filter_shorts_by_default(self):
        """Shorts should be filtered out by default."""
        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        feed = [
            make_item("regular1", dt, is_short=False),
            make_item("short1", dt, is_short=True),
            make_item("regular2", dt, is_short=False),
        ]

        result = aggregate_feeds([feed], limit=10)
        items = result["items"]

        assert len(items) == 2
        assert all(not is_short(item) for item in items)
        # Items with same timestamp are sorted by video_id descending
        assert items[0].video_id == "regular2"
        assert items[1].video_id == "regular1"

    def test_include_shorts_when_flag_set(self):
        """Shorts should be included when include_shorts=True."""
        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        feed = [
            make_item("regular1", dt, is_short=False),
            make_item("short1", dt, is_short=True),
            make_item("regular2", dt, is_short=False),
        ]

        result = aggregate_feeds([feed], include_shorts=True, limit=10)
        items = result["items"]

        assert len(items) == 3

    def test_all_shorts(self):
        """Feed with all shorts should return empty when filtered."""
        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        feed = [
            make_item("short1", dt, is_short=True),
            make_item("short2", dt, is_short=True),
        ]

        result = aggregate_feeds([feed], limit=10)
        assert result["items"] == []
        assert result["next_cursor"] is None

    def test_no_shorts(self):
        """Feed with no shorts should return all items."""
        dt1 = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2024, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        feed = [
            make_item("regular1", dt1, is_short=False),
            make_item("regular2", dt2, is_short=False),
        ]

        result = aggregate_feeds([feed], limit=10)
        items = result["items"]

        assert len(items) == 2


class TestPagination:
    """Tests for cursor-based pagination."""

    def test_pagination_basic(self):
        """Basic pagination should work correctly."""
        # Create 5 items with different timestamps
        items = [
            make_item(f"video{i}", datetime(2024, 1, i + 1, 12, 0, 0, tzinfo=timezone.utc))
            for i in range(5)
        ]

        # Get first page with limit of 2
        result = aggregate_feeds([items], limit=2)
        page1 = result["items"]
        cursor1 = result["next_cursor"]

        assert len(page1) == 2
        assert page1[0].video_id == "video4"  # Jan 5 - newest
        assert page1[1].video_id == "video3"  # Jan 4
        assert cursor1 is not None

        # Get second page using cursor
        result = aggregate_feeds([items], limit=2, cursor=cursor1)
        page2 = result["items"]
        cursor2 = result["next_cursor"]

        assert len(page2) == 2
        assert page2[0].video_id == "video2"  # Jan 3
        assert page2[1].video_id == "video1"  # Jan 2
        assert cursor2 is not None

        # Get last page
        result = aggregate_feeds([items], limit=2, cursor=cursor2)
        page3 = result["items"]
        cursor3 = result["next_cursor"]

        assert len(page3) == 1
        assert page3[0].video_id == "video0"  # Jan 1 - oldest
        assert cursor3 is None  # No more items

    def test_no_next_cursor_when_exact_limit(self):
        """No next cursor when items exactly match limit."""
        items = [
            make_item(f"video{i}", datetime(2024, 1, i + 1, 12, 0, 0, tzinfo=timezone.utc))
            for i in range(3)
        ]

        result = aggregate_feeds([items], limit=3)
        assert len(result["items"]) == 3
        assert result["next_cursor"] is None

    def test_next_cursor_when_more_items(self):
        """Next cursor should be present when more items exist."""
        items = [
            make_item(f"video{i}", datetime(2024, 1, i + 1, 12, 0, 0, tzinfo=timezone.utc))
            for i in range(5)
        ]

        result = aggregate_feeds([items], limit=3)
        assert len(result["items"]) == 3
        assert result["next_cursor"] is not None

    def test_deterministic_pagination(self):
        """Same cursor should always return same results."""
        items = [
            make_item(f"video{i}", datetime(2024, 1, i + 1, 12, 0, 0, tzinfo=timezone.utc))
            for i in range(10)
        ]

        # Get first page twice
        result1 = aggregate_feeds([items], limit=3)
        result2 = aggregate_feeds([items], limit=3)

        assert result1["next_cursor"] == result2["next_cursor"]
        assert len(result1["items"]) == len(result2["items"])

        # Get second page using same cursor twice
        cursor = result1["next_cursor"]
        result3 = aggregate_feeds([items], limit=3, cursor=cursor)
        result4 = aggregate_feeds([items], limit=3, cursor=cursor)

        assert result3["next_cursor"] == result4["next_cursor"]
        assert len(result3["items"]) == len(result4["items"])
        assert result3["items"][0].video_id == result4["items"][0].video_id


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_pagination_with_shorts_filtered(self):
        """Pagination should work correctly when shorts are filtered."""
        items = [
            make_item("video0", datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc), is_short=False),
            make_item("short1", datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc), is_short=True),
            make_item("video2", datetime(2024, 1, 3, 12, 0, 0, tzinfo=timezone.utc), is_short=False),
            make_item("short3", datetime(2024, 1, 4, 12, 0, 0, tzinfo=timezone.utc), is_short=True),
            make_item("video4", datetime(2024, 1, 5, 12, 0, 0, tzinfo=timezone.utc), is_short=False),
        ]

        # First page - should only have regular videos
        result = aggregate_feeds([items], limit=2, include_shorts=False)
        page1 = result["items"]

        assert len(page1) == 2
        assert page1[0].video_id == "video4"
        assert page1[1].video_id == "video2"
        assert result["next_cursor"] is not None

        # Second page
        result = aggregate_feeds([items], limit=2, cursor=result["next_cursor"], include_shorts=False)
        page2 = result["items"]

        assert len(page2) == 1
        assert page2[0].video_id == "video0"
        assert result["next_cursor"] is None

    def test_same_timestamp_different_video_ids(self):
        """Items with same timestamp should be handled consistently."""
        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        items = [
            make_item("video_a", dt),
            make_item("video_b", dt),
            make_item("video_c", dt),
        ]

        result = aggregate_feeds([items], limit=2)
        page1 = result["items"]

        assert len(page1) == 2
        assert result["next_cursor"] is not None

        # Get next page
        result = aggregate_feeds([items], limit=2, cursor=result["next_cursor"])
        page2 = result["items"]

        # Should get remaining item
        assert len(page2) == 1

        # Combined pages should have all videos (no duplicates, no missing)
        all_video_ids = [item.video_id for item in page1 + page2]
        assert sorted(all_video_ids) == ["video_a", "video_b", "video_c"]

    def test_large_feed_pagination(self):
        """Pagination should work with large number of items."""
        items = [
            make_item(
                f"video{i:03d}",
                datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc).replace(hour=i % 24),
            )
            for i in range(100)
        ]

        # Get multiple pages
        all_items = []
        cursor = None
        page_count = 0
        max_pages = 10  # Safety limit

        while page_count < max_pages:
            result = aggregate_feeds([items], limit=10, cursor=cursor)
            all_items.extend(result["items"])
            cursor = result["next_cursor"]
            page_count += 1

            if cursor is None:
                break

        # Should get all 100 items
        assert len(all_items) == 100
        # Should have taken 10 pages
        assert page_count == 10

    def test_cursor_with_empty_result_after_filtering(self):
        """Cursor pagination should work when filtering leaves empty results."""
        # All items are shorts
        items = [
            make_item(f"short{i}", datetime(2024, 1, i + 1, 12, 0, 0, tzinfo=timezone.utc), is_short=True)
            for i in range(5)
        ]

        result = aggregate_feeds([items], limit=10, include_shorts=False)
        assert result["items"] == []
        assert result["next_cursor"] is None
