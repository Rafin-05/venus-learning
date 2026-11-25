"""Provider-neutral video helpers (PDF §6).

YouTube is the initial provider. A lesson stores ``provider`` +
``provider_video_id`` instead of depending on a raw URL, so the player
can later be pointed at a protected streaming provider without
changing the lesson model.

Unlisted YouTube videos can be embedded for enrolled learners, but
anyone who obtains the link can share it — they are not DRM-protected.
Private YouTube videos are not a dependable choice for embedding to
all enrolled learners, so they are not treated as embeddable here.
"""
import re
from urllib.parse import urlparse, parse_qs

_YOUTUBE_ID = re.compile(r'^[A-Za-z0-9_-]{11}$')
_YOUTUBE_HOSTS = {
    'youtube.com', 'www.youtube.com', 'm.youtube.com',
    'youtube-nocookie.com', 'www.youtube-nocookie.com',
}


def extract_youtube_id(value):
    """Return the 11-character YouTube video ID in *value*, or ''.

    Accepts watch URLs (``?v=``), youtu.be links, /embed/, /shorts/,
    /live/ and /v/ paths, and a bare 11-character ID. Returns '' for
    any other URL, including a YouTube host with a malformed ID.
    """
    if not value or not isinstance(value, str):
        return ''
    value = value.strip()
    if _YOUTUBE_ID.match(value):
        return value
    try:
        parsed = urlparse(value)
    except ValueError:
        return ''
    if parsed.scheme not in ('http', 'https'):
        return ''
    host = (parsed.hostname or '').lower()
    if host == 'youtu.be':
        candidate = parsed.path.strip('/').split('/')[0]
        return candidate if _YOUTUBE_ID.match(candidate) else ''
    if host in _YOUTUBE_HOSTS:
        candidate = parse_qs(parsed.query).get('v', [''])[0]
        if _YOUTUBE_ID.match(candidate):
            return candidate
        match = re.match(r'^/(?:embed|shorts|live|v)/([A-Za-z0-9_-]{11})(?:[/?#]|$)', parsed.path)
        if match:
            return match.group(1)
    return ''


def is_youtube_url(value):
    if not value or not isinstance(value, str):
        return False
    try:
        host = (urlparse(value.strip()).hostname or '').lower()
    except ValueError:
        return False
    return host == 'youtu.be' or host in _YOUTUBE_HOSTS


def youtube_embed_url(video_id):
    """Privacy-enhanced embed URL for a validated YouTube video ID."""
    if not video_id or not _YOUTUBE_ID.match(str(video_id)):
        return ''
    return f'https://www.youtube-nocookie.com/embed/{video_id}'
