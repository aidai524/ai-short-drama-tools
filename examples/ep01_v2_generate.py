#!/usr/bin/env python3
"""
Episode 1 v2 - Video Generation with Virtual Character Assets (asset://)
使用Seedance 2.0虚拟人物库保证角色一致性

Changes from v1:
- 每个镜头的content中加入出场人物的asset://引用
- prompt中使用 "the character from Image N" 引用
- 同场景内确保人物穿着一致（在prompt中固定描述）
- 使用generate_audio=True（需要语音）

Usage:
    python ep01_v2_generate.py              # Full pipeline
    python ep01_v2_generate.py --rewrite-only  # Only rewrite prompts
    python ep01_v2_generate.py --generate-only # Only generate videos
    python ep01_v2_generate.py --test-one 1-1-01  # Generate single shot
"""

import base64
import json
import os
import sys
import time
from pathlib import Path

SKILL_DIR = os.path.expanduser("~/.config/opencode/skills/seedance-short-drama-director")
sys.path.insert(0, SKILL_DIR)
from seedance_cli import (
    ArkClient, PromptRewriter, PayloadBuilder, TaskManager,
    DEFAULT_SEEDANCE_MODEL, DEFAULT_DOUBAO_MODEL, DEFAULT_RATIO, DEFAULT_DURATION_MS,
    CONTINUITY_SUFFIX
)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ep01_v2_output")
SCENE_IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "场景图")

SCENE_IMAGE_MAP = {
    1: "酒店套房_1.png",
    2: "酒店套房_1.png",
    3: "酒店套房走廊_0.png",
    4: "酒店宴会厅_1.png",
    5: "酒店走廊_1.png",
}


def scene_image_to_data_uri(scene_num):
    img_file = SCENE_IMAGE_MAP.get(scene_num)
    if not img_file:
        return None
    img_path = os.path.join(SCENE_IMG_DIR, img_file)
    if not os.path.isfile(img_path):
        print(f"  ⚠️  Scene image not found: {img_path}")
        return None
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"

# ═══════════════════════════════════════════════════════════════
# VIRTUAL CHARACTER ASSETS (虚拟人物库)
# ═══════════════════════════════════════════════════════════════

CHARACTERS = {
    "苏佳佳": {
        "asset_id": "asset-20260225014926-vdnsx",
        "asset_uri": "asset://asset-20260225014926-vdnsx",
        "description": "Su Jiajia, young Asian woman, light blue cotton nurse uniform, black low ponytail, white nurse shoes",
        "scene_outfits": {
            # 全剧统一穿着：浅蓝护士服
            "default": "light blue cotton nurse uniform, neat black low ponytail, plain white nurse shoes",
        }
    },
    "程远": {
        "asset_id": "asset-20260410114236-8cdfz",
        "asset_uri": "asset://asset-20260410114236-8cdfz",
        "description": "Cheng Yuan, 28 year old Asian man",
        "scene_outfits": {
            "default": "dark grey tailored suit, crisp white shirt, navy necktie",
        }
    },
    "江止风": {
        "asset_id": "asset-20260225015015-n4gk2",
        "asset_uri": "asset://asset-20260225015015-n4gk2",
        "description": "Jiang Zhifeng, young Asian woman, intelligent and composed",
        "scene_outfits": {
            "default": "simple light-coloured elegant dress",
        }
    },
    "何巧兰": {
        "asset_id": "asset-20260225023540-qvn6l",
        "asset_uri": "asset://asset-20260225023540-qvn6l",
        "description": "He Qiaolan, 52 year old Asian woman",
        "scene_outfits": {
            "default": "emerald green heavy silk dress, polished jade bangle on right wrist, neat black short hair",
        }
    },
    "程世忠": {
        "asset_id": "asset-20260225015021-bkztc",
        "asset_uri": "asset://asset-20260225015021-bkztc",
        "description": "Cheng Shizhong, middle-aged Asian man",
        "scene_outfits": {
            "default": "dark formal suit, middle-aged",
        }
    },
}


def build_character_content(characters_in_scene):
    """
    为出场人物构建content数组中的image_url条目。
    返回 list of content items (每个含asset://引用)。
    """
    content_items = []
    for char_name in characters_in_scene:
        char = CHARACTERS.get(char_name)
        if char and char["asset_uri"]:
            content_items.append({
                "type": "image_url",
                "image_url": {"url": char["asset_uri"]},
                "role": "reference_image",
            })
    return content_items


def build_character_prompt_prefix(characters_in_scene):
    """
    构建prompt中的人物引用前缀。
    例如: "The character from Image 1 (Su Jiajia) ... The character from Image 2 (Cheng Shizhong) ..."
    """
    parts = []
    image_idx = 1
    for char_name in characters_in_scene:
        char = CHARACTERS.get(char_name)
        if char and char["asset_uri"]:
            outfit = char["scene_outfits"].get("default", char["description"])
            parts.append(f"Image {image_idx} = {char_name} wearing {outfit}")
            image_idx += 1
        else:
            # 没有asset的角色，纯文字描述
            outfit = char["scene_outfits"].get("default", char["description"]) if char else ""
            parts.append(f"{char_name} wearing {outfit} (text description only, no reference image)")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# SEGMENT DEFINITIONS - All 22 shots with character mapping
# ═══════════════════════════════════════════════════════════════

