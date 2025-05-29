import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
import csv # 导入 csv 模块
import hashlib # 导入 hashlib 用于生成文件名
import mimetypes # 导入 mimetypes 用于根据 Content-Type 获取后缀

# 导入并发库
import concurrent.futures

# 导入配置
import config

# 导入新的 PdfGenerator 类
from pdf_generator import PdfGenerator

from io import BytesIO
import requests
import platform
from bs4 import BeautifulSoup
from PIL import Image as PILImage # 导入 PIL 库用于图片处理

# 配置日志
logging.basicConfig(
    level=config.LOGGING_LEVEL, # 使用 config 中的日志级别
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawler.log', mode='w'),  # 使用 'w' 模式，每次启动时清空文件
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RedDotCrawler:
    def __init__(self,
                 base_url: str = config.BASE_URL,
                 output_dir: str = config.OUTPUT_DIR,
                 site_base_url: str = config.SITE_BASE_URL):
        self.base_url = base_url
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        # 创建图片保存目录
        self.images_dir = os.path.join(self.output_dir, "images")
        if not os.path.exists(self.images_dir):
            os.makedirs(self.images_dir)
        logger.info("初始化爬虫")
        self.site_base_url = site_base_url
        self.seen_design_ids = set() # 添加一个集合用于存储已见过的作品ID
        
        # 初始化 PdfGenerator 实例
        self.pdf_generator = PdfGenerator(output_dir=self.output_dir)

    def get_design_details(self, detail_url: str) -> Optional[Dict]:
        """从详情页抓取额外数据，例如描述"""
        max_retries = config.MAX_RETRIES
        retry_delay = config.RETRY_DELAY # 秒

        for retry_num in range(max_retries):
            try:
                logger.info(f"开始抓取详情页数据 (尝试 {retry_num + 1}/{max_retries}): {detail_url}")
                response = requests.get(detail_url, timeout=config.REQUEST_TIMEOUT)
                response.raise_for_status()
                
                logger.info("详情页请求成功，开始解析")
                soup = BeautifulSoup(response.content, 'html.parser')
                
                description = ''
                description_div = soup.find('div', class_='description')
                if description_div:
                    description = description_div.get_text(strip=True)

                # 提取作者信息
                author_parts = [] # 使用列表收集所有作者相关的价值内容
                credits_div = soup.find('div', class_='credits')
                if credits_div:
                    logger.debug("找到 credits 块，开始提取所有内容作为作者信息")
                    # 查找所有的 li.flex 元素
                    for li in credits_div.find_all('li'):
                        value_div = li.find('div', class_='value') # 查找 value 块
                        if value_div:
                            value = value_div.get_text(strip=True)
                            if value: # 只添加非空的值
                                author_parts.append(value)
                                logger.debug(f"提取到内容作为作者信息: {value}")


                # 将所有收集到的作者相关内容合并成一个字符串
                combined_author = ", ".join(author_parts) if author_parts else ''
                if combined_author:
                    logger.debug(f"合并后的作者信息: {combined_author}")
                else:
                    logger.debug("在 credits 块内未找到任何内容")

                logger.info("详情页解析完成")
                return {'description': description, 'author': combined_author} # 返回描述和合并后的作者信息

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

    def _process_single_design(self, design: Dict) -> Optional[Dict]:
        """处理单个设计作品：获取详情页数据和下载图片"""
        try:
            # 获取详情页数据 (描述和作者)
            details = self.get_design_details(design.get('detail_url'))
            if details:
                 if 'description' in details:
                     design['description'] = details['description'] # 更新描述
                     logger.debug(f"更新作品 {design.get('title','未知标题')} 描述")
                 # 从详情页获取作者信息并更新
                 if 'author' in details and details['author']:
                     design['author'] = details['author'] # 更新作者信息
                     logger.debug(f"更新作品 {design.get('title','未知标题')} 作者为: {design['author']}")
                 else:
                      logger.debug(f"作品 {design.get('title','未知标题')} 详情页未提取到作者信息")


            # 下载图片并保存到文件
            image_url = design.get('image_url')
            logger.info(f"尝试下载图片: {image_url} 为作品: {design.get('title','未知标题')}")
            image_path = self.download_image(image_url, self.images_dir)
            design['image_path'] = image_path
            if image_path:
                 logger.debug(f"下载并保存作品 {design.get('title','未知标题')} 图片到: {image_path}")
            else:
                 logger.warning(f"未能下载或保存作品 {design.get('title','未知标题')} 图片")

            return design # 返回处理后的设计作品字典

        except Exception as e:
            logger.error(f"处理单个设计作品失败: {design.get('title','未知标题')} - {str(e)}", exc_info=True)
            return None # 处理失败返回 None


    def search_designs(self, keyword: str = "", category_filter: str = "", category_name: str = "") -> List[Dict]:
        """搜索设计作品，逐页处理并生成临时PDF"""
        all_designs = [] # 新增一个列表用于存储所有作品数据
        page = 1
        max_retries = config.MAX_RETRIES
        retry_delay = config.RETRY_DELAY # 秒 # 确保延时为1秒

        temp_pdf_paths = [] # 初始化临时PDF文件路径列表

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
                        response = requests.Session().send(prepared_request, timeout=config.REQUEST_TIMEOUT) # 使用Session发送预处理的请求
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
                    for doc in data['result']['docs']:
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
                            if not title or not image_url or not detail_url_suffix:
                                logger.warning(f"跳过无效数据 (缺少标题、图片URL或详情页URL后缀): {json.dumps(doc, ensure_ascii=False)}")
                                continue

                            # 构建完整的详情页URL
                            detail_url = f"{self.site_base_url}{detail_url_suffix}"
                            logger.debug(f"构建的详情页完整URL: {detail_url}")

                            # 检查作品URL，如果已见过则跳过，否则添加到列表和seen_design_ids
                            design_url = doc.get('url') # 使用url字段进行去重
                            if design_url:
                                if design_url in self.seen_design_ids:
                                    logger.info(f"作品URL {design_url} 已见过，跳过: {title}")
                                    continue # 跳过已见过的作品
                                else:
                                    self.seen_design_ids.add(design_url)
                                    design = {
                                        'title': title,
                                        'description': '', # 描述先留空，后面抓取详情页
                                        'type': category,
                                        'image_url': image_url,
                                        'author': author, # 作者先用API返回的，后面详情页更新
                                        'date': year,
                                        'detail_url': detail_url # 保留详情页URL，可能有用
                                    }
                                    page_designs.append(design)
                                    logger.info(f"解析到设计作品: {design['title']} (URL: {design_url})")
                            else:
                                logger.warning(f"作品缺少URL字段，无法去重: {title}")
                                # 如果没有URL，暂时还是添加到列表，但无法保证去重
                                design = {
                                    'title': title,
                                    'description': '', # 描述先留空，后面抓取详情页
                                    'type': category,
                                    'image_url': image_url,
                                    'author': author, # 作者先用API返回的，后面详情页更新
                                    'date': year,
                                    'detail_url': detail_url # 保留详情页URL，可能有用
                                }
                                page_designs.append(design)
                                logger.info(f"解析到设计作品 (无URL): {design.get('title', '未知标题')}")

                        except Exception as e:
                            logger.error(f"处理单个设计作品时出错: {str(e)}", exc_info=True)
                            continue

                if not page_designs:
                    logger.info(f"第 {page} 页去重后没有作品，停止获取") # 修改日志信息
                    break

                logger.info(f"成功获取并处理第 {page} 页的 {len(page_designs)} 个设计作品（去重后），开始并行处理详情和图片下载...") # 修改日志信息

                # 使用线程池并行处理每个作品的详情抓取和图片下载
                processed_page_designs = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=config.NUM_THREADS) as executor:
                    # 提交任务到线程池
                    future_to_design = {executor.submit(self._process_single_design, design): design for design in page_designs}

                    # 收集结果
                    for future in concurrent.futures.as_completed(future_to_design):
                        original_design = future_to_design[future]
                        try:
                            processed_design = future.result()
                            if processed_design:
                                processed_page_designs.append(processed_design)
                                logger.debug(f"作品 {processed_design.get('title', '未知标题')} 并行处理完成")
                            else:
                                logger.warning(f"作品 {original_design.get('title', '未知标题')} 并行处理失败")
                        except Exception as e:
                            logger.error(f"作品 {original_design.get('title', '未知标题')} 并行处理过程中发生异常: {str(e)}", exc_info=True)

                logger.info(f"第 {page} 页并行处理完成，成功处理 {len(processed_page_designs)} 个作品。") # Added log


                # 将当前页处理后的作品添加到总列表
                all_designs.extend(processed_page_designs)

                # 在每一页数据获取和处理完成后保存CSV
                logger.info(f"开始保存 {category_name} 分类的 CSV 文件 (当前已采集 {len(all_designs)} 条)... ")
                # 注意：这里需要确保save_designs_to_csv支持追加模式，或者每次都重写
                self.save_designs_to_csv(processed_page_designs, self.output_dir, category_name)

                # 将当前页处理后的作品生成临时PDF
                logger.info(f"准备为第 {page} 页生成临时PDF...")
                # create_temp_page_pdf 方法需要在 PdfGenerator 中实现，接收当前页的设计列表和页码
                temp_pdf_path = self.pdf_generator.create_temp_page_pdf(processed_page_designs, page)
                if temp_pdf_path:
                    temp_pdf_paths.append(temp_pdf_path)
                    logger.info(f"生成第 {page} 页临时PDF: {temp_pdf_path}")
                else:
                    logger.warning(f"生成第 {page} 页临时PDF失败")

                page += 1 # 页数增加

            except Exception as e:
                logger.error(f"处理第 {page} 页数据时发生异常: {str(e)}", exc_info=True)
                break

        logger.info(f"数据获取完成，总共获取到 {len(all_designs)} 个作品。")
        # 返回所有采集到的作品数据和临时PDF文件路径列表
        return all_designs, temp_pdf_paths

    def download_image(self, image_url: str, output_dir: str) -> Optional[str]:
        """下载图片并保存到指定目录，根据 Content-Type 确定文件后缀，增加重试机制"""
        max_retries = config.MAX_RETRIES
        retry_delay = config.RETRY_DELAY # 秒

        if not image_url:
            logger.warning("图片URL为空，跳过下载")
            return None

        for retry_num in range(max_retries):
            try:
                logger.info(f"开始下载图片 (尝试 {retry_num + 1}/{max_retries}): {image_url}")
                
                response = requests.get(image_url, timeout=config.REQUEST_TIMEOUT)
                response.raise_for_status()
                
                # 根据 Content-Type 确定文件后缀
                content_type = response.headers.get('Content-Type', '')
                if not content_type or 'image' not in content_type:
                    logger.warning(f"URL {image_url} 返回的不是图片类型 ({content_type})，跳过保存")
                    return None

                # 使用 mimetypes 获取标准的文件扩展名
                extension = mimetypes.guess_extension(content_type)
                if not extension:
                    # 如果 mimetypes 无法猜测，尝试从 content_type 中直接获取子类型作为扩展名
                    extension = '.' + content_type.split('/')[-1] if '/' in content_type else '.jpg' # 默认为 .jpg
                    logger.warning(f"无法通过 mimetypes 确定扩展名，使用 Content-Type 的子类型: {extension}")

                # 生成文件名，可以使用 URL 的哈希值或者结合部分 URL 和扩展名
                # 使用 URL 的哈希值可以避免文件名过长或包含特殊字符
                url_hash = hashlib.md5(image_url.encode('utf-8')).hexdigest()
                image_filename = f"{url_hash}{extension}"

                image_path = os.path.join(output_dir, image_filename)

                # 如果文件已存在且大小一致，跳过下载 (可选优化)
                # if os.path.exists(image_path) and os.path.getsize(image_path) == len(response.content):
                #     logger.info(f"图片已存在且一致，跳过下载: {image_path}")
                #     return image_path

                # 保存图片到文件
                with open(image_path, 'wb') as f:
                    f.write(response.content)
                
                logger.info("图片下载成功")
                return image_path

            except requests.exceptions.RequestException as e:
                logger.warning(f"下载图片失败 (尝试 {retry_num + 1}/{max_retries}): {str(e)}")
                if retry_num < max_retries - 1:
                    logger.info(f"等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"下载图片在 {max_retries} 次尝试后仍然失败: {image_url}")
                    return None

            except Exception as e:
                 logger.error(f"保存图片文件时出错: {str(e)}", exc_info=True)
                 return None

        return None

    def save_designs_to_csv(self, designs: List[Dict], output_dir: str, category_name: str):
        """将采集到的设计作品数据保存为 CSV 文件，支持追加数据"""
        if not designs:
            logger.warning(f"没有 {category_name} 分类的作品数据可保存为 CSV")
            return
            
        csv_filename = f"reddot_designs_{category_name}.csv"
        csv_filepath = os.path.join(output_dir, csv_filename)
        
        # 确定 CSV 文件的字段名
        fieldnames = list(designs[0].keys())
        core_fields = ['title', 'description', 'type', 'image_url', 'image_path', 'author', 'date', 'detail_url']
        for field in core_fields:
            if field not in fieldnames:
                 fieldnames.append(field)

        # 检查文件是否存在，如果存在则以追加模式打开，否则以写入模式打开并写入表头
        file_exists = os.path.exists(csv_filepath)
        mode = 'a' if file_exists else 'w'

        try:
            with open(csv_filepath, mode, newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                if not file_exists:  
                    writer.writeheader() # 如果文件不存在，写入表头

                writer.writerows(designs) # 写入数据行
            logger.info(f"数据已保存到 CSV 文件: {csv_filepath}")
        except Exception as e:
             logger.error(f"保存 CSV 文件失败: {str(e)}", exc_info=True)

    def generate_designs_pdf(self, designs: List[Dict], output_filename: str, output_dir: str):
        """使用 PdfGenerator 生成包含作品数据的 PDF 文件"""
        if not designs:
            logger.warning(f"没有作品数据可生成 PDF")
            return
            
        total_designs_count = len(designs)
        logger.info(f"开始生成包含 {total_designs_count} 个作品的 PDF")

        # 调用 PdfGenerator 的方法来生成 PDF
        try:
            # 假设 PdfGenerator 有一个 generate_full_pdf 方法来处理完整的作品列表
            # 这个方法需要在 PdfGenerator 类中实现
            final_pdf_path = self.pdf_generator.generate_full_pdf(designs, output_filename)
            if final_pdf_path:
                logger.info(f"最终 PDF 文件已生成: {final_pdf_path}")
            else:
                logger.warning("生成最终 PDF 文件失败")
        except AttributeError:
             logger.error("PdfGenerator 类缺少 generate_full_pdf 方法，无法生成 PDF")
        except Exception as e:
             logger.error(f"生成 PDF 时发生异常: {str(e)}", exc_info=True)

def main():
    # 从配置中读取分类
    categories = config.CATEGORIES

    for category_name, category_filter in categories.items():
        logger.info(f"\n--- 开始采集分类: {category_name} (过滤参数: {category_filter}) ---")

        category_output_dir = os.path.join(config.OUTPUT_DIR, category_name)
        if not os.path.exists(category_output_dir):
             os.makedirs(category_output_dir)
             logger.info(f"创建分类输出目录: {category_output_dir}")

        # 为当前分类创建一个新的爬虫实例
        crawler = RedDotCrawler(
            base_url=config.BASE_URL,
            output_dir=category_output_dir,
            site_base_url=config.SITE_BASE_URL
        )

        # 搜索设计作品，采集所有数据，并生成临时PDF
        all_designs, temp_pdf_paths = crawler.search_designs(keyword="", category_filter=category_filter, category_name=category_name)

        if all_designs:
            # 获取总作品数量
            total_designs_count = len(all_designs)
            logger.info(f"总共获取到 {total_designs_count} 个设计作品")

            # 生成 PDF 文件，调用新封装的方法
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"reddot_designs_{category_name}_{timestamp}.pdf"
            logger.info(f"开始生成 {category_name} 分类的 PDF 文件: {output_filename}...")
            crawler.generate_designs_pdf(all_designs, output_filename, category_output_dir)
            logger.info(f"PDF 文件生成完成。")

        else:
            logger.warning(f"未找到 {category_name} 分类的设计作品")

        logger.info(f"--- 完成采集分类: {category_name} ---\n")

    logger.info("所有分类采集任务完成")

if __name__ == "__main__":
    main()
    