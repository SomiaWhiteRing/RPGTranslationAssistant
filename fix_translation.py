#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import re
import os
import sys
from pathlib import Path

def fix_translations(json_file_path, verbose=False):
    """修复翻译文件中的常见问题"""
    print(f"开始处理文件: {json_file_path}")
    
    try:
        # 读取JSON文件
        with open(json_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            try:
                translations = json.loads(content)
            except json.JSONDecodeError:
                print("JSON解析错误，尝试修复格式...")
                raise
    except Exception as e:
        print(f"读取文件时出错: {e}")
        return None, None
    
    # 创建修正后的字典
    fixed_translations = {}
    
    # 错误计数器
    error_count = {
        'escape_mismatch': 0,
        'japanese_residue': 0,
        'newline_mismatch': 0,
        'control_code_mismatch': 0,
        'dots_converted': 0,  # 新增：点号转换计数
        'dash_converted': 0,  # 新增：破折号转换计数
        'other_issues': 0,
        'total_fixed': 0
    }
    
    # 日语检测模式（包含平假名、片假名，但排除日中共有汉字）
    japanese_pattern = re.compile(r'[\u3040-\u309F\u30A0-\u30FF]')
    # 中文检测模式
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
    # 控制代码模式（匹配任何字母后跟[数字]的模式）
    control_code_pattern = re.compile(r'\\[A-Za-z]\[\d+\]')
    # 连续点号模式（分别匹配不同类型的点号）
    dots_patterns = {
        'middle_dots': re.compile(r'[・]{2,}'),  # 连续的中点
        'horizontal_dots': re.compile(r'[…⋯]{1,}'),  # 连续的省略号
        'periods': re.compile(r'[.]{3,}'),  # 连续的英文句点
        'single_middle_dot': re.compile(r'[・](?![・])'),  # 单个中点（后面不跟中点）
        'japanese_dash': re.compile(r'[ー]{1,}')  # 日文破折号
    }
    # 中日共有的标点符号（排除在日语检测之外）
    common_punctuation = re.compile(r'[！？。、．，：；（）【】「」『』〈〉《》""\'\'…⋯—‥]')
    
    total_items = len(translations)
    print(f"共找到 {total_items} 条翻译条目")
    
    for i, (key, value) in enumerate(translations.items()):
        if i % 1000 == 0 and i > 0:
            print(f"已处理 {i}/{total_items} 条条目...")
            
        fixed_value = value
        fixed = False
        
        # 1. 修复控制代码问题 (\X[n] 其中X可以是任何字母)
        # 先找出所有控制代码
        key_control_codes = list(control_code_pattern.finditer(key))
        value_control_codes = list(re.finditer(r'\\+[A-Za-z]\[\d+\]', fixed_value))
        
        if value_control_codes:
            # 创建控制代码映射
            code_map = {}
            # 记录已处理的控制代码位置
            processed_positions = set()
            
            # 按照在文本中的位置顺序处理控制代码
            for k_match in key_control_codes:
                k_code = k_match.group()
                k_pos = k_match.start()
                k_letter = re.search(r'\\([A-Za-z])\[', k_code).group(1)  # 提取控制字母
                
                # 找到最近的未处理的value中的控制代码
                best_match = None
                min_pos_diff = float('inf')
                for v_match in value_control_codes:
                    v_code = v_match.group()
                    v_pos = v_match.start()
                    v_letter = re.search(r'\\+([A-Za-z])\[', v_code).group(1)  # 提取控制字母
                    
                    # 如果这个位置已经处理过，跳过
                    if v_pos in processed_positions:
                        continue
                    
                    # 检查是否是相同的控制代码（必须是相同字母的控制代码）
                    if v_letter.upper() == k_letter.upper():
                        # 获取数字部分
                        k_num = re.search(r'\[(\d+)\]', k_code).group(1)
                        v_num = re.search(r'\[(\d+)\]', v_code).group(1)
                        
                        # 如果数字也相同，计算位置差异
                        if k_num == v_num:
                            pos_diff = abs(v_pos - k_pos)
                            if pos_diff < min_pos_diff:
                                min_pos_diff = pos_diff
                                best_match = v_match
                
                if best_match:
                    v_code = best_match.group()
                    # 保持与key中完全相同的形式（包括字母大小写）
                    if v_code != k_code:
                        code_map[v_code] = k_code
                        processed_positions.add(best_match.start())
            
            # 应用修复
            for wrong_code, correct_code in code_map.items():
                if wrong_code in fixed_value:
                    fixed_value = fixed_value.replace(wrong_code, correct_code)
                    if verbose:
                        print("修复控制代码: {} -> {}".format(wrong_code, correct_code))
                    error_count['control_code_mismatch'] += 1
                    fixed = True
        
        # 2. 修复转义字符问题
        # 首先处理多重转义的情况
        double_backslashes = re.findall(r'\\\\+[^\\]', fixed_value)
        if double_backslashes:
            for bs in sorted(double_backslashes, key=len, reverse=True):
                # 在key中找到对应的转义字符
                corresponding_bs = bs.replace('\\\\', '\\')
                if corresponding_bs in key:
                    fixed_value = fixed_value.replace(bs, corresponding_bs)
                    if verbose:
                        print("修复转义字符: {} -> {}".format(bs, corresponding_bs))
                    error_count['escape_mismatch'] += 1
                    fixed = True
        
        # 特殊处理某些转义序列
        special_escapes = ['\\<', '\\>', '\\^', '\\$', '\\.', '\\!']
        for esc in special_escapes:
            if esc in key and esc.replace('\\', '\\\\') in fixed_value:
                wrong_esc = esc.replace('\\', '\\\\')
                fixed_value = fixed_value.replace(wrong_esc, esc)
                if verbose:
                    print("修复特殊转义字符: {} -> {}".format(wrong_esc, esc))
                error_count['escape_mismatch'] += 1
                fixed = True
        
        # 3. 修复换行符问题
        # 检查开头的换行符
        if key.startswith('\\n') and not fixed_value.startswith('\\n'):
            # 如果原文是转义的换行符，value也用转义的
            fixed_value = '\\n' + fixed_value
            error_count['newline_mismatch'] += 1
            fixed = True
            if verbose:
                print("修复开头换行符（转义）")
        elif key.startswith('\n') and not fixed_value.startswith('\n'):
            # 如果原文是未转义的换行符，value也用未转义的
            fixed_value = '\n' + fixed_value
            error_count['newline_mismatch'] += 1
            fixed = True
            if verbose:
                print("修复开头换行符（未转义）")
        
        # 检查中间和结尾的换行符
        # 分别匹配转义和未转义的换行符
        key_escaped_newlines = [m.start() for m in re.finditer(r'\\n', key)]
        key_raw_newlines = [m.start() for m in re.finditer(r'(?<!\\)\n', key)]  # 不匹配被转义的\n
        value_escaped_newlines = [m.start() for m in re.finditer(r'\\n', fixed_value)]
        value_raw_newlines = [m.start() for m in re.finditer(r'(?<!\\)\n', fixed_value)]
        
        # 检查转义换行符
        if len(key_escaped_newlines) != len(value_escaped_newlines):
            missing_count = len(key_escaped_newlines) - len(value_escaped_newlines)
            if missing_count > 0:
                # 找出所有可能的句子结束位置
                sentence_ends = [m.end() for m in re.finditer(r'[。！？，]', fixed_value)]
                
                if sentence_ends and missing_count > 0:
                    # 选择合适的位置插入换行符
                    positions = sorted(sentence_ends)[:missing_count]
                    for pos in sorted(positions, reverse=True):
                        if pos < len(fixed_value):
                            fixed_value = fixed_value[:pos] + '\\n' + fixed_value[pos:]
                    
                    error_count['newline_mismatch'] += 1
                    fixed = True
                    if verbose:
                        print(f"修复转义换行符: 添加 {missing_count} 个")
        
        # 检查未转义换行符
        if len(key_raw_newlines) != len(value_raw_newlines):
            missing_count = len(key_raw_newlines) - len(value_raw_newlines)
            if missing_count > 0:
                # 找出所有可能的句子结束位置
                sentence_ends = [m.end() for m in re.finditer(r'[。！？，]', fixed_value)]
                
                if sentence_ends and missing_count > 0:
                    # 选择合适的位置插入换行符
                    positions = sorted(sentence_ends)[:missing_count]
                    for pos in sorted(positions, reverse=True):
                        if pos < len(fixed_value):
                            fixed_value = fixed_value[:pos] + '\n' + fixed_value[pos:]
                    
                    error_count['newline_mismatch'] += 1
                    fixed = True
                    if verbose:
                        print(f"修复未转义换行符: 添加 {missing_count} 个")
        
        # 4. 处理特殊字符转换（在检测日语残留之前）
        # 处理连续的点号
        for pattern_name, pattern in dots_patterns.items():
            matches = list(pattern.finditer(fixed_value))
            # 从后往前处理，避免替换影响后续匹配
            for match in reversed(matches):
                dots = match.group()
                
                # 根据不同类型的点号计算实际点数
                if pattern_name == 'middle_dots':
                    count = len(dots)  # 每个中点算一个点
                elif pattern_name == 'horizontal_dots':
                    count = len(dots) * 3  # 每个省略号算三个点
                elif pattern_name == 'periods':
                    count = len(dots)  # 每个句点算一个点
                elif pattern_name == 'single_middle_dot':
                    # 单个中点直接替换成中间点
                    if dots != '·':
                        if verbose:
                            print(f"转换中点: {dots} -> ·")
                        start, end = match.span()
                        fixed_value = fixed_value[:start] + '·' + fixed_value[end:]
                        error_count['dots_converted'] += 1
                        fixed = True
                    continue
                elif pattern_name == 'japanese_dash':
                    # 日文破折号转换为中文破折号
                    count = len(dots)
                    if count <= 2:
                        replacement = '—' * count  # 1-2个破折号
                    else:
                        replacement = '—' * count  # 保持相同数量
                    
                    if dots != replacement:
                        if verbose:
                            print(f"转换破折号: {dots} -> {replacement}")
                        start, end = match.span()
                        fixed_value = fixed_value[:start] + replacement + fixed_value[end:]
                        error_count['dash_converted'] += 1
                        fixed = True
                    continue
                
                # 根据点的数量决定替换成什么
                if count <= 2:
                    replacement = '…'  # 1-2个点转换为一个省略号
                elif count <= 5:
                    replacement = '…'  # 3-5个点转换为一个省略号
                else:
                    # 每3个点替换成一个省略号
                    replacement = '…' * ((count + 2) // 3)
                
                if dots != replacement:
                    if verbose:
                        print(f"转换省略号: {dots} -> {replacement}")
                    start, end = match.span()
                    fixed_value = fixed_value[:start] + replacement + fixed_value[end:]
                    error_count['dots_converted'] += 1
                    fixed = True
        
        # 5. 检测并修复日语原文残留
        # 排除控制代码后再检测日语
        clean_value = re.sub(r'\\[A-Za-z]\[\d+\]', '', fixed_value)  # 更新正则表达式以匹配所有控制代码
        clean_value = re.sub(r'\\\\[A-Za-z]\[\d+\]', '', clean_value)
        # 排除中日共有的标点符号
        clean_value_for_check = re.sub(common_punctuation, '', clean_value)
        
        if japanese_pattern.search(clean_value_for_check):
            japanese_chars = japanese_pattern.findall(clean_value_for_check)
            if len(japanese_chars) > 2:
                fixed_value = "[需要翻译] " + fixed_value
                error_count['japanese_residue'] += 1
                fixed = True
                if verbose:
                    print(f"标记未翻译日语: {key[:30]}...")
        
        # 6. 检查其他明显问题
        if key == fixed_value and len(key) > 10 and not key.startswith('\\>'):
            fixed_value = "[可能未翻译] " + fixed_value
            error_count['other_issues'] += 1
            fixed = True
            if verbose:
                print(f"标记可能未翻译: {key[:30]}...")
        
        # 如果进行了任何修复，增加计数
        if fixed:
            error_count['total_fixed'] += 1
        
        # 保存修正后的翻译
        fixed_translations[key] = fixed_value
    
    # 保存修正后的JSON
    output_path = Path(json_file_path).with_suffix('.fixed.json')
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(fixed_translations, f, ensure_ascii=False, indent=4)
        print(f"\n修复完成！结果已保存至: {output_path}")
    except Exception as e:
        print(f"保存文件时出错: {e}")
        return None, error_count
    
    print(f"转义符不匹配修复数量: {error_count['escape_mismatch']}")
    print(f"控制代码不匹配修复数量: {error_count['control_code_mismatch']}")
    print(f"点号转换修复数量: {error_count['dots_converted']}")
    print(f"破折号转换修复数量: {error_count['dash_converted']}")  # 新增输出
    print(f"日语残留标记数量: {error_count['japanese_residue']}")
    print(f"换行符不匹配修复数量: {error_count['newline_mismatch']}")
    print(f"其他问题修复数量: {error_count['other_issues']}")
    print(f"总修复条目数: {error_count['total_fixed']} (占比: {error_count['total_fixed']/total_items*100:.2f}%)")
    
    return output_path, error_count

def create_sample_json(output_path):
    """创建测试用的JSON文件"""
    sample_data = {
        "そんな彼らを数歩後ろから眺めて、\nパンプキンはふっと微笑んだ。": "南瓜在几步之外望着这般景象，\n忽然抿嘴轻笑。",
        "あ？\\!\nどうした、何ニヤついてる。": "哈？\\\\!\n你笑什么，一脸猥琐样。",
        "仲が良いんだな、と思ってさ。": "只是觉得你们感情真好呢。",
        "その答えを聞いたカマソッソとシドが\n同時に被りを振る。": "听到这个回答的卡玛索索与希德\n同时剧烈摇头。",
        "ぷんすかしながら鼻息荒く\nチョコバナナを食べるカマソッソを見て、\nパンプキンはほっと胸をなでおろす。": "ぷんすかしながら鼻息荒く\nチョコバナナを食べるカマソッソを見て、\nパンプキンはほっと胸をなでおろす。",
        "靴から伝わる感触も、\n舗装された道路から下草の這う土へ。": "靴から伝わる感触も、\n舗装された道路から下草の这う土へ。",
        "特に決めてないね。\\!\n私はもう疲れたから\nさっさと帰りたいところだけど。": "还没决定呢。\\\\!\n老娘已经累得想赶紧回家了。",
        "\\>\n（今、膀胱に体感\\C[2]1000mL\\C[0]溜まってる……\\.\n　だが、2000mLまでなら\\C[4]耐えられる\\C[0]）": "\\>\n（现在膀胱里实际储存了\\\\C[2]1000mL\\\\C[0]……\\\\.\n　不过到2000mL的话还能\\\\C[4]忍耐住\\\\C[0]）",
        # 破折号测试用例
        "どこのバカだ、コラーーー！！！！": "哪儿来的蠢货，混账东西ーーー！！！！",
        "へーーー、すごいですねーーー！": "嘿ーーー，真是太厉害了ーーー！",
        # 中日共有标点符号测试用例
        "え？！え？！何が起きてるの？！": "啥？！啥？！发生了什么？！",
        "中に入る！今！": "现在！进去！",
        "まあ！良かった！": "哇！太好了！"
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sample_data, f, ensure_ascii=False, indent=4)
    
    print(f"已创建测试用JSON文件: {output_path}")
    return output_path

def extract_sample_from_existing(source_file, output_file, count=20):
    """从现有文件中提取部分内容作为样本"""
    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            translations = json.load(f)
        
        # 选择一部分条目（包括示例中提到的有问题的条目）
        sample_data = {}
        problem_keys = [
            "ぷんすかしながら鼻息荒く\nチョコバナナを食べるカマソッソを見て、\nパンプキンはほっと胸をなでおろす。",
            "靴から伝わる感触も、\n舗装された道路から下草の這う土へ。",
            "特に決めてないね。\\!\n私はもう疲れたから\nさっさと帰りたいところだけど。",
            "どーどー、喧嘩しない喧嘩しない！\\!\nほら、これを食べて落ち着いて！",
            "\\>\n（今、膀胱に体感\\C[2]1000mL\\C[0]溜まってる……\\.\n　だが、2000mLまでなら\\C[4]耐えられる\\C[0]）",
            # 添加破折号相关的测试用例
            "どこのバカだ、コラーーー！！！！",
            "へーーー、すごいですねーーー！",
            # 中日共有标点符号测试用例
            "え？！え？！何が起きてるの？！",
            "中に入る！今！",
            "まあ！良かった！"
        ]
        
        # 先添加问题条目
        for key in problem_keys:
            if key in translations:
                sample_data[key] = translations[key]
        
        # 再添加随机条目，直到达到指定数量
        import random
        keys = list(translations.keys())
        random.shuffle(keys)
        for key in keys:
            if key not in sample_data and len(sample_data) < count:
                sample_data[key] = translations[key]
            if len(sample_data) >= count:
                break
                
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(sample_data, f, ensure_ascii=False, indent=4)
            
        print(f"已从{source_file}提取{len(sample_data)}条数据到{output_file}")
        return output_file
    except Exception as e:
        print(f"提取样本时出错: {e}")
        return None

def process_real_file(source_file):
    """处理实际文件并应用修复"""
    try:
        # 先创建样本进行测试
        sample_file = "extracted_sample.json"
        extract_sample_from_existing(source_file, sample_file, 30)
        
        # 在样本上运行修复，观察效果
        fixed_sample, stats = fix_translations(sample_file, verbose=True)
        
        # 询问是否要处理完整文件
        print("\n样本修复完成。是否要处理完整文件? (y/n)")
        answer = input().strip().lower()
        
        if answer == 'y':
            print(f"\n开始处理完整文件: {source_file}")
            fixed_file, full_stats = fix_translations(source_file)
            if fixed_file:
                print(f"完整文件修复完成! 结果已保存至: {fixed_file}")
                return fixed_file, full_stats
        else:
            print("已取消处理完整文件")
        
        return fixed_sample, stats
    except Exception as e:
        print(f"处理文件时出错: {e}")
        return None, None

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='修复翻译JSON文件中的问题')
    parser.add_argument('json_file', nargs='?', help='要修复的JSON文件路径')
    parser.add_argument('--create-sample', action='store_true', help='创建测试用JSON文件')
    parser.add_argument('--extract-sample', help='从指定文件提取样本数据')
    parser.add_argument('--sample-count', type=int, default=20, help='提取的样本数量')
    parser.add_argument('--process-real', help='处理真实文件(先创建样本测试)')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示详细输出')
    
    args = parser.parse_args()
    
    if len(sys.argv) == 1:
        print("请指定要处理的文件或使用 --help 查看帮助")
        return
    
    if args.extract_sample:
        if not os.path.exists(args.extract_sample):
            print(f"错误: 文件 {args.extract_sample} 不存在")
            return
            
        sample_file = "extracted_sample.json"
        extract_sample_from_existing(args.extract_sample, sample_file, args.sample_count)
        fix_translations(sample_file, verbose=args.verbose)
        return
        
    if args.process_real:
        if not os.path.exists(args.process_real):
            print(f"错误: 文件 {args.process_real} 不存在")
            return
            
        process_real_file(args.process_real)
        return
    
    if args.json_file:
        if not os.path.exists(args.json_file):
            print(f"错误: 文件 {args.json_file} 不存在")
            return
        
        try:
            fixed_path, stats = fix_translations(args.json_file, verbose=args.verbose)
            if fixed_path:
                print(f"修复成功，共修复了 {stats['total_fixed']} 个问题。")
        except Exception as e:
            print(f"处理文件时出错: {e}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 