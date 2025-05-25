import os
import sys
from PIL import Image, ImageDraw, ImageFont
import pdf2image
from natsort import natsorted
import subprocess

# --- 配置常量 ---
DPI = 300
A4_MM = (210, 297)

def mm_to_px(mm, dpi):
    return int((mm / 25.4) * dpi)

A4_WIDTH_PX = mm_to_px(A4_MM[0], DPI)
A4_HEIGHT_PX = mm_to_px(A4_MM[1], DPI)

# --- 字体设置 ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FONT_FILENAME = "SourceHanSerifCN.otf" 
FONT_PATH = os.path.join(SCRIPT_DIR, DEFAULT_FONT_FILENAME)

if not os.path.exists(FONT_PATH):
    print(f"错误：字体文件未在指定路径找到: {FONT_PATH}")
    print("请将一个包含中文字符的 .ttf 或 .otf 字体文件放到脚本目录下。")
    FONT_LOADED_SUCCESSFULLY = False
else:
    FONT_LOADED_SUCCESSFULLY = True
    print(f"将使用字体: {FONT_PATH}")

# 图像处理函数
def place_image_on_a4_canvas(page_image_pil):
    a4_canvas = Image.new('RGB', (A4_WIDTH_PX, A4_HEIGHT_PX), 'white')
    img_w, img_h = page_image_pil.size

    if img_w <= 0 or img_h <= 0:
        return a4_canvas

    ratio_w = A4_WIDTH_PX / img_w
    ratio_h = A4_HEIGHT_PX / img_h
    scale_ratio = min(ratio_w, ratio_h)

    if scale_ratio > 1.0:
        scale_ratio = 1.0

    new_w = int(img_w * scale_ratio)
    new_h = int(img_h * scale_ratio)

    if new_w <=0 : new_w = 1
    if new_h <=0 : new_h = 1
        
    resized_page_image = page_image_pil.resize((new_w, new_h), Image.Resampling.LANCZOS)

    paste_x = (A4_WIDTH_PX - new_w) // 2
    paste_y = (A4_HEIGHT_PX - new_h) // 2
    a4_canvas.paste(resized_page_image, (paste_x, paste_y))
    return a4_canvas

def add_text_to_image(image_pil, text_info_list):
    draw = ImageDraw.Draw(image_pil)
    for text, x, y, font_size, color in text_info_list:
        try:
            if FONT_LOADED_SUCCESSFULLY:
                font = ImageFont.truetype(FONT_PATH, font_size)
                draw.text((x, y), text, font=font, fill=color)
            else:
                draw.text((x, y), text, fill=color)
        except Exception as e:
            print(f"错误：添加文本 '{text}' 到图片时出错: {e}")
            try:
                draw.text((x, y), text, fill=color)
            except:
                pass
    return image_pil

