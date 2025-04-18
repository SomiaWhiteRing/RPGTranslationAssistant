# config.py
import json
import os
import logging
from core.utils import file_system # 导入文件系统工具以确保目录存在

log = logging.getLogger(__name__)

# --- 默认配置 ---

# --- 默认世界观字典生成配置 (Gemini) ---
DEFAULT_WORLD_DICT_CONFIG = {
    "api_key": "",
    # 使用较强的 Pro 模型进行字典提取，保证准确性
    "model": "gemini-2.5-flash-preview-04-17",
    "character_dict_filename": "character_dictionary.csv", # 人物词典文件名
    "entity_dict_filename": "entity_dictionary.csv",       # 事物词典文件名

    # 默认人物提取 Prompt (保持不变)
    "character_prompt_template": """请分析提供的游戏文本，提取其中反复出现的【角色名称】和【角色昵称】。提取规则如下：
1.  输出格式为严格的CSV，包含八列：原文,译文,对应原名,性别,年龄,性格,口吻,描述。
2.  【对应原名】列：只有当该行是【昵称】时，才填写其对应的【角色名称】原文；如果是【角色名称】或无法确定对应关系，则此列留空。
3.  【性别】、【年龄】、【性格】、【口吻】列：主要针对【角色名称】提取，尽可能根据文本推断；如果是【昵称】，这些列通常留空，除非昵称本身明确指向这些属性。
4.  【描述】列：可以补充其他关键信息，例如角色的种族、身份、与其他角色的关系等。
5.  确保每个字段都被双引号包围，字段内的逗号和换行符需要正确转义。
6.  **重要：生成的任何字段内容本身应避免包含英文双引号(`"`)字符。如果必须表示引用或特定术语，请考虑使用中文引号（“ ”）、单引号（' '）或其他标记，或者直接在描述性文本中说明。**
7.  提取的名词或昵称在原文中至少出现两次。
8.  忽略单个汉字、假名或字母。忽略过于泛化的词语（如“男孩”、“女孩”、“村民”等，除非有明确的指代）。
9.  译文请根据上下文推断一个合适的简体中文翻译。
10.  CSV首行不需要表头。

以下是需要分析的游戏文本内容：
{game_text}""",

    # 默认事物提取 Prompt (包含人物词典参考) (保持不变)
    "entity_prompt_template": """请分析提供的游戏文本，提取其中反复出现的【地点】、【生物】、【组织】、【物品】、【事件】等实体名词（不包括角色）。提取规则如下：
1.  输出格式为严格的CSV，包含四列：原文,译文,类别,描述。
2.  【类别】限定为：地点、生物、组织、物品、事件。
3.  确保每个字段都被双引号包围，字段内的逗号和换行符需要正确转义。
4.  提取的实体名词在原文中至少出现两次。
5.  忽略单个汉字、假名或字母。忽略常见的、过于笼统的词汇（例如：门、钥匙、药水、史莱姆、哥布林等，除非它们有特殊的前缀或后缀，或在特定上下文中具有重要意义）。
6.  译文请根据上下文推断一个合适的简体中文翻译。
7.  CSV首行不需要表头。

### 人物词典参考 (CSV格式)
以下是已提取的人物词典内容，采用CSV格式（原文,译文,对应原名,性别,年龄,性格,口吻,描述）。请在提取和翻译地点、物品等实体时，参考此词典中的'原文'和'译文'，确保与人物相关的用词保持一致。如果游戏文本中提到了某个地点或物品属于某个人物，请在【描述】列中注明。
```csv
{character_reference_csv_content}
```

以下是需要分析的游戏文本内容：
{game_text}

请输出事物词典 (原文,译文,类别,描述)，严格CSV格式。"""
}

