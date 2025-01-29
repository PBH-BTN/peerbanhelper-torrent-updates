# scripts/generate_feeds.py
"""
Github Torrent RSS Generator
BEP-0036 规范实现：https://www.bittorrent.org/beps/bep_0036.html
"""

import json
import markdown
import logging
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from xml.sax.saxutils import escape

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def convert_markdown_to_html(text: str) -> str:
    """将 GitHub Markdown 转换为安全的 HTML 内容
    
    Args:
        text: 原始 Markdown 文本
        
    Returns:
        经过安全处理的 HTML 字符串
    """
    if not text:
        return ""

    try:
        # 预处理 GitHub 特有的换行格式
        text = text.replace('  \n', '<br/>\n')
        
        # 转换 Markdown 到 HTML
        html = markdown.markdown(
            text,
            extensions=[
                'fenced_code',  # 代码块支持
                'tables',       # 表格支持
                'nl2br',        # 自动换行
                'md_in_html'    # 允许混合 Markdown
            ],
            output_format='xhtml'
        )
        
        # 添加基础排版样式
        return f'<div style="white-space: pre-wrap; font-family: sans-serif">{html}</div>'
    except Exception as e:
        logger.error(f"Markdown 转换失败: {str(e)}")
        return escape(text)

def process_releases(max_entries: int = 50) -> list:
    """处理发行版本数据
    
    Args:
        max_entries: 最大处理条目数
        
    Returns:
        处理后的 release 列表，按发布时间倒序排列
    """
    try:
        with open('releases.json', 'r') as f:
            releases = json.load(f)
    except FileNotFoundError:
        logger.error("releases.json 文件未找到")
        return []
    except json.JSONDecodeError:
        logger.error("releases.json 解析失败")
        return []

    valid_releases = []
    
    for release in releases:
        # 跳过草稿
        if release.get('draft', False):
            continue
            
        # 检查 torrent 文件是否存在
        torrent_asset = next(
            (a for a in release['assets'] if a['name'] == 'peerbanhelper.torrent'),
            None
        )
        if not torrent_asset:
            continue

        # 处理必要字段
        processed = {
            'title': release.get('name', release['tag_name']),
            'description': convert_markdown_to_html(release.get('body', '')),
            'pub_date': release.get('published_at', ''),
            'is_prerelease': release.get('prerelease', False),
            'html_url': release.get('html_url', ''),
            'size': torrent_asset['size'],
            'torrent_url': (
                f"https://github.com/PBH-BTN/PeerBanHelper/releases/download/"
                f"{release['tag_name']}/peerbanhelper.torrent"
            ),
            'mirror_url': (
                f"https://ghfast.top/https://github.com/PBH-BTN/PeerBanHelper/"
                f"releases/download/{release['tag_name']}/peerbanhelper.torrent"
            )
        }
        valid_releases.append(processed)

    # 按发布时间排序并限制数量
    valid_releases.sort(
        key=lambda x: datetime.fromisoformat(x['pub_date'].replace('Z', '+00:00')),
        reverse=True
    )
    return valid_releases[:max_entries]

def generate_rss_feed(entries: list, include_prerelease: bool, use_mirror: bool) -> str:
    """生成 RSS XML 内容
    
    Args:
        entries: 处理后的 release 列表
        include_prerelease: 是否包含预发布版本
        use_mirror: 是否使用镜像链接
        
    Returns:
        格式化后的 XML 字符串
    """
    rss = Element('rss', {'version': '2.0'})
    channel = SubElement(rss, 'channel')
    
    # 频道元数据
    title = SubElement(channel, 'title')
    title_text = 'PeerBanHelper Releases'
    if use_mirror:
        title_text += ' [Mirror]'
    if include_prerelease:
        title_text += ' (Including Pre-releases)'
    title.text = title_text

    SubElement(channel, 'link').text = 'https://github.com/PBH-BTN/PeerBanHelper/releases'
    SubElement(channel, 'description').text = title_text

    # 生成条目
    for entry in entries:
        if not include_prerelease and entry['is_prerelease']:
            continue

        item = SubElement(channel, 'item')
        SubElement(item, 'title').text = escape(entry['title'])
        
        description = SubElement(item, 'description')
        description.text = escape(entry['description'])  # 内容已预先转换为 HTML
        
        pub_date = datetime.strptime(
            entry['pub_date'], 
            '%Y-%m-%dT%H:%M:%SZ'
        ).strftime('%a, %d %b %Y %H:%M:%S GMT')
        SubElement(item, 'pubDate').text = pub_date
        
        SubElement(item, 'link').text = entry['html_url']
        
        # Torrent 文件链接
        enclosure_url = entry['mirror_url'] if use_mirror else entry['torrent_url']
        SubElement(item, 'enclosure', {
            'url': enclosure_url,
            'length': str(entry['size']),
            'type': 'application/x-bittorrent'
        })

    # 格式化 XML
    rough_xml = tostring(rss, 'utf-8')
    parsed = minidom.parseString(rough_xml)
    return parsed.toprettyxml(indent='  ', encoding='utf-8').decode('utf-8')

def main():
    logger.info("开始生成 RSS Feed")
    
    # 处理数据
    entries = process_releases(max_entries=50)
    logger.info(f"找到 {len(entries)} 个有效 Release")
    
    # 生成所有 Feed 变体
    feed_configs = [
        ('feeds/github.feed.xml', False, False),
        ('feeds/github.feed.prerelease.xml', True, False),
        ('feeds/mirror.feed.xml', False, True),
        ('feeds/mirror.feed.prerelease.xml', True, True)
    ]

    for filename, include_pre, use_mirror in feed_configs:
        try:
            content = generate_rss_feed(entries, include_pre, use_mirror)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"成功生成 {filename}")
        except Exception as e:
            logger.error(f"生成 {filename} 失败: {str(e)}")

    logger.info("RSS 生成流程完成")

if __name__ == "__main__":
    main()
