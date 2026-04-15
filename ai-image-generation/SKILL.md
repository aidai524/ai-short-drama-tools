---
name: ai-image-generation
description: Generate AI images from text prompts. Supports text-to-image, image-to-image, and batch generation. Triggers: "生成图片", "generate image", "create image", "批量生图", "AI绘图", "文生图", "text to image", "product photos".
mcp:
  tools:
    - name: generate_image
      description: Generate a single AI image from text prompt
      inputSchema:
        type: object
        properties:
          prompt:
            type: string
            description: "Detailed English prompt for image generation"
          api_key:
            type: string
            description: "Manniu API Key (sk-...)"
          output_path:
            type: string
            description: "Local path to save the image"
          model:
            type: string
            default: "gemini-3.1-flash-image-preview"
            description: "AI model: gemini-3.1-flash-image-preview (fast) or gemini-3-pro-image-preview (quality)"
          image_size:
            type: string
            default: "1024"
            description: "Output image size: 512, 1024, 2048"
          aspect_ratio:
            type: string
            enum: ["1:1", "16:9", "9:16", "4:3", "3:4", "2:3", "3:2", "4:5", "5:4"]
            default: "1:1"
          input_image:
            type: string
            description: "Path to reference image (for image-to-image)"
          api_base:
            type: string
            default: "https://test-api.manniu.io"
        required: [prompt, api_key, output_path]
    - name: generate_batch
      description: Generate multiple AI images from a batch config
      inputSchema:
        type: object
        properties:
          tasks:
            type: array
            items:
              type: object
              properties:
                prompt: { type: string }
                output_name: { type: string }
                input_image: { type: string }
              required: [prompt, output_name]
          output_dir:
            type: string
            description: "Directory to save all images"
          api_key:
            type: string
          concurrency:
            type: integer
            default: 3
          defaults:
            type: object
            properties:
              model: { type: string, default: "gemini-3.1-flash-image-preview" }
              image_size: { type: string, default: "1024" }
              aspect_ratio: { type: string, default: "1:1" }
        required: [tasks, api_key, output_dir]
---

# AI Image Generation (Manniu Gemini API)

Universal AI image generation tool using Manniu's Gemini API proxy - no Python installation required.

## Quick Start

### Single Image Generation (Text-to-Image)

```bash
API_KEY="sk-your-api-key"
API_BASE="https://test-api.manniu.io"

RESPONSE=$(curl -s -X POST "$API_BASE/v1beta/models/gemini-3.1-flash-image-preview:generateContent" \
  -H "api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{
      "role": "user",
      "parts": [{
        "text": "A modern minimalist white cabinet in a contemporary living room, natural sunlight, product photography"
      }]
    }]
  }')

# Extract and save image
echo "$RESPONSE" | jq -r '.candidates[0].content.parts[0].inlineData.data' > temp_base64.txt
base64 -i temp_base64.txt -d > output.png
rm temp_base64.txt
echo "Saved to output.png"
```

### Image-to-Image Generation

```bash
API_KEY="sk-your-api-key"
API_BASE="https://test-api.manniu.io"

# Prepare reference image (compress first!)
sips -Z 512 original.png --out compressed.png 2>/dev/null
IMAGE_BASE64=$(base64 -i compressed.png | tr -d '\n')

RESPONSE=$(curl -s -X POST "$API_BASE/v1beta/models/gemini-3.1-flash-image-preview:generateContent" \
  -H "api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{
      "role": "user",
      "parts": [
        {
          "inline_data": {
            "data": "'"$IMAGE_BASE64"'",
            "mime_type": "image/png"
          }
        },
        {
          "text": "Change the cabinet colors to pastel yellow, pink, and purple. Keep the same layout. Warm bright lighting, cute cartoon decorations."
        }
      ]
    }]
  }')

# Extract and save image
echo "$RESPONSE" | jq -r '.candidates[0].content.parts[0].inlineData.data' > temp_base64.txt
base64 -i temp_base64.txt -d > output.png
rm temp_base64.txt
echo "Saved to output.png"
```

