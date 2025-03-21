import json
import os
import re

def fix_newline_escapes(json_file_path):
    """修复JSON文件中的换行转义符问题
    当key中的"\\!\n"与"\n"相加的数量与value中的"\n"数量相等时，
    找出key中的"\\!\n"对应value中的哪些"\n"，并进行修复
    """
    try:
        # 读取JSON文件
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        # 创建修复后的数据
        fixed_data = {}
        changes = []
        
        for key, value in data.items():
            original_value = value
            fixed_value = value
            
            # 计算key中的换行符数量
            key_normal_newlines = key.count('\n') - key.count('\\!\n')
            key_escaped_newlines = key.count('\\!\n')
            total_key_newlines = key_normal_newlines + key_escaped_newlines
            
            # 计算value中的换行符数量
            value_newlines = value.count('\n')
            value_escaped_newlines = value.count('\\!\n')
            
            # 当key中的总换行符数量与value中的换行符数量相等，且value中缺少转义时
            if total_key_newlines == value_newlines and key_escaped_newlines > value_escaped_newlines:
                # 找出key中的"\\!\n"位置
                key_newline_positions = []
                pos = 0
                while True:
                    pos = key.find('\n', pos)
                    if pos == -1:
                        break
                    # 检查这个\n前面是否有\\!
                    if pos >= 2 and key[pos-2:pos] == '\\!':
                        key_newline_positions.append((pos, True))  # True表示是\\!\n
                    else:
                        key_newline_positions.append((pos, False))  # False表示是普通\n
                    pos += 1
                
                # 找出value中的"\n"位置
                value_newline_positions = []
                pos = 0
                while True:
                    pos = value.find('\n', pos)
                    if pos == -1:
                        break
                    # 检查这个\n前面是否有\\!
                    if pos >= 2 and value[pos-2:pos] == '\\!':
                        value_newline_positions.append((pos, True))  # True表示是\\!\n
                    else:
                        value_newline_positions.append((pos, False))  # False表示是普通\n
                    pos += 1
                
                # 根据key中的模式修复value
                if len(key_newline_positions) == len(value_newline_positions):
                    new_value = value
                    offset = 0  # 由于插入\\!导致的位置偏移
                    
                    for i, (key_pos, key_is_escaped) in enumerate(key_newline_positions):
                        value_pos, value_is_escaped = value_newline_positions[i]
                        
                        # 如果key中是\\!\n但value中只是\n，则修复
                        if key_is_escaped and not value_is_escaped:
                            # 在value的对应位置添加\\!
                            adjusted_pos = value_pos + offset
                            new_value = new_value[:adjusted_pos] + '\\!' + new_value[adjusted_pos:]
                            offset += 2  # \\!长度为2
                    
                    fixed_value = new_value
            
            # 记录修改
            if fixed_value != original_value:
                changes.append({
                    '原文': key,
                    '修改前': original_value,
                    '修改后': fixed_value,
                    '说明': '添加换行符前的\\!'
                })
            
            fixed_data[key] = fixed_value
        
        if changes:
            # 保存修改后的文件
            backup_path = json_file_path + '.bak'
            os.rename(json_file_path, backup_path)
            
            with open(json_file_path, 'w', encoding='utf-8') as file:
                json.dump(fixed_data, file, ensure_ascii=False, indent=4)
            
            # 保存修改记录
            changes_path = os.path.splitext(json_file_path)[0] + '_newline修改记录.yaml'
            import yaml
            with open(changes_path, 'w', encoding='utf-8') as file:
                yaml.dump(changes, file, allow_unicode=True, sort_keys=False, indent=2)
        
        return len(changes)
        
    except Exception as e:
        print(f"错误: {str(e)}")
        return 0

def main():
    import sys
    if len(sys.argv) < 2:
        print("用法: python fix_newline_escapes.py <json文件路径>")
        return
    
    json_file_path = sys.argv[1]
    if json_file_path.startswith('"') and json_file_path.endswith('"'):
        json_file_path = json_file_path[1:-1]
    
    changes_count = fix_newline_escapes(json_file_path)
    if changes_count > 0:
        print(f"完成修复，共修改 {changes_count} 处内容")
        print(f"原文件已备份为: {json_file_path}.bak")
        print(f"修改记录已保存至: {os.path.splitext(json_file_path)[0]}_newline修改记录.yaml")
    else:
        print("未发现需要修复的内容")

if __name__ == "__main__":
    main() 