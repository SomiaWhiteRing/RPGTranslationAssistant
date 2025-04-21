# core/tasks/translate.py
import os
import json
import csv
import re
import time
import math
import datetime
import logging
import queue
import threading
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
# 导入 Gemini 客户端
from core.api_clients import gemini
from core.utils import file_system, text_processing
# 导入默认配置以获取默认文件名和列定义等
from core.config import DEFAULT_WORLD_DICT_CONFIG, DEFAULT_TRANSLATE_CONFIG

log = logging.getLogger(__name__)

# --- 辅助函数 ---

def _estimate_tokens(text):
    """粗略估算文本的 Token 数量。"""
    if not text: return 0
    return (len(text) + 1) // 2

def _build_glossary_section(dictionary, entry_format_str, header_line, keys_in_format, max_entries=500):
    """
    构建 Prompt 中的术语表部分。
    修复了格式化逻辑，直接使用字典键。

    Args:
        dictionary (list[dict]): 词典列表。
        entry_format_str (str): 单个条目的格式化字符串，例如 "{原文}|{译文}|{类别} - {描述}"。
        header_line (str): 术语表部分的标题行。
        keys_in_format (list[str]): 格式字符串中实际使用的 key 列表。
        max_entries (int): 最大条目数。

    Returns:
        str: 构建好的术语表文本。
    """
    section_text = ""
    entries = []
    if dictionary:
        count = 0
        for entry in dictionary:
            if count >= max_entries:
                 log.warning(f"术语表条目超过 {max_entries}，已截断。")
                 break
            try:
                # 使用 .get(key, '') 安全地获取值，并格式化
                format_dict = {key: str(entry.get(key, '')) for key in keys_in_format}
                # 特殊处理：如果格式字符串包含 '类别 - 描述' 这种组合，需要手动拼接
                if '{类别} - {描述}' in entry_format_str:
                     category = str(entry.get('类别', ''))
                     desc = str(entry.get('描述', ''))
                     category_desc = f"{category} - {desc}" if category and desc else category or desc
                     format_dict['类别 - 描述'] = category_desc # 添加组合字段

                formatted_entry = entry_format_str.format(**format_dict)
                entries.append(formatted_entry)
                count += 1
            except Exception as fmt_err:
                 # 更详细地记录错误和相关条目
                 log.warning(f"格式化术语表条目时出错: {fmt_err}。格式字符串: '{entry_format_str}', 条目: {entry}", exc_info=True)

        if entries:
            section_text = header_line + "\n" + "\n".join(entries) + "\n"

    return section_text

def _create_chunks_more_even(items, config):
    """
    尝试更均匀地划分块，基于预估的块数和平均行数。
    """
    chunks = []
    total_items = len(items)
    if total_items == 0:
        return chunks

    max_tokens_per_text_block = config.get("chunk_max_tokens", DEFAULT_TRANSLATE_CONFIG["chunk_max_tokens"])
    line_number_width = len(str(total_items))

    # 1. 估算总文本 Token (需要遍历一次)
    total_text_tokens = 0
    item_token_list = [] # 存储每行的 token 数，避免重复计算
    for i, (original_key, _) in enumerate(items):
        processed_key = text_processing.pre_process_text_for_llm(original_key)
        line_marker = f"[LINE_{i+1:0{line_number_width}d}]"
        line_text_for_token = f"{line_marker}{processed_key}\n"
        item_tokens = _estimate_tokens(line_text_for_token)
        item_token_list.append(item_tokens)
        total_text_tokens += item_tokens

    log.info(f"预估总文本 Tokens: {total_text_tokens}")

    if total_text_tokens == 0: # 如果所有行都是空的
         if items: return [items] # 将所有空行放一个块
         else: return []

    # 2. 计算期望的块数
    num_chunks = math.ceil(total_text_tokens / max_tokens_per_text_block)
    # 确保至少有一个块
    num_chunks = max(1, num_chunks)
    log.info(f"根据文本 Token 上限 ({max_tokens_per_text_block})，预计划分为 {num_chunks} 个块。")

    # 3. 计算平均每块 Item 数量 (向下取整，最后一个块处理剩余)
    # avg_items_per_chunk = total_items // num_chunks
    # 优化：使用更精确的划分点
    target_items_per_chunk = math.ceil(total_items / num_chunks)

    # 4. 划分块
    start_index = 0
    current_chunk_tokens = 0 # 当前块已累加的token
    current_chunk_items = []

    for i in range(total_items):
        item_tokens = item_token_list[i]
        original_key, original_value = items[i]

        # 判断是否需要结束当前块
        # 条件1：当前块已达到目标行数
        # 条件2：当前块 Token 加上新行会超过上限 (安全检查)
        # 条件3：当前行是最后一行
        force_new_chunk = False
        if len(current_chunk_items) >= target_items_per_chunk:
             force_new_chunk = True
        if current_chunk_tokens + item_tokens > max_tokens_per_text_block and len(current_chunk_items) > 0:
             log.warning(f"块 {len(chunks)+1} 在达到目标行数前 Token 超限 ({current_chunk_tokens + item_tokens} > {max_tokens_per_text_block})，强制分块。")
             force_new_chunk = True

        if force_new_chunk:
             chunks.append(current_chunk_items)
             log.debug(f"创建块 {len(chunks)}，行数 {len(current_chunk_items)}，文本 Tokens ~={current_chunk_tokens}")
             current_chunk_items = []
             current_chunk_tokens = 0

        # 添加当前行到块
        current_chunk_items.append((original_key, original_value))
        current_chunk_tokens += item_tokens

        # 如果因为Token超限导致单行成块，单独处理 (虽然理论上基于平均行数划分不易出现)
        if item_tokens > max_tokens_per_text_block and len(current_chunk_items) == 1:
             log.warning(f"单行文本过长! 行号: {i+1}, Tokens~={item_tokens}. 强制单行块。")
             chunks.append(current_chunk_items)
             log.debug(f"创建单行超长块 {len(chunks)}，文本 Tokens ~={current_chunk_tokens}")
             current_chunk_items = []
             current_chunk_tokens = 0


    # 添加最后一个块
    if current_chunk_items:
        chunks.append(current_chunk_items)
        log.debug(f"创建最后一个块 {len(chunks)}，行数 {len(current_chunk_items)}，文本 Tokens ~={current_chunk_tokens}")

    # 验证块数量是否符合预期 (可能因为单行超长等原因略有偏差)
    if len(chunks) != num_chunks:
         log.warning(f"实际块数 ({len(chunks)}) 与预计算块数 ({num_chunks}) 不符，可能是由于文本行长度分布不均导致。")
    else:
         log.info(f"成功将 {total_items} 行划分为 {len(chunks)} 个近似均衡的块。")

    return chunks

