#!/bin/bash

# 导入环境变量，防止 cron 找不到 python3 和 git 命令
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# 切换到项目根目录（服务器路径）
cd /var/Projects/PAOW

echo "=========================================="
echo "[$(date +'%Y-%m-%d %H:%M:%S')] 开始执行同步任务..."

# 1. 运行 Python 爬虫脚本
/var/Projects/PAOW/venv/bin/python3 Peoples_Daily_Sync.py

# 2. 检查是否有新生成的 md 文件或数据变动
if [ -n "$(git status --porcelain)" ]; then
    echo "检测到新文件，准备提交并推送到 GitHub..."
    git add .
    git commit -m "auto: 服务器自动同步 $(date +'%Y-%m-%d') 文章数据"
    git push origin main
    echo "✅ [$(date +'%Y-%m-%d %H:%M:%S')] 数据成功推送到GitHub仓库！"
else
    echo "☕ 今天暂无新数据更新，跳过提交与推送。"
fi