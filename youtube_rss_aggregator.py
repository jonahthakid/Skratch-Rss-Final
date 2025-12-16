#!/usr/bin/env python3
"""
YouTube Multi-Channel RSS Aggregator for Skratch Golf
Combines multiple YouTube channel feeds into a single Media RSS feed.

Usage:
    python youtube_rss_aggregator.py > skratch_combined.xml
"""

import feedparser
import requests
import re
from datetime import datetime, timezone
import html
from typing import List, Dict, Optional

# ============================================================================
# CONFIGURATION - Add your feeds here
# ============================================================================

YOUTUBE_CHANNELS = [
    {
        "name": "Skratch",
        "channel_id": "UCwtGQ3sgidNlQGbIUBPP3xw",
    },
    {
        "name": "Dan On Golf Show", 
        "channel_id": "UCQvs9V1djea1wFurLJPlqMg",
    },
]

RSS_FEEDS = [
    {
        "name": "Skratch Articles",
        "url": "https://www.skratch.golf/rss",
        "content_type": "article",
    },
]

FEED_TITLE = "Skratch Golf Video Feed"
FEED_DESCRIPTION = "Combined video feed from Skratch Golf YouTube channels"
FEED_LINK = "https://skratch.golf"
MAX_ITEMS_PER_CHANNEL = 25
MAX_TOTAL_ITEMS = 50


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_youtube_rss_url(channel_id: str) -> str:
    """Generate the YouTube RSS feed URL for a channel."""
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


def fetch_standard_rss_feed(feed_config: Dict) -> List[Dict]:
    """Fetch and parse a standard RSS feed."""
    feed_url = feed_config.get("url")
    if not feed_url:
        return []
    
    try:
        # Fetch with requests first
        response = requests.get(feed_url, timeout=15)
        response.raise_for_status()
        feed = feedparser.parse(response.text)
        entries = []
        
        for entry in feed.entries[:MAX_ITEMS_PER_CHANNEL]:
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                pub_datetime = datetime(*published[:6])
            else:
                pub_datetime = datetime.now()
            
            thumbnail = ""
            if hasattr(entry, 'media_content') and entry.media_content:
                for media in entry.media_content:
                    if media.get('medium') == 'image' or media.get('type', '').startswith('image'):
                        thumbnail = media.get('url', '')
                        break
            if not thumbnail and hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                thumbnail = entry.media_thumbnail[0].get('url', '')
            
            description = entry.get("description", "") or entry.get("summary", "")
            description_plain = re.sub(r'<[^>]+>', '', description)[:500]
            
            entries.append({
                "title": entry.get("title", "Untitled"),
                "link": entry.get("link", ""),
                "video_id": None,
                "description": description_plain,
                "published": pub_datetime,
                "author": entry.get("author", "") or feed_config.get("name", "Skratch"),
                "channel_name": feed_config.get("name", "Unknown"),
                "channel_id": None,
                "thumbnail_high": thumbnail,
                "embed_url": None,
                "content_type": feed_config.get("content_type", "article"),
            })
        
        return entries
        
    except Exception as e:
        print(f"<!-- Warning: Error fetching {feed_config.get('name', 'Unknown')}: {e} -->")
        return []


def fetch_channel_feed(channel: Dict) -> List[Dict]:
    """Fetch and parse a YouTube channel's RSS feed."""
    channel_id = channel.get("channel_id")
    if not channel_id:
        return []
    
    feed_url = get_youtube_rss_url(channel_id)
    
    try:
        # Fetch with requests first (feedparser sometimes can't fetch directly)
        response = requests.get(feed_url, timeout=15)
        response.raise_for_status()
        feed = feedparser.parse(response.text)
        entries = []
        
        for entry in feed.entries[:MAX_ITEMS_PER_CHANNEL]:
            video_id = entry.get("yt_videoid", "")
            if not video_id:
                link = entry.get("link", "")
                match = re.search(r"v=([a-zA-Z0-9_-]{11})", link)
                if match:
                    video_id = match.group(1)
            
            published = entry.get("published_parsed")
            if published:
                pub_datetime = datetime(*published[:6])
            else:
                pub_datetime = datetime.now()
            
            thumbnail_high = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
            
            entries.append({
                "title": entry.get("title", "Untitled"),
                "link": entry.get("link", ""),
                "video_id": video_id,
                "description": entry.get("summary", ""),
                "published": pub_datetime,
                "author": entry.get("author", channel.get("name", "Skratch")),
                "channel_name": channel.get("name", "Unknown"),
                "channel_id": channel_id,
                "thumbnail_high": thumbnail_high,
                "embed_url": f"https://www.youtube.com/embed/{video_id}",
                "content_type": "video",
            })
        
        return entries
        
    except Exception as e:
        print(f"<!-- Warning: Error fetching {channel.get('name', 'Unknown')}: {e} -->")
        return []