# --- 核心翻译函数 (第一轮) ---
def _translate_single_chunk(
    chunk_items, chunk_index, total_chunks, context_keys,
    character_dictionary, entity_dictionary, api_client, config,
    error_log_path, error_log_lock
):
    """翻译单个文本块 (第一轮)。修复了 Prompt 格式化和术语表构建。"""
    prompt_template = config.get("prompt_template", DEFAULT_TRANSLATE_CONFIG["prompt_template"])
    model_name = config.get("model", "")
    source_language = config.get("source_language", "日语")
    target_language = config.get("target_language", "简体中文")
    max_retries = config.get("max_retries", DEFAULT_TRANSLATE_CONFIG["max_retries"])
    generation_config = config.get("generation_config", {})
    safety_settings = config.get("safety_settings", [])

    last_error_info = {}
    num_lines = len(chunk_items)
    line_number_width = len(str(num_lines)) if num_lines > 0 else 1

    # --- 构建术语表 (使用修复后的逻辑) ---
    char_keys = ['原文', '译文', '对应原名', '性别', '年龄', '性格', '口吻', '描述']
    char_format = "|".join([f"{{{key}}}" for key in char_keys]) # "{原文}|{译文}|..."
    char_header = f"### 人物术语表 (格式: {'|'.join(char_keys)})"
    character_glossary_section = _build_glossary_section(character_dictionary, char_format, char_header, char_keys)

    entity_keys = ['原文', '译文', '类别', '描述'] # 确保 CSV 有这几列
    entity_format_combined = "{原文}|{译文}|{类别} - {描述}" # Prompt 中合并显示
    entity_header_combined = "### 事物术语表 (格式: 原文|译文|类别 - 描述)"
    # _build_glossary_section 需要知道格式字符串依赖的原始 key
    entity_keys_for_format = ['原文', '译文', '类别', '描述']
    entity_glossary_section = _build_glossary_section(entity_dictionary, entity_format_combined, entity_header_combined, entity_keys_for_format)

    # --- 构建输入块文本 ---
    input_block_lines = []
    original_keys_in_chunk = []
    for i, (original_key, _) in enumerate(chunk_items):
        original_keys_in_chunk.append(original_key)
        processed_key = text_processing.pre_process_text_for_llm(original_key)
        line_marker = f"[LINE_{i+1:0{line_number_width}d}]"
        input_block_lines.append(f"{line_marker}{processed_key}")
    input_block_text = "\n".join(input_block_lines)


    for attempt in range(max_retries + 1):
        context_section = ""
        if context_keys:
            context_section = f"### 上文内容参考 ({source_language})\n<context>\n" + "\n".join(context_keys[-config.get("context_lines", 10):]) + "\n</context>\n"

        # --- 构建最终 Prompt (确保使用正确的 key) ---
        try:
            current_final_prompt = prompt_template.format(
                source_language=source_language,
                target_language=target_language,
                character_glossary_section=character_glossary_section,
                entity_glossary_section=entity_glossary_section,
                context_section=context_section,
                input_block_text=input_block_text, # <-- 使用 input_block_text
                target_language_placeholder=target_language
            )
        except KeyError as e:
             log.error(f"格式化主 Prompt 时缺少键: {e}。请检查 config.py 中的 prompt_template。")
             # 无法格式化 Prompt，此块失败
             return None

        # c. 调用 API
        log.info(f"翻译块 {chunk_index+1}/{total_chunks} (尝试 {attempt+1}/{max_retries+1})，共 {num_lines} 行...")
        success, response_content, error_message = api_client.generate_content(
            model_name,
            current_final_prompt,
            generation_config=generation_config,
            safety_settings=safety_settings
        )

        # (后续的错误记录、解析、验证逻辑与上一个版本相同)
        last_error_info = { # 更新错误信息记录
            "attempt": attempt + 1, 
            "prompt_size": len(current_final_prompt),
            "model": model_name, 
            "api_success": success,
            "api_response_len": len(response_content) if response_content else 0,
            "api_error": error_message if not success else None, 
            "validation_reason": None,
            "api_response": response_content if response_content else "", # 记录响应体
        }

        if not success:
            log.warning(f"块 {chunk_index+1}/{total_chunks} API 调用失败 (尝试 {attempt+1}): {error_message}")
            # (记录日志...)
            try:
                with error_log_lock:
                    with open(error_log_path, 'a', encoding='utf-8') as elog:
                        elog.write(f"[{datetime.datetime.now().isoformat()}] 块翻译 API 调用失败 (块 {chunk_index+1}/{total_chunks}, 尝试 {attempt+1}/{max_retries+1})\n")
                        elog.write(f"  失败原因: {error_message}\n")
                        elog.write(f"  模型: {model_name}\n")
                        elog.write(f"  Prompt 大小: {last_error_info['prompt_size']} 字符\n")
                        elog.write(f"  API 响应长度: {last_error_info['api_response_len']} 字符\n")
                        if last_error_info.get('api_response'): elog.write(f"  API 响应: {last_error_info['api_response']}\n")
                        elog.write("-" * 20 + "\n")
            except Exception as log_err: log.error(f"写入 API 错误日志失败: {log_err}")
            if attempt < max_retries: time.sleep(1.5 ** attempt); continue
            else: log.error(f"块 {chunk_index+1}/{total_chunks} API 调用失败达到最大重试次数。"); return None

        match = re.search(r'<output_block>(.*?)</output_block>', response_content, re.DOTALL)
        if not match:
            log.warning(f"块 {chunk_index+1}/{total_chunks} API 响应未找到 <output_block> (尝试 {attempt+1})。")
            last_error_info["validation_reason"] = "响应缺少 <output_block>"
            if attempt < max_retries: continue
            else: break

        output_block_content = match.group(1).strip(); output_lines = output_block_content.split('\n')

        if len(output_lines) != num_lines:
            log.warning(f"块 {chunk_index+1}/{total_chunks} 验证失败 (尝试 {attempt+1}): 输出行数 ({len(output_lines)}) != 输入行数 ({num_lines})。")
            last_error_info["validation_reason"] = f"行数不匹配"
            if attempt < max_retries: continue
            else: break

        parsed_translations = {}; marker_validation_failed = False
        for i, line in enumerate(output_lines):
            expected_marker = f"[LINE_{i+1:0{line_number_width}d}]"
            if line.startswith(expected_marker): parsed_translations[i] = line[len(expected_marker):]
            else:
                log.warning(f"块 {chunk_index+1}/{total_chunks} 验证失败 (尝试 {attempt+1}): 行 {i+1} 标记错误。")
                last_error_info["validation_reason"] = f"行 {i+1} 标记错误"; marker_validation_failed = True; break
        if marker_validation_failed:
            if attempt < max_retries: continue
            else: break

        chunk_results = []; all_lines_valid_in_chunk = True; failed_line_reasons = []
        for i in range(num_lines):
            original_key = original_keys_in_chunk[i]; original_value = chunk_items[i][1]
            raw_translated = parsed_translations.get(i)
            if raw_translated is None:
                 log.error(f"块 {chunk_index+1}/{total_chunks} 内部错误：行 {i+1} 解析丢失。")
                 all_lines_valid_in_chunk = False; chunk_results.append((original_key, original_value, 'pending_correction')); failed_line_reasons.append(f"行 {i+1}: 解析丢失"); continue
            restored = text_processing.restore_pua_placeholders(raw_translated); post_processed = text_processing.post_process_translation(restored, original_key)
            is_valid, reason = text_processing.validate_translation(original_key, restored, post_processed)
            if is_valid: chunk_results.append((original_key, post_processed, 'success'))
            else:
                log.warning(f"块 {chunk_index+1}/{total_chunks} 行 {i+1} 验证失败 (尝试 {attempt+1}): {reason}.")
                all_lines_valid_in_chunk = False; chunk_results.append((original_key, original_value, 'pending_correction')); failed_line_reasons.append(f"行 {i+1}: {reason}")
                # (记录单行失败日志...)
                try:
                    with error_log_lock:
                        with open(error_log_path, 'a', encoding='utf-8') as elog:
                            elog.write(f"[{datetime.datetime.now().isoformat()}] 单行翻译验证失败 (块 {chunk_index+1}/{total_chunks}, 行 {i+1}, 尝试 {attempt+1}/{max_retries+1})\n")
                            elog.write(f"  原文: {original_key}\n")
                            elog.write(f"  失败原因: {reason}\n")
                            elog.write(f"  模型: {model_name}\n")
                            elog.write(f"  API响应行: {output_lines[i]}\n")
                            elog.write(f"  提取译文: {raw_translated}\n")
                            elog.write(f"  处理后译文: {post_processed}\n")
                            elog.write("-" * 20 + "\n")
                except Exception as log_err: log.error(f"写入单行验证错误日志失败: {log_err}")


        if all_lines_valid_in_chunk:
            log.info(f"块 {chunk_index+1}/{total_chunks} 翻译验证通过 (尝试 {attempt+1})。")
            return chunk_results
        else:
            last_error_info["validation_reason"] = "; ".join(failed_line_reasons)
            if attempt < max_retries:
                log.warning(f"块 {chunk_index+1}/{total_chunks} 有验证失败行 (尝试 {attempt+1})，重试...")
                time.sleep(1.0); continue
            else:
                log.error(f"块 {chunk_index+1}/{total_chunks} 达最大重试次数，仍有行验证失败。")
                return chunk_results

    # --- 重试循环结束，因为 break 跳出 ---
    log.error(f"块 {chunk_index+1}/{total_chunks} 翻译验证在所有尝试后失败。原因: {last_error_info.get('validation_reason', '未知')}")
    # (记录最终块失败日志...)
    try:
        with error_log_lock:
            with open(error_log_path, 'a', encoding='utf-8') as elog:
                elog.write(f"[{datetime.datetime.now().isoformat()}] 块翻译彻底失败 (块 {chunk_index+1}/{total_chunks}, 所有尝试)\n")
                elog.write(f"  最后尝试 ({last_error_info.get('attempt', 'N/A')}): API Success={last_error_info.get('api_success', 'N/A')}\n")
                if last_error_info.get('api_error'): elog.write(f"  API Error: {last_error_info['api_error']}\n")
                if last_error_info.get('validation_reason'): elog.write(f"  Validation Reason: {last_error_info['validation_reason']}\n")
                elog.write(f"  模型: {last_error_info.get('model', 'N/A')}\n")
                elog.write(f"  Prompt 大小: {last_error_info.get('prompt_size', 'N/A')} 字符\n")
                elog.write("-" * 20 + "\n")
    except Exception as log_err: log.error(f"写入最终块失败错误日志失败: {log_err}")

    return [(key, value, 'pending_correction') for key, value in chunk_items]


