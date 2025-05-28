#!/bin/bash

# 设置颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}开始设置红点设计奖爬虫...${NC}"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到Python3，请先安装Python3${NC}"
    exit 1
fi

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}创建虚拟环境...${NC}"
    python3 -m venv venv
fi

# 激活虚拟环境
echo -e "${YELLOW}激活虚拟环境...${NC}"
source venv/bin/activate

# 升级pip
echo -e "${YELLOW}升级pip...${NC}"
python -m pip install --upgrade pip

# 安装依赖
echo -e "${YELLOW}安装项目依赖...${NC}"
pip install -r requirements.txt

# 验证依赖安装
echo -e "${YELLOW}验证依赖安装...${NC}"
python -c "
import sys
dependencies = {
    'firecrawl': 'firecrawl',
    'requests': 'requests',
    'bs4': 'beautifulsoup4',
    'reportlab': 'reportlab',
    'PIL': 'Pillow',
    'dotenv': 'python-dotenv',
    'lxml': 'lxml'
}
missing = []
for module, package in dependencies.items():
    try:
        __import__(module)
    except ImportError:
        missing.append(package)
if missing:
    print('缺少以下依赖：', ', '.join(missing))
    sys.exit(1)
print('所有依赖已正确安装')
"

if [ $? -ne 0 ]; then
    echo -e "${RED}依赖安装验证失败，请检查错误信息${NC}"
    exit 1
fi

# 清理输出目录
echo -e "${YELLOW}清理输出目录...${NC}"
if [ -d "output" ]; then
    rm -rf output/*
    echo -e "${GREEN}输出目录已清理${NC}"
else
    mkdir output
    echo -e "${GREEN}创建输出目录${NC}"
fi

# 运行爬虫
echo -e "${YELLOW}启动爬虫程序...${NC}"
python reddot_crawler.py

# 检查运行结果
if [ $? -eq 0 ]; then
    echo -e "${GREEN}爬虫程序运行完成！${NC}"
else
    echo -e "${RED}爬虫程序运行出错，请检查错误信息${NC}"
fi

# 退出虚拟环境
deactivate 