def build_mrss_feed(entries: List[Dict]) -> str:
    """Build a Media RSS (MRSS) feed from the combined entries."""
    lines = []
    lines.append('<rss version="2.0"')
    lines.append('  xmlns:atom="http://www.w3.org/2005/Atom"')
    lines.append('  xmlns:media="http://search.yahoo.com/mrss/"')
    lines.append('  xmlns:yt="http://www.youtube.com/xml/schemas/2015"')
    lines.append('  xmlns:dc="http://purl.org/dc/elements/1.1/">')
    lines.append('<channel>')
    lines.append(f'  <title>{html.escape(FEED_TITLE)}</title>')
    lines.append(f'  <link>{html.escape(FEED_LINK)}</link>')
    lines.append(f'  <description>{html.escape(FEED_DESCRIPTION)}</description>')
    lines.append('  <language>en-us</language>')
    lines.append(f'  <lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>')
    lines.append('  <generator>Skratch YouTube RSS Aggregator</generator>')
    
    for entry in entries:
        lines.append('  <item>')
        lines.append(f'    <title>{html.escape(entry["title"])}</title>')
        lines.append(f'    <link>{html.escape(entry["link"])}</link>')
        lines.append(f'    <guid isPermaLink="true">{html.escape(entry["link"])}</guid>')
        lines.append(f'    <pubDate>{entry["published"].strftime("%a, %d %b %Y %H:%M:%S +0000")}</pubDate>')
        lines.append(f'    <dc:creator>{html.escape(entry["author"])}</dc:creator>')
        
        desc = html.escape(entry.get("description", "")[:500])
        if entry.get("video_id"):
            desc_html = f'&lt;p&gt;{desc}&lt;/p&gt;&lt;p&gt;&lt;a href="{html.escape(entry["link"])}"&gt;Watch on YouTube&lt;/a&gt;&lt;/p&gt;'
        else:
            desc_html = f'&lt;p&gt;{desc}&lt;/p&gt;&lt;p&gt;&lt;a href="{html.escape(entry["link"])}"&gt;Read more&lt;/a&gt;&lt;/p&gt;'
        lines.append(f'    <description>{desc_html}</description>')
        
        if entry.get("thumbnail_high"):
            lines.append(f'    <media:thumbnail url="{html.escape(entry["thumbnail_high"])}"/>')
        
        if entry.get("video_id"):
            lines.append(f'    <media:content url="{html.escape(entry["embed_url"])}" type="text/html" medium="video"/>')
            lines.append(f'    <yt:videoId>{html.escape(entry["video_id"])}</yt:videoId>')
        
        if entry.get("channel_id"):
            lines.append(f'    <yt:channelId>{html.escape(entry["channel_id"])}</yt:channelId>')
        
        lines.append(f'    <category>{html.escape(entry["channel_name"])}</category>')
        if entry.get("content_type"):
            lines.append(f'    <category>{html.escape(entry["content_type"])}</category>')
        
        lines.append('  </item>')
    
    lines.append('</channel>')
    lines.append('</rss>')
    
    return '\n'.join(lines)


def main():
    """Main function to generate the combined feed."""
    all_entries = []
    
    for channel in YOUTUBE_CHANNELS:
        entries = fetch_channel_feed(channel)
        all_entries.extend(entries)
    
    for feed in RSS_FEEDS:
        entries = fetch_standard_rss_feed(feed)
        all_entries.extend(entries)
    
    all_entries.sort(key=lambda x: x["published"], reverse=True)
    all_entries = all_entries[:MAX_TOTAL_ITEMS]
    
    feed_xml = build_mrss_feed(all_entries)
    
    print('<?xml version="1.0" encoding="UTF-8"?>')
    print(feed_xml)


if __name__ == "__main__":
    main()
