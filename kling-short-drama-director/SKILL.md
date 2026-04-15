---
name: kling-short-drama-director
description: |
  基于 Kling AI v3 Omni API 的短剧视频导演工具。自动解析中文短剧脚本（口语化/结构化），改写为英文 prompt，调用 Kling API 生成视频。
  支持主体一致性（subject reference）、视频延伸（extend video）、多镜头分镜（最多6个镜头）。
  Short drama video director powered by Kling v3 Omni API. Auto-parse Chinese scripts, rewrite to English prompts, generate cinematic videos.
  触发词 Triggers: "kling视频", "可灵视频", "生成视频", "kling", "generate video", "short drama", "/kling", "/kvideo"
---

# Kling Short Drama Director / 可灵短剧视频导演

把你的中文短剧脚本自动转成 Kling v3 Omni 视频。支持口语化和结构化两种输入格式。

**相比 Seedance 的优势**：
- 🎭 **主体一致性**：Kling v3 支持主体上传，跨镜头保持人物外观一致
- 🎬 **多镜头分镜**：单次生成最多 6 个镜头的场景转换
- 🔊 **原生音视频同步**：支持多说话人、多语言（含口音）
- 📐 **视频延伸**：从已有视频延伸后续内容

---

## 工作流程 / Workflow

当用户想生成短剧视频时，按以下步骤执行：

### Step 1: 收集素材

确认用户提供以下内容（缺什么问什么）：

1. **脚本**（必需）— 口语化或结构化格式
2. **素材映射文件** `asset_map.json`（如有 @引用 则必需）
3. **输出目录**（默认 `./kling_output`）
4. **画面比例**（默认 `9:16`，横屏用 `16:9`）

### Step 2: 准备 asset_map.json

如果用户提供了素材 ID 但没有 asset_map.json，帮用户创建。格式：

```json
{
  "@tea_01": "https://example.com/tea1.jpg",
  "@tea_02": "https://example.com/tea2.jpg",
  "@girl_01": "https://example.com/girl.png"
}
```

保存到工作目录后继续。

### Step 3: 执行生成

使用 `kling_cli.py` 执行完整流程：

```bash
python3 {SKILL_DIR}/kling_cli.py run \
  -i script.txt \
  -a asset_map.json \
  -o ./kling_output \
  -r 9:16
```

或分步执行：

```bash
# 1. 解析脚本
python3 {SKILL_DIR}/kling_cli.py parse -i script.txt -a asset_map.json -o ./output

# 2. 查看解析结果，确认无误后改写 prompt
python3 {SKILL_DIR}/kling_cli.py rewrite -i ./output/parsed_segments.json -o ./output

# 3. 查看 prompt，确认后构建 payload
python3 {SKILL_DIR}/kling_cli.py build -p ./output/parsed_segments.json --prompts ./output/prompt.txt -o ./output

# 4. 提交任务并下载
python3 {SKILL_DIR}/kling_cli.py submit -p ./output/payload.json -o ./output
```

### Step 4: 汇报结果

告知用户：
- 生成多少段视频
- 每段的模式（text_to_video / image_to_video / extend_video）
- 保存路径
- 如有失败段落，列出原因

---

## 输入格式 / Input Formats

与 Seedance skill 完全相同的口语化和结构化两种格式。详见 Seedance skill 文档。

---

## 环境变量 / Environment Variables

| 变量 | 必需 | 说明 |
|------|------|------|
| `KLING_ACCESS_KEY` | ✅ | Kling API Access Key |
| `KLING_SECRET_KEY` | ✅ | Kling API Secret Key |
| `KLING_MODEL` | 可选 | 模型名称（默认 `kling-v3-omni`） |
| `KLING_MODE` | 可选 | 生成模式 std/pro（默认 `std`） |
| `KLING_API_BASE` | 可选 | API 基础 URL（默认全球站） |
| `KLING_DEFAULT_RATIO` | 可选 | 默认画面比例（默认 `9:16`） |
| `KLING_DEFAULT_DURATION` | 可选 | 默认时长 "5" 或 "10"（默认 `"10"`） |
| `ARK_API_KEY` | ⚠️ | Doubao LLM API Key（用于 prompt 改写） |
| `ARK_DOUBAO_MODEL` | ⚠️ | Doubao 模型端点 ID（不设则用规则改写） |
| `ARK_CONCURRENCY` | 可选 | 最大并发数（默认 3） |

