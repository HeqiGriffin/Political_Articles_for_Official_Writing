import os
import re
import datetime
import requests

def clean_filename(filename):
    """清理文件名中的非法字符"""
    return re.sub(r'[\/\\\:\*\?\"\<\>\|]', '_', filename).strip()

def clean_html(text):
    """清理 HTML 标签并保留段落换行"""
    if not text:
        return ""
    text = re.sub(r'</p>|<br\s*/?>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()

def scrape_and_save_tech_daily():
    # ==========================================
    now = datetime.datetime.now()
    # ==========================================
    
    today_str = now.strftime('%Y-%m-%d')        
    date_str_folder = now.strftime('%Y%m%d')    
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_save_dir = os.path.join(script_dir, "《科技日报》版面")
    
    BASE_API_URL = "https://epaper.stdaily.com/stdailynewspaperapi/uv/article"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
        'Origin': 'https://epaper.stdaily.com',
        'Referer': 'https://epaper.stdaily.com/statics/technology-site/index.html',
        'x-requested-with': 'XMLHttpRequest'
    }

    print(f"[*] 正在核实《科技日报》今日 ({today_str}) 是否出刊...")

    # ==========================================
    # 第一层：获取当天的版面目录 
    # ==========================================
    period_url = f"{BASE_API_URL}/period/periodTime"
    period_payload = {
        "code": "KJRB",
        "siteId": "811c18b08cf04e79be3b67d6902ee1a7",
        "periodTime": today_str
    }
    
    try:
        resp = requests.post(period_url, json=period_payload, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"[*] 访问 API 失败 (状态码: {resp.status_code})。")
            return
        period_data = resp.json()
    except Exception as e:
        print(f"[*] 获取目录 API 发生异常: {e}")
        return

    obj = period_data.get('obj', {})
    if not obj:
        print(f"☕ 科技日报今日 ({today_str}) 接口无数据返回，疑似停刊。")
        return

    returned_date = obj.get('periodTime')
    if returned_date != today_str:
        print(f"☕ 科技日报今日 ({today_str}) 未出刊 (当前接口最新为 {returned_date})。")
        return

    edition_list = obj.get('editionList', [])
    if not edition_list:
        print("[*] 今日版面列表为空。")
        return

    print(f"[*] 科技日报今日正常出刊！发现 {len(edition_list)} 个版面，开始抓取...")

    # ==========================================
    # 第二层：遍历版面，获取文章列表摘要
    # ==========================================
    for edition in edition_list:
        edition_id = edition.get('id')
        raw_edition_name = edition.get('editionName', '未知版面')
        
        # 【优化】：提取并格式化版面名称为纯粹的“第XX版”
        # 匹配类似于 "第1版" 或 "01·第01版：今日要闻" 中的数字
        match = re.search(r'第(\d+)版', raw_edition_name)
        if match:
            # 拿到数字部分，比如 '1' 或 '01'
            num_str = match.group(1)
            # 使用 zfill(2) 确保一位数前面补 0，比如 '1' 变成 '01'
            safe_edition_name = f"第{num_str.zfill(2)}版"
        else:
            safe_edition_name = clean_filename(raw_edition_name)
        folder_path = os.path.join(base_save_dir, date_str_folder, safe_edition_name)
        os.makedirs(folder_path, exist_ok=True)
        
        print(f"\n正在处理: {safe_edition_name}")
        
        edition_url = f"{BASE_API_URL}/article/editionId"
        edition_payload = {
            "code": "KJRB",
            "id": edition_id,
            "siteId": "811c18b08cf04e79be3b67d6902ee1a7"
        }
        
        try:
            art_resp = requests.post(edition_url, json=edition_payload, headers=headers, timeout=10)
            art_data = art_resp.json()
        except Exception as e:
            print(f"  - 获取版面文章失败: {e}")
            continue
            
        article_list = art_data.get('list', [])
        print(f"  - 该版面共找到 {len(article_list)} 篇文章，开始获取全文...")
        
        # ==========================================
        # 第三层：利用文章 ID，请求文章全文并生成原文链接
        # ==========================================
        for item in article_list:
            article_id = item.get('id')
            fallback_title = item.get('title') or '无标题文章'
            
            if not article_id:
                continue

            article_url = f"https://epaper.stdaily.com/statics/technology-site/index.html#/newsDetail?id={article_id}"

            detail_url = f"{BASE_API_URL}/article/articleId"
            detail_payload = {
                "code": "KJRB",
                "id": article_id,
                "siteId": "811c18b08cf04e79be3b67d6902ee1a7"
            }
            
            try:
                detail_resp = requests.post(detail_url, json=detail_payload, headers=headers, timeout=10)
                detail_data = detail_resp.json()
            except Exception as e:
                print(f"  - 获取全文失败: {e}")
                continue

            # 【核心修复】：加上了 articleVo 这个壳子！
            detail_obj = detail_data.get('obj') or {}
            article_vo = detail_obj.get('articleVo') or {}
            
            # 提取引题、主标题、副标题
            pre_title = clean_html(article_vo.get('pretitle') or '')
            main_title = clean_html(article_vo.get('title') or fallback_title)
            sub_title = clean_html(article_vo.get('subtitle') or '')
            
            # 提取正文（优先拿带有HTML段落的content，用来做漂亮的换行）
            full_html = article_vo.get('content') or article_vo.get('txt') or ''
            
            if not full_html:
                continue 
                
            clean_full_content = clean_html(full_html)
            
            safe_filename = clean_filename(main_title)
            file_path = os.path.join(folder_path, f"{safe_filename}.md")
            
            with open(file_path, "w", encoding="utf-8") as f:
                # 按照光明日报的排版标准注入
                if pre_title:
                    f.write(f"### {pre_title}\n\n")
                f.write(f"# {main_title}\n\n")
                if sub_title:
                    f.write(f"## {sub_title}\n\n")
                    
                f.write(f"**原文链接：** [{article_url}]({article_url})\n\n")
                f.write("---\n\n")
                f.write(clean_full_content)
                
            print(f"  - 已保存: {safe_filename}.md")

if __name__ == '__main__':
    print("==========================================")
    print("开始执行科技日报抓取...")
    scrape_and_save_tech_daily()
    print("🎉 科技日报抓取流程结束！")