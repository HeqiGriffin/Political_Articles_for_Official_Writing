import os
import re
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# 清理文件名中的非法字符
def clean_filename(filename):
    return re.sub(r'[\/\\\:\*\?\"\<\>\|]', '_', filename).strip()

# 抓取并保存为 MD
def save_article_to_md_pro(article_url, default_title, folder_path, headers, seen_fingerprints):
    try:
        resp = requests.get(article_url, headers=headers, timeout=10)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        main_title = soup.find('h1')
        actual_title_text = main_title.text.strip() if main_title else default_title

        # 【最新结构适配：囊括光明日报新老版所有容器】
        content_div = (
            soup.find('div', class_='m-article-main') or 
            soup.find('div', class_='m-article-text') or 
            soup.find('div', id='articleContent') or 
            soup.find('div', id='ozoom') or 
            soup.find('founder-content') or 
            soup.find('div', class_='text_c') or 
            soup.find('div', id='contentMain') or
            soup.find('div', class_='article-content')
        )
        
        raw_text = content_div.get_text(strip=True) if content_div else ""
        
        # 指纹去重逻辑
        clean_text = re.sub(r'第\w+版', '', raw_text)
        clean_text = re.sub(r'[（\(][上下][接转].*?[）\)]', '', clean_text)
        text_fingerprint = re.sub(r'\s+', '', clean_text)[:150]
        
        # 图片容器：如果正文里没图，尝试在更大范围找
        pic_container = soup.find('div', class_='m-article-content') or soup.find('table', id='newspic') or soup.find('div', class_='attachment') or content_div
        
        first_img = pic_container.find('img') if pic_container else None
        img_fingerprint = first_img.get('src') if first_img else ""
        
        title_fingerprint = re.sub(r'\s+', '', default_title)
        fingerprint = title_fingerprint + text_fingerprint + img_fingerprint
        
        if fingerprint in seen_fingerprints:
            print(f"  - [精准去重跳过] 发现跨版重复内容: {default_title}")
            return
            
        seen_fingerprints.add(fingerprint)

        pre_title = soup.find('h3')
        sub_title = soup.find('h2')

        md_content_lines = []
        
        # 1. 【提取图片】
        if pic_container:
            for img in pic_container.find_all('img'):
                img_src = img.get('src')
                if img_src:
                    abs_img_url = urljoin(article_url, img_src).replace("http://", "https://")
                    md_content_lines.append(f"![报纸配图]({abs_img_url})\n\n")

        # 2. 【提取正文文字】
        if content_div:
            # 步骤A：先把干扰提取的 script 和 style 标签全部摧毁
            for tag in content_div.find_all(['script', 'style']):
                tag.decompose()
                
            # 步骤B：把所有的换行符 <br> 真正变成双换行
            for br in content_div.find_all(['br', 'BR']):
                br.replace_with('\n\n')
                
            # 步骤C：扒掉所有 <p> 标签的外壳，并强制在它们的前后加上换行
            for p in content_div.find_all(['p', 'P']):
                p.insert_before('\n\n')
                p.insert_after('\n\n')
                p.unwrap() 
                
            # 步骤D：直接抽取整个区块的纯文本
            # 【关键修复】：这里去掉了 strip=True！保留了我们刚插入的 \n\n 换行符
            final_text = content_div.get_text()
            
            # 步骤E：用正则把混乱的多个空行强制压缩为两个，恢复成漂亮的 Markdown 段落
            for text in re.split(r'\n{2,}', final_text):
                text = text.strip()
                if text:
                    md_content_lines.append(f"{text}\n\n")

        safe_filename = clean_filename(actual_title_text) or "无标题文章"
        file_path = os.path.join(folder_path, f"{safe_filename}.md")
        
        with open(file_path, "w", encoding="utf-8") as f:
            if pre_title and pre_title.text.strip():
                f.write(f"### {pre_title.text.strip()}\n\n")
            f.write(f"# {actual_title_text}\n\n")
            if sub_title and sub_title.text.strip():
                f.write(f"## {sub_title.text.strip()}\n\n")
                
            f.write(f"**原文链接：** [{article_url}]({article_url})\n\n")
            f.write("---\n\n")
            
            if not md_content_lines:
                f.write("> 【抓取提示】该文章可能仅包含特殊排版内容或由于网站结构变动，未能提取到标准文本。\n\n")
            else:
                for line in md_content_lines:
                    f.write(line)
                    
        print(f"  - 已保存: {safe_filename}.md")
        
    except Exception as e:
        print(f"  - 抓取失败 ({article_url}): {e}")

def scrape_and_save_gmrb():
    # ==========================================
    now = datetime.datetime.now()
    # ==========================================
    
    date_str_url = now.strftime('%Y%m/%d')
    date_str_folder = now.strftime('%Y%m%d')
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_save_dir = os.path.join(script_dir, "《中国青年报》版面")
    
    base_layout_url = f'https://zqb.cyol.com/pc/layout/{date_str_url}/'
    node01_url = urljoin(base_layout_url, 'node_01.html')
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    print(f"[*] 正在尝试访问中国青年报首页: {node01_url}")

    try:
        resp = requests.get(node01_url, headers=headers, timeout=10)
        resp.encoding = 'utf-8'
        
        if resp.status_code != 200:
            print(f"[报错] 网页访问失败！HTTP 状态码: {resp.status_code}")
            return
            
        html_content = resp.text
    except Exception as e:
        print(f"[报错] 网络请求发生异常: {e}")
        return

    nodes = sorted(list(set(re.findall(r'node_\d+\.html', html_content))))
    
    if not nodes:
        print("[报错] 网页访问成功，但没有解析到任何版面链接！")
        return
        
    print(f"[*] 成功找到 {len(nodes)} 个版面，开始抓取...")
    
    seen_fingerprints = set()
    seen_urls = set()

    for node in nodes:
        node_num_match = re.search(r'node_(\d+)\.html', node)
        if node_num_match:
            num_str = node_num_match.group(1).zfill(2)
            node_label = f"第{num_str}版"
        else:
            node_label = node
            
        node_url = urljoin(base_layout_url, node)
        
        folder_path = os.path.join(base_save_dir, date_str_folder, node_label)
        os.makedirs(folder_path, exist_ok=True)
        
        print(f"\n正在处理中国青年报: {node_label}")

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
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            
            save_article_to_md_pro(full_url, clean_title, folder_path, headers, seen_fingerprints)

if __name__ == '__main__':
    print("==========================================")
    print("开始执行中国青年报抓取...")
    scrape_and_save_gmrb()
    print("🎉 中国青年报抓取流程结束！")