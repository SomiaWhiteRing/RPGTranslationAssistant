#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import yaml
import sys
from pathlib import Path

def load_check_results(check_result_file):
    """
    加载检查结果文件
    参数:
        check_result_file: 检查结果文件路径
    返回:
        检查结果列表
    """
    try:
        with open(check_result_file, 'r', encoding='utf-8') as file:
            check_results = yaml.safe_load(file)
        return check_results
    except Exception as e:
        print(f"无法加载检查结果文件: {e}")
        return None

def load_translation_file(translation_file):
    """
    加载翻译文件
    参数:
        translation_file: 翻译文件路径
    返回:
        翻译数据
    """
    try:
        with open(translation_file, 'r', encoding='utf-8') as file:
            data = json.load(file)
        return data
    except Exception as e:
        print(f"无法加载翻译文件: {e}")
        return None

def fix_escape_chars(translation_data, check_results):
    """
    根据检查结果修复转义字符不匹配
    参数:
        translation_data: 翻译数据
        check_results: 检查结果列表
    返回:
        修复后的翻译数据, 修复统计信息
    """
    fixed_data = translation_data.copy()
    stats = {
        '反斜杠修复': 0,
        '感叹号修复': 0,
        '竖线修复': 0,
        '总修复项': 0
    }
    
    # 创建键名到键的映射(用于处理repr格式的键)
    key_map = {}
    for key in translation_data.keys():
        key_repr = repr(key)[1:-1]  # 去掉repr产生的引号
        key_map[key_repr] = key
    
    # 处理每个检查结果
    for result in check_results:
        if isinstance(result, str) or "错误" in result:
            continue
            
        key_repr = result.get('键')
        if not key_repr in key_map:
            print(f"警告: 未找到匹配的键: {key_repr}")
            continue
            
        original_key = key_map[key_repr]
        original_value = translation_data[original_key]
        
        # 根据不匹配详情进行修复
        mismatch_details = result.get('不匹配详情', {})
        fixed_value = original_value
        
        for char_type, details in mismatch_details.items():
            if char_type == '反斜杠':
                # 修复反斜杠不匹配
                key_count = details['键中数量']
                value_count = details['值中数量']
                
                if key_count > value_count:
                    # 需要增加反斜杠
                    # 找出所有可能需要添加反斜杠的位置
                    potential_positions = []
                    for i in range(len(fixed_value)):
                        if i > 0 and fixed_value[i-1:i+1] == '\\<' or fixed_value[i-1:i+1] == '\\>':
                            continue  # 跳过已经有反斜杠的位置
                        if fixed_value[i] in '<>':
                            potential_positions.append(i)
                    
                    # 添加反斜杠
                    missing_count = key_count - value_count
                    for i in range(min(missing_count, len(potential_positions))):
                        pos = potential_positions[i]
                        fixed_value = fixed_value[:pos] + '\\' + fixed_value[pos:]
                        # 更新后续潜在位置的索引
                        potential_positions = [p+1 if p > pos else p for p in potential_positions]
                
                elif key_count < value_count:
                    # 需要减少反斜杠
                    # 找出所有多余反斜杠
                    i = 0
                    while i < len(fixed_value) - 1:
                        if fixed_value[i:i+2] == '\\\\':
                            # 检查是否是必要的转义
                            if i+2 < len(fixed_value) and fixed_value[i+2] in '<>':
                                fixed_value = fixed_value[:i] + fixed_value[i+1:]
                            else:
                                i += 1
                        i += 1
                
                if fixed_value != original_value:
                    stats['反斜杠修复'] += 1
            
            elif char_type == '感叹号':
                # 修复感叹号不匹配
                key_count = details['键中数量']
                value_count = details['值中数量']
                
                if key_count > value_count:
                    # 在合适的位置添加感叹号
                    missing_count = key_count - value_count
                    # 优先在句末添加
                    sentence_ends = [i for i, char in enumerate(fixed_value) if char in '。？']
                    
                    for i in range(min(missing_count, len(sentence_ends))):
                        pos = sentence_ends[i]
                        fixed_value = fixed_value[:pos+1] + '!' + fixed_value[pos+1:]
                        # 更新后续位置
                        sentence_ends = [p+1 if p > pos else p for p in sentence_ends]
                    
                    # 如果仍有缺失，添加到末尾
                    if missing_count > len(sentence_ends):
                        fixed_value += '!' * (missing_count - len(sentence_ends))
                
                elif key_count < value_count:
                    # 减少感叹号
                    excess_count = value_count - key_count
                    # 从末尾开始移除
                    i = len(fixed_value) - 1
                    removed = 0
                    while i >= 0 and removed < excess_count:
                        if fixed_value[i] == '!':
                            fixed_value = fixed_value[:i] + fixed_value[i+1:]
                            removed += 1
                        i -= 1
                
                if fixed_value != original_value:
                    stats['感叹号修复'] += 1
            
            elif char_type == '竖线':
                # 修复竖线不匹配
                key_count = details['键中数量']
                value_count = details['值中数量']
                
                if key_count > value_count:
                    # 添加竖线
                    missing_count = key_count - value_count
                    fixed_value += '|' * missing_count
                
                elif key_count < value_count:
                    # 减少竖线
                    excess_count = value_count - key_count
                    # 从末尾开始移除
                    i = len(fixed_value) - 1
                    removed = 0
                    while i >= 0 and removed < excess_count:
                        if fixed_value[i] == '|':
                            fixed_value = fixed_value[:i] + fixed_value[i+1:]
                            removed += 1
                        i -= 1
                
                if fixed_value != original_value:
                    stats['竖线修复'] += 1
        
        # 更新修复后的值
        if fixed_value != original_value:
            fixed_data[original_key] = fixed_value
            stats['总修复项'] += 1
            print(f"第{result.get('行号')}行 已修复: {original_value} -> {fixed_value}")
    
    return fixed_data, stats

