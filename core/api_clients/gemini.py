# core/api_clients/gemini.py
import logging
from google import genai
# 导入 types 用于配置 (虽然可以直接用字典，但保留导入以备未来可能需要显式类型)
from google.genai import types
from google.api_core import exceptions as google_exceptions

log = logging.getLogger(__name__)

class GeminiClient:
    """封装与 Google Gemini API (新版 google-genai SDK) 的交互。"""

    def __init__(self, api_key):
        """
        初始化 Gemini 客户端 (新版 google-genai SDK)。

        Args:
            api_key (str): Google AI Studio 的 API Key。

        Raises:
            ValueError: 如果 API Key 为空。
            ConnectionError: 如果客户端初始化失败。
        """
        if not api_key:
            raise ValueError("API Key 不能为空。")
        self.api_key = api_key
        try:
            # 使用 Client 类初始化，显式传递 API Key
            # 新 SDK 不再需要 genai.configure()
            self.client = genai.Client(api_key=self.api_key)
            log.info("Gemini API Client (google-genai SDK) 初始化成功。")
        except Exception as e:
            log.exception(f"初始化 Gemini API Client 失败: {e}")
            raise ConnectionError(f"初始化 Gemini API Client 失败: {e}") from e

    def generate_content(self, model_name, prompt, generation_config=None, safety_settings=None):
        """
        调用 Gemini API 生成内容 (新版 google-genai SDK)。

        Args:
            model_name (str): 要使用的模型名称 (例如 "gemini-1.5-pro-latest", "gemini-2.5-flash-preview-04-17")。
                                SDK 通常不需要 "models/" 前缀，但 API 可能需要，Client 会处理。
            prompt (str or list): 发送给模型的完整提示 (作为 contents)。可以是字符串或内容列表。
            generation_config (dict, optional): 生成参数字典 (如 temperature, max_output_tokens)。
                                                例如: {"temperature": 0.7, "max_output_tokens": 8192}
            safety_settings (list[dict], optional): 安全设置列表，每个元素是字典。
                                                例如: [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]

        Returns:
            tuple: (success, result_text, error_message)
                   success (bool): API 调用是否成功并获得有效响应。
                   result_text (str): 如果成功，返回模型生成的文本；否则为 None。
                   error_message (str): 如果失败，返回错误信息；否则为 None。
        """
        if not model_name:
            return False, None, "模型名称不能为空。"
        if not prompt:
            return False, None, "Prompt (contents) 不能为空。"

        # 准备传递给 API 的 config 字典
        api_config_params = {}
        if generation_config:
            api_config_params.update(generation_config)
            log.debug(f"使用 generation_config 参数: {generation_config}")

        if safety_settings:
            # safety_settings 也是 config 的一部分
            api_config_params['safety_settings'] = safety_settings
            log.debug(f"使用 safety_settings 参数: {safety_settings}")

        try:
            log.debug(f"向 Gemini 模型 '{model_name}' (新 SDK) 发送请求...")

            # 使用 client.models.generate_content
            response = self.client.models.generate_content(
                model=model_name,       # 模型名称作为参数
                contents=prompt,        # Prompt 作为 contents 参数
                # 将包含 generation 和 safety 设置的字典传给 config
                # 如果字典为空，则不传递 config 参数
                config=api_config_params if api_config_params else None
            )

            # --- 响应处理 ---
            # 检查 Prompt Feedback 是否有 Block Reason
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                reason = response.prompt_feedback.block_reason.name # 获取枚举名称
                error_msg = f"Gemini API 请求被阻止 (Prompt Feedback): {reason}"
                log.error(error_msg)
                # 记录详细的安全评分
                for rating in response.prompt_feedback.safety_ratings:
                     log.error(f"  - 安全类别: {rating.category.name}, 概率: {rating.probability.name}")
                return False, None, error_msg

            # 检查 Candidates 是否存在以及是否有 Block Reason
            # （有时 prompt_feedback 可能没有 block，但 candidate 被 block）
            if response.candidates:
                 candidate = response.candidates[0] # 通常只关心第一个 candidate
                 if candidate.finish_reason.name not in ('STOP', 'MAX_TOKENS'): # 其他原因都视为异常
                     reason = candidate.finish_reason.name
                     # 检查是否有安全相关的阻止
                     if reason == 'SAFETY':
                          safety_ratings_details = " | ".join([f"{r.category.name}: {r.probability.name}" for r in candidate.safety_ratings])
                          error_msg = f"Gemini API 响应被阻止 (Candidate Finish Reason): SAFETY. Ratings: [{safety_ratings_details}]"
                          log.error(error_msg)
                          return False, None, error_msg
                     else: # 其他非正常停止原因
                          error_msg = f"Gemini API 响应提前终止 (Candidate Finish Reason): {reason}"
                          log.warning(error_msg)
                          # 这种情况可能仍有部分文本，但我们视作失败
                          return False, None, error_msg

                 # 如果正常停止，检查是否有文本
                 if hasattr(candidate, 'content') and candidate.content.parts:
                      # 尝试从 parts 拼接文本，因为 response.text 可能不存在或不完整
                      result_text = "".join(part.text for part in candidate.content.parts if hasattr(part, 'text'))
                      if result_text:
                          log.debug("Gemini API (新 SDK) 成功返回文本响应。")
                          return True, result_text, None

            # 兼容旧的检查：直接看 response.text (可能在新版中不太可靠，优先看 candidate)
            if hasattr(response, 'text') and response.text:
                log.debug("Gemini API (新 SDK) 成功返回文本响应 (via response.text)。")
                return True, response.text, None

            # 如果所有检查都未返回有效文本
            finish_reason_str = "未知"
            if response.candidates:
                 finish_reason_str = response.candidates[0].finish_reason.name

            error_msg = f"Gemini API 调用成功，但未返回有效文本内容。完成原因: {finish_reason_str}"
            log.warning(error_msg)
            # 记录完整的响应对象以供调试（可能很大，只记录部分信息或类型）
            log.debug(f"完整响应对象类型: {type(response)}")
            # log.debug(f"响应详情 (部分): {str(response)[:500]}") # 注意可能泄露信息
            return False, None, error_msg

        # --- 异常处理 (保持不变，核心 API 错误类型可能类似) ---
        except google_exceptions.InvalidArgument as e:
            error_msg = f"Gemini API 参数错误 (新 SDK): {e}"
            log.error(error_msg)
            return False, None, error_msg
        except google_exceptions.PermissionDenied as e:
            error_msg = f"Gemini API 权限错误 (检查 API Key?) (新 SDK): {e}"
            log.error(error_msg)
            return False, None, error_msg
        except google_exceptions.ResourceExhausted as e:
            error_msg = f"Gemini API 资源耗尽 (检查配额?) (新 SDK): {e}"
            log.error(error_msg)
            # 这里可以考虑加入自动重试或等待逻辑
            return False, None, error_msg
        except google_exceptions.GoogleAPIError as e:
            # 捕获更通用的 Google API 错误
            error_msg = f"Gemini API 调用失败 (GoogleAPIError) (新 SDK): {e}"
            log.exception(error_msg)
            return False, None, error_msg
        except Exception as e:
            # 捕获其他所有意外错误
            error_msg = f"与 Gemini API (新 SDK) 交互时发生意外错误: {e}"
            log.exception(error_msg)
            return False, None, error_msg

    def count_tokens(self, model_name, contents):
        """
        使用 Gemini API 统计 Token 数量 (新版 google-genai SDK)。

        Args:
            model_name (str): 要使用的模型名称 (例如 "gemini-1.5-pro-latest")。
            contents (str or list): 需要计算 Token 的文本或内容列表。

        Returns:
            int: 估算的 Token 数量。如果 API 调用失败，返回基于字符数的粗略估计。
                 返回 -1 表示估算彻底失败。
        """
        if not model_name or not contents:
            return 0

        try:
            # 新 SDK count_tokens 可能不需要 'models/' 前缀，但加上通常也兼容
            # 为了保险起见，确保有前缀
            # if not model_name.startswith("models/"):
            #     model_ref = f"models/{model_name}"
            # else:
            #     model_ref = model_name
            # 更新：根据文档示例，直接使用模型名字符串即可，Client 会处理
            model_ref = model_name

            log.debug(f"向 Gemini 模型 '{model_ref}' 请求计算 Tokens...")
            response = self.client.models.count_tokens(model=model_ref, contents=contents)
            log.debug(f"计算 Tokens 成功，数量: {response.total_tokens}")
            return response.total_tokens
        except google_exceptions.GoogleAPIError as e:
             log.error(f"调用 Gemini count_tokens API 失败 (GoogleAPIError): {e}")
        except Exception as e:
            log.error(f"调用 Gemini count_tokens API 时发生意外错误: {e}")

        # API 调用失败，进行粗略估算
        try:
            if isinstance(contents, str):
                # 简单估算：假设 2 个字符约等于 1 个 Token (对 CJK 语言可能偏低)
                estimated_tokens = len(contents) // 2 + (len(contents) % 2)
                log.warning(f"Token 计算 API 调用失败，回退到基于字符数的粗略估算: {estimated_tokens} tokens")
                return estimated_tokens
            elif isinstance(contents, list):
                 total_len = 0
                 for part in contents:
                      if isinstance(part, str):
                           total_len += len(part)
                      # 假设是 ContentDict 格式
                      elif isinstance(part, dict) and 'parts' in part:
                           for sub_part in part['parts']:
                                if isinstance(sub_part, str):
                                     total_len += len(sub_part)
                                elif isinstance(sub_part, dict) and 'text' in sub_part:
                                     total_len += len(sub_part['text'])
                                # 可以扩展处理其他类型的 part (如 fileData)
                      # 假设是简单的 PartDict 格式
                      elif isinstance(part, dict) and 'text' in part:
                           total_len += len(part['text'])
                 estimated_tokens = total_len // 2 + (total_len % 2)
                 log.warning(f"Token 计算 API 调用失败，回退到基于字符数的粗略估算: {estimated_tokens} tokens")
                 return estimated_tokens
            else:
                 log.error("Token 计算 API 调用失败，且无法对输入内容进行字符估算。")
                 return -1 # 表示估算失败
        except Exception as fallback_err:
            log.error(f"Token 计算回退估算时也发生错误: {fallback_err}")
            return -1 # 表示估算失败


    def test_connection(self, model_name):
        """
        尝试与 Gemini API (新版 google-genai SDK) 进行简单的连接测试。

        Args:
            model_name (str): 用于测试的模型名称。

        Returns:
            tuple: (success, message)
                   success (bool): 连接测试是否成功。
                   message (str): 测试结果或错误信息。
        """
        log.info(f"测试与 Gemini API (新 SDK, 模型: {model_name}) 的连接...")
        # 使用简单的 Prompt 和默认配置进行测试
        # 不传递 generation_config 和 safety_settings 以简化测试
        success, text, error = self.generate_content(
            model_name=model_name,
            prompt="你好，请确认你能正常工作。"
        )
        if success and text:
            msg = f"Gemini API (新 SDK, 模型: {model_name}) 连接测试成功！"
            log.info(msg)
            return True, msg
        elif error:
            msg = f"Gemini API (新 SDK, 模型: {model_name}) 连接测试失败: {error}"
            log.error(msg)
            return False, msg
        else:
            # 这种情况可能是 API 调用成功但返回空文本
            msg = f"Gemini API (新 SDK, 模型: {model_name}) 连接测试失败: 未收到有效响应或响应为空。"
            log.error(msg)
            return False, msg