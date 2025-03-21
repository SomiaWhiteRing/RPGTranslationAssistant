#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import re
import sys

def fix_dot_newline_escapes(json_file_path):
    """
    修复JSON文件中的 \\.\n 转义符问题
    
    当key中包含"\\.\n"时，value中对应位置可能缺少"\\."，
    此函数会检测并在value的对应\n前添加缺失的"\\."
    
    参数:
        json_file_path: JSON文件路径
    返回:
        修复的条目数量
    """
    try:
        # 读取JSON文件
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        # 创建修复后的数据和修改记录
        fixed_data = {}
        changes = []
        
        for key, value in data.items():
            original_value = value
            
            # 检查key中是否包含\\.\n
            if '\\.\n' in key:
                # 获取key中所有\n的位置
                key_newlines = [i for i, c in enumerate(key) if c == '\n']
                
                # 检查每个\n前面是否有\\.
                key_has_dot_before = []
                for i in key_newlines:
                    if i >= 2 and key[i-2:i] == '\\.':
                        key_has_dot_before.append(True)
                    else:
                        key_has_dot_before.append(False)
                
                # 获取value中所有\n的位置
                value_newlines = [i for i, c in enumerate(value) if c == '\n']
                
                # 如果key和value中的\n数量相同，我们可以一一对应处理
                if len(key_newlines) == len(value_newlines):
                    # 创建新的value，在需要的地方添加\\.
                    fixed_value = list(value)  # 转换为列表以便修改
                    
                    # 记录添加的字符数，用于调整后续索引
                    offset = 0
                    
                    for i, (pos, has_dot) in enumerate(zip(value_newlines, key_has_dot_before)):
                        if has_dot:
                            # 检查value中的\n前面是否已经有\\.
                            adj_pos = pos + offset
                            if adj_pos < 2 or fixed_value[adj_pos-2:adj_pos] != ['\\', '.']:
                                # 在\n前插入\\.
                                fixed_value.insert(adj_pos, '.')
                                fixed_value.insert(adj_pos, '\\')
                                offset += 2
                    
                    fixed_value = ''.join(fixed_value)
                else:
                    # 如果\n数量不匹配，使用原值
                    fixed_value = value
            else:
                # 如果key中没有\\.\n，则不需要修复
                fixed_value = value
            
            # 记录修改
            if fixed_value != original_value:
                changes.append({
                    '原文': key,
                    '修改前': original_value,
                    '修改后': fixed_value,
                    '说明': '添加换行符前的\\.'
                })
            
            fixed_data[key] = fixed_value
        
        if changes:
            # 保存修改前的备份
            backup_path = json_file_path + '.bak'
            if not os.path.exists(backup_path):
                os.rename(json_file_path, backup_path)
            else:
                # 如果备份已存在，则只复制文件内容
                with open(json_file_path, 'r', encoding='utf-8') as src, open(backup_path, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
            
            # 保存修改后的文件
            with open(json_file_path, 'w', encoding='utf-8') as file:
                json.dump(fixed_data, file, ensure_ascii=False, indent=4)
            
            # 保存修改记录
            changes_path = os.path.splitext(json_file_path)[0] + '_dot_newline修改记录.json'
            with open(changes_path, 'w', encoding='utf-8') as file:
                json.dump(changes, file, ensure_ascii=False, indent=4)
        
        return len(changes)
        
    except Exception as e:
        print(f"错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0

def main():
    if len(sys.argv) < 2:
        print("用法: python fix_dot_newline_escapes.py <json文件路径>")
        return
    
    json_file_path = sys.argv[1]
    if json_file_path.startswith('"') and json_file_path.endswith('"'):
        json_file_path = json_file_path[1:-1]
    
    print(f"正在处理文件: {json_file_path}")
    changes_count = fix_dot_newline_escapes(json_file_path)
    
    if changes_count > 0:
        print(f"完成修复，共修改 {changes_count} 处内容")
        print(f"原文件已备份为: {json_file_path}.bak")
        print(f"修改记录已保存至: {os.path.splitext(json_file_path)[0]}_dot_newline修改记录.json")
    else:
        print("未发现需要修复的内容")

if __name__ == "__main__":
    main() 