SEGMENTS = [
    # ── Scene 1: Hotel Suite (前生·撞破奸情) ──────────────
    {
        "id": "1-1-01", "scene": 1, "is_anchor": True, "duration": 15,
        "characters": ["苏佳佳", "程世忠"],
        "chinese": (
            "高档酒店套房内，暖黄色灯光昏暗暧昧。苏佳佳穿着浅蓝色棉质护士服，黑色低马尾，白色护士鞋，"
            "背靠墙壁。程世忠穿着深色西装，整个人贴在她身上，面带猥琐笑容，贪婪地嗅着她颈侧。"
            "房间内有双人床、茶几、半掩的窗帘。\n"
            "程世忠（眯眼沉醉，贪婪嗅着）：佳佳，你真香。\n"
            "苏佳佳（面色潮红，假意推拒）：世忠叔，你猴急什么，今天可是家宴，楼下那么多亲戚朋友都在，我们这样，太刺激了吧~"
        ),
    },
    {
        "id": "1-1-02", "scene": 1, "is_anchor": False, "duration": 12,
        "characters": ["苏佳佳", "程世忠"],
        "chinese": (
            "程世忠轻抚苏佳佳脸颊，表情急不可耐。随后一把将苏佳佳抱起，摔在床上，俯身压了上去。"
            "苏佳佳发出一声轻呼。两人穿着与上一镜头完全一致。\n"
            "程世忠：放心，他们都在喝酒，没人上来，宝贝，我可想死你了。\n"
            "床铺发出沉闷的声响。"
        ),
    },
    {
        "id": "1-1-03", "scene": 1, "is_anchor": False, "duration": 15,
        "characters": ["江止风"],
        "chinese": (
            "画面切到床底视角——镜头从床沿缓慢下移，进入床底黑暗空间。床底阴影中，赫然可见一个人蜷缩着——"
            "江止风（年轻知性女性，浅色连衣裙）。她紧紧捂住自己的嘴，眼睛因惊恐而瞪大，面色苍白。"
            "透过床单缝隙能看到上方床铺在震动。\n"
            "环境音：心跳声加速、床板轻微吱呀声。\n"
            "江止风内心独白（不张嘴）：我刚刚在楼下弄湿衣服想换一下，却没想到走错了房间，还刚好撞上公公和月嫂的奸情？不行，我必须揭穿这两个狗男女的真面目！"
        ),
    },
    {
        "id": "1-1-04", "scene": 1, "is_anchor": False, "duration": 10,
        "characters": ["江止风", "程世忠", "苏佳佳"],
        "chinese": (
            "江止风从床底爬出，猛地站起身，手指直指床上的两人，表情愤怒厉声怒斥。"
            "程世忠和苏佳佳吓得魂飞魄散，手忙脚乱扯衣服遮挡。\n"
            "江止风（厉声）：爸！苏佳佳！你们在干什么！"
        ),
    },
    {
        "id": "1-1-05", "scene": 1, "is_anchor": False, "duration": 15,
        "characters": ["苏佳佳", "江止风"],
        "chinese": (
            "苏佳佳率先反应，恼羞成怒地站起身，反咬一口指着江止风。"
            "江止风抱着胳膊冷笑，毫不退缩。两人正面交锋，面对面怒视。\n"
            "苏佳佳（恼羞成怒）：江止风！谁让你乱闯的？要不要脸！\n"
            "江止风（冷笑）：我不要脸？苏佳佳，你搞清楚，你一个月嫂，居然敢和我公公厮混在一起，不要脸的人，是你吧！"
        ),
    },
    {
        "id": "1-1-06", "scene": 1, "is_anchor": False, "duration": 15,
        "characters": ["江止风", "程世忠"],
        "chinese": (
            "江止风转头看向程世忠，眼神凌厉质问。程世忠慌乱失措，双手不停摆动极力掩饰。"
            "江止风嗤笑一声，转身大步走向门口。\n"
            "江止风（转头）：还有你，爸，你这样做，对得起妈吗？\n"
            "程世忠：止风，误会，全是误会！\n"
            "江止风：误会？我亲眼所见，别想狡辩！我现在就去告诉妈！"
        ),
    },
    {
        "id": "1-1-07", "scene": 1, "is_anchor": False, "duration": 15,
        "characters": ["江止风", "苏佳佳"],
        "chinese": (
            "江止风转身冲向门口，苏佳佳疯了般从床上弹起，冲上去死死拽住江止风的手臂。"
            "两人激烈撕扯推搡。突然，苏佳佳狠命猛推一把——江止风脚下打滑，身体失控后仰，"
            "后脑重重砸在茶几尖角上。慢动作：鲜血从发间涌出。\n"
            "苏佳佳（嘶吼）：你不能去！\n"
            "江止风（挣扎）：放开我！我必须揭发你们！\n"
            "【音效】沉闷的撞击声"
        ),
    },
    {
        "id": "1-1-08", "scene": 1, "is_anchor": False, "duration": 12,
        "characters": ["江止风", "程世忠", "苏佳佳"],
        "chinese": (
            "江止风躺在地上，头发散开，后脑下蔓延着鲜血。她的眼神逐渐涣散，嘴唇微微开合。"
            "程世忠站在一旁呆若木鸡，苏佳佳捂住嘴惊恐后退。画面逐渐失焦变暗至全黑。\n"
            "江止风（气息微弱）：苏佳......佳，程世忠，如果有来生......我一定不会放过你们......\n"
            "【音效】心跳声逐渐减弱→归于寂静→画面全黑"
        ),
    },
    # ── Scene 2: Hotel Suite (重生·暗中潜伏) ──────────────
    {
        "id": "1-1-09", "scene": 2, "is_anchor": True, "duration": 10,
        "characters": ["江止风"],
        "chinese": (
            "全黑画面→一双眼睛猛然睁开，瞳孔剧烈收缩。镜头缓慢拉远："
            "江止风（浅色连衣裙）蜷缩在床底，浑身微微颤抖，惊恐地打量四周。"
            "与场景一相同的酒店套房，暖色灯光。\n"
            "江止风（惊恐低语）：我不是死了吗？这里是哪里？"
        ),
    },
    {
        "id": "1-1-10", "scene": 2, "is_anchor": False, "duration": 12,
        "characters": ["江止风"],
        "chinese": (
            "镜头缓慢扫过酒店套房环境——暖色灯光、大床、茶几、半掩窗帘。"
            "江止风从床底向上看，床板在头顶轻微震动。她的表情从惊恐变为不敢置信，再到激动。\n"
            "江止风（激动低语）：是苏佳佳和程世忠偷情的那间套房卧室，我重生了！一切还来得及！"
        ),
    },
    {
        "id": "1-1-11", "scene": 2, "is_anchor": False, "duration": 10,
        "characters": ["江止风"],
        "chinese": (
            "江止风的面部特写：她的眼神从迷茫变为坚定，默默握紧拳头。"
            "透过床单缝隙，上方的灯光摇曳。\n"
            "江止风内心独白（不张嘴，表情坚定）：这一世，我一定不能冲动，苏佳佳，程世忠，你们的好日子，就要到头了！"
        ),
    },
    {
        "id": "1-1-12", "scene": 2, "is_anchor": False, "duration": 12,
        "characters": ["江止风"],
        "chinese": (
            "江止风趁床上两人不注意，悄悄从床底爬出，蹑手蹑脚弓着腰走向房门。"
            "她轻轻按下门把手，无声地溜了出去。\n"
            "【音效】地板轻微吱呀声、呼吸压抑声"
        ),
    },
    {
        "id": "1-1-13", "scene": 2, "is_anchor": False, "duration": 15,
        "characters": ["苏佳佳", "程世忠"],
        "chinese": (
            "苏佳佳（浅蓝护士服）突然停住动作，侧耳倾听，脸上浮现疑虑。"
            "她轻推程世忠，低声询问。程世忠四下扫视，没发现异常，松了口气继续拥抱苏佳佳。\n"
            "苏佳佳（疑惑）：世忠叔，你刚刚有没有听见什么动静，房间里，好像有人？\n"
            "程世忠：佳佳，你就是神经太紧张了，放心，门都从里面锁好了，不会有人的，快继续让我抱抱~\n"
            "苏佳佳（面色一红，轻打他胸膛）：讨厌~"
        ),
    },
    # ── Scene 3: Hotel Corridor (布局·抛杯引众) ───────────
    {
        "id": "1-2-01", "scene": 3, "is_anchor": True, "duration": 15,
        "characters": ["江止风"],
        "chinese": (
            "江止风（浅色连衣裙）溜出房门，随手从走廊边桌上摸来一个透明玻璃水杯。"
            "她走到走廊栏杆处，向下俯瞰——楼下宴会厅里宾客满座，觥筹交错，欢声笑语。"
            "她的眼眸逐渐眯起，嘴角微微勾起一抹冷笑。\n"
            "江止风内心独白（不张嘴）：苏佳佳，程世忠，准备迎接我的报复吧！\n"
            "【环境音】楼下的宴会嘈杂声"
        ),
    },
    {
        "id": "1-2-02", "scene": 3, "is_anchor": False, "duration": 10,
        "characters": ["江止风"],
        "chinese": (
            "江止风猛然将水杯从栏杆缝隙扔下去！镜头跟随水杯坠落——穿过中空的天井直坠而下，"
            "重重砸在楼下宴会厅人群中间的地面上，碎片四溅！\n"
            "【音效】玻璃杯坠落的风声→清脆的碎裂声！"
        ),
    },
    # ── Scene 4: Hotel Banquet Hall ─────────────────────────
    {
        "id": "1-3-01", "scene": 4, "is_anchor": True, "duration": 15,
        "characters": ["何巧兰", "程远"],
        "chinese": (
            "宴会厅内，碎玻璃散落在地面上，所有人的目光被吸引。"
            "何巧兰（52岁亚洲女性，祖母绿色重磅真丝连衣裙，翡翠玉镯，黑色短发）从主桌站起，"
            "看着碎裂的杯子，抬头怒视楼上方向。"
            "程远（28岁亚洲男性，深灰色西装，白衬衫，藏青色领带）快步走来。\n"
            "何巧兰（气愤）：这是谁干的？好端端的宴会都被毁了，是谁？\n"
            "程远（不满）：妈，这摆明了有人想要毁了这次家宴，不能这么放过他，我们现在就去楼上，把人抓住！"
        ),
    },
    # ── Scene 5: Hotel Corridor (高潮·奸情败露) ──────────
    {
        "id": "1-4-01", "scene": 5, "is_anchor": True, "duration": 12,
        "characters": ["何巧兰", "程远"],
        "chinese": (
            "何巧兰（祖母绿连衣裙，翡翠玉镯，黑色短发）双手掐腰、神色凶狠地走在酒店走廊最前面，"
            "程远（深灰西装）紧随其后，后面跟着一群亲戚。众人来到走廊上。\n"
            "何巧兰（怒喝）：刚刚是谁往楼下扔的杯子，破坏了家宴，快点给老娘滚出来！\n"
            "程远（严肃）：别躲躲藏藏，敢做不敢当是吗？"
        ),
    },
    {
        "id": "1-4-02", "scene": 5, "is_anchor": False, "duration": 12,
        "characters": ["江止风", "程远"],
        "chinese": (
            "江止风（浅色连衣裙）从走廊尽头缓步走来，表情茫然无辜，像是什么都不知道。"
            "程远看到她，语气急切。\n"
            "江止风（无辜状）：妈，程远，出什么事了？\n"
            "程远（气愤）：止风你来的正好，刚才有人在宴会上闹事，我们正准备来捉人。"
        ),
    },
    {
        "id": "1-4-03", "scene": 5, "is_anchor": False, "duration": 15,
        "characters": ["何巧兰", "江止风"],
        "chinese": (
            "众人正在走廊交谈时，紧闭的套房门内突然传出刺耳的暧昧声响！"
            "众人脸色骤变——何巧兰皱眉怒喝，亲戚甲（酒红色连衣裙，灰色开衫，珍珠项链）捂嘴议论，"
            "程远表情尴尬。江止风站在人群中，嘴角不易察觉地微微上扬。\n"
            "【音效】套房内传出的暧昧声响\n"
            "何巧兰（怒喝）：什么声音？太不要脸了！\n"
            "亲戚甲：大白天做这种事，简直败坏门风！\n"
            "江止风内心独白（不张嘴，嘴角微勾）：鱼儿上钩了，该收网了！"
        ),
    },
    {
        "id": "1-4-04", "scene": 5, "is_anchor": False, "duration": 15,
        "characters": ["江止风", "何巧兰"],
        "chinese": (
            "江止风故作狐疑地开口，引导话题。何巧兰一愣，不满地反问。"
            "江止风急忙摇头否认，表情无辜。何巧兰穿着祖母绿连衣裙，翡翠玉镯。\n"
            "江止风（故作疑惑）：奇怪……家宴这么长时间，怎么一直没看见爸和佳佳？\n"
            "何巧兰（不满）：江止风，你这是什么意思？难道你是想说这房间里的人，是世忠和佳佳吗？\n"
            "江止风（急忙摇头）：不是不是，我只是好奇这么久不见他们的人影，担心他们是不是出事了。"
        ),
    },
    {
        "id": "1-4-05", "scene": 5, "is_anchor": False, "duration": 12,
        "characters": ["江止风", "何巧兰"],
        "chinese": (
            "房间里动静越来越大，江止风故意提高音量说话。她侧耳做倾听状，脸上浮现若有若无的笑意。"
            "何巧兰的表情逐渐变化——从愤怒到狐疑，到难以置信。\n"
            "江止风（故意大声）：咦，我怎么听着，这个男人的声线，跟爸好像啊。"
        ),
    },
    {
        "id": "1-4-06", "scene": 5, "is_anchor": False, "duration": 10,
        "characters": ["何巧兰", "江止风"],
        "chinese": (
            "何巧兰瞬间暴怒——眼睛瞪圆，面部肌肉扭曲，猛然扬起手朝江止风扇去！"
            "江止风微微偏头但并未闪避。镜头定格在巴掌落下前一帧。\n"
            "何巧兰（暴怒嘶吼）：小贱人！你敢污蔑你爸，我打死你！\n"
            "【音效】尖锐的巴掌声"
        ),
    },
]