# --- 主合并函数 ---
def merge_pdfs_via_images(output_filename="merged_output_as_images.pdf", poppler_path='bin', input_dir='pdfs'):
    if poppler_path:
        poppler_bin_path = os.path.join(poppler_path, 'pdfinfo')
        if not os.path.exists(poppler_bin_path) and not os.path.exists(f"{poppler_bin_path}.exe"):
            print(f"错误：Poppler的bin目录未正确配置。未找到 '{poppler_bin_path}'。")
            print("请确保Poppler已安装，并设置正确的 'poppler_path'。")
            sys.exit(1)
        else:
            try:
                subprocess.run([poppler_bin_path, "-v"], capture_output=True, check=True)
                print(f"Poppler工具链在 '{poppler_path}' 路径下可用。")
            except Exception as e:
                print(f"警告：Poppler工具链在 '{poppler_path}' 路径下可能存在问题。错误: {e}")
    else:
        print("警告：未指定Poppler路径，将依赖系统PATH。")

    # 检查输入目录是否存在
    if not os.path.isdir(input_dir):
        print(f"错误：输入目录 '{input_dir}' 不存在。请创建该目录并将PDF文件放入其中。")
        sys.exit(1)

    # 从指定目录读取PDF文件
    pdf_files_in_dir = []
    for f in os.listdir(input_dir):
        full_path = os.path.join(input_dir, f)
        if f.lower().endswith('.pdf') and os.path.isfile(full_path) and f.lower() != output_filename.lower():
            pdf_files_in_dir.append(full_path)

    pdf_files_in_dir = natsorted(pdf_files_in_dir)

    if not pdf_files_in_dir:
        print(f"在目录 '{input_dir}' 中没有找到任何 PDF 文件。")
        sys.exit(1)

    print(f"找到以下 PDF 文件：")
    for i, fname in enumerate(pdf_files_in_dir):
        print(f"  {i+1}. {os.path.basename(fname)}") # 显示文件名而不是完整路径
    print("-" * 30)

    all_final_a4_images = []
    toc_entries_metadata = []

    # --- 阶段 1: 预处理，获取每个PDF的页数信息 ---
    print("阶段 1: 正在扫描PDF文件获取页数信息...")
    for pdf_path in pdf_files_in_dir:
        pdf_name = os.path.basename(pdf_path)
        try:
            pdf_info = pdf2image.pdfinfo_from_path(pdf_path, poppler_path=poppler_path)
            page_count = int(pdf_info['Pages'])
            toc_entries_metadata.append({'name': pdf_name, 'page_count': page_count, 'path': pdf_path})
        except KeyError:
            print(f"警告：无法从 '{pdf_name}' 获取页数信息。将跳过此文件。")
        except Exception as e:
            print(f"警告：无法获取 '{pdf_name}' 的页数信息，将跳过此文件。错误: {e}")
    
    if not toc_entries_metadata:
        print("没有可处理的PDF文件信息。")
        sys.exit(1)

    # --- 阶段 2: 生成目录图片 ---
    print("\n阶段 2: 正在生成目录图片...")
    toc_images = []
    if toc_entries_metadata:
        TOC_TEXT_COLOR = (0, 0, 0)
        TOC_TITLE_FONT_SIZE = int(A4_HEIGHT_PX / 35)
        TOC_ENTRY_FONT_SIZE = int(A4_HEIGHT_PX / 50)
        TOC_PAGE_NUM_FONT_SIZE = int(A4_HEIGHT_PX / 65)

        toc_lines = []
        toc_lines.append(("文档目录", 'center', A4_HEIGHT_PX * 0.05, TOC_TITLE_FONT_SIZE, True))

        temp_content_page_idx = 1
        for entry_meta in toc_entries_metadata:
            entry_meta['start_page_placeholder'] = temp_content_page_idx
            temp_content_page_idx += entry_meta['page_count']
            entry_meta['end_page_placeholder'] = temp_content_page_idx -1

        lines_per_toc_page_estimate = (A4_HEIGHT_PX * 0.8) // (TOC_ENTRY_FONT_SIZE * 1.5)
        if lines_per_toc_page_estimate < 1 : lines_per_toc_page_estimate = 1
        
        num_toc_pages_estimated = 1 + (len(toc_entries_metadata) // lines_per_toc_page_estimate)
        if len(toc_entries_metadata) % lines_per_toc_page_estimate == 0 and len(toc_entries_metadata) > 0 :
             num_toc_pages_estimated = (len(toc_entries_metadata) // lines_per_toc_page_estimate)

        for entry_meta in toc_entries_metadata:
            entry_meta['start_page'] = entry_meta['start_page_placeholder'] + num_toc_pages_estimated
            entry_meta['end_page'] = entry_meta['end_page_placeholder'] + num_toc_pages_estimated
            clean_name = os.path.splitext(entry_meta['name'])[0]
            toc_lines.append((clean_name, entry_meta['start_page'], entry_meta['end_page'], TOC_ENTRY_FONT_SIZE))

        current_toc_page_image = Image.new('RGB', (A4_WIDTH_PX, A4_HEIGHT_PX), 'white')
        draw = ImageDraw.Draw(current_toc_page_image)
        y_cursor = 0
        
        first_toc_page = True
        toc_page_counter = 1

        for i, item in enumerate(toc_lines):
            if isinstance(item[0], str) and len(item) > 4 and item[4] == True: # 标题行
                text, x_align, y_offset, font_size, is_title = item
                try:
                    font = ImageFont.truetype(FONT_PATH, font_size) if FONT_LOADED_SUCCESSFULLY else ImageFont.load_default()
                except IOError:
                    font = ImageFont.load_default()

                text_bbox = draw.textbbox((0,0), text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                x_pos = (A4_WIDTH_PX - text_width) / 2
                y_cursor = y_offset 
                draw.text((x_pos, y_cursor), text, font=font, fill=TOC_TEXT_COLOR)
                y_cursor += (text_bbox[3] - text_bbox[1]) * 2
            else: # 普通条目
                filename, start_page, end_page, font_size = item
                if first_toc_page and y_cursor == 0:
                    y_cursor = A4_HEIGHT_PX * 0.05 + TOC_TITLE_FONT_SIZE * 3
                elif y_cursor == 0:
                    y_cursor = A4_HEIGHT_PX * 0.05

                try:
                    font = ImageFont.truetype(FONT_PATH, font_size) if FONT_LOADED_SUCCESSFULLY else ImageFont.load_default()
                except IOError:
                    font = ImageFont.load_default()

                # 文件名居左
                filename_x = A4_WIDTH_PX * 0.1
                draw.text((filename_x, y_cursor), filename, font=font, fill=TOC_TEXT_COLOR)

                # 页码居右
                page_num_text = f"第 {int(start_page)} - {int(end_page)} 页"
                page_num_font = ImageFont.truetype(FONT_PATH, font_size) if FONT_LOADED_SUCCESSFULLY else ImageFont.load_default()
                page_num_bbox = draw.textbbox((0,0), page_num_text, font=page_num_font)
                page_num_width = page_num_bbox[2] - page_num_bbox[0]
                page_num_x = A4_WIDTH_PX - page_num_width - (A4_WIDTH_PX * 0.1)
                draw.text((page_num_x, y_cursor), page_num_text, font=page_num_font, fill=TOC_TEXT_COLOR)

                text_bbox = draw.textbbox((0,0), filename, font=font)
                text_height = text_bbox[3] - text_bbox[1]

                if y_cursor + text_height > A4_HEIGHT_PX * 0.9:
                    page_num_text_toc = f"第 {toc_page_counter} 页"
                    add_text_to_image(current_toc_page_image, [(page_num_text_toc, A4_WIDTH_PX - mm_to_px(30,DPI), A4_HEIGHT_PX - mm_to_px(15,DPI), TOC_PAGE_NUM_FONT_SIZE, TOC_TEXT_COLOR)])
                    toc_images.append(current_toc_page_image)
                    toc_page_counter += 1
                    
                    current_toc_page_image = Image.new('RGB', (A4_WIDTH_PX, A4_HEIGHT_PX), 'white')
                    draw = ImageDraw.Draw(current_toc_page_image)
                    y_cursor = A4_HEIGHT_PX * 0.05
                
                y_cursor += text_height * 1.5
            first_toc_page = False
        
        if current_toc_page_image:
            page_num_text_toc = f"第 {toc_page_counter} 页"
            add_text_to_image(current_toc_page_image, [(page_num_text_toc, A4_WIDTH_PX - mm_to_px(30,DPI), A4_HEIGHT_PX - mm_to_px(15,DPI), TOC_PAGE_NUM_FONT_SIZE, TOC_TEXT_COLOR)])
            toc_images.append(current_toc_page_image)

        all_final_a4_images.extend(toc_images)
        print(f"目录图片生成完毕，共 {len(toc_images)} 页。")

    # --- 阶段 3: 处理内容PDF页面 ---
    print("\n阶段 3: 正在转换内容PDF页面并添加文本...")
    actual_content_page_start_num = len(toc_images) + 1
    
    current_overall_page_num = actual_content_page_start_num

    for entry_meta in toc_entries_metadata:
        pdf_path = entry_meta['path']
        pdf_name = os.path.basename(pdf_path) # 这里使用 basename 来获取文件名，避免路径问题
        print(f"  处理文件: {pdf_name} ...")
        try:
            page_images_from_pdf = pdf2image.convert_from_path(pdf_path, dpi=DPI, poppler_path=poppler_path)

            for i, page_image_pil in enumerate(page_images_from_pdf):
                a4_processed_image = place_image_on_a4_canvas(page_image_pil)

                page_num_text = f"第 {current_overall_page_num} 页"
                filename_text = os.path.splitext(pdf_name)[0]
                
                text_color = (50, 50, 50)
                FOOTER_FONT_SIZE = int(A4_HEIGHT_PX / 70)

                pos_x_page_num = A4_WIDTH_PX - mm_to_px(30, DPI)
                pos_y_page_num = A4_HEIGHT_PX - mm_to_px(15, DPI)
                pos_x_filename = mm_to_px(15, DPI)
                pos_y_filename = A4_HEIGHT_PX - mm_to_px(15, DPI)

                texts_to_add = [
                    (page_num_text, pos_x_page_num, pos_y_page_num, FOOTER_FONT_SIZE, text_color),
                    (filename_text, pos_x_filename, pos_y_filename, FOOTER_FONT_SIZE, text_color)
                ]
                a4_processed_image_with_text = add_text_to_image(a4_processed_image, texts_to_add)
                
                all_final_a4_images.append(a4_processed_image_with_text)
                current_overall_page_num += 1
                
                page_image_pil.close()
            
            del page_images_from_pdf

        except pdf2image.exceptions.PDFPageCountError:
            print(f"错误：无法从 '{pdf_name}' 获取页面。")
        except Exception as e:
            print(f"错误：处理PDF文件 '{pdf_name}' 时发生错误: {e}")

    # --- 阶段 4: 保存所有处理好的图片到一个PDF文件 ---
    print("\n阶段 4: 正在合并所有图片到最终PDF...")
    if not all_final_a4_images:
        print("没有生成任何图片页面。")
        sys.exit(1)

    try:
        first_image = all_final_a4_images[0]
        other_images = all_final_a4_images[1:]

        if first_image.mode == 'RGBA':
            first_image = first_image.convert('RGB')
        
        converted_other_images = []
        for img in other_images:
            if img.mode == 'RGBA':
                converted_other_images.append(img.convert('RGB'))
            else:
                converted_other_images.append(img)

        first_image.save(
            output_filename,
            save_all=True,
            append_images=converted_other_images,
            resolution=DPI,
            compress_level=9
        )
        print(f"\nPDF 合并完成！输出文件: '{output_filename}'")
        print(f"总页数: {len(all_final_a4_images)}")

    except Exception as e:
        print(f"错误：保存最终PDF时发生错误: {e}")
    finally:
        for img in all_final_a4_images:
            try:
                img.close()
            except:
                pass
        del all_final_a4_images


if __name__ == '__main__':
    # --- Poppler路径配置 ---
    poppler_path_manual = r'bin'
    # poppler_path_manual = None 

    # 指定PDF文件所在的目录
    input_pdf_directory = 'pdfs'

    if len(sys.argv) > 1:
        output_file_name = sys.argv[1]
        if not output_file_name.lower().endswith(".pdf"):
            output_file_name += ".pdf"
    else:
        output_file_name = "merged_output_image.pdf"
    
    merge_pdfs_via_images(output_file_name, poppler_path=poppler_path_manual, input_dir=input_pdf_directory)