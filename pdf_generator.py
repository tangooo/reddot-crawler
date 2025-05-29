import os
import logging
from datetime import datetime
from typing import List, Dict, Optional
import platform
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT # 导入对齐常量
from PIL import Image as PILImage
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

# 导入配置
import config

# 配置日志 (在 PdfGenerator 中也需要日志)
logger = logging.getLogger(__name__)

# 根据操作系统选择合适的中文字体
def get_system_font():
    def is_valid_font(font_path):
        try:
            try:
                pdfmetrics.registerFont(TTFont('TestFont', font_path))
                return True
            except Exception as e:
                logger.debug(f"字体文件 {font_path} 注册测试失败: {str(e)}")
                return False
        except Exception as e:
            logger.warning(f"检查字体文件 {font_path} 时出错: {str(e)}")
            return False

    # 首先检查fonts目录下的字体
    fonts_dir = config.FONTS_DIR # 使用 config 中配置的字体目录
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
            logger.info(f"使用有效的系统字体: {path}")
            return font_path
        elif os.path.exists(font_path):
            logger.warning(f"系统字体格式无效: {path}")
    
    logger.warning("未找到任何有效的中文字体")
    return None

# 注册系统字体
FONT_PATH = get_system_font()
try:
    if FONT_PATH and os.path.exists(FONT_PATH):
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

