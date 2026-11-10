"""Stable release lookup for the JR Controller GitHub repository."""
import json
import re
from urllib.request import Request, urlopen

VERSION = '1.1.3'
RELEASES = 'https://github.com/Lc2007081623/jr-controller/releases'
ENDPOINT = 'https://api.github.com/repos/Lc2007081623/jr-controller/releases/latest'

def version_tuple(tag):
    if not isinstance(tag, str) or not re.fullmatch(r'v?[0-9]+\.[0-9]+\.[0-9]+', tag):
        raise ValueError('GitHub 版本号格式无法识别')
    return tuple(map(int, tag.lstrip('v').split('.')))

def check_update():
    request = Request(ENDPOINT, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': f'JRController/{VERSION}',
    })
    with urlopen(request, timeout=6) as response:
        release = json.loads(response.read(512 * 1024))
    latest = release.get('tag_name')
    return latest, version_tuple(latest) > version_tuple(VERSION)