# ═══════════════════════════════════════════════════════════════
# PROMPT REWRITER (with character asset awareness)
# ═══════════════════════════════════════════════════════════════

CHARACTER_AWARE_SYSTEM_PROMPT = """You are a professional video prompt writer for Seedance 2.0, a cinematic AI video generator by ByteDance.

Your task is to rewrite Chinese drama scripts into prompts that produce high-quality, cinematic video.

## CRITICAL RULES:

1. **CHARACTER REFERENCES (MOST IMPORTANT)**:
   - The prompt will include "Image N = CharacterName wearing ..." mappings at the top.
   - You MUST refer to characters using "the character from Image N" or simply the character name.
   - DO NOT describe facial features in detail - the asset image already defines the face.
   - DO describe outfit, hairstyle, and accessories to reinforce consistency.
   - For characters WITHOUT an image (no asset), describe them textually in the prompt.

2. **LANGUAGE POLICY**:
   - ALL character dialogue (spoken lines) MUST remain in the ORIGINAL Chinese text, verbatim. Do NOT translate any dialogue to English.
   - Camera directions, shot descriptions, lighting, and visual descriptions should be in English.
   - End every prompt with: "所有角色对白使用中文普通话 (All character dialogue must be spoken in Mandarin Chinese)."

3. **OUTFIT CONSISTENCY (CRITICAL)**:
   - Within the same scene, a character's outfit MUST remain identical across ALL segments.
   - Explicitly state "wearing the exact same [outfit] as described" in every segment for each character.
   - If a character's outfit changes due to plot, state the new outfit clearly.

4. **Be extremely visual** — describe only what the CAMERA can see.
5. **Cinematic language**: use terms like "close-up shot", "wide shot", "tracking shot", etc.
6. **Internal monologue**: ALWAYS rewrite as: "silent internal monologue, the character's lips remain firmly closed, contemplative expression" followed by thought content in Chinese.
7. **Dialogue**: clearly mark with character name + "says aloud in Mandarin:"
8. **Present tense** throughout.
9. **Keep each segment focused** on a single shot/scene.

## OUTPUT FORMAT:
Return ONLY the prompt text. No explanations, no markdown formatting, no preamble."""


