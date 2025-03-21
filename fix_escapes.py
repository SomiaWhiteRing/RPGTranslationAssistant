import json
import os
import re

def fix_escapes(json_file_path):
    """修复JSON文件中的转义字符问题"""
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
            
            # 1. 修复 \\! 的情况
            if '\\!' in key and '!' in value:
                fixed_value = value.replace('!', '\\!')
            
            # 2. 修复 \\. 的情况
            if '\\.' in key:
                # 查找原文中 \\. 的数量
                dot_count = key.count('\\.')
                # 在译文中添加相应数量的 \\.
                if '.' in fixed_value:
                    fixed_value = fixed_value.replace('.', '\\.', dot_count)
                elif '…' in fixed_value:
                    fixed_value = fixed_value.replace('…', '\\.', dot_count)
            
            # 3. 修复 \\| 的情况
            if '\\|' in key and '|' in value:
                fixed_value = value.replace('|', '\\|')
            
            # 4. 修复多余的转义符
            if value.count('\\') > key.count('\\'):
                # 仅当原文没有对应的转义符时才移除
                extra_escapes = value.count('\\') - key.count('\\')
                fixed_value = re.sub(r'\\([^\\])', r'\1', fixed_value, extra_escapes)
            
            # 记录修改
            if fixed_value != original_value:
                changes.append({
                    '原文': key,
                    '修改前': original_value,
                    '修改后': fixed_value
                })
            
            fixed_data[key] = fixed_value
        
        # 保存修改后的文件
        backup_path = json_file_path + '.bak'
        os.rename(json_file_path, backup_path)
        
        with open(json_file_path, 'w', encoding='utf-8') as file:
            json.dump(fixed_data, file, ensure_ascii=False, indent=4)
        
        # 保存修改记录
        changes_path = os.path.splitext(json_file_path)[0] + '_修改记录.yaml'
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
        print("用法: python fix_escapes.py <json文件路径>")
        return
    
    json_file_path = sys.argv[1]
    if json_file_path.startswith('"') and json_file_path.endswith('"'):
        json_file_path = json_file_path[1:-1]
    
    changes_count = fix_escapes(json_file_path)
    print(f"完成修复，共修改 {changes_count} 处内容")
    print(f"原文件已备份为: {json_file_path}.bak")
    print(f"修改记录已保存至: {os.path.splitext(json_file_path)[0]}_修改记录.yaml")

if __name__ == "__main__":
    main() 