首次使用时检查环境：

```bash
python3 {SKILL_DIR}/kling_cli.py status
```

---

## Kling vs Seedance 差异

| 特性 | Seedance 2.0 | Kling v3 Omni |
|------|-------------|---------------|
| 认证 | 固定 API Key | JWT (access_key + secret_key) |
| 时长 | 4-15秒整数 | "5" 或 "10"（字符串） |
| 主体一致性 | 不支持（需视频延伸） | ✅ 支持主体上传 |
| 多镜头 | 不支持 | ✅ 最多6个镜头 |
| 音频生成 | generate_audio 参数 | 原生音视频同步 |
| 视频延伸 | reference_video role | extend-video endpoint |
| 模式 | 无 | std（标准）/ pro（高质量） |

---

## 输出文件 / Output Files

| 文件 | 说明 |
|------|------|
| `parsed_segments.json` | 解析后的结构化分镜数据 |
| `prompt.txt` | 改写后的英文 prompt（分段用 `---` 分隔） |
| `prompts.json` | 结构化的 prompt 数据（原文 + 改写） |
| `payload.json` | Kling API 请求 payload |
| `task_result.json` | 任务执行结果（含视频 URL） |
| `segment_000.mp4` ~ `segment_NNN.mp4` | 下载的视频文件 |

---

## 视频模式自动检测

| 条件 | 模式 | 参数设置 |
|------|------|---------|
| 有首帧图 | `image_to_video` | `image` 字段传图片 URL |
| 无图片 | `text_to_video` | 无图片字段 |
| 有前置视频 | `extend_video` | `video` 字段传视频 URL |

- **全局首帧** → 自动应用到第 1 段
- **全局尾帧** → 自动应用到末段
- **分段帧** → 用 XML 标签在结构化格式中指定

---

## Prompt 改写规则

与 Seedance skill 相同的改写规则（通过 Doubao LLM 或规则 fallback）：

1. **中文对白保留原文**，镜头描述用英文
2. **心里想 → silent internal monologue**：明确标注角色不能张嘴
3. **连续性约束**：每段自动追加一致性后缀
4. **电影语言**：添加摄影机运动、镜头类型描述
5. **动作细节**：将抽象情感转化为可见动作
6. **末尾追加**："所有角色对白使用中文普通话"

---

## 常见问题 / FAQ

### Q: 首次使用怎么配置？
```bash
export KLING_ACCESS_KEY="your-access-key"
export KLING_SECRET_KEY="your-secret-key"
# 可选：prompt 改写
export ARK_API_KEY="your-ark-api-key"
export ARK_DOUBAO_MODEL="your-doubao-endpoint"
python3 {SKILL_DIR}/kling_cli.py status  # 验证
```

### Q: 视频时长有限制吗？
Kling v3 Omni 支持每段 "5" 或 "10" 秒。通过视频延伸可拼接更长内容。

### Q: 支持什么比例？
16:9, 9:16, 1:1, 4:3, 3:4, 21:9。抖音/竖屏用 9:16。

### Q: std 和 pro 模式区别？
- **std**：标准质量，生成更快，成本更低
- **pro**：更高质量，细节更丰富，但耗时更长

### Q: 如何保证人物一致性？
Kling v3 的核心优势：
1. 使用**主体上传**功能（image2video + subject reference）
2. 使用**视频延伸**从锚点视频延续
3. 使用**多镜头分镜**在单次生成中保持一致

### Q: 需要 PyJWT 吗？
是的，Kling 使用 JWT 认证。安装：`pip install PyJWT requests`
