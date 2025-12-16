#!/usr/bin/env python3
"""
YouTube Multi-Channel RSS Aggregator for Skratch Golf
Combines multiple YouTube channel feeds into a single Media RSS feed.

Usage:
    python youtube_rss_aggregator.py > skratch_combined.xml
    
Or run as a scheduled job to keep the feed updated.

To find a YouTube channel ID from a handle (@username):
    1. Go to the channel page (e.g., youtube.com/@DanOnGolfShow)
    2. View page source (Ctrl+U or Cmd+Option+U)
    3. Search for "channelId" - you'll find something like "channelId":"UCxxxxxxxxxx"
    4. Or use: https://commentpicker.com/youtube-channel-id.php
"""

import feedparser
import requests
import re
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
import html
from typing import List, Dict, Optional

# ============================================================================
# CONFIGURATION - Add your feeds here
# ============================================================================

# YouTube channels (will fetch from YouTube RSS)
YOUTUBE_CHANNELS = [
    {
        "name": "Skratch",
        "channel_id": "UCwtGQ3sgidNlQGbIUBPP3xw",
    },
    {
        "name": "Dan On Golf Show", 
        "channel_id": "UCQvs9V1djea1wFurLJPlqMg",
    },
    # Add more YouTube channels as needed
]

# Standard RSS feeds (articles, podcasts, etc.)
RSS_FEEDS = [
    {
        "name": "Skratch Articles",
        "url": "https://www.skratch.golf/rss",
        "content_type": "article",  # article, podcast, or video
    },
    # Add more RSS feeds as needed
]

FEED_TITLE = "Skratch Golf Video Feed"
FEED_DESCRIPTION = "Combined video feed from Skratch Golf YouTube channels"
FEED_LINK = "https://skratch.golf"
MAX_ITEMS_PER_CHANNEL = 25  # How many recent videos to pull per channel
MAX_TOTAL_ITEMS = 50  # Total items in combined feed


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def resolve_handle_to_channel_id(handle: str) -> Optional[str]:
    """
    Resolve a YouTube @handle to a channel ID by fetching the channel page.
    """
    url = f"https://www.youtube.com/@{handle}"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
        
        # Look for channel ID in the page source
        match = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]{22})"', response.text)
        if match:
            return match.group(1)
        
        # Alternative pattern
        match = re.search(r'channel_id=([UC][a-zA-Z0-9_-]{22})', response.text)
        if match:
            return match.group(1)
            
    except Exception as e:
        print(f"<!-- Warning: Could not resolve handle @{handle}: {e} -->")
    
    return None


def get_youtube_rss_url(channel_id: str) -> str:
    """Generate the YouTube RSS feed URL for a channel."""
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


def fetch_standard_rss_feed(feed_config: Dict) -> List[Dict]:
    """
    Fetch and parse a standard RSS feed (articles, podcasts, etc.)
    Returns a list of entries with normalized fields.
    """
    feed_url = feed_config.get("url")
    if not feed_url:
        return []
    
    try:
        feed = feedparser.parse(feed_url)
        entries = []
        
        for entry in feed.entries[:MAX_ITEMS_PER_CHANNEL]:
            # Parse published date
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                pub_datetime = datetime(*published[:6])
            else:
                pub_datetime = datetime.now()
            
            # Try to get thumbnail from media:content or media:thumbnail
            thumbnail = ""
            if hasattr(entry, 'media_content') and entry.media_content:
                for media in entry.media_content:
                    if media.get('medium') == 'image' or media.get('type', '').startswith('image'):
                        thumbnail = media.get('url', '')
                        break
            if not thumbnail and hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                thumbnail = entry.media_thumbnail[0].get('url', '')
            
            # Get description/summary
            description = entry.get("description", "") or entry.get("summary", "")
            # Strip HTML tags for plain text description
            description_plain = re.sub(r'<[^>]+>', '', description)[:500]
            
            entries.append({
                "title": entry.get("title", "Untitled"),
                "link": entry.get("link", ""),
                "video_id": None,  # Not a video
                "description": description_plain,
                "published": pub_datetime,
                "published_str": entry.get("published", ""),
                "author": entry.get("author", "") or entry.get("dc_creator", feed_config.get("name", "Skratch")),
                "channel_name": feed_config.get("name", "Unknown"),
                "channel_id": None,
                "thumbnail_default": thumbnail,
                "thumbnail_medium": thumbnail,
                "thumbnail_high": thumbnail,
                "thumbnail_maxres": thumbnail,
                "embed_url": None,
                "content_type": feed_config.get("content_type", "article"),
            })
        
        return entries
        
    except Exception as e:
        print(f"<!-- Warning: Error fetching {feed_config.get('name', 'Unknown')}: {e} -->")
        return []


