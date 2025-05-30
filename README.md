# RedDot Crawler

红点设计奖作品爬虫工具，用于收集和生成红点设计奖作品集 PDF。

## 功能特点

- 自动采集红点设计奖网站的作品数据。
- 抓取作品的标题、类型、作者、年份等基本信息。
- **并行访问**作品详情页，**提取详细描述和 `<div class="credits">` 块内的所有作者/团队信息**。
- **并行下载**作品高清图片。
- 将采集到的数据按分类保存为 CSV 文件，支持追加模式，确保数据不丢失。
- 为每个分类生成美观的 PDF 报告，包含：
  - 封面页（标题、生成时间、作者、作品总数）。
  - 作品详情页（图片、标题、描述、类型、作者、年份、序号）。
  - 统一的页尾（包含页码和作者信息）。
- 支持通过配置文件 `config.py` 灵活设置 API 地址、输出目录、采集分类、网络请求参数、**并行线程数**、字体目录、日志级别等。
- 代码采用面向对象设计，逻辑清晰，易于维护。
- 实现了网络请求的重试机制，提高采集稳定性。
- 提供详细的日志输出，方便调试和监控。

## 系统要求

- Python 3.8 或更高版本
- macOS/Linux/Windows 操作系统

## 安装步骤

1. 克隆仓库：
```bash
git clone https://github.com/tangooo/reddot-crawler.git
cd reddot-crawler
```

2. 创建虚拟环境（推荐）：
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
.\venv\Scripts\activate  # Windows
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 安装中文字体（可选）：
   - 将中文字体文件（如 .ttf 或 .ttc 格式）放入 `fonts` 目录
   - 支持的字体格式：TTF、TTC、OTF

## 使用方法

1. 运行爬虫：
```bash
./start.sh
```

2. 运行PDF单元测试：
```bash
python pdf_generator.py
```

测试结果将显示：
```
==================================================
测试结果汇总:
==================================================
merge_pdfs           : ✅ 通过
create_temp_page_pdf : ✅ 通过
pdf_styles          : ✅ 通过
download_image      : ✅ 通过
==================================================
总体结果: ✅ 全部通过
==================================================
```

## 配置说明

编辑 `config.py` 文件，根据需要修改以下配置项：

- `BASE_URL`: 红点设计奖 API 的基础 URL。
- `SITE_BASE_URL`: 红点设计奖网站的基础 URL，用于构建详情页链接。
- `OUTPUT_DIR`: 输出文件（CSV、PDF、图片、临时文件）保存的根目录。
- `CATEGORIES`: 一个字典，定义需要采集的分类及其对应的 API 过滤参数。
- `MAX_RETRIES`: 网络请求的最大重试次数。
- `RETRY_DELAY`: 网络请求重试之间的等待秒数。
- `REQUEST_TIMEOUT`: 网络请求超时时间（秒）。
- `**NUM_THREADS**`: **并行处理作品详情和图片下载的线程数**。
- `FONTS_DIR`: 字体文件所在的目录，用于 PDF 生成。
- `LOGGING_LEVEL`: 日志输出级别 (如 `logging.INFO`, `logging.DEBUG`, `logging.WARNING` 等)。需要导入 `logging` 模块。
- (可选) 如果需要在 PDF 中使用特定字体，请将字体文件（.ttf, .ttc, .otf）放入 `fonts` 目录。可以在 `config.py` 中修改 `FONTS_DIR` 指定其他目录。

## 输出

采集结果将保存在 `OUTPUT_DIR` 指定的目录下，每个分类一个子目录。每个分类子目录中包含：

- `reddot_designs_<category_name>.csv`: 包含该分类所有作品数据的 CSV 文件。
- `reddot_designs_<category_name>_*.pdf`: 包含该分类所有作品详情的 PDF 报告。
- `images/`: 保存所有下载的作品图片文件。
- `temp/`: 保存 PDF 生成过程中产生的临时文件（如临时页 PDF 和封面 PDF）。这些文件在合并后通常会被移动到分类输出目录并清理临时目录。


## 项目结构

```
reddot-crawler/
├── main.py              # 主程序入口
├── crawler.py           # 爬虫核心逻辑
├── pdf_generator.py     # PDF 生成器
├── config.py           # 配置文件
├── requirements.txt    # 依赖列表
├── fonts/             # 字体目录
├── output/            # 输出目录
└── tests/             # 测试目录
```

## 开发说明

1. 代码风格遵循 PEP 8 规范
2. 使用 logging 模块进行日志记录
3. 包含完整的单元测试
4. 使用类型注解提高代码可读性


## 注意事项

1. 确保网络连接稳定
2. 需要足够磁盘空间存储图片和 PDF
3. 建议使用虚拟环境运行
4. 如遇到字体问题，请检查字体文件是否正确安装

## 许可证

MIT License

## 作者

tAngo / org.java.tango@gmail.com

## 版权与学习交流

本项目仅供学习交流使用，请勿用于任何商业用途。遵循相关网站的数据抓取政策和法律法规。因使用本项目而产生的一切后果由使用者自行承担。
