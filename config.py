# config.py

# API 相关配置
BASE_URL = "https://www.red-dot.org/de/search/search.json"
SITE_BASE_URL = "https://www.red-dot.org"

# 输出目录配置
OUTPUT_DIR = "output"

# 分类配置
CATEGORIES = {
    "product_design": "meta_categories:/10/",
    "brand_communication_design": "meta_categories:/11/",
    "design_concept": "meta_categories:/12/"
}

# 其他配置
MAX_RETRIES = 3
RETRY_DELAY = 1 # 秒
REQUEST_TIMEOUT = 10 # 秒

# 字体配置
FONTS_DIR = "fonts"

# 日志配置
import logging
LOGGING_LEVEL = logging.DEBUG # 默认日志级别为 INFO 