# --- 核心翻译函数 (第二轮 - 修正) ---
def _translate_single_correction_chunk(
    chunk_items, chunk_index, total_chunks, context_keys,
    character_dictionary, entity_dictionary, api_client, config,
    error_log_path, error_log_lock
):
    """翻译单个修正文本块 (第二轮)，只尝试一次。修复了 Prompt 格式化。"""
    prompt_template = config.get("prompt_template_correction", DEFAULT_TRANSLATE_CONFIG["prompt_template_correction"])
    model_name = config.get("model", "")
    source_language = config.get("source_language", "日语")
    target_language = config.get("target_language", "简体中文")
    generation_config = config.get("generation_config", {})
    safety_settings = config.get("safety_settings", [])

    num_lines = len(chunk_items)
    line_number_width = len(str(num_lines)) if num_lines > 0 else 1

    # --- 构建术语表 (同第一轮) ---
    char_keys = ['原文', '译文', '对应原名', '性别', '年龄', '性格', '口吻', '描述']
    char_format = "|".join([f"{{{key}}}" for key in char_keys])
    char_header = f"### 人物术语表 (格式: {'|'.join(char_keys)})"
    character_glossary_section = _build_glossary_section(character_dictionary, char_format, char_header, char_keys)
    entity_keys = ['原文', '译文', '类别', '描述']
    entity_format_combined = "{原文}|{译文}|{类别} - {描述}"
    entity_header_combined = "### 事物术语表 (格式: 原文|译文|类别 - 描述)"
    entity_keys_for_format = ['原文', '译文', '类别', '描述']
    entity_glossary_section = _build_glossary_section(entity_dictionary, entity_format_combined, entity_header_combined, entity_keys_for_format)

    # --- 构建输入块文本 ---
    input_block_lines = []
    original_keys_in_chunk = []
    for i, (original_key, _) in enumerate(chunk_items):
        original_keys_in_chunk.append(original_key)
        processed_key = text_processing.pre_process_text_for_llm(original_key)
        line_marker = f"[LINE_{i+1:0{line_number_width}d}]"
        input_block_lines.append(f"{line_marker}{processed_key}")
    input_block_text = "\n".join(input_block_lines)

    log.info(f"修正块 {chunk_index+1}/{total_chunks}，共 {num_lines} 行...")

    context_section = ""
    if context_keys:
        context_section = f"### 上文内容参考 ({source_language})\n<context>\n" + "\n".join(context_keys[-config.get("context_lines", 10):]) + "\n</context>\n"

    # --- 构建修正 Prompt (确保使用正确的 key) ---
    optional_failure_reason_guidance = "请特别注意保留原文格式、遵循术语表，并修正之前验证失败的问题。"
    try:
        current_final_prompt = prompt_template.format(
            source_language=source_language,
            target_language=target_language,
            optional_failure_reason_guidance=optional_failure_reason_guidance,
            character_glossary_section=character_glossary_section,
            entity_glossary_section=entity_glossary_section,
            context_section=context_section,
            input_block_text=input_block_text, # <-- 使用 input_block_text
            target_language_placeholder=target_language
        )
    except KeyError as e:
         log.error(f"格式化修正 Prompt 时缺少键: {e}。请检查 config.py 中的 prompt_template_correction。")
         # 返回修正失败
         return [(key, value, 'correction_failed') for key, value in chunk_items]

    # --- 调用 API (仅一次) ---
    success, response_content, error_message = api_client.generate_content(
        model_name,
        current_final_prompt,
        generation_config=generation_config, # 使用主配置
        safety_settings=safety_settings
    )

    final_results = []

    if not success:
        log.error(f"修正块 {chunk_index+1}/{total_chunks} API 调用失败: {error_message}")
        final_results = [(key, value, 'correction_failed') for key, value in chunk_items]
        try:
             with error_log_lock:
                  with open(error_log_path, 'a', encoding='utf-8') as elog:
                      elog.write(f"[{datetime.datetime.now().isoformat()}] 修正块翻译 API 调用失败 (块 {chunk_index+1}/{total_chunks})\n")
                      elog.write(f"  失败原因: {error_message}\n")
                      elog.write(f"  模型: {model_name}\n")
                      # *** 添加记录原始响应体 ***
                      elog.write(f"  API 原始响应体 (前 1000 字符):\n{str(response_content)[:1000]}...\n")
                      elog.write("-" * 20 + "\n")
        except Exception as log_err: log.error(f"写入修正块 API 错误日志失败: {log_err}")
        return final_results

    # --- 提取和验证修正结果 ---
    match = re.search(r'<output_block>(.*?)</output_block>', response_content, re.DOTALL)
    if not match:
        log.error(f"修正块 {chunk_index+1}/{total_chunks} API 响应未找到 <output_block>。")
        # *** 添加记录响应体到错误日志 ***
        try:
            with error_log_lock:
                with open(error_log_path, 'a', encoding='utf-8') as elog:
                    elog.write(f"[{datetime.datetime.now().isoformat()}] 修正块翻译失败：缺少output_block (块 {chunk_index+1}/{total_chunks})\n")
                    elog.write(f"  模型: {model_name}\n")
                    elog.write(f"  API 原始响应体:\n{response_content}\n") # 记录完整响应体
                    elog.write("-" * 20 + "\n")
        except Exception as log_err:
            log.error(f"写入修正块缺少 output_block 错误日志失败: {log_err}")
        # *** 结束添加 ***
        final_results = [(key, value, 'correction_failed') for key, value in chunk_items]
        return final_results

    output_block_content = match.group(1).strip(); output_lines = output_block_content.split('\n')

    if len(output_lines) != num_lines:
        log.error(f"修正块 {chunk_index+1}/{total_chunks} 验证失败: 行数不匹配。")
        final_results = [(key, value, 'correction_failed') for key, value in chunk_items]
        return final_results

    parsed_translations = {}; marker_validation_failed = False
    for i, line in enumerate(output_lines):
        expected_marker = f"[LINE_{i+1:0{line_number_width}d}]"
        if line.startswith(expected_marker): parsed_translations[i] = line[len(expected_marker):]
        else: log.error(f"修正块 {chunk_index+1}/{total_chunks} 验证失败: 行 {i+1} 标记错误。"); marker_validation_failed = True; break
    if marker_validation_failed:
        final_results = [(key, value, 'correction_failed') for key, value in chunk_items]
        return final_results

    # 逐行验证修正结果
    for i in range(num_lines):
        original_key = original_keys_in_chunk[i]; original_value = chunk_items[i][1]
        raw_translated = parsed_translations.get(i)
        if raw_translated is None:
             log.error(f"修正块 {chunk_index+1}/{total_chunks} 内部错误：行 {i+1} 解析丢失。")
             final_results.append((original_key, original_value, 'correction_failed')); continue
        restored = text_processing.restore_pua_placeholders(raw_translated); post_processed = text_processing.post_process_translation(restored, original_key)
        is_valid, reason = text_processing.validate_translation(original_key, restored, post_processed)
        if is_valid:
            log.info(f"修正块 {chunk_index+1}/{total_chunks} 行 {i+1} 修正成功。")
            final_results.append((original_key, post_processed, 'corrected_success'))
        else:
            log.error(f"修正块 {chunk_index+1}/{total_chunks} 行 {i+1} 修正后仍失败: {reason}.")
            final_results.append((original_key, original_value, 'correction_failed')) # 回退原文
            # (记录最终失败日志...)
            try:
                with error_log_lock:
                    with open(error_log_path, 'a', encoding='utf-8') as elog:
                        elog.write(f"[{datetime.datetime.now().isoformat()}] 单行翻译修正失败 (块 {chunk_index+1}/{total_chunks}, 行 {i+1})\n")
                        elog.write(f"  原文: {original_key}\n")
                        elog.write(f"  失败原因: {reason}\n")
                        elog.write(f"  模型: {model_name}\n")
                        elog.write(f"  修正后 API 响应行: {output_lines[i]}\n")
                        elog.write(f"  修正后处理译文: {post_processed}\n")
                        elog.write("-" * 20 + "\n")
            except Exception as log_err: log.error(f"写入修正失败错误日志失败: {log_err}")

    return final_results