def save_fixed_translations(fixed_data, original_file):
    """
    保存修复后的翻译数据
    参数:
        fixed_data: 修复后的翻译数据
        original_file: 原始翻译文件路径
    返回:
        保存的文件路径
    """
    output_file = original_file.rsplit('.', 1)[0] + '.fixed.json'
    try:
        with open(output_file, 'w', encoding='utf-8') as file:
            json.dump(fixed_data, file, ensure_ascii=False, indent=2)
        return output_file
    except Exception as e:
        print(f"保存修复后的翻译文件失败: {e}")
        return None

def main():
    if len(sys.argv) < 2:
        print("用法: python fix_escape_chars.py <检查结果文件路径>")
        return
    
    # 处理命令行参数
    check_result_file = sys.argv[1]
    if check_result_file.startswith('"') and check_result_file.endswith('"'):
        check_result_file = check_result_file[1:-1]
    
    # 推断翻译文件路径
    check_file_base = check_result_file.rsplit('_检查结果.yaml', 1)[0]
    translation_file = check_file_base + '.json'
    
    if not os.path.exists(translation_file):
        print(f"无法找到对应的翻译文件: {translation_file}")
        return
    
    print(f"正在处理检查结果: {check_result_file}")
    print(f"对应的翻译文件: {translation_file}")
    
    # 加载检查结果和翻译文件
    check_results = load_check_results(check_result_file)
    if not check_results:
        return
    
    translation_data = load_translation_file(translation_file)
    if not translation_data:
        return
    
    # 修复转义字符不匹配
    print("开始修复转义字符不匹配...")
    fixed_data, stats = fix_escape_chars(translation_data, check_results)
    
    # 保存修复后的翻译
    if stats['总修复项'] > 0:
        output_file = save_fixed_translations(fixed_data, translation_file)
        if output_file:
            print(f"修复完成，已保存到: {output_file}")
            print(f"统计信息:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
    else:
        print("未发现需要修复的项目")

if __name__ == "__main__":
    main() 