# Seedance 2.0 Prompt Engineering Guide

## Camera Movements

| Chinese | English | Description |
|---------|---------|-------------|
| 推近 | push-in / dolly in | Camera moves closer to subject |
| 拉远 | pull-out / dolly out | Camera moves away from subject |
| 平移 | pan left/right | Camera rotates horizontally |
| 俯仰 | tilt up/down | Camera rotates vertically |
| 跟拍 | tracking shot | Camera follows moving subject |
| 环绕 | orbit / arc shot | Camera circles around subject |
| 升降 | crane up/down | Vertical camera movement |
| 手持 | handheld | Shaky, documentary feel |
| 稳定器 | stabilized / gimbal | Smooth, fluid movement |

## Shot Types

| Chinese | English |
|---------|---------|
| 特写 | extreme close-up (ECU) |
| 近景 | close-up (CU) |
| 中近景 | medium close-up (MCU) |
| 中景 | medium shot (MS) |
| 中远景 | medium long shot (MLS) |
| 远景 | wide shot (WS) / long shot (LS) |
| 大远景 | extreme wide shot (EWS) |
| 过肩镜头 | over-the-shoulder shot (OTS) |
| 主观镜头 | POV shot / first-person |
| 鸟瞰 | bird's eye view / top-down |
| 低角度 | low angle shot |
| 高角度 | high angle shot |
| 荷兰角 | Dutch angle / tilted frame |

## Lighting

| Chinese | English |
|---------|---------|
| 自然光 | natural lighting |
| 逆光 | backlit / rim lighting |
| 侧光 | side lighting |
| 顶光 | overhead lighting |
| 柔光 | soft lighting / diffused |
| 硬光 | hard lighting / direct |
| 暖光 | warm lighting / golden hour |
| 冷光 | cool lighting / blue tone |
| 霓虹灯 | neon lighting |
| 烛光 | candlelight |

## Internal Monologue Handling

When a character is thinking (心里想 / 内心独白):

```
❌ She thinks about how handsome he is.

✅ Silent internal monologue, her lips remain firmly closed, 
   a contemplative expression crosses her face, eyes slightly 
   unfocused in thought, a subtle smile forming at the corners 
   of her mouth.
```

Key constraints:
- Character MUST NOT move their lips
- Express thought through: eye movement, micro-expressions, posture
- Never show speaking or mouth movement

## Continuity Constraints

Every segment prompt should include:
```
Maintain strict visual continuity: same outfit, same hairstyle,
same location layout, same lighting, direct continuity with 
previous/next segment.
```

## Prompt Structure Template

```
[Camera setup] of [subject] in [location], [action description], 
[emotion/expression], [lighting], [time of day], [mood/atmosphere].
[Transition cue]. [Continuity note].
```

Example:
```
Medium shot of a young woman in a white dress standing in a 
sunlit coffee shop, she slowly turns her head toward the camera, 
a gentle smile appearing on her face, warm golden afternoon 
light streaming through the windows, cozy and romantic atmosphere.
The scene begins with her looking down at her coffee cup, then 
she looks up and notices someone. Maintain strict visual continuity: 
same outfit, same hairstyle, same location layout, same lighting.
```

## Dialogue Formatting

Spoken dialogue:
```
She says aloud with a warm smile: "Hello, is anyone sitting here?"
Her voice is gentle and slightly nervous, she tucks a strand of 
hair behind her ear while speaking.
```

Whispered dialogue:
```
She leans in close and whispers, barely audible: "I think he's 
watching us." Her eyes dart nervously to the side.
```

Shouted dialogue:
```
He raises his voice, standing up abruptly: "That's not what I said!"
His jaw clenches, fists balling at his sides.
```

## Aspect Ratio Guidelines

| Ratio | Best For |
|-------|----------|
| 21:9 | Cinematic widescreen, establishing shots |
| 16:9 | Standard video, YouTube, most scenes |
| 4:3 | Classic film look, intimate scenes |
| 1:1 | Social media (Instagram) |
| 3:4 | Portrait video, mobile-first |
| 9:16 | Vertical video, TikTok/Douyin, Stories |

## Duration Guidelines

| Duration | Suitable For |
|----------|-------------|
| 4-5s | Single action, simple transition |
| 6-8s | Standard scene, dialogue exchange |
| 9-12s | Complex scene, multiple actions |
| 13-15s | Extended scene, dramatic sequence |
