#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import sys

def main():
    """检查修复前后的对比"""
    if len(sys.argv) < 2:
        print("用法: python check_fix_results.py <json文件路径>")
        return
    
    json_file_path = sys.argv[1]
    if json_file_path.startswith('"') and json_file_path.endswith('"'):
        json_file_path = json_file_path[1:-1]
    
    # 读取修复后的文件
    with open(json_file_path, 'r', encoding='utf-8') as file:
        fixed_data = json.load(file)
    
    # 读取备份文件（修复前）
    with open(json_file_path + '.bak', 'r', encoding='utf-8') as file:
        original_data = json.load(file)
    
    # 示例key
    example_keys = [
        "\\>\nそいつにハメてる\\C[2]ボール\\C[0]使って遊ぼう\\.\nそれならみんなで出来るでしょ",
        "\\>\n\\>ええい！\\<\\.\nここは\\c[2]魔物のうんこ\\C[0]を探す会にしよう！",
        "\\>\nもしかしたら\\C[2]珍しい魔物\\C[0]がいるかもしれん！\\.\nクソのロマンを探求しにいくぞ！"
    ]
    
    print("示例修复结果：")
    for i, key in enumerate(example_keys, 1):
        if key in fixed_data and key in original_data:
            print(f"\n示例{i}:")
            print(f"原文: {key}")
            print(f"修复前: {original_data[key]}")
            print(f"修复后: {fixed_data[key]}")
    
    # 统计修复情况
    different_values = 0
    for key in fixed_data:
        if key in original_data and fixed_data[key] != original_data[key]:
            different_values += 1
    
    print(f"\n总共修复了 {different_values} 处内容。")

if __name__ == "__main__":
    main() 