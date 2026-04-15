---
name: seedance-short-drama-director
description: |
  基于 Seedance 2.0 API 的短剧视频导演工具。自动解析中文短剧脚本（口语化/结构化），改写为英文 prompt，调用 API 生成视频。
  Short drama video director powered by Seedance 2.0 API. Auto-parse Chinese scripts, rewrite to English prompts, generate cinematic videos.
  触发词 Triggers: "生成视频", "短剧视频", "seedance", "generate video", "short drama", "视频导演", "/video", "/drama"
---

# Seedance Short Drama Director / 短剧视频导演

把你的中文短剧脚本自动转成 Seedance 2.0 视频。支持口语化和结构化两种输入格式。

---

## 工作流程 / Workflow

当用户想生成短剧视频时，按以下步骤执行：

### Step 1: 收集素材

确认用户提供以下内容（缺什么问什么）：

1. **脚本**（必需）— 口语化或结构化格式
2. **素材映射文件** `asset_map.json`（如有 @引用 则必需）
3. **输出目录**（默认 `./seedance_output`）
4. **画面比例**（默认 `16:9`，竖屏短视频用 `9:16`）

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

使用 `seedance_cli.py` 执行完整流程：

```bash
python3 {SKILL_DIR}/seedance_cli.py run \
  -i script.txt \
  -a asset_map.json \
  -o ./seedance_output \
  -m "$ARK_SEEDANCE_MODEL" \
  -r 16:9
```

或分步执行：

```bash
# 1. 解析脚本
python3 {SKILL_DIR}/seedance_cli.py parse -i script.txt -a asset_map.json -o ./output

# 2. 查看解析结果，确认无误后改写 prompt
python3 {SKILL_DIR}/seedance_cli.py rewrite -i ./output/parsed_segments.json -o ./output

# 3. 查看 prompt，确认后构建 payload
python3 {SKILL_DIR}/seedance_cli.py build -p ./output/parsed_segments.json --prompts ./output/prompt.txt -o ./output

# 4. 提交任务并下载
python3 {SKILL_DIR}/seedance_cli.py submit -p ./output/payload.json -o ./output
```

### Step 4: 汇报结果

告知用户：
- 生成多少段视频
- 每段的模式（first_last_frame / first_frame / text_to_video）
- 保存路径
- 如有失败段落，列出原因

---

## 输入格式 / Input Formats

### 格式一：口语化

```
首帧：@tea_01
尾帧：@tea_02
@girl_01 为女主，20岁长发穿白裙
场景：咖啡店

分镜1：
女主推开咖啡店的门走进来，环顾四周
阳光透过玻璃窗洒在她身上

分镜2：
她看到角落里坐着一个人
她心里想：这个男生好帅啊

分镜3：
女主鼓起勇气走到男主面前
"你好，请问这里有人坐吗？"
```

### 格式二：结构化

```
画面风格：电影质感，暖色调，浅景深
<location>咖啡店</location>
<role ref="@girl_01">女主，20岁长发穿白裙</role>

分镜1<duration-ms>6000</duration-ms>
<first-frame>@tea_01</first-frame>
女主推开咖啡店的门走进来，环顾四周

分镜2<duration-ms>5000</duration-ms>
她看到角落里坐着一个人
她心里想：这个男生好帅啊

分镜3<duration-ms>8000</duration-ms>
<last-frame>@tea_02</last-frame>
女主走到男主面前，微笑着说：
"你好，请问这里有人坐吗？"
```

---

## 环境变量 / Environment Variables

| 变量 | 必需 | 说明 |
|------|------|------|
| `ARK_API_KEY` | ✅ | BytePlus ModelArk API Key |
| `ARK_SEEDANCE_MODEL` | ✅ | Seedance 2.0 端点 ID（如 `ep-xxxxx`） |
| `ARK_DOUBAO_MODEL` | ⚠️ | 豆包 LLM 端点 ID（用于 prompt 改写，不设则用规则改写） |
| `ARK_CONCURRENCY` | 可选 | 最大并发数（默认 3） |
| `ARK_DEFAULT_RATIO` | 可选 | 默认画面比例（默认 `16:9`） |

首次使用时检查环境：

```bash
python3 {SKILL_DIR}/seedance_cli.py status
```

---

## 输出文件 / Output Files

| 文件 | 说明 |
|------|------|
| `parsed_segments.json` | 解析后的结构化分镜数据 |
| `prompt.txt` | 改写后的英文 prompt（分段用 `---` 分隔） |
| `prompts.json` | 结构化的 prompt 数据（原文 + 改写） |
| `payload.json` | Seedance 2.0 API 请求 payload |
| `task_result.json` | 任务执行结果（含视频 URL） |
| `segment_000.mp4` ~ `segment_NNN.mp4` | 下载的视频文件 |

---

## 视频模式自动检测

| 条件 | 模式 | role 设置 |
|------|------|-----------|
| 有首帧 + 尾帧 | `first_last_frame` | `first_frame` + `last_frame` |
| 只有首帧 | `first_frame` | `first_frame` |
| 无图片 | `text_to_video` | 无图片 content |

- **全局首帧** → 自动应用到第 1 段
- **全局尾帧** → 自动应用到末段
- **分段帧** → 用 XML 标签在结构化格式中指定

---

## Prompt 改写规则

脚本自动处理以下转换（通过豆包 LLM 或规则 fallback）：

1. **中文 → 英文**：全文翻译
2. **心里想 → silent internal monologue**：明确标注角色不能张嘴
3. **连续性约束**：每段自动追加 `same outfit, same hairstyle, same location layout, same lighting`
4. **电影语言**：添加摄影机运动、镜头类型描述
5. **动作细节**：将抽象情感转化为可见动作

详细的 prompt 工程参考见 `references/prompt_guide.md`。

---

## 常见问题 / FAQ

### Q: 首次使用怎么配置？
```bash
export ARK_API_KEY="your-api-key"
export ARK_SEEDANCE_MODEL="ep-xxxxx"
export ARK_DOUBAO_MODEL="ep-xxxxx"  # 可选
python3 {SKILL_DIR}/seedance_cli.py status  # 验证
```

### Q: 视频时长有限制吗？
4-15 秒。短剧建议每段 5-8 秒。

### Q: 支持什么比例？
21:9, 16:9, 4:3, 1:1, 3:4, 9:16。抖音/竖屏用 9:16。

### Q: 没有 Doubao 模型怎么办？
不影响核心功能。Prompt 会用基础规则改写（翻译效果较粗糙）。强烈建议配置以获得最佳效果。

### Q: 并发数怎么选？
个人 BytePlus 账户：最多 3。企业账户：最多 10。用 `ARK_CONCURRENCY` 环境变量调整。