# --- 线程工作函数 (第一轮) ---
def _translate_chunk_worker(
    chunk_items,
    chunk_index,
    total_chunks,
    context_keys,
    character_dictionary,
    entity_dictionary,
    api_client,
    config,
    translated_data, # 共享字典，存储最终结果 (key -> (text, status))
    results_lock,    # 锁 translated_data
    failed_lines_for_correction, # 共享列表，存储失败的 (key, value)
    failed_list_lock, # 锁 failed_lines_for_correction
    progress_queue,  # 用于发送进度更新的队列
    error_log_path,
    error_log_lock
):
    """处理一个块的翻译任务 (第一轮)。"""
    processed_count_in_chunk = 0
    try:
        chunk_results = _translate_single_chunk(
            chunk_items, chunk_index, total_chunks, context_keys,
            character_dictionary, entity_dictionary, api_client, config,
            error_log_path, error_log_lock
        )

        if chunk_results is None: # API 彻底失败
            log.error(f"块 {chunk_index+1}/{total_chunks} 因 API 彻底失败，全部标记为待修正。")
            chunk_results = [(key, value, 'pending_correction') for key, value in chunk_items]

        items_to_correct_in_chunk = []
        with results_lock:
            for key, text, status in chunk_results:
                translated_data[key] = (text, status)
                if status == 'pending_correction':
                     original_value = next((v for k, v in chunk_items if k == key), None)
                     if original_value is not None:
                         items_to_correct_in_chunk.append((key, original_value))
                     else:
                          log.error(f"内部错误：无法在 chunk_items 中找到 key '{key}' 的原始 value。")

        if items_to_correct_in_chunk:
            with failed_list_lock:
                failed_lines_for_correction.extend(items_to_correct_in_chunk)

    except Exception as chunk_err:
        log.exception(f"处理块 {chunk_index+1}/{total_chunks} 时发生意外错误: {chunk_err} - 块内所有行标记为待修正")
        items_to_correct = []
        with results_lock:
            for key, value in chunk_items:
                translated_data[key] = (value, 'pending_correction')
                items_to_correct.append((key, value))
        with failed_list_lock:
            failed_lines_for_correction.extend(items_to_correct)
        try: # 记录日志
            with error_log_lock:
                with open(error_log_path, 'a', encoding='utf-8') as elog:
                    elog.write(f"[{datetime.datetime.now().isoformat()}] 处理块时发生意外错误 (块 {chunk_index+1}/{total_chunks})，块内所有行标记为待修正:\n")
                    elog.write(f"  错误: {chunk_err}\n")
                    elog.write("-" * 20 + "\n")
        except Exception as log_err: log.error(f"写入块处理意外错误日志失败: {log_err}")
    finally:
        processed_count_in_chunk = len(chunk_items)
        progress_queue.put(processed_count_in_chunk)
        log.debug(f"Worker 完成块 {chunk_index+1}/{total_chunks}，处理 {processed_count_in_chunk} 行。")