def phase_rewrite(client, force=False):
    """Rewrite all 22 segments with character-aware prompts."""
    print("\n" + "=" * 60)
    print("  Phase 1/4: Rewriting prompts (Chinese → English)")
    print("  with character asset references")
    print("=" * 60)

    prompts_path = os.path.join(OUTPUT_DIR, "prompts.json")
    if os.path.exists(prompts_path) and not force:
        print("  ↳ Loading existing prompts...")
        with open(prompts_path, "r", encoding="utf-8") as f:
            prompts = json.load(f)
        if len(prompts) == len(SEGMENTS):
            print(f"  ✅ Loaded {len(prompts)} existing prompts")
            return [p["rewritten"] if isinstance(p, dict) else p for p in prompts]

    rewriter = PromptRewriter(client)
    prompts = []
    total = len(SEGMENTS)

    for i, seg in enumerate(SEGMENTS):
        # Build character reference prefix
        char_prefix = build_character_prompt_prefix(seg["characters"])
        
        # Build context from adjacent segments
        ctx_parts = []
        if i > 0:
            ctx_parts.append(f"Previous shot ({SEGMENTS[i-1]['id']}): ...{SEGMENTS[i-1]['chinese'][-120:]}")
        if i < total - 1:
            ctx_parts.append(f"Next shot ({SEGMENTS[i+1]['id']}): {SEGMENTS[i+1]['chinese'][:120]}...")
        context = "; ".join(ctx_parts)

        # Compose full input
        user_content = f"[Character Reference Images]:\n{char_prefix}\n\n"
        if context:
            user_content += f"[Adjacent context]: {context}\n\n"
        user_content += f"[Segment to rewrite]:\n{seg['chinese']}"

        try:
            result = client.chat_completion(
                model=DEFAULT_DOUBAO_MODEL,
                messages=[
                    {"role": "system", "content": CHARACTER_AWARE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.7,
            )
            prompt = result
        except Exception as e:
            print(f"  ⚠️  LLM rewrite failed for {seg['id']}: {e}")
            print("  ↳ Falling back to rule-based rewrite...")
            prompt = PromptRewriter._fallback_rewrite(seg["chinese"])

        prompts.append(prompt)
        print(f"  ✅ [{i+1}/{total}] {seg['id']}: {prompt[:80]}...")

    # Save
    prompts_data = []
    for seg, prompt in zip(SEGMENTS, prompts):
        prompts_data.append({
            "id": seg["id"],
            "scene": seg["scene"],
            "is_anchor": seg["is_anchor"],
            "duration": seg["duration"],
            "characters": seg["characters"],
            "original": seg["chinese"],
            "rewritten": prompt,
        })
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(prompts_path, "w", encoding="utf-8") as f:
        json.dump(prompts_data, f, ensure_ascii=False, indent=2)
    print(f"\n  ✅ Saved {len(prompts)} prompts → {prompts_path}")
    return prompts


def build_segment_content(seg, prompt, is_anchor=True, anchor_scene=None):
    content = []
    
    full_prompt = prompt + CONTINUITY_SUFFIX
    content.append({"type": "text", "text": full_prompt})

    scene_num = seg["scene"]
    if is_anchor:
        scene_uri = scene_image_to_data_uri(scene_num)
        if scene_uri:
            content.append({
                "type": "image_url",
                "image_url": {"url": scene_uri},
                "role": "reference_image",
            })

    for char_name in seg["characters"]:
        char = CHARACTERS.get(char_name)
        if char and char["asset_uri"]:
            content.append({
                "type": "image_url",
                "image_url": {"url": char["asset_uri"]},
                "role": "reference_image",
            })
    
    return content


def phase_submit_anchors(client, prompts):
    """Generate anchor videos for each scene with character assets."""
    print("\n" + "=" * 60)
    print("  Phase 2/4: Generating anchor videos")
    print("  (text-to-video + character assets)")
    print("=" * 60)

    model = DEFAULT_SEEDANCE_MODEL
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Find anchor segments
    anchors = []
    for i, seg in enumerate(SEGMENTS):
        if seg["is_anchor"]:
            anchors.append((i, seg, prompts[i]))

    print(f"  Submitting {len(anchors)} anchor videos...")
    for idx, seg, prompt in anchors:
        char_names = ", ".join(seg["characters"])
        print(f"  📝 {seg['id']}: characters=[{char_names}]")

    # Submit all anchors
    submitted = []
    for idx, seg, prompt in anchors:
        content = build_segment_content(seg, prompt, is_anchor=True)
        payload = {
            "model": model,
            "content": content,
            "ratio": "9:16",
            "duration": seg["duration"],
            "generate_audio": True,
            "return_last_frame": True,
            "watermark": False,
        }
        try:
            result = client.create_video_task(
                model=payload["model"],
                content=payload["content"],
                ratio=payload["ratio"],
                duration=payload["duration"],
                generate_audio=payload["generate_audio"],
                return_last_frame=payload.get("return_last_frame", True),
            )
            task_id = result.get("id", "?")
            print(f"  🚀 {seg['id']}: task_id={task_id}")
            submitted.append({
                "idx": idx, "seg_id": seg["id"], "scene": seg["scene"],
                "task_id": task_id,
            })
        except Exception as e:
            print(f"  ❌ {seg['id']}: {e}")
            submitted.append({
                "idx": idx, "seg_id": seg["id"], "scene": seg["scene"],
                "task_id": None, "error": str(e),
            })

    # Poll all anchors
    print(f"\n  ⏳ Polling {len(submitted)} anchor tasks...")
    results = {}
    for sub in submitted:
        if not sub.get("task_id"):
            results[sub["scene"]] = None
            continue

        task_id = sub["task_id"]
        print(f"  ⏳ Polling {sub['seg_id']} ({task_id[:16]}...)...")
        start = time.time()
        while time.time() - start < 600:
            try:
                r = client.get_task(task_id)
                status = r.get("status", "unknown")
                elapsed = int(time.time() - start)
                if status == "succeeded":
                    content_data = r.get("content", {})
                    video_url = content_data.get("video_url") or r.get("video_url")
                    last_frame_url = content_data.get("last_frame_url")
                    results[sub["scene"]] = {
                        "video_url": video_url,
                        "last_frame_url": last_frame_url,
                        "task_id": task_id,
                    }
                    print(f"  ✅ {sub['seg_id']}: done ({elapsed}s)")
                    break
                elif status in ("failed", "cancelled", "canceled"):
                    error = r.get("error", r.get("message", "unknown"))
                    print(f"  ❌ {sub['seg_id']}: {status} - {error}")
                    results[sub["scene"]] = None
                    break
                else:
                    print(f"  ⏳ {sub['seg_id']}: {status} ({elapsed}s)")
                    time.sleep(30)
            except Exception as e:
                print(f"  ⚠️  Poll error: {e}")
                time.sleep(30)
        else:
            print(f"  ❌ {sub['seg_id']}: timed out")
            results[sub["scene"]] = None

    # Save results
    with open(os.path.join(OUTPUT_DIR, "anchor_results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Download
    print("\n  📥 Downloading anchor videos...")
    for scene, res in results.items():
        if not res or not res.get("video_url"):
            continue
        anchor_seg = next((s for s in SEGMENTS if s["scene"] == scene and s["is_anchor"]), None)
        fname = f"{anchor_seg['id']}.mp4" if anchor_seg else f"scene{scene}_anchor.mp4"
        out_path = os.path.join(OUTPUT_DIR, fname)
        try:
            ArkClient.download_file(res["video_url"], out_path)
            res["local_path"] = out_path
            print(f"  📹 {fname} ({os.path.getsize(out_path) / 1024 / 1024:.1f} MB)")
        except Exception as e:
            print(f"  ⚠️  Download failed: {e}")
        # Last frame
        if res.get("last_frame_url"):
            frame_path = os.path.join(OUTPUT_DIR, f"{anchor_seg['id']}_last_frame.jpg" if anchor_seg else f"scene{scene}_last_frame.jpg")
            try:
                ArkClient.download_file(res["last_frame_url"], frame_path)
                res["last_frame_path"] = frame_path
                print(f"  🖼️  Last frame saved")
            except:
                pass

    return results


def phase_fanout(client, prompts, anchor_results):
    print("\n" + "=" * 60)
    print("  Phase 3/4: Generating fan-out segments (CHAIN mode)")
    print("  Each segment references the PREVIOUS segment's video")
    print("=" * 60)

    model = DEFAULT_SEEDANCE_MODEL

    scenes = {}
    for i, seg in enumerate(SEGMENTS):
        s = seg["scene"]
        if s not in scenes:
            scenes[s] = []
        scenes[s].append((i, seg, prompts[i]))

    fanout_results = []
    chain_video_urls = {}

    for scene_num, segs in scenes.items():
        anchor_info = anchor_results.get(scene_num)
        if not anchor_info or not anchor_info.get("video_url"):
            print(f"  ⚠️  Scene {scene_num}: no anchor video, skipping")
            continue

        prev_video_url = anchor_info["video_url"]
        anchor_seg_id = next((s["id"] for s in segs if s["is_anchor"]), f"scene{scene_num}")
        chain_video_urls[anchor_seg_id] = prev_video_url
        print(f"\n  Scene {scene_num}: anchor={anchor_seg_id}")

        for idx, seg, prompt in segs:
            if seg["is_anchor"]:
                continue

            full_prompt = (
                f"Generate the content that happens AFTER the provided reference video. "
                f"The scene continues seamlessly from where the reference video ends. "
                f"Same characters, same location, same lighting, direct continuity.\n\n"
                f"{prompt}{CONTINUITY_SUFFIX}"
            )

            content = [{"type": "text", "text": full_prompt}]
            content.append({
                "type": "video_url",
                "video_url": {"url": prev_video_url},
                "role": "reference_video",
            })

            scene_uri = scene_image_to_data_uri(seg["scene"])
            if scene_uri:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": scene_uri},
                    "role": "reference_image",
                })

            for char_name in seg["characters"]:
                char = CHARACTERS.get(char_name)
                if char and char["asset_uri"]:
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": char["asset_uri"]},
                        "role": "reference_image",
                    })

            ref_from = anchor_seg_id if prev_video_url == anchor_info["video_url"] else list(chain_video_urls.keys())[-1]
            print(f"  🔗 {seg['id']}: referencing video from [{ref_from}]")

            try:
                result = client.create_video_task(
                    model=model, content=content,
                    ratio="9:16", duration=seg["duration"],
                    generate_audio=True, return_last_frame=True,
                )
                task_id = result.get("id", "?")
            except Exception as e:
                print(f"  ❌ {seg['id']}: submit failed - {e}")
                fanout_results.append({"seg_id": seg["id"], "error": str(e)})
                continue

            print(f"  ⏳ {seg['id']}: polling ({task_id[:16]}...)...")
            seg_result = None
            start = time.time()
            while time.time() - start < 600:
                try:
                    r = client.get_task(task_id)
                    status = r.get("status", "unknown")
                    elapsed = int(time.time() - start)
                    if status == "succeeded":
                        content_data = r.get("content", {})
                        video_url = content_data.get("video_url") or r.get("video_url")
                        last_frame_url = content_data.get("last_frame_url")
                        seg_result = {
                            "seg_id": seg["id"], "video_url": video_url,
                            "last_frame_url": last_frame_url, "task_id": task_id,
                            "referenced_from": ref_from,
                        }
                        out_path = os.path.join(OUTPUT_DIR, f"{seg['id']}.mp4")
                        ArkClient.download_file(video_url, out_path)
                        sz = os.path.getsize(out_path) / 1024 / 1024
                        if last_frame_url:
                            ArkClient.download_file(last_frame_url, os.path.join(OUTPUT_DIR, f"{seg['id']}_last_frame.jpg"))
                        print(f"  ✅ {seg['id']}: done ({elapsed}s, {sz:.1f}MB)")
                        break
                    elif status in ("failed", "cancelled", "canceled"):
                        error = r.get("error", r.get("message", "unknown"))
                        if "AudioSensitive" in str(error):
                            print(f"  ⚠️  {seg['id']}: audio sensitive, retrying without audio...")
                            retry_result = _retry_without_audio(client, model, seg, content, task_id)
                            if retry_result:
                                seg_result = retry_result
                            else:
                                fanout_results.append({"seg_id": seg["id"], "error": str(error)})
                        else:
                            print(f"  ❌ {seg['id']}: {status} - {error}")
                            fanout_results.append({"seg_id": seg["id"], "error": str(error)})
                        break
                    else:
                        if elapsed % 60 == 0:
                            print(f"  ⏳ {seg['id']}: {status} ({elapsed}s)")
                        time.sleep(15)
                except Exception as e:
                    time.sleep(15)
            else:
                print(f"  ❌ {seg['id']}: timeout")
                fanout_results.append({"seg_id": seg["id"], "error": "timeout"})
                continue

            if seg_result:
                fanout_results.append(seg_result)
                prev_video_url = seg_result["video_url"]
                chain_video_urls[seg["id"]] = seg_result["video_url"]

    with open(os.path.join(OUTPUT_DIR, "fanout_results.json"), "w", encoding="utf-8") as f:
        json.dump(fanout_results, f, ensure_ascii=False, indent=2)

    print(f"\n  Chain map:")
    for sid, url in chain_video_urls.items():
        print(f"    {sid} → {url[:50]}...")
    return fanout_results