# --- 默认翻译配置 (Gemini) ---
DEFAULT_TRANSLATE_CONFIG = {
    # 不再需要 api_url，Gemini Client 使用官方 SDK
    "api_key": "",
    # 使用 Gemini 2.5 Flash Preview 模型进行翻译，性价比高
    "model": "gemini-2.5-flash-preview-04-17",
    # 块最大 Token 数 (输入)，略小于模型上限以留出余量给 Prompt 和输出
    "chunk_max_tokens": 1000000,
    # 并发数，用于控制同时处理多少个文本块的线程数量
    "concurrency": 16,
    # 单个块翻译失败时的最大重试次数
    "max_retries": 3,
    # Gemini Generation Config (示例)
    "generation_config": {
        "temperature": 1,         # 控制生成文本的随机性
        "max_output_tokens": 65535   # 限制单次响应的最大输出 Token 数 (Flash 最大 65k)
        # "top_p": 0.9,             # 可以添加 Top-p 等其他参数
        # "top_k": 40,              # 可以添加 Top-k 等其他参数
    },
    # Gemini Safety Settings (默认为不阻止，适用于游戏内容，请谨慎调整)
    "safety_settings": [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ],
    "source_language": "日语",
    "target_language": "简体中文",
    # 更新的 Prompt 模板，用于 Gemini 块翻译
    "prompt_template": """你是专业的游戏翻译引擎，你的任务是将以下 {source_language} 文本块翻译成 {target_language}。

### 重要指令
1.  **逐行翻译**: 严格按照输入文本块中的行数和顺序进行翻译，输出完全相同的行数。输入的每一行都以 `[LINE_XXX]` 标记开始，请在输出的对应译文行也保留此标记。
2.  **保留格式**: 必须原样保留原始文本中的所有 PUA 占位符 (\uE000-\uF8FF) 以及其他特殊格式标记 (如 RPG Maker 的 \\N, \\!, \\< 等)。**绝对禁止**修改、删除或翻译这些占位符和标记。
3.  **术语遵循**: 请严格参考下方提供的术语表进行翻译，确保译文与术语表一致。
4.  **语言纯净**: 译文中**禁止**出现任何 {source_language} 字符（例如，当源语言是日语时，不允许出现平假名或片假名）。
5.  **忠实原文**: 游戏文本可能包含直白或粗俗的描述，请忠实翻译，不应随意删减、修改或美化。

### 人物术语表 (格式: 原文|译文|对应原名|性别|年龄|性格|口吻|描述)
{character_glossary_section}

### 事物术语表 (格式: 原文|译文|类别 - 描述)
{entity_glossary_section}

{context_section}

### 需要翻译的文本块 (原文: {source_language})
<input_block>
{input_block_text}
</input_block>

### 请将翻译结果 (目标语言: {target_language}) 放在下面的标签中，保持与输入完全相同的行数和 `[LINE_XXX]` 标记格式:
<output_block>
</output_block>""",

    # 新增：用于第二轮修正翻译的 Prompt 模板
    "prompt_template_correction": """你是一个专业的游戏翻译校对员。之前的翻译尝试中，以下文本行未能通过验证或翻译不佳。请根据提供的上下文、术语表和之前的尝试（如果有提供），重新将这些 {source_language} 文本行翻译成 {target_language}。

### 重要指令
1.  **聚焦修正**: 重点关注每一行的准确性和流畅性，确保遵循所有翻译规则。
2.  **逐行翻译**: 严格按照输入文本块中的行数和顺序进行翻译，输出完全相同的行数。输入的每一行都以 `[LINE_XXX]` 标记开始，请在输出的对应译文行也保留此标记。
3.  **保留格式**: 必须原样保留原始文本中的所有 PUA 占位符 (\uE000-\uF8FF) 以及其他特殊格式标记 (如 RPG Maker 的 \\N, \\!, \\< 等)。**绝对禁止**修改、删除或翻译这些占位符和标记。
4.  **术语遵循**: 请严格参考下方提供的术语表进行翻译，确保译文与术语表一致。
5.  **语言纯净**: 译文中**禁止**出现任何 {source_language} 字符（例如，当源语言是日语时，不允许出现平假名或片假名）。
6.  **忠实原文**: 游戏文本可能包含直白或粗俗的描述，请忠实翻译，不应随意删减、修改或美化。
7.  **参考失败原因**: {optional_failure_reason_guidance}

### 人物术语表 (格式: 原文|译文|对应原名|性别|年龄|性格|口吻|描述)
{character_glossary_section}

### 事物术语表 (格式: 原文|译文|类别 - 描述)
{entity_glossary_section}

{context_section}

### 需要修正翻译的文本行 (原文: {source_language})
<input_block>
{input_block_text}
</input_block>

### 请将修正后的翻译结果 (目标语言: {target_language}) 放在下面的标签中，保持与输入完全相同的行数和 `[LINE_XXX]` 标记格式:
<output_block>
</output_block>"""
}

# --- 默认专业模式配置 (保持不变) ---
DEFAULT_PRO_MODE_SETTINGS = {
    "export_encoding": "932",   # 默认 Shift-JIS
    "import_encoding": "936",   # 默认 GBK
    "write_log_rename": True,   # 默认输出重命名日志
    "rtp_options": {            # RTP 默认选项
        "2000": True,
        "2000en": False,
        "2003": False,
        "2003steam": False
    }
}

# --- 完整的默认应用配置 ---
DEFAULT_CONFIG = {
    "selected_mode": "easy", # 默认启动模式
    # 使用深拷贝确保子字典独立
    "world_dict_config": DEFAULT_WORLD_DICT_CONFIG.copy(),
    "translate_config": DEFAULT_TRANSLATE_CONFIG.copy(), # 使用新的翻译配置
    "pro_mode_settings": DEFAULT_PRO_MODE_SETTINGS.copy(),
    # 可以添加其他全局配置，例如上次使用的游戏路径等
    # "last_game_path": ""
}