def fetch_channel_feed(channel: Dict) -> List[Dict]:
    """
    Fetch and parse a YouTube channel's RSS feed.
    Returns a list of video entries with normalized fields.
    """
    # Get channel ID (resolve handle if needed)
    channel_id = channel.get("channel_id")
    if not channel_id and channel.get("handle"):
        channel_id = resolve_handle_to_channel_id(channel["handle"])
        if not channel_id:
            print(f"<!-- Warning: Could not resolve channel {channel.get('name', 'Unknown')} -->")
            return []
    
    if not channel_id:
        return []
    
    feed_url = get_youtube_rss_url(channel_id)
    
    try:
        feed = feedparser.parse(feed_url)
        entries = []
        
        for entry in feed.entries[:MAX_ITEMS_PER_CHANNEL]:
            # Extract video ID from the link
            video_id = entry.get("yt_videoid", "")
            if not video_id:
                # Try to extract from link
                link = entry.get("link", "")
                match = re.search(r"v=([a-zA-Z0-9_-]{11})", link)
                if match:
                    video_id = match.group(1)
            
            # Parse published date
            published = entry.get("published_parsed")
            if published:
                pub_datetime = datetime(*published[:6])
            else:
                pub_datetime = datetime.now()
            
            # Get thumbnail URLs
            thumbnail_default = f"https://img.youtube.com/vi/{video_id}/default.jpg"
            thumbnail_medium = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
            thumbnail_high = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
            thumbnail_maxres = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
            
            entries.append({
                "title": entry.get("title", "Untitled"),
                "link": entry.get("link", ""),
                "video_id": video_id,
                "description": entry.get("summary", ""),
                "published": pub_datetime,
                "published_str": entry.get("published", ""),
                "author": entry.get("author", channel.get("name", "Skratch")),
                "channel_name": channel.get("name", "Unknown"),
                "channel_id": channel_id,
                "thumbnail_default": thumbnail_default,
                "thumbnail_medium": thumbnail_medium,
                "thumbnail_high": thumbnail_high,
                "thumbnail_maxres": thumbnail_maxres,
                "embed_url": f"https://www.youtube.com/embed/{video_id}",
                "content_type": "video",
            })
        
        return entries
        
    except Exception as e:
        print(f"<!-- Warning: Error fetching {channel.get('name', 'Unknown')}: {e} -->")
        return []