def _retry_without_audio(client, model, seg, original_content, failed_task_id):
    out_path = os.path.join(OUTPUT_DIR, f"{seg['id']}.mp4")
    try:
        result = client.create_video_task(
            model=model, content=original_content,
            ratio="9:16", duration=seg["duration"],
            generate_audio=False, return_last_frame=True,
        )
        tid = result.get("id", "?")
    except Exception as e:
        print(f"  ❌ {seg['id']}: retry submit failed - {e}")
        return None

    print(f"  ⏳ {seg['id']}: retry polling ({tid[:16]}...)...")
    start = time.time()
    while time.time() - start < 600:
        try:
            r = client.get_task(tid)
            status = r.get("status", "unknown")
            elapsed = int(time.time() - start)
            if status == "succeeded":
                cd = r.get("content", {})
                vu = cd.get("video_url") or r.get("video_url")
                lfu = cd.get("last_frame_url")
                ArkClient.download_file(vu, out_path)
                sz = os.path.getsize(out_path) / 1024 / 1024
                if lfu:
                    ArkClient.download_file(lfu, os.path.join(OUTPUT_DIR, f"{seg['id']}_last_frame.jpg"))
                print(f"  ✅ {seg['id']}: retry done ({elapsed}s, {sz:.1f}MB, no audio)")
                return {
                    "seg_id": seg["id"], "video_url": vu,
                    "last_frame_url": lfu, "task_id": tid,
                    "referenced_from": "retry_no_audio",
                }
            elif status in ("failed", "cancelled", "canceled"):
                err = r.get("error", r.get("message", "unknown"))
                print(f"  ❌ {seg['id']}: retry {status} - {err}")
                return None
            else:
                if elapsed % 60 == 0:
                    print(f"  ⏳ {seg['id']}: retry {status} ({elapsed}s)")
                time.sleep(15)
        except Exception as e:
            time.sleep(15)
    print(f"  ❌ {seg['id']}: retry timeout")
    return None


