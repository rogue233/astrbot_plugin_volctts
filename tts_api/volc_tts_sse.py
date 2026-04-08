import base64
import json
import uuid
from typing import Optional

import aiohttp
from astrbot.api import logger


VOLC_TTS_SSE_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse"


async def volc_tts_sse_bytes(
    *,
    appid: str,
    access_token: str,
    resource_id: str,
    speaker: str,
    text: str,
    audio_format: str,
    sample_rate: int,
    speed_ratio: int = 0,
    loudness_rate: int = 0,
    additions: Optional[dict] = None,
) -> bytes:
    """
    调用火山 V3 TTS SSE，拼接音频chunk，返回音频bytes。
    audio_format: "wav" / "mp3" 等（按火山支持为准）
    """
    headers = {
        "X-Api-App-Id": appid,
        "X-Api-Access-Key": access_token,
        "X-Api-Resource-Id": resource_id,
        "Content-Type": "application/json",
        "Connection": "keep-alive",
    }

    additions_payload = additions or {
        "explicit_language": "zh-cn",
        "disable_markdown_filter": True
    }
    additions_json_str = json.dumps(additions_payload, ensure_ascii=False)

    payload = {
        "user": {"uid": str(uuid.uuid4())},
        "req_params": {
            "text": text,
            "speaker": speaker,
            "audio_params": {
                "format": audio_format,
                "sample_rate": sample_rate,
                "speech_rate": speed_ratio,
                "loudness_rate": loudness_rate
            },
            "additions": additions_json_str,
        },
    }

    audio_data = bytearray()
    async with aiohttp.ClientSession() as session:
        async with session.post(VOLC_TTS_SSE_URL, headers=headers, json=payload) as resp:
            if resp.status != 200:
                detail = await resp.text()
                logger.error(f"VolcTTS HTTP {resp.status}: {detail}")
                raise RuntimeError(f"VolcTTS请求失败: {resp.status}")

            async for line in resp.content:
                if not line:
                    continue
                line_str = line.decode("utf-8", errors="ignore").strip()
                if not line_str.startswith("data:"):
                    continue

                data_str = line_str[len("data:"):].strip()
                if not data_str:
                    continue

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                code = data.get("code")
                if code == 0 and data.get("data"):
                    try:
                        audio_data.extend(base64.b64decode(data["data"]))
                    except Exception:
                        continue
                elif code == 20000000:
                    break
                elif code not in (None, 0, 20000000):
                    # 其他错误码：尽早报错
                    raise RuntimeError(f"VolcTTS返回错误: {data}")

    if not audio_data:
        raise RuntimeError("VolcTTS无音频数据返回")
    return bytes(audio_data)
