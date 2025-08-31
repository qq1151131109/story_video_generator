# 部署指南

本指南将帮助你在不同环境中部署历史故事生成器。

## 📋 系统要求

### 最低要求
- Python 3.8+
- 内存: 4GB RAM
- 存储: 10GB 可用空间
- 网络: 稳定的互联网连接

### 推荐配置
- Python 3.9+
- 内存: 8GB+ RAM
- 存储: 50GB+ SSD
- CPU: 4核心+
- 网络: 高速互联网连接

## 🚀 快速部署

### 1. 环境准备

```bash
# 克隆或下载项目
cd historical-story-generator

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
# 必需的API密钥
OPENROUTER_API_KEY=your_openrouter_api_key_here

# 可选的API密钥（用于增强功能）
RUNNINGHUB_API_KEY=your_runninghub_api_key
AZURE_API_KEY=your_azure_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
STABILITY_API_KEY=your_stability_api_key

# 可选配置
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
AZURE_REGION=eastus
```

### 3. 验证安装

```bash
# 验证系统配置
python validate_setup.py

# 运行测试套件
python test_suite.py --quick

# 运行多语言测试
python test_multilang.py
```

### 4. 基本使用

```bash
# 生成单个故事
python main.py --theme "秦始皇统一六国" --language zh

# 运行测试模式
python main.py --test

# 交互式模式
python main.py
```

## 🐳 Docker 部署

### 创建 Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 创建输出目录
RUN mkdir -p output

# 设置环境变量
ENV PYTHONPATH=/app

EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import sys; sys.path.insert(0, '/app'); from core.config_manager import ConfigManager; ConfigManager()" || exit 1

CMD ["python", "main.py"]
```

### Docker Compose 配置

```yaml
# docker-compose.yml
version: '3.8'

services:
  story-generator:
    build: .
    container_name: historical-story-generator
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - RUNNINGHUB_API_KEY=${RUNNINGHUB_API_KEY}
      - AZURE_API_KEY=${AZURE_API_KEY}
      - ELEVENLABS_API_KEY=${ELEVENLABS_API_KEY}
      - STABILITY_API_KEY=${STABILITY_API_KEY}
    volumes:
      - ./output:/app/output
      - ./config:/app/config
    restart: unless-stopped
    
  # 可选：Redis 缓存
  redis:
    image: redis:6-alpine
    container_name: story-generator-redis
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
```

### 部署命令

```bash
# 构建镜像
docker build -t historical-story-generator .

# 使用 Docker Compose 启动
docker-compose up -d

# 查看日志
docker-compose logs -f story-generator

# 进入容器
docker-compose exec story-generator bash
```

## ☁️ 云服务部署

### AWS EC2 部署

```bash
# 1. 启动 EC2 实例 (推荐 t3.large 或更大)
# 2. 连接到实例
ssh -i your-key.pem ubuntu@your-ec2-ip

# 3. 安装依赖
sudo apt update
sudo apt install python3.9 python3.9-venv python3-pip ffmpeg -y

# 4. 克隆项目
git clone https://github.com/your-repo/historical-story-generator.git
cd historical-story-generator

# 5. 设置虚拟环境
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 6. 配置环境变量
nano .env

# 7. 配置systemd服务
sudo nano /etc/systemd/system/story-generator.service
```

systemd 服务配置：

```ini
[Unit]
Description=Historical Story Generator
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/historical-story-generator
Environment=PATH=/home/ubuntu/historical-story-generator/venv/bin
ExecStart=/home/ubuntu/historical-story-generator/venv/bin/python main.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl enable story-generator
sudo systemctl start story-generator
sudo systemctl status story-generator
```

### Google Cloud Platform 部署

```bash
# 1. 创建 Compute Engine 实例
gcloud compute instances create story-generator \
    --zone=us-central1-a \
    --machine-type=n1-standard-4 \
    --image-family=ubuntu-2004-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=50GB

# 2. SSH 连接
gcloud compute ssh story-generator --zone=us-central1-a

# 3. 后续步骤与 AWS 类似
```

## 🔧 生产环境配置

### 1. 性能优化

编辑 `config/settings.json`：

```json
{
  "general": {
    "max_concurrent_tasks": 8,
    "log_level": "INFO"
  },
  "cache": {
    "ttl_hours": 168,
    "max_size_mb": 4096
  }
}
```

### 2. 日志配置

```bash
# 创建日志轮转配置
sudo nano /etc/logrotate.d/story-generator

