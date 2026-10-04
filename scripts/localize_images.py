#!/usr/bin/env python3
"""
扫描所有 Markdown 文件中的外部图片链接，
下载到 images/ 目录，并替换为相对路径。
"""

import os
import re
import hashlib
from pathlib import Path
from urllib.parse import urlparse, unquote
import requests

# 配置
MD_GLOB = "**/*.md"
IMAGE_DIR = Path("images")
TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (compatible; GitHub-Actions-Image-Localizer/1.0)"

# 匹配 ![alt](url) 和 <img src="url">
IMG_PATTERN = re.compile(
    r'(!\[.*?\]\()(https?://[^)\s]+)(\))'          # Markdown
    r'|'
    r'(<img[^>]+src=["\'])(https?://[^"\']+)(["\'])',  # HTML img
    re.IGNORECASE
)

def get_filename_from_url(url: str) -> str:
    """从 URL 提取文件名，必要时加 hash 防止冲突"""
    path = unquote(urlparse(url).path)
    name = os.path.basename(path)
    if not name or '.' not in name:
        # 没有扩展名时用 hash
        ext = '.png'
        name = hashlib.md5(url.encode()).hexdigest()[:12] + ext
    return name

def download_image(url: str, dest: Path) -> bool:
    """下载图片，成功返回 True"""
    try:
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=TIMEOUT, stream=True)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"  ✓ Downloaded: {dest.name}")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {url} -> {e}")
        return False

def process_markdown(md_path: Path) -> bool:
    """处理单个 MD 文件，返回是否有修改"""
    content = md_path.read_text(encoding="utf-8")
    original = content
    url_to_local = {}

    def replacer(match):
        # 兼容 Markdown 和 HTML 两种匹配组
        if match.group(1):  # Markdown ![alt](url)
            prefix, url, suffix = match.group(1), match.group(2), match.group(3)
        else:               # HTML <img src="url">
            prefix, url, suffix = match.group(4), match.group(5), match.group(6)

        # 已经是相对路径或本地路径则跳过
        if not url.startswith(("http://", "https://")):
            return match.group(0)

        # 同一 URL 只下载一次
        if url not in url_to_local:
            filename = get_filename_from_url(url)
            local_path = IMAGE_DIR / filename
            # 文件已存在则跳过下载
            if not local_path.exists():
                if not download_image(url, local_path):
                    return match.group(0)  # 下载失败保持原链接
            url_to_local[url] = f"./{IMAGE_DIR.name}/{filename}"

        new_url = url_to_local[url]
        return f"{prefix}{new_url}{suffix}"

    new_content = IMG_PATTERN.sub(replacer, content)

    if new_content != original:
        md_path.write_text(new_content, encoding="utf-8")
        print(f"Updated: {md_path}")
        return True
    return False

def main():
    IMAGE_DIR.mkdir(exist_ok=True)
    md_files = list(Path(".").glob(MD_GLOB))
    # 排除 .github 等目录（可选）
    md_files = [f for f in md_files if not any(p.startswith(".") for p in f.parts[:-1])]

    print(f"Found {len(md_files)} Markdown files")
    changed = 0
    for md in sorted(md_files):
        print(f"\nProcessing {md} ...")
        if process_markdown(md):
            changed += 1

    print(f"\nDone. {changed} file(s) updated. Images saved in {IMAGE_DIR}/")

if __name__ == "__main__":
    main()