def generate_single(client, seg_id, prompts):
    """Generate a single shot for testing."""
    seg = next((s for s in SEGMENTS if s["id"] == seg_id), None)
    if not seg:
        print(f"❌ Segment {seg_id} not found")
        return 1
    
    idx = SEGMENTS.index(seg)
    prompt = prompts[idx]
    model = DEFAULT_SEEDANCE_MODEL

    content = build_segment_content(seg, prompt, is_anchor=True)
    char_names = ", ".join(seg["characters"])
    print(f"  📝 {seg['id']}: duration={seg['duration']}s chars=[{char_names}]")
    print(f"  Content items: {len(content)}")
    for ci in content:
        if ci["type"] == "image_url":
            print(f"    - image_url: {ci['image_url']['url'][:60]}... (role={ci['role']})")
        else:
            print(f"    - text: {ci['text'][:80]}...")

    payload = {
        "model": model,
        "content": content,
        "ratio": "9:16",
        "duration": seg["duration"],
        "generate_audio": True,
        "return_last_frame": True,
        "watermark": False,
    }

    print(f"\n  🚀 Submitting {seg_id}...")
    try:
        result = client.create_video_task(
            model=payload["model"], content=payload["content"],
            ratio=payload["ratio"], duration=payload["duration"],
            generate_audio=payload["generate_audio"],
            return_last_frame=payload.get("return_last_frame", True),
        )
        task_id = result.get("id", "?")
        print(f"  ✅ Task submitted: {task_id}")
    except Exception as e:
        print(f"  ❌ Submit failed: {e}")
        return 1

    # Poll
    print(f"\n  ⏳ Polling {task_id}...")
    start = time.time()
    while time.time() - start < 600:
        try:
            r = client.get_task(task_id)
            status = r.get("status", "unknown")
            elapsed = int(time.time() - start)
            if status == "succeeded":
                content_data = r.get("content", {})
                video_url = content_data.get("video_url") or r.get("video_url")
                last_frame_url = content_data.get("last_frame_url")
                print(f"  ✅ Done ({elapsed}s)")
                # Download
                out_path = os.path.join(OUTPUT_DIR, f"{seg_id}.mp4")
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                ArkClient.download_file(video_url, out_path)
                print(f"  📹 Saved: {out_path} ({os.path.getsize(out_path)/1024/1024:.1f} MB)")
                if last_frame_url:
                    frame_path = os.path.join(OUTPUT_DIR, f"{seg_id}_last_frame.jpg")
                    ArkClient.download_file(last_frame_url, frame_path)
                    print(f"  🖼️  Last frame: {frame_path}")
                return 0
            elif status in ("failed", "cancelled", "canceled"):
                error = r.get("error", r.get("message", "unknown"))
                print(f"  ❌ {status}: {error}")
                return 1
            else:
                print(f"  ⏳ {status} ({elapsed}s)")
                time.sleep(30)
        except Exception as e:
            print(f"  ⚠️  Poll error: {e}")
            time.sleep(30)

    print(f"  ❌ Timed out")
    return 1


