#!/bin/bash

# 导入环境变量，防止 cron 找不到 python3 和 git 命令
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# 切换到项目根目录（服务器路径）
cd /var/Projects/PAOW

echo "=========================================="
echo "[$(date +'%Y-%m-%d %H:%M:%S')] 开始执行三大报纸同步任务..."

# 1. 运行 Python 爬虫脚本（严格使用虚拟环境中的 python3）

echo "▶️ [1/3] 开始抓取《人民日报》..."
/var/Projects/PAOW/venv/bin/python3 Peoples_Daily_Sync.py

echo "▶️ [2/3] 开始抓取《光明日报》..."
/var/Projects/PAOW/venv/bin/python3 Guangming_Daily_Sync.py

echo "▶️ [3/3] 开始抓取《科技日报》..."
/var/Projects/PAOW/venv/bin/python3 Science_and_Technology_Daily_Sync.py

echo "✅ 三大报纸抓取全部结束，开始检查数据变动..."
echo "------------------------------------------"

# 2. 检查是否有新生成的 md 文件或数据变动
if [ -n "$(git status --porcelain)" ]; then
    echo "检测到新文件，准备提交并推送到 GitHub..."
    git add .
    git commit -m "auto: 服务器自动同步 $(date +'%Y-%m-%d') 文章数据"
    git push origin main
    echo "🎉 [$(date +'%Y-%m-%d %H:%M:%S')] 数据成功推送到 GitHub 仓库！"
else
    echo "☕ 今天暂无新数据更新，跳过提交与推送。"
fi