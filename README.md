# AI Short Drama Director Tools / AI短剧视频导演工具集

Seedance 2.0、Kling v3 Omni 视频生成 + Gemini 图片生成的 OpenCode Skills 工具集。

将中文短剧剧本自动解析为分镜脚本，改写为英文 cinematic prompt，生成场景图，调用 API 批量生成视频。

## 包含工具

| Skill | 用途 | 核心能力 |
|-------|------|---------|
| **seedance-short-drama-director** | Seedance 2.0 视频生成 | asset://虚拟人物、场景图、链式fan-out、LLM prompt改写 |
| **kling-short-drama-director** | Kling v3 Omni 视频生成 | JWT认证、text2video、image2video、multi-image2video |
| **ai-image-generation** | Gemini 图片生成 | text-to-image、batch批量生成、尺寸/分辨率控制 |
| **image-skill-builder** | 图片Skill构建器 | 交互式问答创建自定义批量生图Skill，支持风格模板 |

## 功能特性

- 🎬 **剧本解析** — 自动将中文短剧拆解为结构化分镜
- ✍️ **Prompt改写** — 通过LLM将中文描述改写为英文cinematic prompt
- 🎭 **人物一致性** — Seedance支持asset://虚拟人物预设，Kling支持多图参考
- 🏠 **场景一致性** — 通过场景概念图作为reference_image保证场景连贯
- 🔗 **链式视频延伸** — 锚点text-to-video + 串行chain fan-out，每段引用前一段视频
- 🗣️ **中文对白** — prompt中保留中文原文，生成视频自带中文语音
- 🖼️ **场景图生成** — 通过Gemini生成电影感场景概念图
- 🔧 **自定义生图Skill** — 交互式创建任意场景的批量生图工具

## 安装

### 前置要求

- Python 3.10+
- OpenCode (用于skill加载)
- API账号（按需）：BytePlus ModelArk、Kling AI、Google Gemini

### 1. 克隆仓库

```bash
git clone https://github.com/aidai524/ai-short-drama-tools.git
cd ai-short-drama-tools
```

### 2. 安装Skill

将需要的skill链接到OpenCode skills目录：

```bash
# 视频生成
ln -s $(pwd)/seedance-short-drama-director ~/.config/opencode/skills/
ln -s $(pwd)/kling-short-drama-director ~/.config/opencode/skills/

# 图片生成
ln -s $(pwd)/ai-image-generation ~/.config/opencode/skills/
ln -s $(pwd)/image-skill-builder ~/.config/opencode/skills/
```

### 3. 配置环境变量

#### Seedance 2.0

```bash
export ARK_API_KEY="your-api-key"
export ARK_SEEDANCE_MODEL="ep-xxxxx"
export ARK_DOUBAO_MODEL="ep-xxxxx"    # 可选，用于LLM prompt改写
```

#### Kling v3 Omni

```bash
export KLING_ACCESS_KEY="your-access-key"
export KLING_SECRET_KEY="your-secret-key"
export KLING_API_BASE="https://api-beijing.klingai.com"
export KLING_MODEL="kling-v3-omni"
```

#### 图片生成 (Gemini)

```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

### 4. 安装Python依赖

```bash
pip install requests
```

## 使用方法

### Seedance — 完整Pipeline

```bash
python seedance-short-drama-director/seedance_cli.py run \
  -i script.txt -a asset_map.json -o ./output -r 9:16
```

### Kling — 完整Pipeline

```bash
python kling-short-drama-director/kling_cli.py run \
  -i script.txt -o ./output -r 9:16
```

### 图片生成

```bash
python image-skill-builder/scripts/generate_image.py \
  --prompt "cinematic hotel suite bedroom" \
  --output scene.png --aspect-ratio "9:16" --resolution "2K"
```

### 在OpenCode中使用

安装skill后，在对话中直接触发：

- `seedance视频` / `生成视频` → Seedance skill
- `kling视频` / `可灵视频` → Kling skill
- `生成图片` / `generate image` → ai-image-generation skill
- `创建生图Skill` / `帮我做配图技能` → image-skill-builder skill

## 虚拟人物配置 (Seedance)

在Seedance后台「虚拟人物库」中创建角色，获取asset ID：

```json
{
  "角色名": "asset-20260225014926-vdnsx"
}
```

## 项目结构

```
ai-short-drama-tools/
├── README.md
├── LICENSE
├── seedance-short-drama-director/
│   ├── SKILL.md
│   ├── seedance_cli.py
│   └── references/prompt_guide.md
├── kling-short-drama-director/
│   ├── SKILL.md
│   └── kling_cli.py
├── ai-image-generation/
│   └── SKILL.md
├── image-skill-builder/
│   ├── SKILL.md
│   ├── scripts/generate_image.py
│   ├── references/skill-template.md
│   └── references/style-library.md
└── examples/
    └── ep01_v2_generate.py
```

## License

MIT
