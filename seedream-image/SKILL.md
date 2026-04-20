---
name: seedream-image
description: Use when generating images with Seedream 5.0 via BytePlus ModelArk API. Supports text-to-image, image-to-image, and batch generation with high quality. Triggers: "seedream", "豆包生图", "字节生图", "BytePlus image", "用seedream生成图片".
---

# Seedream Image Generation (BytePlus ModelArk)

Generate images using BytePlus Seedream 5.0 Lite model via ModelArk API. High quality, supports text-to-image and image-to-image.

## Quick Start

### Environment Setup

```bash
export ARK_API_KEY="<your-api-key>"
```

Get your API key from: [ModelArk API Key Management](https://console.byteplus.com/ark/region:ark+ap-southeast-1/apiKey)

### Text-to-Image (Single)

```bash
curl -s -X POST https://ark.ap-southeast.bytepluses.com/api/v3/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -d '{
    "model": "seedream-5-0-260128",
    "prompt": "A serene Japanese garden in autumn, golden maple leaves, stone pathway, morning mist, photorealistic, 8K",
    "sequential_image_generation": "disabled",
    "response_format": "b64_json",
    "size": "2K",
    "stream": false,
    "watermark": false,
    "output_format": "png"
  }' | jq -r '.data[0].b64_json' | base64 -d > output.png
```

### Text-to-Image (URL Response)

```bash
curl -s -X POST https://ark.ap-southeast.bytepluses.com/api/v3/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -d '{
    "model": "seedream-5-0-260128",
    "prompt": "A cinematic portrait of a young woman, dramatic lighting",
    "sequential_image_generation": "disabled",
    "response_format": "url",
    "size": "2K",
    "stream": false,
    "watermark": false
  }' | jq -r '.data[0].url'
```

### Image-to-Image (Single Reference)

```bash
# Compress reference image
sips -Z 1024 input.png --out /tmp/ref.png 2>/dev/null
IMAGE_B64=$(base64 -i /tmp/ref.png | tr -d '\n')

curl -s -X POST https://ark.ap-southeast.bytepluses.com/api/v3/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -d '{
    "model": "seedream-5-0-260128",
    "prompt": "Change the background to a sunset beach, keep the same person and pose",
    "image": "data:image/png;base64,'"$IMAGE_B64"'",
    "sequential_image_generation": "disabled",
    "response_format": "b64_json",
    "size": "2K",
    "stream": false,
    "watermark": false,
    "output_format": "png"
  }' | jq -r '.data[0].b64_json' | base64 -d > output.png
```

### Batch Generation (Multiple Related Images)

```bash
curl -s -X POST https://ark.ap-southeast.bytepluses.com/api/v3/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -d '{
    "model": "seedream-5-0-260128",
    "prompt": "A family of four at different seasons: spring picnic, summer beach, autumn hike, winter snowman",
    "sequential_image_generation": "auto",
    "sequential_image_generation_options": {"max_images": 4},
    "response_format": "b64_json",
    "size": "2K",
    "stream": false,
    "watermark": false,
    "output_format": "png"
  }'
```

---

## API Reference

### Endpoint

```
POST https://ark.ap-southeast.bytepluses.com/api/v3/images/generations
```

**Alternative regions:**
- `ap-southeast-1`: `https://ark.ap-southeast.bytepluses.com/api/v3`
- `eu-west-1`: `https://ark.eu-west.bytepluses.com/api/v3`

### Authentication

| Header | Value |
|--------|-------|
| `Content-Type` | `application/json` |
| `Authorization` | `Bearer $ARK_API_KEY` |

### Request Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `model` | string | Yes | - | Model ID: `seedream-5-0-260128` (recommended), `seedream-4-5-251128`, `seedream-4-0-250828`, `seedream-3-0-t2i-250415` |
| `prompt` | string | Yes | - | Text prompt. Recommended under 600 English words |
| `image` | string/array | No | - | Reference image(s) as Base64 (`data:image/png;base64,...`) or URL. Max 14 images |
| `size` | string | No | `2K` | Resolution: `2K`, `4K`, or custom `WxH` (e.g. `1600x2848`) |
| `sequential_image_generation` | string | No | `disabled` | `disabled` = single image, `auto` = batch |
| `sequential_image_generation_options.max_images` | integer | No | 15 | Max batch images (1-15). Input refs + output <= 15 |
| `response_format` | string | No | `url` | `url` (24h link) or `b64_json` (base64 in JSON) |
| `output_format` | string | No | `jpeg` | `png` or `jpeg`. **Only seedream-5-0-260128** |
| `stream` | boolean | No | false | Streaming output mode |
| `watermark` | boolean | No | true | `false` = no watermark, `true` = "AI generated" watermark |
| `optimize_prompt_options.mode` | string | No | `standard` | `standard` (higher quality) or `fast` (faster) |
| `seed` | integer | No | -1 | Random seed (only seedream-3-0-t2i/seededit-3-0-i2i) |

### Size Presets (seedream-5-0-260128)

| Resolution | Ratio | Width x Height |
|------------|-------|----------------|
| 2K | 1:1 | 2048x2048 |
| 2K | 4:3 | 2304x1728 |
| 2K | 3:4 | 1728x2308 |
| 2K | 16:9 | 2848x1600 |
| 2K | **9:16** | **1600x2848** |
| 2K | 3:2 | 2496x1664 |
| 2K | 2:3 | 1664x2496 |
| 2K | 21:9 | 3136x1344 |
| 4K | 1:1 | 4096x4096 |
| 4K | **9:16** | **3040x5504** |
| 4K | 16:9 | 5504x3040 |

Custom size constraints:
- Total pixels: [3,686,400 , 16,777,216] (i.e. min ~1920x1920)
- Aspect ratio range: [1/16, 16]

### Input Image Requirements

| Constraint | Value |
|------------|-------|
| Formats | JPEG, PNG, WEBP, BMP, TIFF, GIF |
| Aspect ratio | [1/16, 16] |
| Min dimension | 14px |
| Max file size | 10 MB per image |
| Max total pixels | 6000x6000 per image |
| Max reference images | 14 |

**Base64 format:** MUST include data URL prefix: `data:image/png;base64,<base64data>`

### Response Format

**URL response:**
```json
{
  "model": "seedream-5-0-260128",
  "created": 1234567890,
  "data": [
    {
      "url": "https://...",
      "size": "2048x2048"
    }
  ],
  "usage": {
    "generated_images": 1,
    "output_tokens": 16384,
    "total_tokens": 16384
  }
}
```

**Base64 response:**
```json
{
  "model": "seedream-5-0-260128",
  "created": 1234567890,
  "data": [
    {
      "b64_json": "<base64-encoded-image>",
      "size": "2048x2048"
    }
  ],
  "usage": {
    "generated_images": 1,
    "output_tokens": 16384,
    "total_tokens": 16384
  }
}
```

### Error Response

```json
{
  "error": {
    "code": "AuthenticationError",
    "message": "The API key or AK/SK in the request is missing or invalid"
  }
}
```

---

## Helper Script

Save and use as a command-line tool:

```bash
#!/bin/bash
# seedream_gen.sh — Generate image with Seedream 5.0 Lite
# Usage: ./seedream_gen.sh "prompt" output.png [ref_image.png]

set -e

API_KEY="${ARK_API_KEY:?Set ARK_API_KEY env var}"
MODEL="seedream-5-0-260128"
SIZE="2K"
RESPONSE_FORMAT="b64_json"
OUTPUT_FORMAT="png"

PROMPT="$1"
OUTPUT="$2"
INPUT_IMAGE="$3"

[[ -z "$PROMPT" || -z "$OUTPUT" ]] && { echo "Usage: $0 \"prompt\" output.png [ref_image]"; exit 1; }

if [[ -n "$INPUT_IMAGE" && -f "$INPUT_IMAGE" ]]; then
  sips -Z 2048 "$INPUT_IMAGE" --out /tmp/seedream_ref.png 2>/dev/null
  IMG_B64=$(base64 -i /tmp/seedream_ref.png | tr -d '\n')
  IMAGE_FIELD="\"data:image/png;base64,${IMG_B64}\","
else
  IMAGE_FIELD=""
fi

REQUEST=$(jq -n \
  --arg model "$MODEL" \
  --arg prompt "$PROMPT" \
  --arg size "$SIZE" \
  --arg fmt "$RESPONSE_FORMAT" \
  --arg ofmt "$OUTPUT_FORMAT" \
  "{model:\$model,prompt:\$prompt,${IMAGE_FIELD}sequential_image_generation:\"disabled\",response_format:\$fmt,size:\$size,stream:false,watermark:false,output_format:\$ofmt}")

RESPONSE=$(curl -s -X POST \
  https://ark.ap-southeast.bytepluses.com/api/v3/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d "$REQUEST")

if echo "$RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
  echo "ERROR: $(echo "$RESPONSE" | jq -r '.error.message')"
  exit 1
fi

IMG_DATA=$(echo "$RESPONSE" | jq -r '.data[0].b64_json // .data[0].url // empty')

if [[ "$RESPONSE_FORMAT" == "b64_json" ]]; then
  echo "$IMG_DATA" | base64 -d > "$OUTPUT"
else
  curl -s -o "$OUTPUT" "$IMG_DATA"
fi

echo "Saved: $OUTPUT ($(stat -f%z "$OUTPUT" 2>/dev/null || stat -c%s "$OUTPUT") bytes)"
```

---

## Prompt Tips for Seedream

Seedream responds well to descriptive prompts with specific style keywords:

**Portrait Photography:**
```
Professional studio portrait, [age]-year-old [ethnicity] [gender], [face details], [clothing], 
pure white seamless backdrop, softbox lighting, shot on Hasselblad H6D-100c 100mm f/2.2, 
photorealistic, editorial quality, real skin texture
```

**Cinematic Scene:**
```
[Cinematic scene description], dramatic lighting, depth of field, 
cinematic color grading, anamorphic lens flare, 8K resolution
```

**Product Photography:**
```
[Product description] on [surface], [lighting direction] light, 
professional studio setup, clean composition, commercial photography, 4K
```

---

## Error Handling

| Error Code | Meaning | Solution |
|------------|---------|----------|
| `AuthenticationError` | Invalid/missing API key | Check `ARK_API_KEY` env var |
| `PermissionError` | No model access | Activate model in ModelArk console |
| `RateLimitError` | Too many requests | Wait and retry |
| `ContentFilterError` | Blocked by safety | Modify prompt to avoid sensitive content |
| 500 | Server error | Retry after a few seconds |

---

## Models Comparison

| Model | ID | Quality | Max Resolution | Price |
|-------|---|---------|----------------|-------|
| Seedream 5.0 | `seedream-5-0-260128` | Highest | 4K | Premium |
| Seedream 4.5 | `seedream-4-5-251128` | High | 4K | Standard |
| Seedream 4.0 | `seedream-4-0-250828` | Good | 4K | Economy |
| Seedream 3.0 | `seedream-3-0-t2i-250415` | Basic | 2K | Lowest |

**Recommended:** `seedream-5-0-260128` for best quality, supports PNG output, prompt optimization.

---

## Environment Variables

```bash
export ARK_API_KEY="<your-api-key>"
```

Get API key: [ModelArk Console](https://console.byteplus.com/ark/region:ark+ap-southeast-1/apiKey)