---

## API Reference

### POST /v1beta/models/{model}:generateContent

**Endpoint:** `https://test-api.manniu.io/v1beta/models/{model}:generateContent`

**Models:**
- `gemini-3.1-flash-image-preview` - Fast generation
- `gemini-3-pro-image-preview` - Higher quality

**Headers:**
| Header | Value |
|--------|-------|
| `Content-Type` | `application/json` |
| `api-key` | Your Manniu API Key (`sk-...`) |

### Request Body

```json
{
  "contents": [{
    "role": "user",
    "parts": [
      { "text": "Your prompt here" }
    ]
  }]
}
```

**Note:** `generationConfig.imageConfig` is optional. If you get 400 errors, try removing it and let the API use defaults.

With image config (optional):
```json
{
  "contents": [{
    "role": "user",
    "parts": [
      { "text": "Your prompt here" }
    ]
  }],
  "generationConfig": {
    "imageConfig": {
      "aspectRatio": "1:1",
      "imageSize": "1024"
    }
  }
}
```

### Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `contents` | array | Yes | Content array with role and parts |
| `contents[].role` | string | Yes | Always `"user"` for image generation |
| `contents[].parts` | array | Yes | Array of text and/or image parts |
| `contents[].parts[].text` | string | Yes* | Text prompt |
| `contents[].parts[].inline_data` | object | Yes* | Reference image for img2img |
| `contents[].parts[].inline_data.data` | string | Yes | Base64 image (NO data URL prefix!) |
| `contents[].parts[].inline_data.mime_type` | string | Yes | `image/png` or `image/jpeg` |
| `generationConfig.imageConfig.aspectRatio` | string | No | `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `2:3`, `3:2`, `4:5`, `5:4` |
| `generationConfig.imageConfig.imageSize` | string | No | `512`, `1024`, `2048` |

*Either text or inline_data is required. Both can be combined for image-to-image.

### Response

```json
{
  "candidates": [{
    "finishReason": "STOP",
    "content": {
      "parts": [{
        "inlineData": {
          "mimeType": "image/png",
          "data": "iVBORw0KGgo..."
        }
      }]
    }
  }]
}
```

### Response Fields

| Field | Description |
|-------|-------------|
| `candidates[0].finishReason` | `STOP` = success, `SAFETY` = blocked by safety |
| `candidates[0].content.parts[0].inlineData.data` | Base64 encoded result image |
| `candidates[0].content.parts[0].inlineData.mimeType` | Image MIME type |

### Error Response

```json
{
  "statusCode": 401,
  "message": "Invalid or expired token",
  "error": "Unauthorized"
}
```

---

## Reference Image Guidelines (Image-to-Image)

### Requirements

| Limit | Value | Reason |
|-------|-------|--------|
| Max dimension | 512px recommended | Faster processing |
| Max file size | ~200KB | Base64 encoding overhead |
| Formats | PNG, JPEG | Standard formats |

### Important: Base64 Format

**NO data URL prefix!** Use raw base64 only:

```bash
# ✅ Correct - raw base64 only
IMAGE_BASE64=$(base64 -i image.png | tr -d '\n')

# ❌ Wrong - includes data URL prefix
IMAGE_DATA="data:image/png;base64,$IMAGE_BASE64"  # DON'T DO THIS
```

### Auto-Compression Script

```bash
compress_image() {
  local input="$1"
  local output="${2:-compressed.png}"
  
  # Resize to max 512px
  sips -Z 512 "$input" --out "$output" 2>/dev/null
  
  # If still too large, reduce quality
  if [[ $(stat -f%z "$output") -gt 200000 ]]; then
    sips -s format jpeg -s formatOptions 70 "$output" --out "${output%.*}.jpg" 2>/dev/null
    echo "${output%.*}.jpg"
  else
    echo "$output"
  fi
}