# --- 配置管理类 ---
class ConfigManager:
    """负责加载和保存应用程序配置 (app_config.json)。"""

    def __init__(self, config_file_path):
        """
        初始化配置管理器。

        Args:
            config_file_path (str): 配置文件的完整路径。
        """
        self.config_file_path = config_file_path
        log.info(f"配置文件路径设置为: {self.config_file_path}")

    def load_config(self):
        """
        加载配置文件。如果文件不存在或无效，则返回合并后的默认配置。
        合并逻辑会确保新旧配置文件的兼容性。
        """
        loaded_config = {}
        if os.path.exists(self.config_file_path):
            try:
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                log.info(f"成功从 {self.config_file_path} 加载配置。")
            except (json.JSONDecodeError, IOError) as e:
                log.error(f"加载配置文件 {self.config_file_path} 失败: {e}。将使用合并默认配置。")
                loaded_config = {} # 加载失败则视为空配置
        else:
            log.info(f"配置文件 {self.config_file_path} 不存在，将使用默认配置。")

        # --- 递归合并加载的配置和默认配置 ---
        # 以默认配置为基础，用加载的配置覆盖它
        # 这确保了即使添加了新的默认配置项，旧配置文件也能正常工作
        final_config = {} # 从空字典开始，以确保正确的深拷贝

        def merge_dicts(target, source):
            """递归合并字典，source 的值覆盖 target 的值。"""
            for key, value in source.items():
                if isinstance(value, dict):
                    node = target.setdefault(key, {})
                    if isinstance(node, dict):
                        merge_dicts(node, value)
                    else:
                        target[key] = value # 类型不匹配，直接覆盖
                elif isinstance(value, list):
                     # 对于列表（如 safety_settings），简单覆盖。
                     # 注意：如果希望更精细地合并列表（例如保留旧设置中没有的项），需要更复杂的逻辑
                     target[key] = value
                else:
                    target[key] = value

        # 先将默认配置深拷贝到 final_config
        final_config = json.loads(json.dumps(DEFAULT_CONFIG))

        # 然后将加载的配置合并到 final_config 中
        merge_dicts(final_config, loaded_config)

        # --- 验证和确保关键子字典及内部键存在 (使用 setdefault) ---
        # 对 world_dict_config 进行检查和填充默认值
        world_dict_node = final_config.setdefault('world_dict_config', {})
        if not isinstance(world_dict_node, dict):
            world_dict_node = final_config['world_dict_config'] = json.loads(json.dumps(DEFAULT_WORLD_DICT_CONFIG))
        for key, default_value in DEFAULT_WORLD_DICT_CONFIG.items():
            world_dict_node.setdefault(key, default_value)

        # 对 translate_config 进行检查和填充默认值 (现在是 Gemini 的配置)
        translate_node = final_config.setdefault('translate_config', {})
        if not isinstance(translate_node, dict):
            translate_node = final_config['translate_config'] = json.loads(json.dumps(DEFAULT_TRANSLATE_CONFIG))
        # 确保所有新的默认键都存在
        for key, default_value in DEFAULT_TRANSLATE_CONFIG.items():
             # 特殊处理字典和列表类型的默认值，确保它们至少是空的，而不是 None
            if isinstance(default_value, dict):
                translate_node.setdefault(key, {})
                 # 如果加载的值不是字典，则用默认字典覆盖
                if not isinstance(translate_node[key], dict):
                    translate_node[key] = json.loads(json.dumps(default_value))
                else: # 如果是字典，再确保内部默认键存在 (仅针对 generation_config 示例)
                     if key == "generation_config":
                         for sub_key, sub_default in default_value.items():
                             translate_node[key].setdefault(sub_key, sub_default)
            elif isinstance(default_value, list):
                 translate_node.setdefault(key, [])
                 # 如果加载的值不是列表，用默认列表覆盖
                 if not isinstance(translate_node[key], list):
                      translate_node[key] = json.loads(json.dumps(default_value))
            else:
                 translate_node.setdefault(key, default_value)


        # 对 pro_mode_settings 进行检查和填充默认值 (保持不变)
        pro_node = final_config.setdefault('pro_mode_settings', {})
        if not isinstance(pro_node, dict):
            pro_node = final_config['pro_mode_settings'] = json.loads(json.dumps(DEFAULT_PRO_MODE_SETTINGS))
        else:
            rtp_node = pro_node.setdefault('rtp_options', {})
            if not isinstance(rtp_node, dict):
                 rtp_node = pro_node['rtp_options'] = json.loads(json.dumps(DEFAULT_PRO_MODE_SETTINGS['rtp_options']))
            for key, default_value in DEFAULT_PRO_MODE_SETTINGS['rtp_options'].items():
                rtp_node.setdefault(key, default_value)
        for key, default_value in DEFAULT_PRO_MODE_SETTINGS.items():
             if key != 'rtp_options':
                 pro_node.setdefault(key, default_value)

        # 确保顶层 selected_mode 存在
        final_config.setdefault('selected_mode', DEFAULT_CONFIG['selected_mode'])

        return final_config

    def save_config(self, config_data):
        """
        将当前的配置数据保存到文件。

        Args:
            config_data (dict): 要保存的配置字典。
        """
        try:
            config_dir = os.path.dirname(self.config_file_path)
            if config_dir and not os.path.exists(config_dir):
                 file_system.ensure_dir_exists(config_dir)

            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            log.info(f"配置已成功保存到: {self.config_file_path}")
            return True
        except (IOError, TypeError) as e:
            log.exception(f"保存配置到 {self.config_file_path} 失败: {e}")
            return False