# --- 线程工作函数 (第二轮 - 修正) ---
def _translate_correction_chunk_worker(
    chunk_items, # [(key, value), ...]
    chunk_index,
    total_chunks,
    context_keys,
    character_dictionary,
    entity_dictionary,
    api_client,
    config,
    translated_data, # 共享字典
    results_lock,    # 锁
    progress_queue,  # 进度队列
    error_log_path,
    error_log_lock
):
    """处理一个修正块的翻译任务 (第二轮)。"""
    processed_count_in_chunk = 0
    try:
        chunk_results = _translate_single_correction_chunk(
            chunk_items, chunk_index, total_chunks, context_keys,
            character_dictionary, entity_dictionary, api_client, config,
            error_log_path, error_log_lock
        )

        with results_lock:
            for key, text, status in chunk_results:
                translated_data[key] = (text, status)

    except Exception as chunk_err:
        log.exception(f"处理修正块 {chunk_index+1}/{total_chunks} 时发生意外错误: {chunk_err} - 块内所有行标记为修正失败")
        with results_lock:
            for key, value in chunk_items:
                translated_data[key] = (value, 'correction_failed')
        try: # 记录日志
            with error_log_lock:
                with open(error_log_path, 'a', encoding='utf-8') as elog:
                    elog.write(f"[{datetime.datetime.now().isoformat()}] 处理修正块时发生意外错误 (块 {chunk_index+1}/{total_chunks})，块内所有行标记为修正失败:\n")
                    elog.write(f"  错误: {chunk_err}\n")
                    elog.write("-" * 20 + "\n")
        except Exception as log_err: log.error(f"写入修正块处理意外错误日志失败: {log_err}")
    finally:
        processed_count_in_chunk = len(chunk_items)
        progress_queue.put(processed_count_in_chunk)
        log.debug(f"Correction Worker 完成块 {chunk_index+1}/{total_chunks}，处理 {processed_count_in_chunk} 行。")


