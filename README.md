# reddot-crawler / 红点设计奖作品采集工具
本项目是一个用于采集红点设计奖（Red Dot Design Award）官方网站作品信息并生成 PDF 报告的自动化工具。

## 功能特性

- **多分类采集:** 支持按不同设计分类（如产品设计、品牌与传播设计、设计概念）分别采集数据并生成独立的报告。
- **逐页采集与合并:** 自动处理分页，逐页抓取数据并生成临时 PDF，最终合并为完整的 PDF 报告。
- **作品详情抓取:** 访问每个作品的详情页，获取完整的项目描述。
- **图片下载:** 自动下载作品相关的图片。
- **PDF 报告生成:** 生成包含封面页、作品列表和详细信息的 PDF 报告。
- **自定义样式:** PDF 报告支持中文字体，布局和样式可配置。
- **详细日志:** 提供详细的运行日志，方便调试和跟踪。
- **错误处理:** 内置网络请求重试和数据处理错误处理机制。

## 环境要求

- Python 3.6+
- 操作系统: macOS, Linux, Windows

## 安装依赖

项目依赖可以通过 `requirements.txt` 文件安装：

```bash
pip install -r requirements.txt
```

建议在一个 [Python 虚拟环境](https://docs.python.org/zh-cn/3/library/venv.html) 中进行安装。

## 使用方法

1. 克隆项目到本地：

   ```bash
   git clone https://github.com/tangooo/reddot-crawler.git
   cd reddot-crawler
   ```

2. 安装项目依赖：

   ```bash
   pip install -r requirements.txt
   ```

3. 运行爬虫程序：

   ```bash
   ./start.sh
   ```

程序将开始采集数据，并在 `output` 目录下为每个分类生成独立的 PDF 报告和临时文件。

## 输出说明

程序会在运行目录下创建 `output` 目录。在该目录下，会为每个分类（如 `product_design`、`brand_communication_design`、`design_concept`）创建一个子目录。

每个分类子目录下会包含：

- `reddot_designs_<分类名称>_YYYYMMDD_HHMMSS.pdf`: 最终合并的 PDF 报告文件。
- `temp/`: 临时文件存放目录，包含封面 `cover.pdf` 和每页的临时 PDF 文件 `temp_page_X.pdf`。采集完成后，临时文件会被移动到分类输出目录下。
- `crawler.log`: 运行日志文件，记录采集过程中的详细信息。

最终生成的 PDF 报告中，每个作品会以段落形式展示以下信息：

- 序号 (页码-当前页序号)
- 作品图片
- 标题
- 项目描述
- 类型
- 作者
- 时间

## 作者与版权

**作者:** tAngo
**联系方式:** org.java.tango@gmail.com

本项目仅用于学习交流目的，请勿用于任何商业用途。

## 许可证

本项目采用 [MIT License](https://opensource.org/licenses/MIT) 开源许可证。 
