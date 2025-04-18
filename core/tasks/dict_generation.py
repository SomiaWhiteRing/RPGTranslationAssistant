# core/tasks/dict_generation.py
import os
import json
import csv
import io # 用于将字符串模拟成文件给 csv reader
import logging
# 确认导入的是我们更新后的 Gemini 客户端
from core.api_clients import gemini
from core.utils import file_system, text_processing
# 导入默认配置以获取默认文件名和 Prompt
from core.config import DEFAULT_WORLD_DICT_CONFIG

log = logging.getLogger(__name__)

# --- CSV 解析辅助函数 (保持不变) ---
def _parse_csv_response(csv_response_text, expected_columns, message_queue):
    """
    解析 Gemini 返回的 CSV 文本。

    Args:
        csv_response_text (str): Gemini 返回的原始文本。
        expected_columns (int): 期望的列数。
        message_queue (queue.Queue): 用于发送日志消息的队列。

    Returns:
        list[list[str]]: 解析后的数据列表，每个子列表是一行。
                         如果解析失败或无有效数据，返回空列表。
    """
    parsed_data = []
    if not csv_response_text:
        log.warning("Gemini API 未返回任何内容。")
        message_queue.put(("log", ("warning", "Gemini API 未返回任何内容。")))
        return parsed_data

    try:
        # 移除响应前后可能存在的空白或```csv标记
        clean_csv_response = csv_response_text.strip().strip('```csv').strip('```').strip()
        if not clean_csv_response:
            log.warning("清理后的 Gemini CSV 响应为空。")
            message_queue.put(("log", ("warning", "Gemini API 返回的 CSV 内容为空或仅包含标记。")))
            return parsed_data

        csv_file = io.StringIO(clean_csv_response)
        # 严格按照 Prompt 要求解析：双引号包围，逗号分隔
        reader = csv.reader(csv_file, quotechar='"', delimiter=',',
                            quoting=csv.QUOTE_ALL, skipinitialspace=True)

        for i, row in enumerate(reader):
            if not row: continue # 跳过空行
            # 检查列数是否完全匹配
            if len(row) == expected_columns:
                # 移除每个字段可能存在的首尾多余空格 (有些模型可能会添加)
                cleaned_row = [field.strip() for field in row]
                parsed_data.append(cleaned_row)
            else:
                log.warning(f"跳过格式错误的 CSV 行 #{i+1} (期望{expected_columns}列，得到{len(row)}列): {row}")
                message_queue.put(("log", ("warning", f"跳过格式错误的 CSV 行 #{i+1} (列数不符): {row}")))

    except csv.Error as csv_err:
        log.error(f"解析 Gemini 返回的 CSV 数据时发生 CSV 错误: {csv_err}")
        log.error(f"原始 CSV 响应内容 (前500字符):\n{csv_response_text[:500]}")
        message_queue.put(("error", f"解析 Gemini 返回的 CSV 数据失败 (CSV格式问题): {csv_err}"))
    except Exception as parse_err:
        log.exception(f"解析 Gemini 返回的 CSV 数据时发生意外错误: {parse_err}")
        log.error(f"原始 CSV 响应内容 (前500字符):\n{csv_response_text[:500]}")
        message_queue.put(("error", f"解析 Gemini 返回的 CSV 数据失败: {parse_err}"))

    return parsed_data