# --- 主任务函数 ---
def run_translate(game_path, works_dir, translate_config, world_dict_config, message_queue):
    """
    执行 JSON 文件的翻译流程 (使用 Gemini 块翻译和两轮修正)。

    Args: (同上一个版本)
    """
    start_time = time.time()
    character_dictionary = []
    entity_dictionary = []
    failed_lines_for_correction = []

    try:
        message_queue.put(("status", "正在准备翻译任务..."))
        message_queue.put(("log", ("normal", "步骤 5: 开始翻译 JSON 文件 (使用 Gemini)...")))

        # --- 确定路径 ---
        # (与原代码相同)
        game_folder_name = text_processing.sanitize_filename(os.path.basename(game_path))
        if not game_folder_name: game_folder_name = "UntitledGame"
        work_game_dir = os.path.join(works_dir, game_folder_name)
        untranslated_dir = os.path.join(work_game_dir, "untranslated")
        translated_dir = os.path.join(work_game_dir, "translated")
        untranslated_json_path = os.path.join(untranslated_dir, "translation.json")
        translated_json_path = os.path.join(translated_dir, "translation_translated.json")
        error_log_path = os.path.join(translated_dir, "translation_errors.log")
        char_dict_filename = world_dict_config.get("character_dict_filename", DEFAULT_WORLD_DICT_CONFIG["character_dict_filename"])
        entity_dict_filename = world_dict_config.get("entity_dict_filename", DEFAULT_WORLD_DICT_CONFIG["entity_dict_filename"])
        character_dict_path = os.path.join(work_game_dir, char_dict_filename)
        entity_dict_path = os.path.join(work_game_dir, entity_dict_filename)

        if not file_system.ensure_dir_exists(translated_dir): raise OSError(f"无法创建翻译输出目录: {translated_dir}")
        if os.path.exists(error_log_path):
            log.info(f"删除旧的翻译错误日志: {error_log_path}")
            file_system.safe_remove(error_log_path)

        # --- 加载未翻译 JSON ---
        # (与原代码相同)
        if not os.path.exists(untranslated_json_path): raise FileNotFoundError(f"未找到未翻译的 JSON 文件: {untranslated_json_path}")
        message_queue.put(("log", ("normal", "加载未翻译的 JSON 文件...")))
        with open(untranslated_json_path, 'r', encoding='utf-8') as f: untranslated_data = json.load(f)
        original_items = list(untranslated_data.items())
        total_items = len(original_items)
        if total_items == 0:
            message_queue.put(("warning", "未翻译的 JSON 文件为空。")); message_queue.put(("status", "翻译跳过(无内容)")); message_queue.put(("done", None)); return
        message_queue.put(("log", ("normal", f"成功加载 JSON，共 {total_items} 个待翻译条目。")))
        translated_data = {key: None for key, _ in original_items}

        # --- 加载双词典 ---
        # (与原代码相同，加载逻辑)
        if os.path.exists(character_dict_path):
             message_queue.put(("log", ("normal", f"加载人物词典: {char_dict_filename}...")))
             try:
                with open(character_dict_path, 'r', newline='', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    if not reader.fieldnames or not all(h in reader.fieldnames for h in ['原文', '译文']): log.warning(f"人物词典 {char_dict_filename} 缺少表头。")
                    else: character_dictionary = [row for row in reader if row.get('原文')]; message_queue.put(("log", ("success", f"加载人物词典 {len(character_dictionary)} 条。")))
             except Exception as e: log.exception(f"加载人物词典失败: {e}"); message_queue.put(("log", ("error", f"加载人物词典失败: {e}。")))
        else: message_queue.put(("log", ("normal", f"未找到人物词典文件 ({char_dict_filename})。")))
        if os.path.exists(entity_dict_path):
            message_queue.put(("log", ("normal", f"加载事物词典: {entity_dict_filename}...")))
            try:
                with open(entity_dict_path, 'r', newline='', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    if not reader.fieldnames or not all(h in reader.fieldnames for h in ['原文', '译文', '类别', '描述']): log.warning(f"事物词典 {entity_dict_filename} 缺少表头。")
                    else: entity_dictionary = [row for row in reader if row.get('原文')]; message_queue.put(("log", ("success", f"加载事物词典 {len(entity_dictionary)} 条。")))
            except Exception as e: log.exception(f"加载事物词典失败: {e}"); message_queue.put(("log", ("error", f"加载事物词典失败: {e}。")))
        else: message_queue.put(("log", ("normal", f"未找到事物词典文件 ({entity_dict_filename})。")))

        # --- 获取 Gemini 翻译配置 ---
        config = translate_config.copy()
        api_key = config.get("api_key", "").strip() or world_dict_config.get("api_key", "").strip()
        model_name = config.get("model", "").strip()
        concurrency = config.get("concurrency", DEFAULT_TRANSLATE_CONFIG["concurrency"])
        chunk_max_tokens = config.get("chunk_max_tokens", DEFAULT_TRANSLATE_CONFIG["chunk_max_tokens"])
        if not api_key: raise ValueError("未配置 Gemini API Key。")
        if not model_name: raise ValueError("未配置 Gemini 模型名称。")
        message_queue.put(("log", ("normal", f"翻译配置: 模型={model_name}, 并发数={concurrency}, 块Token上限={chunk_max_tokens}")))

        # --- 初始化 Gemini API 客户端 ---
        try:
            api_client = gemini.GeminiClient(api_key)
            message_queue.put(("log", ("normal", "Gemini API 客户端初始化成功。")))
        except Exception as client_err: raise ConnectionError(f"初始化 Gemini API 客户端失败: {client_err}") from client_err

        # --- 动态分块 ---
        message_queue.put(("log", ("normal", "正在划分翻译块...")))
        # (构建术语表文本逻辑同上一个版本)
        char_keys = ['原文', '译文', '对应原名', '性别', '年龄', '性格', '口吻', '描述']
        char_format = "{原文}|{译文}|{对应原名}|{性别}|{年龄}|{性格}|{口吻}|{描述}"
        char_header = "### 人物术语表 (格式: 原文|译文|对应原名|性别|年龄|性格|口吻|描述)"
        char_glossary_txt = _build_glossary_section(character_dictionary, char_format, char_header, char_keys)
        entity_keys = ['原文', '译文', '类别', '描述']
        entity_format_combined = "{原文}|{译文}|{类别} - {描述}"
        entity_header_combined = "### 事物术语表 (格式: 原文|译文|类别 - 描述)"
        entity_keys_for_format = ['原文', '译文', '类别', '描述']
        entity_glossary_txt = _build_glossary_section(entity_dictionary, entity_format_combined, entity_header_combined, entity_keys_for_format)

        chunks = _create_chunks_more_even(original_items, config)
        total_chunks = len(chunks)
        if total_chunks == 0 and total_items > 0: raise RuntimeError("未能成功划分翻译块。")
        elif total_chunks == 0 and total_items == 0: message_queue.put(("warning", "无内容需翻译。")); message_queue.put(("status", "翻译完成")); message_queue.put(("done", None)); return

        # --- 并发处理 - 第一轮 ---
        results_lock = threading.Lock()
        failed_list_lock = threading.Lock()
        error_log_lock = threading.Lock()
        progress_queue = queue.Queue()
        processed_items_count = 0

        message_queue.put(("status", f"开始第一轮翻译: {total_items}行, {total_chunks}块, 并发{concurrency}..."))
        message_queue.put(("log", ("normal", f"开始第一轮翻译，使用 {concurrency} 个线程...")))

        with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="TranslateWorker") as executor:
            futures = []
            last_chunk_keys = []
            for i, chunk in enumerate(chunks):
                context = list(last_chunk_keys)
                futures.append(executor.submit(
                    _translate_chunk_worker,
                    chunk, i, total_chunks, context,
                    character_dictionary, entity_dictionary, api_client, config,
                    translated_data, results_lock,
                    failed_lines_for_correction, failed_list_lock,
                    progress_queue, error_log_path, error_log_lock
                ))
                last_chunk_keys = [item[0] for item in chunk]

            # --- 监控第一轮进度 ---
            PROGRESS_FIRST_PASS_MAX_PERCENT = 80.0 # 第一轮最多占 80% 进度
            completed_count_first_pass = 0
            while completed_count_first_pass < total_items:
                try:
                    processed_in_worker = progress_queue.get(timeout=2.0)
                    completed_count_first_pass += processed_in_worker
                    progress_percent = (completed_count_first_pass / total_items) * PROGRESS_FIRST_PASS_MAX_PERCENT
                    elapsed_time = time.time() - start_time
                    est_total_time = (elapsed_time / completed_count_first_pass) * total_items if completed_count_first_pass > 0 else 0
                    remaining_time = max(0, est_total_time - elapsed_time)
                    status_msg = (f"第一轮: {completed_count_first_pass}/{total_items} ({progress_percent:.1f}%) "
                                  f"- 预计剩余: {remaining_time:.0f}s")
                    message_queue.put(("status", status_msg))
                    message_queue.put(("progress", progress_percent))
                except queue.Empty:
                    all_futures_done = all(f.done() for f in futures)
                    if all_futures_done:
                        exceptions = [f.exception() for f in futures if f.exception()]
                        if exceptions: log.error(f"第一轮翻译出现 {len(exceptions)} 个线程错误: {exceptions[0]}")
                        log.info("第一轮所有工作线程已结束。")
                        # 确保进度至少达到目标
                        final_progress = (completed_count_first_pass / total_items) * PROGRESS_FIRST_PASS_MAX_PERCENT
                        message_queue.put(("progress", final_progress))
                        break
            message_queue.put(("log", ("normal", f"第一轮翻译处理完成，共处理 {completed_count_first_pass} 行。")))


        # --- 并发处理 - 第二轮 (修正) ---
        total_failed_count = len(failed_lines_for_correction)
        if total_failed_count > 0:
            message_queue.put(("log", ("warning", f"检测到 {total_failed_count} 行需要修正。")))
            message_queue.put(("status", f"开始第二轮修正，共 {total_failed_count} 行..."))

            correction_chunks = _create_chunks_more_even(original_items, config)
            total_correction_chunks = len(correction_chunks)
            log.info(f"{total_failed_count} 行失败条目被划分成 {total_correction_chunks} 个修正块。")

            completed_count_second_pass = 0

            with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="CorrectionWorker") as executor:
                futures_correction = []
                for i, chunk in enumerate(correction_chunks):
                    context = [] # 修正轮不使用上下文
                    futures_correction.append(executor.submit(
                        _translate_correction_chunk_worker,
                        chunk, i, total_correction_chunks, context,
                        character_dictionary, entity_dictionary, api_client, config,
                        translated_data, results_lock,
                        progress_queue, error_log_path, error_log_lock
                    ))

                # --- 监控第二轮进度 ---
                # 进度从 80% 开始
                progress_offset = PROGRESS_FIRST_PASS_MAX_PERCENT
                progress_range = 100.0 - progress_offset
                while completed_count_second_pass < total_failed_count:
                     try:
                         processed_in_worker = progress_queue.get(timeout=2.0)
                         completed_count_second_pass += processed_in_worker
                         progress_percent = progress_offset + (completed_count_second_pass / total_failed_count) * progress_range
                         status_msg = (f"第二轮修正: {completed_count_second_pass}/{total_failed_count} ({progress_percent:.1f}%) ")
                         message_queue.put(("status", status_msg))
                         message_queue.put(("progress", min(progress_percent, 100.0)))
                     except queue.Empty:
                          all_futures_done = all(f.done() for f in futures_correction)
                          if all_futures_done:
                              exceptions = [f.exception() for f in futures_correction if f.exception()]
                              if exceptions: log.error(f"第二轮修正出现 {len(exceptions)} 个线程错误: {exceptions[0]}")
                              log.info("第二轮所有修正工作线程已结束。")
                              # 确保进度达到100%
                              message_queue.put(("progress", 100.0))
                              break
            message_queue.put(("log", ("normal", f"第二轮修正处理完成，共处理 {completed_count_second_pass} 行。")))
        else:
             message_queue.put(("log", ("success", "第一轮翻译完成，无需要修正的行。")))
             message_queue.put(("progress", 100.0))

        # --- 检查错误日志 ---
        # (与原代码相同)
        error_count_in_log = 0
        if os.path.exists(error_log_path):
            try:
                with open(error_log_path, 'r', encoding='utf-8') as elog_read:
                    log_content = elog_read.read()
                    error_count_in_log = log_content.count("-" * 20)
                if error_count_in_log > 0:
                    message_queue.put(("log", ("warning", f"检测到 {error_count_in_log} 次错误记录。详情请查看: {error_log_path}")))
            except Exception as read_log_err: log.error(f"读取错误日志时出错: {read_log_err}")

        # --- 整理最终结果 ---
        # (与上一个版本相同)
        final_translated_data = {}
        success_count = 0
        corrected_success_count = 0
        correction_failed_count = 0
        fallback_count = 0
        missing_count = 0

        for key, original_value in original_items:
             result_tuple = translated_data.get(key)
             if result_tuple is None:
                 log.error(f"条目 '{key[:50]}...' 结果丢失，使用原文回退。")
                 final_translated_data[key] = original_value; missing_count += 1; fallback_count += 1
             else:
                 final_text, status = result_tuple
                 if status == 'success': final_translated_data[key] = final_text; success_count += 1
                 elif status == 'corrected_success': final_translated_data[key] = final_text; corrected_success_count += 1
                 elif status == 'correction_failed': final_translated_data[key] = original_value; correction_failed_count += 1; fallback_count += 1
                 elif status == 'pending_correction': log.error(f"条目 '{key[:50]}...' 状态仍为 pending_correction，强制回退。"); final_translated_data[key] = original_value; fallback_count += 1
                 elif status == 'fallback': final_translated_data[key] = original_value; fallback_count += 1
                 else: log.error(f"条目 '{key[:50]}...' 状态未知: {status}，强制回退。"); final_translated_data[key] = original_value; fallback_count += 1

        log.info(f"翻译统计: 成功={success_count}, 修正成功={corrected_success_count}, 修正失败={correction_failed_count}, 丢失/其他回退={fallback_count - correction_failed_count}, 总回退={fallback_count}")
        if missing_count > 0: message_queue.put(("error", f"严重警告: {missing_count} 个翻译结果丢失!"))
        if correction_failed_count > 0: message_queue.put(("log", ("warning", f"{correction_failed_count} 个条目修正失败，已使用原文。")))

        # --- 保存翻译后的 JSON ---
        message_queue.put(("log", ("normal", f"正在保存翻译结果到: {translated_json_path}")))
        try:
            file_system.ensure_dir_exists(os.path.dirname(translated_json_path))
            with open(translated_json_path, 'w', encoding='utf-8') as f_out:
                json.dump(final_translated_data, f_out, ensure_ascii=False, indent=4)
            elapsed = time.time() - start_time
            message_queue.put(("log", ("success", f"翻译后的 JSON 文件保存成功。耗时: {elapsed:.2f} 秒。")))

            final_status_message = "翻译完成"
            final_log_level = "success"
            final_result_message = "JSON 文件翻译完成"
            if fallback_count > 0:
                 final_status_message += f" ({fallback_count}个回退)"
                 final_result_message += f" ({fallback_count}个最终使用原文)"
                 final_log_level = "warning"
            message_queue.put((final_log_level, f"{final_result_message}"))
            message_queue.put(("status", final_status_message))
            message_queue.put(("progress", 100.0))
            message_queue.put(("done", None))
        except Exception as save_err:
            log.exception(f"保存翻译结果失败: {save_err}")
            message_queue.put(("error", f"保存翻译结果失败: {save_err}"))
            message_queue.put(("status", "翻译失败(保存错误)"))
            message_queue.put(("done", None))

    except (ValueError, FileNotFoundError, OSError, ConnectionError, RuntimeError) as setup_err:
        log.error(f"翻译任务失败: {setup_err}")
        message_queue.put(("error", f"翻译任务失败: {setup_err}"))
        message_queue.put(("status", "翻译失败"))
        message_queue.put(("done", None))
    except Exception as e:
        log.exception("翻译任务执行期间发生意外顶级错误。")
        message_queue.put(("error", f"翻译过程中发生严重错误: {e}"))
        message_queue.put(("status", "翻译失败"))
        message_queue.put(("done", None))