def phase_summary(anchor_results, fanout_results):
    """Print final summary."""
    print("\n" + "=" * 60)
    print("  SUMMARY - Episode 1 v2 (with Virtual Character Assets)")
    print("=" * 60)
    total = success = failed = 0
    for scene, res in anchor_results.items():
        total += 1
        if res and res.get("video_url"):
            success += 1
        else:
            failed += 1
    for res in fanout_results:
        total += 1
        if res.get("video_url"):
            success += 1
        else:
            failed += 1
    print(f"  Total: {total} | ✅ {success} | ❌ {failed}")
    print(f"  Output: {os.path.abspath(OUTPUT_DIR)}")
    print(f"  Characters used:")
    for name, char in CHARACTERS.items():
        if char["asset_uri"]:
            print(f"    🎭 {name}: {char['asset_uri']}")
        else:
            print(f"    📝 {name}: text description only")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        if f.endswith(".mp4"):
            size = os.path.getsize(os.path.join(OUTPUT_DIR, f)) / 1024 / 1024
            print(f"    📹 {f} ({size:.1f} MB)")
    print("=" * 60)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  Episode 1 v2 - Virtual Character Assets               ║")
    print("║  22 segments | Ratio: 9:16 | Audio: ON                  ║")
    print("║  Characters: 苏佳佳, 程远, 江止风, 何巧兰 (asset://)     ║")
    print("╚═══════════════════════════════════════════════════════════╝")

    # Print character mapping
    print("\n📋 Character Asset Mapping:")
    for name, char in CHARACTERS.items():
        status = f"asset://{char['asset_id']}" if char["asset_id"] else "text-only"
        print(f"  {name}: {status}")

    client = ArkClient()

    # Parse args
    args = sys.argv[1:]
    rewrite_only = "--rewrite-only" in args
    generate_only = "--generate-only" in args
    test_one = None
    if "--test-one" in args:
        idx = args.index("--test-one")
        if idx + 1 < len(args):
            test_one = args[idx + 1]
    force_rewrite = "--force-rewrite" in args

    # Phase 1: Rewrite
    if generate_only:
        prompts_path = os.path.join(OUTPUT_DIR, "prompts.json")
        if not os.path.exists(prompts_path):
            print("❌ No prompts found. Run without --generate-only first.")
            return 1
        with open(prompts_path, "r", encoding="utf-8") as f:
            prompts_data = json.load(f)
        prompts = [p["rewritten"] for p in prompts_data]
        print(f"  Loaded {len(prompts)} existing prompts")
    else:
        prompts = phase_rewrite(client, force=force_rewrite)

    if rewrite_only:
        print("\n✅ Rewrite complete.")
        return 0

    # Test single shot
    if test_one:
        return generate_single(client, test_one, prompts)

    # Phase 2: Anchors
    anchor_results = phase_submit_anchors(client, prompts)

    # Phase 3: Fan-out
    fanout_results = phase_fanout(client, prompts, anchor_results)

    # Phase 4: Summary
    phase_summary(anchor_results, fanout_results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
