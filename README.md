# 火山语音合成插件 for AstrBot
基于火山引擎 **语音合成 2.0（seed-tts-2.0）** 的 AstrBot 插件。  
支持让智能体通过 **LLM 工具调用** 的方式，主动：
- 发送 **语音消息**
- 发送 **mp3 文件**
  
本插件的设计目标是：
**不依赖固定命令、不依赖关键词正则，而是让模型自己理解“发语音 / 唱一段 / 发mp3”之类的用户需求，然后调用工具。**

## 功能特性
- 支持火山引擎普通语音合成 `seed-tts-2.0`
- 支持 AstrBot LLM Tool / Function Calling
- 支持发送 **QQ 语音消息**（OneBot，推荐 wav）
- 支持发送 **mp3 文件**
- 支持配置“发完音频后是否继续发送文字回复”
- 支持自定义音色、语速、音量、采样率
- 音频文件自动保存到插件数据目录

## 适用环境
- AstrBot `4.22.3`
- 平台适配器：**OneBot QQ**
- Python 插件

## 工作方式
本插件注册了两个工具：
- `send_voice`
- `send_mp3`
当模型理解到用户想让它“发语音”“唱歌”“用声音说”“发 mp3 文件”时，可以自行调用工具。
### `send_voice`
将文本合成为语音，并发送语音消息。
### `send_mp3`
将文本合成为 mp3 文件，并以文件形式发送。


## 安装方式
将插件目录放入：
data/plugins

目录结构示例：
astrbot_plugin_volctts/
├── metadata.yaml
├── requirements.txt
├── _conf_schema.json
├── README.md
├── main.py
└── tts_api/
   └── volc_tts_sse.py
 
安装依赖：
aiohttp
pydantic

## 配置说明
安装后，在 AstrBot 插件配置中填写以下参数：
1. enable_tts
是否启用插件。
类型：bool
默认：true
2. appid
火山引擎语音合成 AppID。
类型：string
必填
3. access_token
火山引擎 Access Token。
类型：string
必填
4. resource_id
火山资源 ID。普通语音合成建议填写：seed-tts-2.0
5. speaker
音色 ID，也就是请求中的 req_params.speaker。
注意：
这里必须填写 和 resource_id 匹配 的音色 ID
如果你填了克隆音色 ID，但 resource_id 用的是普通 TTS，就会报错：resource ID is mismatched with speaker related resource
6. sample_rate
采样率，默认推荐：24000
7. speed_ratio
语速范围：-50 ~ 100
默认 0。
8. loudness_rate
音量范围：-50 ~ 100
默认 0。
9. enable_llm_tool
是否允许 LLM 主动调用工具。建议开启。
10. enable_llm_response
工具发送音频后，是否还保留文字回复。
false：只发语音/文件，不继续发文字
true：音频和文字都会发送
11. max_text_length
单次最大合成文本长度，防止文本过长导致速度慢或费用高。
12. storage_subdir
音频保存子目录。
实际保存路径类似：data/plugin_data/astrbot_plugin_volctts/audio/

## 火山引擎接口说明
本插件使用火山引擎官方 TTS SSE 接口，鉴权方式为：
X-Api-App-Id
X-Api-Access-Key
X-Api-Resource-Id
普通 TTS 使用的 resource_id 为：seed-tts-2.0

## 音频格式说明
语音消息：为了兼容 OneBot QQ，本插件默认让 send_voice 生成 wav 并发送语音消息。

mp3 文件：send_mp3 生成 mp3 文件，并通过文件组件发送。

## 插件数据目录
根据 AstrBot 插件存储规范，大文件保存在：data/plugin_data/astrbot_plugin_volctts/
默认音频子目录：data/plugin_data/astrbot_plugin_volctts/audio/

## LLM 工具说明
工具一：send_voice
说明：将文本合成为语音并发送语音消息。
参数：
text: 要用语音说出的文本
适用场景：
用户要求“发语音”
用户要求“用声音说”
用户要求“唱一段”
用户希望机器人直接语音回复时

工具二：send_mp3
说明：将文本合成为 mp3 文件并发送。
参数：
text: 要合成的文本
filename: 可选，自定义文件名
适用场景：
用户要求“发 mp3”
用户要求“导出音频文件”
用户要求“把这句话做成 mp3 给我”

推荐提示词写法
如果你希望模型更稳定地使用工具，可以在系统提示词或人格提示词中加入类似描述：

  当用户希望你发语音、唱一段、用声音说、来段语音时，优先调用 send_voice 工具。
  当用户希望你发送 mp3 文件、导出音频、生成 mp3 给他时，调用 send_mp3 工具。
  如果已经调用了语音工具，就不要再重复输出同样的文字内容，除非配置允许保留文字回复。


## 常见问题
1. 插件已启用，但模型不调用工具
这不是插件故障，通常是模型本身没有正确理解工具能力。
建议：确认 AstrBot 侧已经启用工具调用，在系统提示词中明确告诉模型何时使用 send_voice 和 send_mp3，使用更擅长 function calling 的模型

3. 报错：resource ID is mismatched with speaker related resource
说明你填写的 speaker 和 resource_id 不匹配。
例如：resource_id = seed-tts-2.0但是speaker 却填了克隆音色 ID
解决方法：
普通 TTS 就使用普通音色库对应的 speaker，不要把克隆音色 ID 填到普通 TTS 资源里

5. 发语音失败，但发 mp3 正常
通常是平台对语音格式要求更严格。本插件已经默认使用 wav 发送语音消息。
如果仍失败，请检查：
OneBot 实现是否支持语音发送
语音文件是否成功写入本地
AstrBot 是否对 Comp.Record 有额外平台要求

4. 发送 mp3 文件失败
请检查：
插件数据目录是否有写入权限
文件是否已生成到：
data/plugin_data/astrbot_plugin_volctts/audio/
OneBot / QQ 侧是否允许发送文件

6. 发完语音后仍然出现文字回复
检查配置项：
enable_llm_response
如果设为 true，音频发出后文字也会保留。
如果希望“只发语音/文件”，请设为 false。



## 已知说明
本插件当前针对 OneBot QQ 优化
语音消息默认走 wav
mp3 走文件发送，不作为语音消息发送
本插件不做关键词/正则触发，只依赖 LLM 工具调用


## 备注
如果后续你购买了火山引擎的音色克隆能力，也可以在此插件基础上扩展为：
普通 TTS
克隆音色 TTS
不同 resource_id 自动切换
不同 speaker 分类管理
当前版本先聚焦于：
普通语音合成 + 智能体自主调用工具发语音 / 发 mp3 文件。