class PdfGenerator:
    def __init__(self, output_dir: str = config.OUTPUT_DIR):
        self.output_dir = output_dir
        self.temp_dir = os.path.join(self.output_dir, "temp")
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
        logger.info(f"PDF 生成器初始化，输出目录: {self.output_dir}")
        self.FONT_NAME = FONT_NAME # 使用模块级别的字体名称

        # 设置 chinese_font 为全局确定的字体名称
        self.chinese_font = FONT_NAME

        # 创建样式
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        """设置 PDF 样式"""
        # 标题样式
        self.styles.add(ParagraphStyle(
            name='ChineseTitle',
            fontName=self.chinese_font,
            fontSize=24,
            alignment=TA_CENTER,
            spaceAfter=30,
            leading=30
        ))

        # 子标题样式
        self.styles.add(ParagraphStyle(
            name='ChineseSubTitle',
            fontName=self.chinese_font,
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=20,
            leading=20
        ))

        # 正文样式
        self.styles.add(ParagraphStyle(
            name='ChineseBody',
            fontName=self.chinese_font,
            fontSize=12,
            alignment=TA_LEFT,
            spaceAfter=12,
            leading=14
        ))

        # 标签样式
        self.styles.add(ParagraphStyle(
            name='ChineseLabel',
            fontName=self.chinese_font,
            fontSize=12,
            alignment=TA_LEFT,
            textColor=colors.black,
            spaceAfter=6,
            leading=14
        ))

    def create_temp_page_pdf(self, designs: List[Dict], page_num: int) -> Optional[str]:
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
            fontName=self.FONT_NAME,
            fontSize=18,
            spaceAfter=20,
            alignment=1,  # 居中
            textColor=colors.HexColor('#1a1a1a')
        )
        
        # 临时页标题样式 (参考最终封面标题)
        temp_page_title_style = ParagraphStyle(
            'TempPageTitle',
            parent=styles['Heading1'],
            fontName=self.FONT_NAME,
            fontSize=24, # 适当增大字体
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
            fontName=self.FONT_NAME,
            fontSize=12,  # 调整字体大小
            spaceAfter=0.5*cm, # 调整间距
            alignment=1, # 居中
            textColor=colors.HexColor('#444444')
        )

        story = []

        # 添加临时页标题 - 使用原页眉文本作为主标题
        story.append(Paragraph(f"红点设计奖作品集 (数据页 {page_num})", temp_page_title_style))
        
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
        
        story.append(Spacer(1, 3*cm)) # 调整信息与内容之间的间距

        story.append(PageBreak()) # 强制分页，后续是作品内容

        # 添加当前页的设计作品
        for i, design in enumerate(designs, 1): # 序号相对于当前页
            try:
                logger.info(f"处理第 {page_num} 页的第 {i} 个作品: {design.get('title', '未知标题')}")

                # 添加图片 (这里假设design字典中已经包含了下载好的图片数据或者我们会在这里下载)
                # 为了保持PdfGenerator的独立性，假设图片数据是作为BytesIO对象传递进来的
                # 如果design字典中没有图片数据，或者下载失败，则跳过图片添加
                # 现在design中应该有 'image_path' 字段
                image_path = design.get('image_path')
                if image_path and os.path.exists(image_path):
                    try:
                        logger.info(f"尝试加载图片用于PDF: {image_path} 为作品: {design.get('title', '未知标题')}")
                        img = Image(image_path)
                        # 调整图片大小以适应页面
                        img_width, img_height = img.drawWidth, img.drawHeight
                        aspect = img_height / float(img_width)
                        # 限制图片宽度，高度按比例缩放
                        max_img_width = A4[0] - doc.leftMargin - doc.rightMargin - 20 # 留出一些边距
                        if img_width > max_img_width:
                            img_width = max_img_width
                            img_height = img_width * aspect

                        # 确保图片高度不会超出页面可用高度（考虑边距）
                        max_allowed_height = A4[1] - doc.topMargin - doc.bottomMargin - 20 # 留出更多余量
                        if img_height > max_allowed_height:
                             img_height = max_allowed_height
                             img_width = img_height / aspect


                        story.append(Image(image_path, width=img_width, height=img_height))
                        story.append(Spacer(1, 12)) # 图片下方间距
                        logger.info(f"成功加载图片 {image_path} 并添加到PDF story")
                    except Exception as e:
                        logger.error(f"处理作品 {design.get('title', '未知标题')} 图片时出错: {str(e)}", exc_info=True)
                        story.append(Paragraph("图片加载或处理失败", styles['Normal']))
                        story.append(Spacer(1, 12))
                else:
                     logger.warning(f"作品 {design.get('title', '未知标题')} 没有有效的图片路径: {image_path}")

                # 添加详细信息（不使用表格）
                content_label_style = ParagraphStyle(
                    'ContentLabel',
                    parent=styles['Normal'],
                    fontName=self.FONT_NAME,
                    fontSize=10,
                    textColor=colors.black,
                    bold=1,
                    spaceAfter=3
                )
                content_value_style = ParagraphStyle(
                    'ContentValue',
                    parent=styles['Normal'],
                    fontName=self.FONT_NAME,
                    fontSize=10,
                    textColor=colors.HexColor('#666666'),
                    spaceAfter=8
                )
                description_style = ParagraphStyle(
                     'DescriptionStyle',
                     parent=styles['Normal'],
                     fontName=self.FONT_NAME,
                     fontSize=10,
                     textColor=colors.HexColor('#666666'),
                     spaceAfter=12,
                     leading=14
                )

                # 添加序号
                story.append(Paragraph("序号:", content_label_style))
                story.append(Paragraph(f"{page_num}-{i}", content_value_style))

                # 添加标题
                story.append(Paragraph("标题:", content_label_style))
                story.append(Paragraph(design.get('title', '未知标题'), content_value_style))

                # 添加项目描述
                story.append(Paragraph("项目描述:", content_label_style))
                story.append(Paragraph(design.get('description', '暂无描述') or '暂无描述', description_style))

                # 添加类型
                story.append(Paragraph("类型:", content_label_style))
                story.append(Paragraph(design.get('type', '未知类型') or '未知类型', content_value_style))

                # 添加作者
                story.append(Paragraph("作者:", content_label_style))
                story.append(Paragraph(design.get('author', '未知作者') or '未知作者', content_value_style))

                # 添加时间
                story.append(Paragraph("时间:", content_label_style))
                story.append(Paragraph(design.get('date', '未知时间') or '未知时间', content_value_style))

                # 添加作品之间的间隔
                story.append(Spacer(1, 20))

            except Exception as e:
                logger.error(f"处理第 {page_num} 页的第 {i} 个作品时出错: {str(e)}", exc_info=True)
                continue

        try:
            # 生成临时PDF，不包含页眉页脚，以便合并时统一添加
            doc.build(story)
            logger.info(f"第 {page_num} 页临时PDF文件生成成功: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"生成第 {page_num} 页临时PDF时出错: {str(e)}")
            return None

    def create_cover_pdf(self, total_count: int, output_filename: str = "cover.pdf") -> Optional[str]:
        """生成封面PDF"""
        logger.info("开始生成封面PDF")

        output_path = os.path.join(self.temp_dir, output_filename)
        doc = SimpleDocTemplate(
            output_path,
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
            fontName=self.FONT_NAME,
            fontSize=36,
            spaceAfter=40,
            alignment=1,
            textColor=colors.HexColor('#1a1a1a'),
            bold=1,
            spaceBefore=8*cm # 增加顶部空间，帮助垂直居中
        )

        # 封面信息样式
        cover_info_style = ParagraphStyle(
            'CoverInfo',
            parent=styles['Normal'],
            fontName=self.FONT_NAME,
            fontSize=14,
            spaceAfter=15,
            alignment=1,
            textColor=colors.HexColor('#444444')
        )

        # 时间和作者样式
        time_author_style = ParagraphStyle(
            'TimeAuthorInfo',
            parent=styles['Normal'],
            fontName=self.FONT_NAME,
            fontSize=10,
            spaceAfter=0,
            alignment=1,
            textColor=colors.HexColor('#666666')
        )

        # 时间和作者行间距调整
        time_style = ParagraphStyle(
            'TimeInfo',
            parent=time_author_style,
            spaceAfter=0.2*cm # 调整时间和作者之间的间距
        )


        story = []

        # 添加封面主标题
        story.append(Paragraph("红点设计奖作品集", cover_title_style))

        # 添加总数信息
        story.append(Paragraph(f"共收录 {total_count} 个设计作品", cover_info_style)) # 使用实际总数
        story.append(Spacer(1, 1*cm)) # 减小信息与作者之间的间距

        # 添加作者信息
        story.append(Paragraph(f"生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}", time_style))
        story.append(Paragraph(f"tAngo/org.java.tango@gmail.com", time_author_style))
        story.append(Spacer(1, 0.5*cm)) # 添加一些小的间距

        # 在封面后强制分页
        story.append(PageBreak())

        try:
            doc.build(story)
            logger.info("封面PDF生成完成")
            return output_path
        except Exception as e:
             logger.error(f"生成封面PDF时出错: {str(e)}")
             return None

    def merge_pdfs(self, temp_pdf_files: List[str], output_filename: str, total_count: int) -> Optional[str]:
        """合并临时PDF文件，并重新计算全局页码，将临时文件移动到输出目录"""
        logger.info("开始合并临时PDF文件")

        writer = PdfWriter()
        global_page_count = 0 # 用于计算全局页码

        # 添加封面
        # 封面现在在 main 函数中独立生成，并第一个被添加到临时文件列表中
        # 这里只需要按顺序读取并添加到 writer
        # 临时目录结构应为：temp/cover.pdf, temp/temp_page_1.pdf, temp/temp_page_2.pdf, ...

        all_files_to_merge = [os.path.join(self.temp_dir, "cover.pdf")] + temp_pdf_files

        for pdf_file_path in all_files_to_merge:
            if not os.path.exists(pdf_file_path):
                logger.warning(f"文件不存在，跳过合并: {pdf_file_path}")
                continue

            try:
                reader = PdfReader(pdf_file_path)
                num_pages = len(reader.pages)

                for i in range(num_pages):
                    page = reader.pages[i]

                    # 手动添加页脚（仅内容页添加，封面页不加）
                    if os.path.basename(pdf_file_path) != "cover.pdf":
                        packet = BytesIO()
                        c = canvas.Canvas(packet, pagesize=A4)

                        page_width = A4[0]
                        page_height = A4[1]

                        # 添加页脚作者信息 (左对齐)
                        c.setFont(self.FONT_NAME, 8)
                        footer_author_text = f"红点设计奖作品集 tAngo/org.java.tango@gmail.com"
                        c.drawString(2*cm, 1.5*cm, footer_author_text) # 调整垂直位置

                        # 添加全局页码 (右对齐)
                        # 注意：这里的页码是针对内容页的，不包括封面。如果总页数包含封面，页码应从1开始计算。
                        # global_page_count += 1 # 这一行应该在writer.add_page(page) 之后执行，确保页码计算正确

                        # total_count 是作品总数，封面是1页，所以总页数是 total_count + 1
                        # page_number_text = f"第 {global_page_count} 页 / 共 {total_count + 1} 页" # 页码总数包含封面
                        # page_number_width = c.stringWidth(page_number_text, self.FONT_NAME, 8)
                        # c.drawString(page_width - 2*cm - page_number_width, 1.5*cm, page_number_text) # 调整垂直位置

                        c.save()
                        packet.seek(0)
                        new_pdf = PdfReader(packet)

                        page.merge_page(new_pdf.pages[0]) # 将页脚合并到当前页

                    else:
                         # 如果是封面页，只递增全局页码计数，不绘制页脚
                         global_page_count += 1


                    writer.add_page(page)


            except Exception as e:
                logger.error(f"处理文件 {pdf_file_path} 失败: {str(e)}", exc_info=True)
                continue

        # 保存合并后的文件
        final_output_path = os.path.join(self.output_dir, output_filename)
        try:
            with open(final_output_path, 'wb') as f:
                writer.write(f)
            logger.info(f"PDF文件合并完成: {final_output_path}")
        except Exception as e:
             logger.error(f"保存最终PDF文件失败: {str(e)}")
             return None

        # 将临时文件移动到输出目录
        if os.path.exists(self.temp_dir):
            for file in os.listdir(self.temp_dir):
                src_path = os.path.join(self.temp_dir, file)
                # 移动到上一级目录，也就是分类的输出目录
                dst_path = os.path.join(self.output_dir, file)
                if os.path.isfile(src_path):
                    try:
                        os.rename(src_path, dst_path)
                        logger.debug(f"移动临时文件: {src_path} -> {dst_path}")
                    except OSError as e:
                        logger.error(f"移动临时文件 {src_path} 到 {dst_path} 失败: {str(e)}")

            # 删除临时目录
            if not os.listdir(self.temp_dir):
                try:
                    os.rmdir(self.temp_dir)
                    logger.info("临时目录已删除")
                except OSError as e:
                     logger.error(f"删除临时目录 {self.temp_dir} 失败: {str(e)}")
            else:
                logger.warning("临时目录不为空，跳过删除")

        return final_output_path

    def test_pdf_styles(self, output_filename: str = "test_styles.pdf") -> Optional[str]:
        """测试 PDF 样式"""
        # 创建测试数据
        test_design = {
            'title': '测试作品标题',
            'type': '产品设计',
            'author': '测试作者',
            'date': '2024',
            'description': '这是一个测试作品描述，用于验证 PDF 样式。' * 5,
            'image_path': None  # 测试时不包含图片
        }
        
        # 生成测试 PDF
        return self.generate_full_pdf([test_design], output_filename)

    def generate_full_pdf(self, designs: List[Dict], output_filename: str) -> Optional[str]:
        """生成包含所有作品的完整 PDF"""
        if not designs:
            logger.warning("没有作品数据可生成 PDF")
            return None
            
        output_path = os.path.join(self.output_dir, output_filename)
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        elements = []
        
        # 添加封面
        elements.extend(self.create_cover_page("红点设计奖作品集", len(designs)))
        
        # 添加内容页
        for i, design in enumerate(designs, 1):
            elements.extend(self.create_content_page(design, i, len(designs)))
        
        try:
            doc.build(elements)
            logger.info(f"PDF 文件生成成功: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"生成 PDF 文件失败: {str(e)}")
            return None

    def create_cover_page(self, title: str, total_count: int) -> List:
        """创建封面页"""
        elements = []
        
        # 添加标题
        elements.append(Paragraph(title, self.styles['ChineseTitle']))
        elements.append(Spacer(1, 2*cm))
        
        # 添加时间和作者信息
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        elements.append(Paragraph(f"生成时间：{current_time}", self.styles['ChineseSubTitle']))
        elements.append(Spacer(1, 0.5*cm))
        elements.append(Paragraph(f"生成工具：RedDot Crawler", self.styles['ChineseSubTitle']))
        elements.append(Spacer(1, 0.5*cm))
        elements.append(Paragraph(f"作品总数：{total_count}", self.styles['ChineseSubTitle']))
        
        elements.append(PageBreak())
        return elements

    def create_content_page(self, design: Dict, page_number: int, total_pages: int) -> List:
        """创建内容页"""
        elements = []
        
        # 添加标题
        elements.append(Paragraph(design['title'], self.styles['ChineseTitle']))
        elements.append(Spacer(1, 1*cm))
        
        # 添加图片
        if 'image_path' in design and os.path.exists(design['image_path']):
            try:
                img = Image(design['image_path'])
                # 调整图片大小以适应页面
                img.drawHeight = min(img.drawHeight, 400)
                img.drawWidth = min(img.drawWidth, 400)
                elements.append(img)
                elements.append(Spacer(1, 1*cm))
            except Exception as e:
                logger.error(f"加载图片失败: {str(e)}")
        
        # 添加作品信息
        info_items = [
            ('类型', design.get('type', '')),
            ('作者', design.get('author', '')),
            ('日期', design.get('date', '')),
            ('描述', design.get('description', ''))
        ]
        
        for label, content in info_items:
            if content:
                elements.append(Paragraph(f"{label}：{content}", self.styles['ChineseLabel']))
                elements.append(Spacer(1, 0.3*cm))
        
        # 添加页码
        elements.append(Spacer(1, 1*cm))
        elements.append(Paragraph(f"第 {page_number} 页 / 共 {total_pages} 页", 
                                self.styles['ChineseBody']))
        
        elements.append(PageBreak())
        return elements 