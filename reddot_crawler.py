import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage
from io import BytesIO
import requests
import platform
from PyPDF2 import PdfMerger
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from bs4 import BeautifulSoup

# 配置日志
logging.basicConfig(
    level=logging.DEBUG, # 将日志级别设置为DEBUG
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawler.log', mode='w'),  # 使用 'w' 模式，每次启动时清空文件
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 根据操作系统选择合适的中文字体
def get_system_font():
    def is_valid_font(font_path):
        try:
            # 尝试直接注册字体来验证
            try:
                pdfmetrics.registerFont(TTFont('TestFont', font_path))
                # 如果注册成功，说明是有效的字体文件
                return True
            except Exception as e:
                logger.debug(f"字体文件 {font_path} 注册测试失败: {str(e)}")
                return False
        except Exception as e:
            logger.warning(f"检查字体文件 {font_path} 时出错: {str(e)}")
            return False

    # 首先检查fonts目录下的字体
    fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
    if os.path.exists(fonts_dir):
        for font_file in os.listdir(fonts_dir):
            if font_file.endswith(('.ttf', '.ttc', '.otf')):
                font_path = os.path.join(fonts_dir, font_file)
                if is_valid_font(font_path):
                    logger.info(f"找到有效的自定义字体: {font_path}")
                    return font_path
                else:
                    logger.warning(f"字体文件格式无效: {font_path}")
    
    # 如果fonts目录下没有有效字体，则使用系统字体
    system = platform.system()
    if system == 'Darwin':  # macOS
        # 尝试多个可能的字体路径
        font_paths = [
            '/System/Library/Fonts/STHeiti Light.ttc',
            '/System/Library/Fonts/STHeiti Medium.ttc',
            '/System/Library/Fonts/Hiragino Sans GB.ttc',
            '/Library/Fonts/Arial Unicode.ttf',
            '/System/Library/Fonts/PingFang.ttc'
        ]
        for path in font_paths:
            if os.path.exists(path) and is_valid_font(path):
                logger.info(f"使用有效的系统字体: {path}")
                return path
            elif os.path.exists(path):
                logger.warning(f"系统字体格式无效: {path}")
    elif system == 'Windows':
        font_path = 'C:\\Windows\\Fonts\\msyh.ttc'
        if os.path.exists(font_path) and is_valid_font(font_path):
            logger.info(f"使用有效的系统字体: {font_path}")
            return font_path
        elif os.path.exists(font_path):
            logger.warning(f"系统字体格式无效: {font_path}")
    else:  # Linux
        font_path = '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf'
        if os.path.exists(font_path) and is_valid_font(font_path):
            logger.info(f"使用有效的系统字体: {font_path}")
            return font_path
        elif os.path.exists(font_path):
            logger.warning(f"系统字体格式无效: {font_path}")
    
    logger.warning("未找到任何有效的中文字体")
    return None

# 注册系统字体
FONT_PATH = get_system_font()
try:
    if FONT_PATH and os.path.exists(FONT_PATH):
        # 尝试注册字体
        try:
            pdfmetrics.registerFont(TTFont('SystemFont', FONT_PATH))
            FONT_NAME = 'SystemFont'
            logger.info(f"成功加载字体: {FONT_PATH}")
        except Exception as e:
            logger.error(f"注册字体失败: {str(e)}")
            raise
    else:
        raise Exception("未找到可用的字体")
except Exception as e:
    logger.warning(f"无法加载字体: {str(e)}，将使用默认字体")
    FONT_NAME = 'Helvetica'

class RedDotCrawler:
    def __init__(self,
                 base_url: str = "https://www.red-dot.org/de/search/search.json",
                 output_dir: str = "output",
                 site_base_url: str = "https://www.red-dot.org"):
        self.base_url = base_url
        self.output_dir = output_dir
        self.temp_dir = os.path.join(self.output_dir, "temp")
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
        logger.info("初始化爬虫")
        self.site_base_url = site_base_url
        self.seen_design_ids = set() # 添加一个集合用于存储已见过的作品ID

    def get_design_details(self, detail_url: str) -> Optional[Dict]:
        """从详情页抓取额外数据，例如描述"""
        max_retries = 3
        retry_delay = 1 # 秒

        for retry_num in range(max_retries):
            try:
                logger.info(f"开始抓取详情页数据 (尝试 {retry_num + 1}/{max_retries}): {detail_url}")
                response = requests.get(detail_url, timeout=10)
                response.raise_for_status()
                
                logger.info("详情页请求成功，开始解析")
                soup = BeautifulSoup(response.content, 'html.parser')
                
                description = ''
                description_div = soup.find('div', class_='description')
                if description_div:
                    description = description_div.get_text(strip=True)

                logger.info("详情页解析完成")
                return {'description': description}

            except requests.exceptions.RequestException as e:
                logger.warning(f"抓取详情页失败 (尝试 {retry_num + 1}/{max_retries}): {str(e)}")
                if retry_num < max_retries - 1:
                    logger.info(f"等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"抓取详情页在 {max_retries} 次尝试后仍然失败: {detail_url}")
                    return None
            except Exception as e:
                 logger.error(f"解析详情页 {detail_url} 时出错: {str(e)}")
                 return None

    def search_designs(self, keyword: str = "", category_filter: str = "") -> List[str]:
        """搜索设计作品，逐页处理并生成临时PDF"""
        temp_pdf_files = []
        page = 1
        max_retries = 3
        retry_delay = 1 # 秒 # 确保延时为1秒

        while True:
            try:
                logger.info(f"开始获取第 {page} 页数据 (分类: {category_filter or '所有'}) ") # 修改日志
                
                # 构建请求参数
                params = {
                    'solr[filter][]': [], # 将空字符串改为列表，方便添加多个过滤条件
                    'solr[page]': page
                }
                if keyword:
                    params['solr[q]'] = keyword

                # 添加分类过滤条件
                if category_filter:
                    params['solr[filter][]'].append(category_filter)

                # 构建完整的请求URL并记录
                request = requests.Request('GET', self.base_url, params=params)
                prepared_request = request.prepare()
                full_url = prepared_request.url
                logger.info(f"发送请求到: {full_url}")

                # 发送请求，增加重试机制
                for retry_num in range(max_retries):
                    try:
                        response = requests.Session().send(prepared_request, timeout=10) # 使用Session发送预处理的请求
                        response.raise_for_status() # 检查HTTP状态码
                        logger.info("网络请求成功")
                        # 记录响应状态码和部分内容
                        logger.debug(f"收到完整响应 (状态码: {response.status_code}):\n{response.text}") # 记录完整的响应内容
                        break # 请求成功，跳出重试循环
                    except requests.exceptions.RequestException as e:
                        logger.warning(f"网络请求失败 (尝试 {retry_num + 1}/{max_retries}): {str(e)}")
                        if retry_num < max_retries - 1:
                            logger.info(f"等待 {retry_delay} 秒后重试...")
                            time.sleep(retry_delay)
                        else:
                            logger.error(f"网络请求在 {max_retries} 次尝试后仍然失败")
                            raise # 重试次数用尽，抛出异常

                logger.info("收到响应，开始解析内容")
                data = response.json()
                
                page_designs = []
                # 检查 'result' 和 'docs' 键是否存在，并直接遍历 'docs' 列表
                if 'result' in data and 'docs' in data['result'] and isinstance(data['result']['docs'], list):
                    for doc in data['result']['docs']: # 直接迭代 result['docs']
                        try:
                            # 打印原始doc对象，用于调试
                            logger.debug(f"原始设计作品数据 (doc): {json.dumps(doc, ensure_ascii=False, indent=2)}")

                            # 从API响应中提取必要信息
                            title = doc.get('title', '').strip()
                            category = doc.get('data', {}).get('category', '').strip()
                            image_url = doc.get('image', {}).get('large', '').strip()
                            author = doc.get('meta_second', '').strip()
                            year = doc.get('data', {}).get('year', '').strip()
                            detail_url_suffix = doc.get('url') # 获取详情页URL的后缀

                            # 验证必要字段
                            if not title or not image_url or not detail_url_suffix: # 确保能获取到详情页URL后缀
                                logger.warning(f"跳过无效数据 (缺少标题、图片URL或详情页URL后缀): {json.dumps(doc, ensure_ascii=False)}")
                                continue
                                
                            # 构建完整的详情页URL
                            detail_url = f"{self.site_base_url}{detail_url_suffix}"
                            logger.debug(f"构建的详情页完整URL: {detail_url}")

                            # 抓取详情页数据
                            details = self.get_design_details(detail_url)
                            description = ''
                            if details and 'description' in details:
                                description = details['description']

                            design = {
                                'title': title,
                                'description': description, # 使用从详情页获取的描述
                                'type': category,
                                'image_url': image_url,
                                'author': author,
                                'date': year,
                                'detail_url': detail_url # 保留详情页URL，可能有用
                            }
                            
                            # 检查作品URL，如果已见过则跳过，否则添加到列表和seen_design_ids
                            design_url = doc.get('url') # 使用url字段进行去重
                            if design_url:
                                if design_url in self.seen_design_ids:
                                    logger.info(f"作品URL {design_url} 已见过，跳过: {title}")
                                    continue # 跳过已见过的作品
                                else:
                                    self.seen_design_ids.add(design_url)
                                    page_designs.append(design)
                                    logger.info(f"解析到设计作品: {design['title']} (URL: {design_url}, 描述长度: {len(description)})")
                            else:
                                logger.warning(f"作品缺少URL字段，无法去重: {title}")
                                # 如果没有URL，暂时还是添加到列表，但无法保证去重
                                page_designs.append(design)
                                logger.info(f"解析到设计作品 (无URL): {design.get('title', '未知标题')} (描述长度: {len(description)})")

                        except Exception as e:
                            logger.error(f"处理单个设计作品时出错: {str(e)}", exc_info=True)
                            continue
                
                if not page_designs:
                    logger.info(f"第 {page} 页去重后没有作品，停止获取") # 修改日志信息
                    break
                    
                # logger.info(f"成功获取并处理第 {page} 页的 {len(processed_designs)} 个设计作品")
                # logger.info(f"成功获取并处理第 {page} 页的 {len(page_designs)} 个设计作品") # 原始日志，现在处理后直接使用page_designs

                # 并发获取详情页和下载图片 (在获取到当页所有去重后的作品列表后处理)
                # 将详情页获取和图片下载逻辑移到这里，对 page_designs 列表进行处理
                processed_page_designs = []
                # 同样可以使用并发，但根据用户要求，先实现顺序处理
                for design in page_designs:
                    try:
                        # 获取详情页数据 (描述)
                        details = self.get_design_details(design.get('detail_url')) # 从设计数据中获取详情页URL
                        if details and 'description' in details:
                             design['description'] = details['description'] # 更新描述
                             logger.debug(f"更新作品 {design.get('title','未知标题')} 描述")

                        # 下载图片
                        image_data = self.download_image(design.get('image_url'))
                        design['image_data'] = image_data # 将图片数据添加到设计字典
                        if image_data:
                             logger.debug(f"下载并添加作品 {design.get('title','未知标题')} 图片数据")
                        else:
                             logger.warning(f"未能下载作品 {design.get('title','未知标题')} 图片")

                        processed_page_designs.append(design) # 添加处理后的作品

                    except Exception as e:
                        logger.error(f"处理单个设计作品详情/图片失败: {design.get('title','未知标题')} - {str(e)}", exc_info=True)
                        # 即使处理失败，也可能需要添加到列表中，取决于是否希望在PDF中显示部分信息
                        # 这里选择跳过处理失败的作品，只添加成功处理的
                        # processed_page_designs.append(design) # 如果希望包含处理失败的作品
                        continue

                # 更新 page_designs 为处理了详情页和图片的列表
                page_designs = processed_page_designs

                if not page_designs:
                     logger.warning(f"第 {page} 页所有设计作品详情/图片处理失败，停止获取")
                     break

                logger.info(f"成功处理第 {page} 页的 {len(page_designs)} 个设计作品（去重后）") # 修改日志信息

                 # 处理当前页数据并生成临时PDF
                temp_pdf_path = self.create_temp_page_pdf(page_designs, page)
                # 检查临时PDF是否成功生成
                if temp_pdf_path:
                    temp_pdf_files.append(temp_pdf_path)
                else:
                    logger.warning(f"生成第 {page} 页临时PDF失败，跳过合并此页")

                page += 1
                
            except Exception as e:
                logger.error(f"处理第 {page} 页数据时发生异常: {str(e)}", exc_info=True)
                # 如果是网络请求重试后仍然失败，异常已经抛出并在外层捕获
                # 其他异常（如解析错误）也会在这里捕获并记录
                break # 发生错误时停止获取后续页面
        
        logger.info("数据获取完成")
        return temp_pdf_files

    def download_image(self, image_url: str) -> Optional[BytesIO]:
        """下载图片，增加重试机制"""
        max_retries = 3
        retry_delay = 1 # 秒

        for retry_num in range(max_retries):
            try:
                logger.info(f"开始下载图片 (尝试 {retry_num + 1}/{max_retries}): {image_url}")
                
                # 下载图片
                response = requests.get(image_url, timeout=10) # 增加超时设置
                response.raise_for_status()
                
                logger.info("图片下载成功")
                return BytesIO(response.content)

            except requests.exceptions.RequestException as e:
                logger.warning(f"下载图片失败 (尝试 {retry_num + 1}/{max_retries}): {str(e)}")
                if retry_num < max_retries - 1:
                    logger.info(f"等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"下载图片在 {max_retries} 次尝试后仍然失败: {image_url}")
                    # 如果所有重试都失败，不抛出异常，而是返回 None，以便主流程可以继续处理其他作品
                    return None

        # 重试循环结束，但理论上因为上面的 return None 不会执行到这里
        return None

    def create_temp_page_pdf(self, designs: List[Dict], page_num: int) -> str:
        """生成包含单页数据和临时封面/页眉页脚的PDF文件"""
        logger.info(f"开始生成第 {page_num} 页的临时PDF")
        
        output_filename = f"temp_page_{page_num}.pdf"
        output_path = os.path.join(self.temp_dir, output_filename)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=3*cm,  # 增加顶部边距，为页眉留出空间
            bottomMargin=3*cm  # 增加底部边距，为页脚留出空间
        )

        styles = getSampleStyleSheet()

        # 临时页封面/页眉样式
        temp_cover_style = ParagraphStyle(
            'TempCover',
            parent=styles['Heading1'],
            fontName=FONT_NAME,
            fontSize=18,
            spaceAfter=20,
            alignment=1,  # 居中
            textColor=colors.HexColor('#1a1a1a')
        )
        
        # 临时页标题样式 (参考最终封面标题)
        temp_page_title_style = ParagraphStyle(
            'TempPageTitle',
            parent=styles['Heading1'],
            fontName=FONT_NAME,
            fontSize=30,  # 适当增大字体
            spaceBefore=10*cm, # 增加顶部空间模拟垂直居中
            spaceAfter=0.5*cm, # 调整间距，减小主标题与下方信息的距离
            alignment=1,  # 居中
            textColor=colors.HexColor('#1a1a1a'),
            bold=1 # 加粗
        )
        
        # 临时页信息样式 (参考最终封面副标题/信息)
        temp_page_info_style = ParagraphStyle(
            'TempPageInfo',
            parent=styles['Normal'],
            fontName=FONT_NAME,
            fontSize=12,  # 调整字体大小
            spaceAfter=0.5*cm, # 调整间距
            alignment=1, # 居中
            textColor=colors.HexColor('#444444')
        )

        # 页眉页脚样式 (与最终PDF页眉页脚一致)
        header_footer_style = ParagraphStyle(
            'HeaderFooter',
            parent=styles['Normal'],
            fontName=FONT_NAME,
            fontSize=8,
            textColor=colors.HexColor('#666666'),
            alignment=1  # 居中
        )

        def add_temp_header_footer(canvas, doc):
            canvas.saveState()

            # 临时页脚 (显示作者信息和临时页码)
            canvas.setFont(FONT_NAME, 8)  # 页脚使用小字体
            canvas.drawString(doc.leftMargin, doc.bottomMargin - 1*cm, f"tAngo/org.java.tango@gmail.com") # 只保留作者信息
            # 显示当前临时PDF的页码
            page_number_text = f"页码: {canvas.getPageNumber()}"
            page_number_width = canvas.stringWidth(page_number_text, FONT_NAME, 8)
            # 调整页码位置，确保在右侧
            canvas.drawString(doc.width + doc.leftMargin - page_number_width, doc.bottomMargin - 1*cm, page_number_text)

            canvas.restoreState()

        story = []

        # 添加临时页标题 - 使用原页眉文本作为主标题
        temp_cover_main_title_style = ParagraphStyle(
            'TempCoverMainTitle',
            parent=styles['Heading1'],
            fontName=FONT_NAME,
            fontSize=24, # 适当的字体大小
            spaceBefore=10*cm, # 增加顶部空间
            spaceAfter=1*cm, # 标题与下方信息的间距
            alignment=1,  # 居中
            textColor=colors.HexColor('#1a1a1a'),
            bold=1 # 加粗
        )
        story.append(Paragraph(f"红点设计奖作品集 (数据页 {page_num})", temp_cover_main_title_style))
        
        # 添加本页收录作品数量信息 (移到时间上方)
        story.append(Paragraph(f"本页收录 {len(designs)} 个作品", temp_page_info_style))
        story.append(Spacer(1, 0.5*cm)) # 调整作品数与时间之间的间距

        # 添加临时页信息 (时间、作者)
        temp_time_author_style = ParagraphStyle(
            'TempTimeAuthorInfo',
            parent=temp_page_info_style,
            spaceAfter=0.2*cm # 调整时间和作者之间的间距
        )
        story.append(Paragraph(f"生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}", temp_time_author_style))
        story.append(Paragraph(f"tAngo/org.java.tango@gmail.com", temp_page_info_style))
        
        # story.append(Paragraph(f"本页收录 {len(designs)} 个作品", temp_page_info_style))
        story.append(Spacer(1, 3*cm)) # 调整信息与内容之间的间距

        story.append(PageBreak()) # 强制分页，后续是作品内容

        # 添加当前页的设计作品
        for i, design in enumerate(designs, 1): # 序号相对于当前页
            try:
                logger.info(f"处理第 {page_num} 页的第 {i} 个作品: {design.get('title', '未知标题')}")

                # 添加图片
                image_data = self.download_image(design['image_url'])
                if image_data:
                    try:
                        img = PILImage.open(image_data)
                        img_width, img_height = img.size
                        aspect = img_height / float(img_width)
                        # 限制图片宽度，高度按比例缩放
                        max_img_width = 500 # 最大图片宽度
                        if img_width > max_img_width:
                            img_height = max_img_width * aspect
                            img_width = max_img_width

                        # 确保图片不超过页面宽度
                        available_width = A4[0] - doc.leftMargin - doc.rightMargin
                        if img_width > available_width:
                             img_height = available_width * aspect
                             img_width = available_width

                        # 确保图片高度不会超出页面可用高度（考虑边距和潜在的frame限制）
                        # ReportLab的frame高度可能略小于 (page_height - topMargin - bottomMargin)
                        # 我们使用一个保守的最大高度限制
                        max_allowed_height = A4[1] - doc.topMargin - doc.bottomMargin - 15 # 减去更多的余量，例如15点

                        if img_height > max_allowed_height:
                             # 如果高度超出，按最大允许高度重新缩放，保持比例
                             img_width = max_allowed_height / aspect
                             img_height = max_allowed_height

                        # 最终确认宽度也没有超出可用范围（理论上按高度缩放后宽度不会超，但为了保险）
                        if img_width > available_width:
                            img_height = available_width * aspect
                            img_width = available_width

                        story.append(Image(image_data, width=img_width, height=img_height))
                        story.append(Spacer(1, 12)) # 图片下方间距
                    except Exception as e:
                        logger.error(f"处理图片时出错: {str(e)}")
                        # 如果图片处理失败，可以添加一个占位符或者文字说明
                        story.append(Paragraph("图片加载或处理失败", styles['Normal']))
                        story.append(Spacer(1, 12))

                # 添加详细信息（不使用表格）
                # 定义内容样式
                content_label_style = ParagraphStyle(
                    'ContentLabel',
                    parent=styles['Normal'],
                    fontName=FONT_NAME,
                    fontSize=10,
                    textColor=colors.black, # 将标签颜色改为黑色
                    bold=1,
                    spaceAfter=3 # 标签和值之间增加少量间距
                )
                content_value_style = ParagraphStyle(
                    'ContentValue',
                    parent=styles['Normal'],
                    fontName=FONT_NAME,
                    fontSize=10,
                    textColor=colors.HexColor('#666666'),
                    spaceAfter=8 # 每项信息后的小间距，稍微增加
                )
                description_style = ParagraphStyle(
                     'DescriptionStyle',
                     parent=styles['Normal'],
                     fontName=FONT_NAME,
                     fontSize=10,
                     textColor=colors.HexColor('#666666'),
                     spaceAfter=12, # 描述后的大间距
                     leading=14 # 行高
                )

                # 添加序号
                story.append(Paragraph("序号:", content_label_style))
                story.append(Paragraph(f"{page_num}-{i}", content_value_style))

                # 添加标题
                story.append(Paragraph("标题:", content_label_style))
                story.append(Paragraph(design['title'], content_value_style))

                # 添加项目描述
                story.append(Paragraph("项目描述:", content_label_style))
                story.append(Paragraph(design['description'] or '暂无描述', description_style))

                # 添加类型
                story.append(Paragraph("类型:", content_label_style))
                story.append(Paragraph(design['type'] or '未知类型', content_value_style))

                # 添加作者
                story.append(Paragraph("作者:", content_label_style))
                story.append(Paragraph(design['author'] or '未知作者', content_value_style))

                # 添加时间
                story.append(Paragraph("时间:", content_label_style))
                story.append(Paragraph(design['date'] or '未知时间', content_value_style))

                # 添加作品之间的间隔
                story.append(Spacer(1, 20))

            except Exception as e:
                logger.error(f"处理第 {page_num} 页的第 {i} 个作品时出错: {str(e)}", exc_info=True)
                continue

        try:
            doc.build(story)
            logger.info(f"第 {page_num} 页临时PDF生成完成: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"生成第 {page_num} 页临时PDF时出错: {str(e)}")
            return ""

    def test_pdf_styles(self):
        """生成一个测试PDF，包含封面和示例内容页，方便用户检查样式"""
        logger.info("开始生成测试PDF样式文件")

        test_total_count = 50 # 示例总数
        # test_cover_filename = "test_cover.pdf" # 已经在create_cover_pdf中作为参数传递
        test_output_filename = "test_styles.pdf"

        # 生成测试封面 (文件名与merge_pdfs预期一致)
        self.create_cover_pdf(test_total_count, "cover.pdf")

        # 创建示例设计作品数据，不再进行网络请求
        example_designs = []
        for i in range(1, 6): # 生成5个示例作品
            example_designs.append({
                'title': f'示例设计作品标题 {i}',
                'description': f'这是示例设计作品 {i} 的描述。这是一个较长的描述，用于测试段落布局和换行。重复一些文字以增加长度：Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Cras justo odio, dapibus ac facilisis in, egestas eget quam. Praesent commodo cursus magna, vel scelerisque nisl consectetur et. ',
                'type': f'示例类型 {i}',
                # 使用一个无效或本地的URL，download_image 会处理失败情况
                'image_url': f'http://invalid.url/test_image_{i}.jpg', 
                'author': f'示例作者 {i}',
                'date': f'202{i}',
                'detail_url': f'http://test.url/details/{i}' # 示例详情页URL
            })

        # 生成包含示例内容的临时PDF
        # 注意：这里我们只生成一页临时内容用于测试，实际爬取会生成多页
        temp_pdf_path = self.create_temp_page_pdf(example_designs, 1) # 生成第1页临时PDF

        # 合并测试封面和临时内容PDF
        if temp_pdf_path:
            # 由于merge_pdfs会查找temp目录下的cover.pdf，这里直接调用即可
            temp_files_to_merge = [temp_pdf_path] # 临时内容页文件列表
            self.merge_pdfs(temp_files_to_merge, test_output_filename)
            test_output_path = os.path.join(self.output_dir, test_output_filename)
            logger.info(f"测试PDF样式文件已生成: {test_output_path}")
            logger.info("请打开此文件检查封面和内容样式")
        else:
             logger.warning("无法生成临时内容PDF，跳过合并测试")

    def create_cover_pdf(self, total_count: int, output_filename: str):
        """生成封面PDF"""
        logger.info("开始生成封面PDF")

        doc = SimpleDocTemplate(
            os.path.join(self.temp_dir, output_filename),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=5*cm,  # 增加顶部边距
            bottomMargin=2*cm  # 调整底部边距
        )

        styles = getSampleStyleSheet()

        # 封面主标题样式
        cover_title_style = ParagraphStyle(
            'CoverTitle',
            parent=styles['Heading1'],
            fontName=FONT_NAME,
            fontSize=36,  # 增大字体
            spaceAfter=40, # 增加间距
            alignment=1,  # 居中
            textColor=colors.HexColor('#1a1a1a'),
            bold=1, # 加粗
            spaceBefore=8*cm # 增加顶部空间，帮助垂直居中
        )

        # 封面副标题/信息样式
        cover_info_style = ParagraphStyle(
            'CoverInfo',
            parent=styles['Normal'],
            fontName=FONT_NAME,
            fontSize=14,  # 调整字体大小
            spaceAfter=15, # 调整间距
            alignment=1, # 居中
            textColor=colors.HexColor('#444444')
        )

        story = []

        # 添加封面主标题
        story.append(Paragraph("红点设计奖作品集", cover_title_style))

        # 添加信息
        story.append(Paragraph(f"共收录 {total_count} 个设计作品", cover_info_style))
        story.append(Spacer(1, 1*cm)) # 减小信息与作者之间的间距

        # 添加作者信息
        author_style = ParagraphStyle(
            'AuthorInfo',
            parent=styles['Normal'],
            fontName=FONT_NAME,
            fontSize=10, # 减小字体大小
            spaceAfter=0,
            alignment=1,
            textColor=colors.HexColor('#666666')
        )
        # 将时间和作者信息分开显示，减小间距
        time_style = ParagraphStyle(
            'TimeInfo',
            parent=author_style,
            spaceAfter=0.2*cm # 调整时间和作者之间的间距
        )
        story.append(Paragraph(f"生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}", time_style))
        story.append(Paragraph(f"tAngo/org.java.tango@gmail.com", author_style))
        story.append(Spacer(1, 0.5*cm)) # 添加一些小的间距

        # 在封面后强制分页
        story.append(PageBreak())

        # 构建PDF，封面页不应用页眉页脚
        doc.build(story)
        logger.info("封面PDF生成完成")

    def merge_pdfs(self, temp_pdf_files: List[str], output_filename: str):
        """合并临时PDF文件，跳过每页的第一个临时封面，并重新计算全局页码"""
        logger.info("开始合并临时PDF文件")

        writer = PdfWriter()
        global_page_count = 0 # 用于计算全局页码

        # 添加封面
        cover_path = os.path.join(self.temp_dir, "cover.pdf")
        if os.path.exists(cover_path):
            try:
                reader = PdfReader(cover_path)
                writer.add_page(reader.pages[0]) # 添加封面页
                global_page_count += 1
            except Exception as e:
                 logger.error(f"读取封面文件失败: {str(e)}")

        # 合并临时内容页
        # 临时文件已经是按页码顺序生成的，无需再次排序
        for temp_pdf_file in temp_pdf_files:
            try:
                reader = PdfReader(temp_pdf_file)
                # 跳过每个临时PDF文件的第一页 (临时封面)
                for i in range(1, len(reader.pages)):
                    page = reader.pages[i]

                    # 手动添加页码和页脚
                    packet = BytesIO()
                    # 使用 ReportLab 创建一个只包含页眉页脚和页码的 canvas
                    c = canvas.Canvas(packet, pagesize=A4)
                    
                    # 获取页面的尺寸 (以points为单位)
                    page_width = A4[0]
                    page_height = A4[1]

                    # 添加页脚
                    c.setFont(FONT_NAME, 8) # 页脚使用小字体
                    # 绘制作者信息
                    footer_author_text = f"红点设计奖作品集 tAngo/org.java.tango@gmail.com" # 简化页脚作者信息
                    # 调整作者信息位置，确保在左下角
                    c.drawString(2*cm, 2*cm, footer_author_text)

                    # 添加全局页码
                    global_page_count += 1
                    page_number_text = f"第 {global_page_count} 页"
                    page_number_width = c.stringWidth(page_number_text, FONT_NAME, 8)
                    # 调整页码位置，确保在右下角
                    c.drawString(page_width - 2*cm - page_number_width, 2*cm, page_number_text)

                    c.save()
                    packet.seek(0)
                    new_pdf = PdfReader(packet)
                    
                    page.merge_page(new_pdf.pages[0])
                    writer.add_page(page)

            except Exception as e:
                logger.error(f"处理临时文件 {temp_pdf_file} 失败: {str(e)}", exc_info=True)
                continue

        # 保存合并后的文件
        final_output_path = os.path.join(self.output_dir, output_filename)
        with open(final_output_path, 'wb') as f:
            writer.write(f)
        logger.info(f"PDF文件合并完成: {final_output_path}")

        # 将临时文件移动到输出目录
        for file in os.listdir(self.temp_dir):
            src_path = os.path.join(self.temp_dir, file)
            dst_path = os.path.join(self.output_dir, file)
            # 确保不是目录
            if os.path.isfile(src_path):
                try:
                    os.rename(src_path, dst_path)
                except OSError as e:
                    logger.error(f"移动临时文件 {src_path} 到 {dst_path} 失败: {str(e)}")

        # 删除临时目录
        # 检查目录是否为空再删除
        if not os.listdir(self.temp_dir):
            try:
                os.rmdir(self.temp_dir)
                logger.info("临时目录已删除")
            except OSError as e:
                 logger.error(f"删除临时目录 {self.temp_dir} 失败: {str(e)}")
        else:
            logger.warning("临时目录不为空，跳过删除")

def main():
    # 定义需要采集的分类及其对应的API过滤参数
    categories = {
        "product_design": "meta_categories:/10/", # 更新为正确的过滤参数格式和ID
        "brand_communication_design": "meta_categories:/11/", # 更新为正确的过滤参数格式和ID
        "design_concept": "meta_categories:/12/" # 更新为正确的过滤参数格式和ID
    }

    for category_name, category_filter in categories.items():
        logger.info(f"\n--- 开始采集分类: {category_name} (过滤参数: {category_filter}) ---")

        # 根据分类名称动态生成输出目录（例如 output/product_design）
        category_output_dir = os.path.join("output", category_name)
        # 确保分类输出目录存在
        if not os.path.exists(category_output_dir):
             os.makedirs(category_output_dir)
             logger.info(f"创建分类输出目录: {category_output_dir}")

        # 为当前分类创建一个新的爬虫实例
        crawler = RedDotCrawler(
            base_url="https://www.red-dot.org/de/search/search.json",
            output_dir=category_output_dir, # 使用分类的输出目录
            site_base_url="https://www.red-dot.org"
        )

        # 搜索设计作品，逐页处理并生成临时PDF，返回临时文件列表
        # 传入当前分类过滤参数
        temp_pdf_files = crawler.search_designs(keyword="", category_filter=category_filter)

        if temp_pdf_files:
            # 生成封面
            # 封面会生成在当前分类的临时目录 (category_output_dir/temp) 下
            crawler.create_cover_pdf(0, "cover.pdf")

            # 合并所有临时PDF
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # 输出文件名包含分类名称
            output_filename = f"reddot_designs_{category_name}_{timestamp}.pdf"
            # merge_pdfs 会将最终文件保存到 crawler.output_dir，即 category_output_dir
            crawler.merge_pdfs(temp_pdf_files, output_filename)
            logger.info(f"PDF文件已生成: {os.path.join(category_output_dir, output_filename)}")
        else:
            logger.warning(f"未找到 {category_name} 分类的设计作品")

        logger.info(f"--- 完成采集分类: {category_name} ---\n") # 修改日志

    logger.info("所有分类采集任务完成") # 添加完成日志

if __name__ == "__main__":
    # crawler = RedDotCrawler() # 原始实例化，现在调用main或test_pdf_styles时在函数内部实例化
    # crawler.test_pdf_styles()
    main()
    