# AI Short Drama Director Tools / AI短剧视频导演工具集

Seedance 2.0 和 Kling v3 Omni 的短剧视频生成 OpenCode Skills。

将中文短剧剧本自动解析为分镜脚本，改写为英文 cinematic prompt，调用 API 批量生成视频。

## 包含工具

| Skill | 模型 | 说明 |
|-------|------|------|
| **seedance-short-drama-director** | Seedance 2.0 (BytePlus) | 支持虚拟人物asset://、场景图、锚点+fan-out延伸、LLM prompt改写 |
| **kling-short-drama-director** | Kling v3 Omni | JWT认证、text2video、image2video、multi-image2video、视频延伸 |

## 功能特性

- 🎬 **剧本解析** — 自动将中文短剧拆解为结构化分镜
- ✍️ **Prompt改写** — 通过LLM将中文描述改写为英文cinematic prompt
- 🎭 **人物一致性** — Seedance支持asset://虚拟人物预设，Kling支持多图参考
- 🏠 **场景一致性** — 通过场景概念图作为reference_image保证场景连贯
- 🔗 **视频延伸** — 锚点text-to-video + fan-out video-extension保证镜头衔接
- 🗣️ **中文对白** — prompt中保留中文原文，生成视频自带中文语音

## 安装

### 前置要求

- Python 3.10+
- OpenCode (用于skill加载)
- API账号：BytePlus ModelArk (Seedance) 或 Kling AI

### 1. 克隆仓库

```bash
git clone https://github.com/YOUR_USERNAME/ai-short-drama-tools.git
```

### 2. 安装Skill

将需要的skill链接到OpenCode skills目录：

```bash
# 安装全部
ln -s $(pwd)/seedance-short-drama-director ~/.config/opencode/skills/
ln -s $(pwd)/kling-short-drama-director ~/.config/opencode/skills/

# 或者只安装其中一个
ln -s $(pwd)/seedance-short-drama-director ~/.config/opencode/skills/
```

### 3. 配置环境变量

#### Seedance 2.0

```bash
# 必需
export ARK_API_KEY="your-api-key"
export ARK_SEEDANCE_MODEL="ep-xxxxx"  # Seedance 2.0 endpoint ID

# 可选（用于LLM prompt改写）
export ARK_DOUBAO_MODEL="ep-xxxxx"    # Doubao model endpoint ID
```

#### Kling v3 Omni

```bash
# 必需
export KLING_ACCESS_KEY="your-access-key"
export KLING_SECRET_KEY="your-secret-key"
export KLING_API_BASE="https://api-beijing.klingai.com"  # 中国区
export KLING_MODEL="kling-v3-omni"

# 可选（用于LLM prompt改写）
export ARK_API_KEY="your-ark-api-key"
```

### 4. 安装Python依赖

```bash
pip install requests
```

## 使用方法

### Seedance — 完整Pipeline

```bash
python seedance-short-drama-director/seedance_cli.py run \
  -i script.txt \
  -a asset_map.json \
  -o ./output \
  -r 9:16
```

### Seedance — 分步执行

```bash
# 1. 解析剧本
python seedance-short-drama-director/seedance_cli.py parse -i script.txt -o ./output

# 2. 改写prompt
python seedance-short-drama-director/seedance_cli.py rewrite -i ./output/parsed_segments.json -o ./output

# 3. 构建API payload
python seedance-short-drama-director/seedance_cli.py build \
  -p ./output/parsed_segments.json \
  --prompts ./output/prompt.txt \
  -o ./output

# 4. 提交生成
python seedance-short-drama-director/seedance_cli.py submit -p ./output/payload.json -o ./output
```

### Kling — 完整Pipeline

```bash
python kling-short-drama-director/kling_cli.py run \
  -i script.txt \
  -o ./output \
  -r 9:16
```

### 在OpenCode中使用

安装skill后，在对话中直接触发：

- `seedance视频` / `生成视频` / `/seedance` → 触发Seedance skill
- `kling视频` / `可灵视频` / `/kling` → 触发Kling skill

## 虚拟人物配置 (Seedance)

在Seedance后台「虚拟人物库」中创建角色，获取asset ID，然后在调用时通过asset_map传入：

```json
{
  "苏佳佳": "asset-20260225014926-vdnsx",
  "程世忠": "asset-20260225015021-bkztc"
}
```

## 项目结构

```
ai-short-drama-tools/
├── README.md
├── LICENSE
├── seedance-short-drama-director/
│   ├── SKILL.md              # OpenCode skill定义
│   ├── seedance_cli.py       # CLI工具 (1433行)
│   └── references/
│       └── prompt_guide.md   # Prompt工程指南
└── kling-short-drama-director/
    ├── SKILL.md              # OpenCode skill定义
    └── kling_cli.py          # CLI工具 (1430行)
```

## API参考

### Seedance 2.0 API
- Endpoint: `POST /api/v3/contents/generations/tasks`
- 文档: https://docs.byteplus.com/en/docs/ModelArk/

### Kling v3 Omni API
- Endpoint: `POST /v1/videos/image2video` (单图)
- Endpoint: `POST /v1/videos/multi-image2video` (多图)
- 文档: https://klingai.com/document-api/

## License

MIT