# Usage
COMPRESSED=$(compress_image "original.png")
IMAGE_BASE64=$(base64 -i "$COMPRESSED" | tr -d '\n')
```

---

## Prompt Engineering Guide

### Product Photography Template

```
[Product Description] in [Setting], [Lighting], [Style], [Camera Angle], product photography, [Quality]
```

### Example Prompts

**Living Room:**
```
A modern minimalist white cabinet in a contemporary living room, 
natural sunlight through large windows, warm beige walls, hardwood floor, 
potted plant beside, lifestyle product photography, soft shadows, 4K
```

**Bedroom:**
```
White minimalist cabinet in a cozy bedroom setting, 
soft ambient lighting, pastel color palette, clean linen bedding, 
scandinavian interior design, calm serene atmosphere, product photography
```

**Studio:**
```
White cabinet product photography, studio lighting, 
pure white background, professional setup, 
clean minimal composition, high-end commercial photography, 4K
```

### Scene Keywords

| Scene | Keywords |
|-------|----------|
| Living Room | living room, contemporary, cozy, natural light, lifestyle |
| Bedroom | bedroom, calm, soft lighting, serene, cozy |
| Office | office, professional, clean, organized, modern |
| Outdoor | outdoor, natural environment, sunlight, garden |
| Studio | studio, white background, professional lighting, clean |

### Style Keywords

| Style | Keywords |
|-------|----------|
| Minimalist | minimalist, clean, simple, white space |
| Scandinavian | scandinavian, nordic, light wood, natural |
| Industrial | industrial, raw, metal, concrete, urban |
| Vintage | vintage, retro, nostalgic, warm tones |
| Modern | modern, contemporary, sleek, polished |
| Cute/Cartoon | cute, cartoon, kawaii, playful, pastel colors |

---

## Common Use Cases

| Use Case | Recommended Settings |
|----------|---------------------|
| Quick Preview | `model: gemini-3.1-flash-image-preview`, `imageSize: 512` |
| Product Catalog | `model: gemini-3-pro-image-preview`, `imageSize: 1024`, `aspectRatio: 1:1` |
| Social Media | `model: gemini-3-pro-image-preview`, `imageSize: 1024`, `aspectRatio: 9:16` |
| E-commerce Hero | `model: gemini-3-pro-image-preview`, `imageSize: 2048`, `aspectRatio: 16:9` |

---

## Error Handling

| HTTP Status | Meaning | Solution |
|-------------|---------|----------|
| 401 | Invalid API Key | Check API key format (should start with `sk-`) |
| 403 | Quota/Permission | Check account balance or permissions |
| 429 | Rate Limited | Wait and retry |
| 500 | Server Error | Retry after a few seconds |

### Safety Block

If `finishReason` is `"SAFETY"`, the image was blocked by content safety filters. Modify your prompt to avoid potentially problematic content.

---

## Get API Key

1. Contact Manniu to get access
2. You'll receive:
   - `api-key`: Format `sk-...` (for header)
   - `Authorization` token: Format `eyJ...` (if required by your account)

---

## Batch Generation

```bash
#!/bin/bash
API_KEY="sk-your-api-key"
API_BASE="https://test-api.manniu.io"
OUTPUT_DIR="./output"

mkdir -p "$OUTPUT_DIR"

PROMPTS=(
  "Product in living room, natural light"
  "Product in bedroom, soft lighting"
  "Product in office, professional setting"
)

for i in "${!PROMPTS[@]}"; do
  PROMPT="${PROMPTS[$i]}"
  OUTPUT="$OUTPUT_DIR/image_$i.png"
  
  RESPONSE=$(curl -s -X POST "$API_BASE/v1beta/models/gemini-3.1-flash-image-preview:generateContent" \
    -H "api-key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "contents": [{
        "role": "user",
        "parts": [{ "text": "'"$PROMPT"'" }]
      }],
      "generationConfig": {
        "imageConfig": {
          "aspectRatio": "1:1",
          "imageSize": "1024"
        }
      }
    }')
  
  # Check for errors
  if echo "$RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
    echo "Failed: $OUTPUT - $(echo "$RESPONSE" | jq -r '.message')"
  else
    echo "$RESPONSE" | jq -r '.candidates[0].content.parts[0].inlineData.data' | base64 -d > "$OUTPUT"
    echo "Done: $OUTPUT"
  fi &
