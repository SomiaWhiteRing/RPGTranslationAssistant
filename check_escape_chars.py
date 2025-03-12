import json
import sys
import os
import yaml

def check_escape_chars(json_file_path):
    """
    检查JSON文件中每个键值对的转义字符数量是否匹配
    参数:
        json_file_path: JSON文件路径
    返回:
        警告信息列表
    """
    warnings = []
    
    try:
        # 检查文件是否存在
        if not os.path.exists(json_file_path):
            return [f"错误: 文件不存在: '{json_file_path}'"]
            
        # 读取JSON文件
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            # 获取每个键值对的行号
            file.seek(0)
            lines = file.readlines()
        
        # 创建行号映射
        line_numbers = {}
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if ':' in line:
                # 处理带引号的键
                key = line.split(':', 1)[0].strip()
                if key.startswith('"') and key.endswith('"'):
                    key = json.loads(key)  # 正确解析JSON格式的键
                line_numbers[key] = i
        
        # 检查每个键值对
        for key, value in data.items():
            line_number = line_numbers.get(key, '未知')
            # 计算反斜杠数量
            key_backslashes = key.count('\\')
            value_backslashes = value.count('\\')
            
            # 计算感叹号数量
            key_exclamations = key.count('!')
            value_exclamations = value.count('!')
            
            # 计算竖线数量
            key_pipes = key.count('|')
            value_pipes = value.count('|')
            
            # 检查反斜杠数量是否匹配
            if key_backslashes != value_backslashes:
                warnings.append({
                    "行号": line_number,
                    "类型": "反斜杠不匹配",
                    "键": repr(key)[1:-1],  # 使用repr保持转义符
                    "键中数量": key_backslashes,
                    "值": repr(value)[1:-1],  # 使用repr保持转义符
                    "值中数量": value_backslashes
                })
            
            # 检查感叹号数量是否匹配
            if key_exclamations != value_exclamations:
                warnings.append({
                    "行号": line_number,
                    "类型": "感叹号不匹配",
                    "键": repr(key)[1:-1],
                    "键中数量": key_exclamations,
                    "值": repr(value)[1:-1],
                    "值中数量": value_exclamations
                })
            
            # 检查竖线数量是否匹配
            if key_pipes != value_pipes:
                warnings.append({
                    "行号": line_number,
                    "类型": "竖线不匹配",
                    "键": repr(key)[1:-1],
                    "键中数量": key_pipes,
                    "值": repr(value)[1:-1],
                    "值中数量": value_pipes
                })
    
    except Exception as e:
        warnings.append({"错误": str(e)})
    
    return warnings

def main():
    if len(sys.argv) < 2:
        print("用法: python check_escape_chars.py <json文件路径>")
        return
    
    # 处理命令行参数，支持带引号的路径
    json_file_path = sys.argv[1]
    if json_file_path.startswith('"') and json_file_path.endswith('"'):
        json_file_path = json_file_path[1:-1]
    
    print(f"正在检查文件: {json_file_path}")
    warnings = check_escape_chars(json_file_path)
    
    if warnings:
        print(f"发现 {len(warnings)} 个问题:")
        
        # 将警告以简洁格式打印到控制台
        for i, warning in enumerate(warnings, 1):
            if "错误" in warning:
                print(f"{i}. 错误: {warning['错误']}")
            else:
                print(f"{i}. 第{warning['行号']}行 {warning['类型']}: 键 '{warning['键']}' ({warning['键中数量']}) vs 值 '{warning['值']}' ({warning['值中数量']})")
        
        # 将警告写入结果文件（YAML格式）
        result_file_path = os.path.splitext(json_file_path)[0] + '_检查结果.yaml'
        with open(result_file_path, 'w', encoding='utf-8') as file:
            yaml.dump(warnings, file, allow_unicode=True, sort_keys=False, indent=2)
        print(f"检查结果已保存到: {result_file_path}")
    else:
        print("未发现问题，所有转义字符数量匹配。")

if __name__ == "__main__":
    main() 