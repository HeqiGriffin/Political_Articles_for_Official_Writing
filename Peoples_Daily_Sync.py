import os
import re
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def clean_filename(filename):
    """清理文件名中的非法字符"""
    return re.sub(r'[\/\\\:\*\?\"\<\>\|]', '_', filename).strip()

def save_article_to_md_pro(article_url, default_title, folder_path, headers, seen_fingerprints):
    """
    抓取并保存为 MD，包含：智能指纹去重、层级标题、图片提取（http强制转https）
    """
    try:
        resp = requests.get(article_url, headers=headers, timeout=10)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        main_title = soup.find('h1')
        actual_title_text = main_title.text.strip() if main_title else default_title

        # 定位正文区域
        content_div = soup.find('div', id='ozoom')
        
        # ==========================================
        # 🛡️ 核心改动：生成“内容指纹”进行超级去重
        # ==========================================
        raw_text = content_div.get_text(strip=True) if content_div else ""
        
        # 1. 剔除干扰词：消除正文里的“第05版”、“(下转第2版)”、“(上接第一版)”等差异
        clean_text = re.sub(r'第\w+版', '', raw_text)
        clean_text = re.sub(r'[（\(][上下][接转].*?[）\)]', '', clean_text)
        
        # 2. 提取文本指纹：去除所有空白，取前150个纯文字
        text_fingerprint = re.sub(r'\s+', '', clean_text)[:150]
        
        # 3. 提取图片指纹：获取第一张图片的链接（防止纯图片新闻没有文字）
        first_img = content_div.find('img') if content_div else None
        img_fingerprint = first_img.get('src') if first_img else ""
        
        # 4. 组合最终指纹：无空格标题 + 文本前150字 + 第一张图链接
        title_fingerprint = re.sub(r'\s+', '', default_title)
        fingerprint = title_fingerprint + text_fingerprint + img_fingerprint
        
        # 5. 判断指纹是否已存在
        if fingerprint in seen_fingerprints:
            print(f"  - [精准去重跳过] 发现跨版重复内容: {default_title}")
            return # 直接终止，不保存文件
            
        # 如果是新内容，将指纹加入集合中
        seen_fingerprints.add(fingerprint)
        # ==========================================

        # 提取副标题等
        pre_title = soup.find('h3') 
        sub_title = soup.find('h2')

        # 构建 Markdown 内容
        md_content_lines = []
        if content_div:
            for elem in content_div.find_all(['p', 'img']):
                if elem.name == 'img':
                    img_src = elem.get('src')
                    if img_src:
                        abs_img_url = urljoin(article_url, img_src)
                        # 【图片显示优化】：强制 http 变 https，绕过 VS Code/浏览器的安全警告
                        abs_img_url = abs_img_url.replace("http://", "https://")
                        md_content_lines.append(f"\n![报纸配图]({abs_img_url})\n")
                elif elem.name == 'p':
                    text = elem.get_text(strip=True)
                    if text:
                        md_content_lines.append(f"{text}\n\n")

        safe_filename = clean_filename(actual_title_text) or "无标题文章"
        file_path = os.path.join(folder_path, f"{safe_filename}.md")
        
        # 写入 Markdown 文件
        with open(file_path, "w", encoding="utf-8") as f:
            if pre_title and pre_title.text.strip():
                f.write(f"### {pre_title.text.strip()}\n\n")
            f.write(f"# {actual_title_text}\n\n")
            if sub_title and sub_title.text.strip():
                f.write(f"## {sub_title.text.strip()}\n\n")
                
            f.write(f"**原文链接：** [{article_url}]({article_url})\n\n")
            f.write("---\n\n")
            
            for line in md_content_lines:
                f.write(line)
                    
        print(f"  - 已保存: {safe_filename}.md")
        
    except Exception as e:
        print(f"  - 抓取失败 ({article_url}): {e}")


def scrape_and_save_rmrb_md_pro(date_str=None, base_save_dir="《人民日报》版面"):
    if not date_str:
        now = datetime.datetime.now()
        date_str_url = now.strftime('%Y%m/%d')
        date_str_folder = now.strftime('%Y%m%d')
        print(f"[*] 未指定日期，自动获取当前日期: {date_str_folder}")
    elif len(date_str) == 8 and date_str.isdigit():
        date_str_url = f'{date_str[:6]}/{date_str[6:]}'
        date_str_folder = date_str
        print(f"[*] 使用指定日期: {date_str_folder}")
    else:
        print("日期格式错误，请使用 YYYYMMDD 格式，例如 '20260802'")
        return

    base_layout_url = f'http://paper.people.com.cn/rmrb/pc/layout/{date_str_url}/'
    node01_url = urljoin(base_layout_url, 'node_01.html')
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        resp = requests.get(node01_url, headers=headers, timeout=10)
        resp.encoding = 'utf-8'
        html_content = resp.text
    except Exception as e:
        print(f"获取首页失败: {e}")
        return

    nodes = sorted(list(set(re.findall(r'node_\d+\.html', html_content))))
    
    # 【全局指纹库】存放当天所有已抓取文章的内容指纹
    seen_fingerprints = set()
    # 【URL去重】如果同一个版面里有完全相同的URL，直接忽略（双保险）
    seen_urls = set()

    for node in nodes:
        node_num_match = re.search(r'node_(\d+)\.html', node)
        node_label = f"第{node_num_match.group(1)}版" if node_num_match else node
        node_url = urljoin(base_layout_url, node)
        
        folder_path = os.path.join(base_save_dir, date_str_folder, node_label)
        os.makedirs(folder_path, exist_ok=True)
        
        print(f"\n正在处理: {node_label}")

        try:
            resp_node = requests.get(node_url, headers=headers, timeout=10)
            resp_node.encoding = 'utf-8'
            page_html = resp_node.text
        except Exception:
            continue

        articles = re.findall(r'<a\s+href=["\']([^"\'\>]*content_\d+\.html)["\'][^>]*>(.*?)</a>', page_html, re.DOTALL)

        for href, title_html in articles:
            clean_title = re.sub(r'<[^>]+>', '', title_html).strip()
            
            if '责编' in clean_title:
                continue

            full_url = urljoin(node_url, href)
            
            # 第一层防护：相同的网址绝对不抓第二次
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            
            # 传给处理函数，进行第二层防护：内容指纹去重
            save_article_to_md_pro(full_url, clean_title, folder_path, headers, seen_fingerprints)

if __name__ == '__main__':
    print("开始执行完美终极版抓取脚本...")
    # 修改处：这里去掉了硬编码的日期参数，留空即可默认抓取“今天”的数据
    scrape_and_save_rmrb_md_pro()
    print("\n🎉 全部抓取并保存完毕！")