done

wait
echo "All done!"
```

---

## Complete Helper Script

Save as `generate_image.sh`:

```bash
#!/bin/bash
# AI Image Generation Helper Script
# Usage: ./generate_image.sh "prompt" output.png [input_image.png]

set -e

API_KEY="${MANNIU_API_KEY:-sk-your-api-key}"
API_BASE="${MANNIU_API_BASE:-https://test-api.manniu.io}"
MODEL="${MANNIU_MODEL:-gemini-3.1-flash-image-preview}"
ASPECT_RATIO="${ASPECT_RATIO:-1:1}"
IMAGE_SIZE="${IMAGE_SIZE:-1024}"

PROMPT="$1"
OUTPUT="$2"
INPUT_IMAGE="$3"

if [[ -z "$PROMPT" || -z "$OUTPUT" ]]; then
  echo "Usage: $0 \"prompt\" output.png [input_image.png]"
  exit 1
fi

# Build parts array
PARTS='[]'
PARTS=$(echo "$PARTS" | jq --arg text "$PROMPT" '. + [{"text": $text}]')

# Add input image if provided
if [[ -n "$INPUT_IMAGE" && -f "$INPUT_IMAGE" ]]; then
  echo "Compressing input image..."
  TEMP_IMG=$(mktemp /tmp/compressed.XXXXXX.png)
  sips -Z 512 "$INPUT_IMAGE" --out "$TEMP_IMG" 2>/dev/null
  IMAGE_BASE64=$(base64 -i "$TEMP_IMG" | tr -d '\n')
  MIME_TYPE="image/png"
  
  # Build parts with image first
  PARTS=$(jq -n \
    --arg data "$IMAGE_BASE64" \
    --arg mime "$MIME_TYPE" \
    --arg text "$PROMPT" \
    '[{"inline_data": {"data": $data, "mime_type": $mime}}, {"text": $text}]')
  
  rm "$TEMP_IMG"
fi

# Build request
REQUEST=$(jq -n \
  --argjson parts "$PARTS" \
  --arg aspect "$ASPECT_RATIO" \
  --arg size "$IMAGE_SIZE" \
  '{
    "contents": [{
      "role": "user",
      "parts": $parts
    }],
    "generationConfig": {
      "imageConfig": {
        "aspectRatio": $aspect,
        "imageSize": $size
      }
    }
  }')

echo "Generating image..."
RESPONSE=$(curl -s -X POST "$API_BASE/v1beta/models/$MODEL:generateContent" \
  -H "api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "$REQUEST")

# Check for errors
if echo "$RESPONSE" | jq -e '.statusCode' > /dev/null 2>&1; then
  echo "Error: $(echo "$RESPONSE" | jq -r '.message')"
  exit 1
fi

# Extract finish reason
FINISH_REASON=$(echo "$RESPONSE" | jq -r '.candidates[0].finishReason // "UNKNOWN"')

if [[ "$FINISH_REASON" == "SAFETY" ]]; then
  echo "Error: Image blocked by safety filters"
  exit 1
fi

# Save image
echo "$RESPONSE" | jq -r '.candidates[0].content.parts[0].inlineData.data' | base64 -d > "$OUTPUT"
echo "Saved to: $OUTPUT"
```

---

## Installation (OpenCode)

```bash
mkdir -p ~/.config/opencode/skills/ai-image-generation
cp SKILL.md ~/.config/opencode/skills/ai-image-generation/
```

## Environment Variables (Optional)

```bash
export MANNIU_API_KEY="sk-your-api-key"
export MANNIU_API_BASE="https://test-api.manniu.io"
export MANNIU_MODEL="gemini-3.1-flash-image-preview"
```

---

## License

MIT License