def build_mrss_feed(entries: List[Dict]) -> str:
    """
    Build a Media RSS (MRSS) feed from the combined entries.
    """
    # Namespaces
    NSMAP = {
        "atom": "http://www.w3.org/2005/Atom",
        "media": "http://search.yahoo.com/mrss/",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    
    # Create root RSS element
    rss = Element("rss")
    rss.set("version", "2.0")
    rss.set("xmlns:atom", NSMAP["atom"])
    rss.set("xmlns:media", NSMAP["media"])
    rss.set("xmlns:yt", NSMAP["yt"])
    rss.set("xmlns:dc", NSMAP["dc"])
    
    # Create channel element
    channel = SubElement(rss, "channel")
    
    # Channel metadata
    SubElement(channel, "title").text = FEED_TITLE
    SubElement(channel, "link").text = FEED_LINK
    SubElement(channel, "description").text = FEED_DESCRIPTION
    SubElement(channel, "language").text = "en-us"
    SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    
    # Generator
    SubElement(channel, "generator").text = "Skratch YouTube RSS Aggregator"
    
    # Add atom:link for self-reference (update URL when deployed)
    atom_link = SubElement(channel, "{http://www.w3.org/2005/Atom}link")
    atom_link.set("href", "https://skratch.golf/feeds/videos.xml")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")
    
    # Channel image
    image = SubElement(channel, "image")
    SubElement(image, "url").text = "https://storage.googleapis.com/prod-skratch-strapi/logo-black.svg"
    SubElement(image, "title").text = FEED_TITLE
    SubElement(image, "link").text = FEED_LINK
    
    # Add items
    for entry in entries:
        item = SubElement(channel, "item")
        
        # Basic item elements
        SubElement(item, "title").text = entry["title"]
        SubElement(item, "link").text = entry["link"]
        
        # GUID (use video URL as permanent identifier)
        guid = SubElement(item, "guid")
        guid.set("isPermaLink", "true")
        guid.text = entry["link"]
        
        # Publication date
        SubElement(item, "pubDate").text = entry["published"].strftime("%a, %d %b %Y %H:%M:%S +0000")
        
        # Author/Creator
        SubElement(item, "{http://purl.org/dc/elements/1.1/}creator").text = entry["author"]
        
        # Description with embedded content
        if entry.get("video_id"):
            description_html = f"""
<p>{html.escape(entry.get('description', ''))}</p>
<p><a href="{entry['link']}">Watch on YouTube</a></p>
<p><img src="{entry['thumbnail_high']}" alt="{html.escape(entry['title'])}" /></p>
"""
        else:
            thumbnail_html = f'<p><img src="{entry["thumbnail_high"]}" alt="{html.escape(entry["title"])}" /></p>' if entry.get("thumbnail_high") else ""
            description_html = f"""
{thumbnail_html}
<p>{html.escape(entry.get('description', ''))}</p>
<p><a href="{entry['link']}">Read more</a></p>
"""
        SubElement(item, "description").text = description_html.strip()
        
        # Media RSS elements (for videos and articles with thumbnails)
        if entry.get("thumbnail_high") or entry.get("video_id"):
            media_group = SubElement(item, "{http://search.yahoo.com/mrss/}group")
            
            # Media content (video embed or article link)
            if entry.get("video_id"):
                media_content = SubElement(media_group, "{http://search.yahoo.com/mrss/}content")
                media_content.set("url", entry["embed_url"])
                media_content.set("type", "application/x-shockwave-flash")
                media_content.set("medium", "video")
            
            # Media title
            media_title = SubElement(media_group, "{http://search.yahoo.com/mrss/}title")
            media_title.set("type", "plain")
            media_title.text = entry["title"]
            
            # Media description
            media_desc = SubElement(media_group, "{http://search.yahoo.com/mrss/}description")
            media_desc.set("type", "plain")
            media_desc.text = entry.get("description", "")[:500]
            
            # Media thumbnails (multiple sizes for videos, single for articles)
            if entry.get("video_id"):
                for thumb_size, thumb_url, width, height in [
                    ("default", entry["thumbnail_default"], "120", "90"),
                    ("medium", entry["thumbnail_medium"], "320", "180"),
                    ("high", entry["thumbnail_high"], "480", "360"),
                    ("maxres", entry["thumbnail_maxres"], "1280", "720"),
                ]:
                    thumb = SubElement(media_group, "{http://search.yahoo.com/mrss/}thumbnail")
                    thumb.set("url", thumb_url)
                    thumb.set("width", width)
                    thumb.set("height", height)
            elif entry.get("thumbnail_high"):
                thumb = SubElement(media_group, "{http://search.yahoo.com/mrss/}thumbnail")
                thumb.set("url", entry["thumbnail_high"])
            
            # Media player (for videos)
            if entry.get("video_id"):
                media_player = SubElement(media_group, "{http://search.yahoo.com/mrss/}player")
                media_player.set("url", entry["link"])
        
        # YouTube-specific elements (only for videos)
        if entry.get("video_id"):
            yt_videoid = SubElement(item, "{http://www.youtube.com/xml/schemas/2015}videoId")
            yt_videoid.text = entry["video_id"]
        
        if entry.get("channel_id"):
            yt_channelid = SubElement(item, "{http://www.youtube.com/xml/schemas/2015}channelId")
            yt_channelid.text = entry["channel_id"]
        
        # Category (channel name)
        SubElement(item, "category").text = entry["channel_name"]
        
        # Content type category
        if entry.get("content_type"):
            SubElement(item, "category").text = entry["content_type"]
    
    # Pretty print
    rough_string = tostring(rss, encoding="unicode")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding=None)


def main():
    """Main function to generate the combined feed."""
    all_entries = []
    
    # Fetch YouTube channel feeds
    for channel in YOUTUBE_CHANNELS:
        entries = fetch_channel_feed(channel)
        all_entries.extend(entries)
    
    # Fetch standard RSS feeds
    for feed in RSS_FEEDS:
        entries = fetch_standard_rss_feed(feed)
        all_entries.extend(entries)
    
    # Sort by publication date (newest first)
    all_entries.sort(key=lambda x: x["published"], reverse=True)
    
    # Limit total entries
    all_entries = all_entries[:MAX_TOTAL_ITEMS]
    
    # Build and output the feed
    feed_xml = build_mrss_feed(all_entries)
    
    # Remove XML declaration line that minidom adds (we'll add our own)
    lines = feed_xml.split("\n")
    if lines[0].startswith("<?xml"):
        lines = lines[1:]
    
    # Output with proper XML declaration
    print('<?xml version="1.0" encoding="UTF-8"?>')
    print("\n".join(lines))


if __name__ == "__main__":
    main()
