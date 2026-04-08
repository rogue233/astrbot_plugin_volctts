import time
from pathlib import Path

from pydantic import Field
from pydantic.dataclasses import dataclass

import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext
from astrbot.core.config import AstrBotConfig
from astrbot.core.provider.entities import LLMResponse
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .tts_api.volc_tts_sse import volc_tts_sse_bytes


@register(
    "astrbot_plugin_volctts",
    "you",
    "火山引擎TTS：LLM工具触发发语音(wav)/发mp3文件",
    "0.1.0",
)
class VolcTTSPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)

        self.enable_tts = bool(config.get("enable_tts", True))
        self.enable_llm_tool = bool(config.get("enable_llm_tool", True))
        self.enable_llm_response = bool(config.get("enable_llm_response", False))

        self.appid = str(config.get("appid") or "")
        self.access_token = str(config.get("access_token") or "")
        self.resource_id = str(config.get("resource_id") or "seed-tts-2.0")
        self.speaker = str(config.get("speaker") or "")

        try:
            self.sample_rate = int(config.get("sample_rate", 24000))
        except Exception:
            self.sample_rate = 24000

        try:
            self.speed_ratio = max(-50, min(100, int(config.get("speed_ratio", 0))))
        except Exception:
            self.speed_ratio = 0

        try:
            self.loudness_rate = max(-50, min(100, int(config.get("loudness_rate", 0))))
        except Exception:
            self.loudness_rate = 0

        try:
            self.max_text_length = max(1, int(config.get("max_text_length", 300)))
        except Exception:
            self.max_text_length = 300

        self.storage_subdir = str(config.get("storage_subdir") or "audio")

        # 插件数据目录（规范路径）
        base = Path(get_astrbot_data_path()) / "plugin_data" / "astrbot_plugin_volctts"
        self.audio_dir = base / self.storage_subdir
        self.audio_dir.mkdir(parents=True, exist_ok=True)

        if self.enable_tts and (not self.appid or not self.access_token or not self.resource_id):
            logger.warning("VolcTTS: appid/access_token/resource_id 未配置完整，工具调用将失败")

        self.context.add_llm_tools(SendVoiceTool(plugin=self))
        self.context.add_llm_tools(SendMp3Tool(plugin=self))

    async def initialize(self):
        logger.info("VolcTTS plugin 已启用")

    async def terminate(self):
        logger.info("VolcTTS plugin 已停用/卸载")

    @filter.on_llm_response()
    async def handle_silence(self, event: AstrMessageEvent, resp: LLMResponse):
        if event.get_extra("voice_silence_mode"):
            event.set_extra("voice_silence_mode", False)
            resp.completion_text = "\u200b"
            event.stop_event()

    def _validate_ready(self):
        if not self.enable_tts:
            raise RuntimeError("插件未启用(enable_tts=false)")
        if not self.enable_llm_tool:
            raise RuntimeError("LLM工具未启用(enable_llm_tool=false)")
        if not self.appid or not self.access_token or not self.resource_id:
            raise RuntimeError("火山凭证未配置完整(appid/access_token/resource_id)")
        if not self.speaker:
            raise RuntimeError("未配置音色speaker（请在插件配置中填写）")

    async def _synth_and_save(self, *, text: str, fmt: str, ext: str) -> Path:
        if not text or not str(text).strip():
            raise RuntimeError("文本不能为空")
        if len(text) > self.max_text_length:
            raise RuntimeError(f"文本过长（>{self.max_text_length}）")

        audio_bytes = await volc_tts_sse_bytes(
            appid=self.appid,
            access_token=self.access_token,
            resource_id=self.resource_id,
            speaker=self.speaker,
            text=text,
            audio_format=fmt,
            sample_rate=self.sample_rate,
            speed_ratio=self.speed_ratio,
            loudness_rate=self.loudness_rate,
        )

        ts = int(time.time() * 1000)
        out = self.audio_dir / f"volctts_{ts}.{ext}"
        out.write_bytes(audio_bytes)
        return out


@dataclass
class SendVoiceTool(FunctionTool[AstrAgentContext]):
    name: str = "send_voice"
    description: str = "将文本合成为语音并发送语音消息（OneBot QQ 推荐wav）。当用户要求你发语音/唱歌/用声音说时调用。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要用语音说出的文本"}
            },
            "required": ["text"]
        }
    )
    plugin: object = Field(default=None, repr=False)

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        try:
            self.plugin._validate_ready()
            text = kwargs.get("text", "")

            wav_path = await self.plugin._synth_and_save(text=text, fmt="wav", ext="wav")

            await context.context.event.send(
                context.context.event.chain_result([Comp.Record(file=str(wav_path), url=str(wav_path))])
            )

            if not self.plugin.enable_llm_response:
                context.context.event.set_extra("voice_silence_mode", True)

            return "SUCCESS"
        except Exception as e:
            logger.error(f"send_voice failed: {e}")
            return f"FAILED: {e}"


@dataclass
class SendMp3Tool(FunctionTool[AstrAgentContext]):
    name: str = "send_mp3"
    description: str = "将文本合成为mp3文件并发送。当用户要求你发mp3文件/导出音频时调用。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要合成到mp3里的文本"},
                "filename": {"type": "string", "description": "可选，自定义文件名（不含路径），例如 hello.mp3"}
            },
            "required": ["text"]
        }
    )
    plugin: object = Field(default=None, repr=False)

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        try:
            self.plugin._validate_ready()
            text = kwargs.get("text", "")
            filename = (kwargs.get("filename") or "").strip()

            mp3_path = await self.plugin._synth_and_save(text=text, fmt="mp3", ext="mp3")

            if filename:
                # 简单清理，避免路径穿越
                filename = filename.replace("/", "_").replace("\\", "_")
                if not filename.lower().endswith(".mp3"):
                    filename += ".mp3"
            else:
                filename = mp3_path.name

            await context.context.event.send(
                context.context.event.chain_result([Comp.File(file=str(mp3_path), name=filename)])
            )

            if not self.plugin.enable_llm_response:
                context.context.event.set_extra("voice_silence_mode", True)

            return "SUCCESS"
        except Exception as e:
            logger.error(f"send_mp3 failed: {e}")
            return f"FAILED: {e}"
