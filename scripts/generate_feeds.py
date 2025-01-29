import json
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from xml.sax.saxutils import escape

def load_releases():
    with open('releases.json', 'r') as f:
        releases = json.load(f)
    
    processed = []
    for release in releases:
        if release.get('draft', False):
            continue
        torrent_asset = next((a for a in release['assets'] if a['name'] == 'peerbanhelper.torrent'), None)
        if not torrent_asset:
            continue
        
        processed.append({
            'title': release.get('name', ''),
            'description': release.get('body', ''),
            'pub_date': release.get('published_at', ''),
            'is_prerelease': release.get('prerelease', False),
            'html_url': release.get('html_url', ''),
            'size': torrent_asset['size'],
            'torrent_url': f"https://github.com/PBH-BTN/PeerBanHelper/releases/download/{release['tag_name']}/peerbanhelper.torrent",
            'mirror_url': f"https://ghfast.top/https://github.com/PBH-BTN/PeerBanHelper/releases/download/{release['tag_name']}/peerbanhelper.torrent"
        })
    
    processed.sort(key=lambda x: datetime.fromisoformat(x['pub_date'].replace('Z', '+00:00')), reverse=True)
    return processed

def generate_feed(entries, include_prerelease, use_mirror):
    rss = Element('rss', {'version': '2.0'})
    channel = SubElement(rss, 'channel')
    
    title = SubElement(channel, 'title')
    title_text = 'PeerBanHelper Releases'
    if use_mirror:
        title_text += ' [Mirror]'
    if include_prerelease:
        title_text += ' (Including Pre-releases)'
    title.text = title_text

    SubElement(channel, 'link').text = 'https://github.com/PBH-BTN/PeerBanHelper/releases'
    SubElement(channel, 'description').text = title_text

    for entry in entries:
        if not include_prerelease and entry['is_prerelease']:
            continue
        
        item = SubElement(channel, 'item')
        SubElement(item, 'title').text = escape(entry['title'])
        SubElement(item, 'description').text = escape(entry['description'])
        pub_date = datetime.strptime(entry['pub_date'], '%Y-%m-%dT%H:%M:%SZ').strftime('%a, %d %b %Y %H:%M:%S GMT')
        SubElement(item, 'pubDate').text = pub_date
        SubElement(item, 'link').text = entry['html_url']
        
        url = entry['mirror_url'] if use_mirror else entry['torrent_url']
        SubElement(item, 'enclosure', {
            'url': url,
            'length': str(entry['size']),
            'type': 'application/x-bittorrent'
        })

    return minidom.parseString(tostring(rss)).toprettyxml(indent='  ')

def main():
    entries = load_releases()
    
    feed_configs = [
        ('feeds/github.feed.xml', False, False),
        ('feeds/github.feed.prerelease.xml', True, False),
        ('feeds/mirror.feed.xml', False, True),
        ('feeds/mirror.feed.prerelease.xml', True, True)
    ]

    for filename, include_pre, use_mirror in feed_configs:
        xml_content = generate_feed(entries, include_pre, use_mirror)
        with open(filename, 'w') as f:
            f.write(xml_content)

if __name__ == "__main__":
    main()
