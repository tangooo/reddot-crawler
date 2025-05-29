# RedDot Crawler

一个用于抓取红点设计奖网站作品数据并生成结构化 CSV 和 PDF 报告的 Python 工具。

## 功能

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

## 先决条件

- Python 3.6 或更高版本。
- 依赖库 (详见 `requirements.txt`)。

## 安装

1. 克隆仓库到本地：

   ```bash
   git clone <repository_url>
   cd reddot-crawler
   ```

2. 安装依赖库：

   ```bash
   pip install -r requirements.txt
   ```

3. (可选) 如果需要在 PDF 中使用特定字体，请将字体文件（.ttf, .ttc, .otf）放入 `fonts` 目录。可以在 `config.py` 中修改 `FONTS_DIR` 指定其他目录。

## 配置

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

## 使用方法

直接运行主脚本：

```bash
python reddot_crawler.py
```

脚本将按照 `config.py` 中配置的分类进行采集，并将结果保存在 `OUTPUT_DIR` 下按分类命名的子目录中。

## 输出

采集结果将保存在 `OUTPUT_DIR` 指定的目录下，每个分类一个子目录。每个分类子目录中包含：

- `reddot_designs_<category_name>.csv`: 包含该分类所有作品数据的 CSV 文件。
- `reddot_designs_<category_name>_*.pdf`: 包含该分类所有作品详情的 PDF 报告。
- `images/`: 保存所有下载的作品图片文件。
- `temp/`: 保存 PDF 生成过程中产生的临时文件（如临时页 PDF 和封面 PDF）。这些文件在合并后通常会被移动到分类输出目录并清理临时目录。

## 作者

tAngo / org.java.tango@gmail.com

## 版权与学习交流

本项目仅供学习交流使用，请勿用于任何商业用途。遵循相关网站的数据抓取政策和法律法规。因使用本项目而产生的一切后果由使用者自行承担。