# 内容：
/home/ubuntu/historical-story-generator/output/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    notifempty
    create 644 ubuntu ubuntu
    postrotate
        systemctl reload story-generator
    endscript
}
```

### 3. 监控设置

安装监控工具：

```bash
# 安装 htop 和 iotop
sudo apt install htop iotop

# 设置定期性能报告
crontab -e

# 添加：
0 6 * * * cd /home/ubuntu/historical-story-generator && python optimize.py >> output/logs/performance.log 2>&1
```

## 🛡️ 安全配置

### 1. 防火墙设置

```bash
# UFW 配置
sudo ufw allow ssh
sudo ufw allow 8000/tcp
sudo ufw enable
```

### 2. API密钥安全

```bash
# 设置环境变量文件权限
chmod 600 .env

# 创建专用用户
sudo useradd -m -s /bin/bash story-generator
sudo chown -R story-generator:story-generator /app
```

### 3. SSL/TLS 配置（如果需要Web接口）

```bash
# 安装 Certbot
sudo apt install certbot

# 获取证书
sudo certbot certonly --standalone -d your-domain.com
```

## 📊 监控和维护

### 1. 健康检查脚本

```bash
#!/bin/bash
# health_check.sh

# 检查服务状态
systemctl is-active --quiet story-generator
if [ $? -eq 0 ]; then
    echo "✅ Story Generator is running"
else
    echo "❌ Story Generator is not running"
    systemctl restart story-generator
fi

# 检查磁盘空间
DISK_USAGE=$(df / | grep -v Filesystem | awk '{print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "⚠️  Disk usage is high: ${DISK_USAGE}%"
fi

# 检查内存使用
MEMORY_USAGE=$(free | grep Mem | awk '{printf("%.0f", $3/$2 * 100.0)}')
if [ $MEMORY_USAGE -gt 90 ]; then
    echo "⚠️  Memory usage is high: ${MEMORY_USAGE}%"
fi
```

### 2. 备份策略

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup/story-generator-$DATE"

mkdir -p $BACKUP_DIR

# 备份配置和输出
cp -r config $BACKUP_DIR/
cp -r output $BACKUP_DIR/
cp .env $BACKUP_DIR/

# 压缩备份
tar -czf "${BACKUP_DIR}.tar.gz" $BACKUP_DIR
rm -rf $BACKUP_DIR

# 删除30天前的备份
find /backup -name "story-generator-*.tar.gz" -mtime +30 -delete
```

### 3. 更新流程

```bash
#!/bin/bash
# update.sh

# 停止服务
sudo systemctl stop story-generator

# 备份当前版本
cp -r /home/ubuntu/historical-story-generator /home/ubuntu/historical-story-generator-backup-$(date +%Y%m%d)

# 拉取新版本
cd /home/ubuntu/historical-story-generator
git pull origin main

# 更新依赖
source venv/bin/activate
pip install -r requirements.txt --upgrade

# 运行测试
python test_suite.py --quick

# 重启服务
sudo systemctl start story-generator

echo "Update completed"
```

## 🚨 故障排除

### 常见问题

1. **内存不足**
   ```bash
   # 增加交换空间
   sudo fallocate -l 4G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

2. **API调用超时**
   ```bash
   # 检查网络连接
   curl -I https://openrouter.ai/api/v1/models
   
   # 增加超时配置
   export HTTPX_TIMEOUT=300
   ```

3. **缓存问题**
   ```bash
   # 清理缓存
   rm -rf output/cache/*
   
   # 重新创建缓存目录
   mkdir -p output/cache/{scripts,scenes,images,audio}
   ```

### 日志分析

```bash
# 查看错误日志
tail -f output/logs/errors.log

# 查看API调用日志
grep "API" output/logs/story_generator.log

# 查看性能日志
tail -f output/logs/performance.log
```

## 📈 扩展和集成

### 1. 负载均衡

使用 nginx 配置负载均衡：

```nginx
upstream story_generator {
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}

server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://story_generator;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 2. 数据库集成

如需要持久化存储，可以集成数据库：

```python
# database.py
import sqlite3
from contextlib import contextmanager

@contextmanager
def get_db_connection():
    conn = sqlite3.connect('story_generator.db')
    try:
        yield conn
    finally:
        conn.close()

def init_database():
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS generated_stories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                theme TEXT NOT NULL,
                language TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
```

这个部署指南提供了从开发到生产的完整部署流程，包括安全、监控、备份等最佳实践。