# --- 主任务函数 ---
def run_generate_dictionary(game_path, works_dir, world_dict_config, message_queue):
    """
    使用 Gemini API 从提取的文本生成人物词典和事物词典 (CSV 文件)。

    Args:
        game_path (str): 游戏根目录路径。
        works_dir (str): Works 工作目录的根路径。
        world_dict_config (dict): 包含 Gemini API Key、模型、两个Prompt模板和词典文件名的配置字典。
        message_queue (queue.Queue): 用于向主线程发送消息的队列。
    """
    character_dict_success = False
    entity_dict_success = False
    character_entries_count = 0
    entity_entries_count = 0
    temp_text_path = None

    try:
        message_queue.put(("status", "正在准备生成字典..."))
        message_queue.put(("log", ("normal", "步骤 4: 开始生成世界观字典 (使用 Gemini API)...")))

        # --- 获取配置 ---
        # API Key 和模型从 world_dict_config 获取
        api_key = world_dict_config.get("api_key", "").strip()
        model_name = world_dict_config.get("model", DEFAULT_WORLD_DICT_CONFIG["model"]).strip() # 使用字典生成的默认模型
        char_prompt_template = world_dict_config.get("character_prompt_template", DEFAULT_WORLD_DICT_CONFIG["character_prompt_template"])
        entity_prompt_template = world_dict_config.get("entity_prompt_template", DEFAULT_WORLD_DICT_CONFIG["entity_prompt_template"])
        char_dict_filename = world_dict_config.get("character_dict_filename", DEFAULT_WORLD_DICT_CONFIG["character_dict_filename"])
        entity_dict_filename = world_dict_config.get("entity_dict_filename", DEFAULT_WORLD_DICT_CONFIG["entity_dict_filename"])

        # --- 检查配置 ---
        if not api_key: raise ValueError("Gemini API Key 未配置。")
        if not model_name: raise ValueError("Gemini 字典生成模型名称未配置。")
        if not char_prompt_template: raise ValueError("人物提取 Prompt 模板未配置。")
        if not entity_prompt_template: raise ValueError("事物提取 Prompt 模板未配置。")
        if not char_dict_filename: raise ValueError("人物词典文件名未配置。")
        if not entity_dict_filename: raise ValueError("事物词典文件名未配置。")
        log.info(f"使用模型 '{model_name}' 生成字典。")

        # --- 确定文件路径 ---
        # (保持不变)
        game_folder_name = text_processing.sanitize_filename(os.path.basename(game_path))
        if not game_folder_name: game_folder_name = "UntitledGame"
        work_game_dir = os.path.join(works_dir, game_folder_name)
        untranslated_dir = os.path.join(work_game_dir, "untranslated")
        json_path = os.path.join(untranslated_dir, "translation.json")
        character_dict_path = os.path.join(work_game_dir, char_dict_filename)
        entity_dict_path = os.path.join(work_game_dir, entity_dict_filename)
        temp_text_path = os.path.join(work_game_dir, "_temp_world_text.txt")

        if not os.path.exists(json_path):
            raise FileNotFoundError(f"未找到未翻译的 JSON 文件: {json_path}")

        # --- 加载 JSON 并准备输入文本 ---
        # (保持不变)
        message_queue.put(("log", ("normal", "加载 JSON 文件并提取原文...")))
        try:
            with open(json_path, 'r', encoding='utf-8') as f: translations = json.load(f)
            original_texts = list(translations.keys())
            message_queue.put(("log", ("normal", f"共提取 {len(original_texts)} 条原文用于分析。")))
            if not original_texts:
                 message_queue.put(("warning", "JSON 文件中没有可用于分析的原文。")); message_queue.put(("status", "生成字典跳过(无文本)")); message_queue.put(("done", None)); return

            message_queue.put(("log", ("normal", "将原文聚合到临时文件...")))
            with open(temp_text_path, 'w', encoding='utf-8') as f_temp: f_temp.write("\n".join(original_texts))
            log.info(f"临时原文聚合文件已创建: {temp_text_path}")

            with open(temp_text_path, 'r', encoding='utf-8') as f_temp_read: game_text_content = f_temp_read.read()

            MAX_TEXT_SIZE_MB = 50 # 增大检查阈值，因为 Gemini Pro/Flash 上下文更大
            text_size_mb = len(game_text_content.encode('utf-8')) / (1024*1024)
            if text_size_mb > MAX_TEXT_SIZE_MB:
                 log.warning(f"聚合后的游戏文本大小 ({text_size_mb:.2f} MB) 较大，API 调用可能耗时较长或失败。")
                 message_queue.put(("log",("warning", f"游戏文本内容较多 ({text_size_mb:.2f} MB)，API处理可能需要较长时间。")))

        except Exception as e:
            log.exception(f"加载 JSON 或处理临时文件时出错: {e}")
            raise RuntimeError(f"加载 JSON 或准备输入文本失败: {e}") from e

        # --- 初始化 Gemini 客户端 ---
        # (保持不变，使用我们更新后的 gemini.py)
        try:
            client = gemini.GeminiClient(api_key)
            log.info("Gemini 客户端初始化成功。")
        except Exception as client_err:
            raise ConnectionError(f"初始化 Gemini API 客户端失败: {client_err}") from client_err

        # ==================================================
        # === 阶段一：生成人物词典 (Character Dictionary) ===
        # ==================================================
        message_queue.put(("status", "正在生成人物词典..."))
        message_queue.put(("log", ("normal", "阶段 1: 开始生成人物词典...")))
        character_data = []
        try:
            char_final_prompt = char_prompt_template.format(game_text=game_text_content)
            message_queue.put(("log", ("normal", f"调用 Gemini API '{model_name}' (人物提取)...")))

            # 调用 gemini.py 中的 generate_content
            # 字典生成通常不需要特殊的 generation_config 或 safety_settings
            success, char_csv_response, error_message = client.generate_content(
                model_name,
                char_final_prompt
                # generation_config=..., # 可以按需添加
                # safety_settings=...     # 可以按需添加
            )

            if not success:
                message_queue.put(("log", ("error", f"人物词典生成失败: Gemini API 调用失败: {error_message}")))
            else:
                message_queue.put(("log", ("success", "人物提取 API 调用成功，正在解析...")))
                # 解析 CSV (期望 8 列)
                character_data = _parse_csv_response(char_csv_response, 8, message_queue)
                character_entries_count = len(character_data)
                message_queue.put(("log", ("normal", f"解析完成，获得 {character_entries_count} 条有效人物条目。")))

                # 保存人物词典 CSV 文件
                message_queue.put(("log", ("normal", f"正在保存人物词典到: {character_dict_path}")))
                try:
                    file_system.ensure_dir_exists(os.path.dirname(character_dict_path))
                    with open(character_dict_path, 'w', newline='', encoding='utf-8-sig') as f_csv:
                        writer = csv.writer(f_csv, quoting=csv.QUOTE_ALL)
                        # 写入表头 (与 Prompt 模板对应)
                        writer.writerow(['原文', '译文', '对应原名', '性别', '年龄', '性格', '口吻', '描述'])
                        if character_data:
                            writer.writerows(character_data)
                    character_dict_success = True
                    message_queue.put(("log", ("success", f"人物词典保存成功: {character_dict_path}")))
                except Exception as write_err:
                    log.exception(f"保存人物词典 CSV 文件失败: {write_err}")
                    message_queue.put(("log", ("error", f"保存人物词典失败: {write_err}")))

        except Exception as char_err:
            log.exception(f"生成人物词典阶段发生错误: {char_err}")
            message_queue.put(("log", ("error", f"生成人物词典时出错: {char_err}")))

        # --- 准备人物词典参考内容 ---
        # (保持不变)
        character_reference_csv_content = ""
        if character_dict_success and character_entries_count > 0:
            message_queue.put(("log", ("normal", "准备人物词典参考内容...")))
            try:
                with open(character_dict_path, 'r', encoding='utf-8-sig') as f_ref:
                    reader = csv.reader(f_ref)
                    header = next(reader) # 读取并丢弃表头
                    output = io.StringIO()
                    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
                    # writer.writerow(header) # 事物 Prompt 不需要表头作为参考
                    for row in reader:
                         writer.writerow(row)
                    character_reference_csv_content = output.getvalue().strip()
                    output.close()
                log.info(f"成功准备了 {len(character_reference_csv_content.splitlines())} 行人物词典参考。")
            except Exception as ref_err:
                log.exception(f"读取人物词典参考内容时出错: {ref_err}")
                message_queue.put(("log", ("warning", f"无法读取人物词典参考: {ref_err}。")))
                character_reference_csv_content = ""
        elif not character_dict_success:
             message_queue.put(("log", ("warning", "人物词典生成失败，事物词典将不包含人物参考。")))
        else:
             message_queue.put(("log", ("normal", "人物词典为空，事物词典将不包含人物参考。")))


        # ==================================================
        # === 阶段二：生成事物词典 (Entity Dictionary) =====
        # ==================================================
        message_queue.put(("status", "正在生成事物词典..."))
        message_queue.put(("log", ("normal", "阶段 2: 开始生成事物词典...")))
        entity_data = []
        try:
            entity_final_prompt = entity_prompt_template.format(
                game_text=game_text_content,
                character_reference_csv_content=character_reference_csv_content or "无" # 如果为空，提供明确提示
            )
            message_queue.put(("log", ("normal", f"调用 Gemini API '{model_name}' (事物提取)...")))
            # 调用 generate_content
            success, entity_csv_response, error_message = client.generate_content(
                model_name,
                entity_final_prompt
            )

            if not success:
                message_queue.put(("log", ("error", f"事物词典生成失败: Gemini API 调用失败: {error_message}")))
            else:
                message_queue.put(("log", ("success", "事物提取 API 调用成功，正在解析...")))
                # 解析 CSV (期望 4 列)
                entity_data = _parse_csv_response(entity_csv_response, 4, message_queue)
                entity_entries_count = len(entity_data)
                message_queue.put(("log", ("normal", f"解析完成，获得 {entity_entries_count} 条有效事物条目。")))

                # 保存事物词典 CSV 文件
                message_queue.put(("log", ("normal", f"正在保存事物词典到: {entity_dict_path}")))
                try:
                    file_system.ensure_dir_exists(os.path.dirname(entity_dict_path))
                    with open(entity_dict_path, 'w', newline='', encoding='utf-8-sig') as f_csv:
                        writer = csv.writer(f_csv, quoting=csv.QUOTE_ALL)
                        # 写入表头 (与 Prompt 模板对应)
                        writer.writerow(['原文', '译文', '类别', '描述'])
                        if entity_data:
                            writer.writerows(entity_data)
                    entity_dict_success = True
                    message_queue.put(("log", ("success", f"事物词典保存成功: {entity_dict_path}")))
                except Exception as write_err:
                    log.exception(f"保存事物词典 CSV 文件失败: {write_err}")
                    message_queue.put(("log", ("error", f"保存事物词典失败: {write_err}")))

        except Exception as entity_err:
            log.exception(f"生成事物词典阶段发生错误: {entity_err}")
            message_queue.put(("log", ("error", f"生成事物词典时出错: {entity_err}")))

        # --- 最终总结 ---
        # (保持不变)
        if character_dict_success and entity_dict_success:
            message_queue.put(("success", f"字典生成成功: 人物({character_entries_count}条), 事物({entity_entries_count}条)。"))
            message_queue.put(("status", "生成字典完成"))
        elif character_dict_success:
            message_queue.put(("warning", f"字典生成部分成功: 人物({character_entries_count}条)成功, 事物失败。"))
            message_queue.put(("status", "生成字典部分完成 (事物失败)"))
        elif entity_dict_success:
            message_queue.put(("warning", f"字典生成部分成功: 人物失败, 事物({entity_entries_count}条)成功。"))
            message_queue.put(("status", "生成字典部分完成 (人物失败)"))
        else:
            message_queue.put(("error", "字典生成失败: 人物和事物词典均未成功生成。"))
            message_queue.put(("status", "生成字典失败"))

        message_queue.put(("done", None))

    except (ValueError, FileNotFoundError, RuntimeError, ConnectionError) as config_or_setup_err:
        log.error(f"字典生成准备失败: {config_or_setup_err}")
        message_queue.put(("error", f"字典生成准备失败: {config_or_setup_err}"))
        message_queue.put(("status", "生成字典失败"))
        message_queue.put(("done", None))
    except Exception as e:
        log.exception("生成字典任务执行期间发生意外错误。")
        message_queue.put(("error", f"生成字典过程中发生严重错误: {e}"))
        message_queue.put(("status", "生成字典失败"))
        message_queue.put(("done", None))
    finally:
        # 清理临时文件
        if temp_text_path and os.path.exists(temp_text_path):
            if file_system.safe_remove(temp_text_path):
                 log.info(f"已清理临时原文聚合文件: {temp_text_path}")
            else:
                 log.warning(f"清理临时文件失败: {temp_text_path}")