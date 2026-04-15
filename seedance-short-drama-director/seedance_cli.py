#!/usr/bin/env python3
"""
Seedance Short Drama Director - 短剧视频导演工具
基于 BytePlus ModelArk Seedance 2.0 API 的短剧视频生成工具

Usage:
    python seedance_cli.py run -i script.txt -a asset_map.json -o ./output
    python seedance_cli.py parse -i script.txt -a asset_map.json
    python seedance_cli.py rewrite -i parsed_segments.json
    python seedance_cli.py build -i parsed_segments.json -p prompts.txt
    python seedance_cli.py submit -p payload.json -o ./output
    python seedance_cli.py status
"""

import argparse
import json
import os
import re
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ═══════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════

API_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_SEEDANCE_MODEL = os.environ.get("ARK_SEEDANCE_MODEL", "")
DEFAULT_DOUBAO_MODEL = os.environ.get("ARK_DOUBAO_MODEL", "")
DEFAULT_CONCURRENCY = int(os.environ.get("ARK_CONCURRENCY", "3"))
DEFAULT_RATIO = os.environ.get("ARK_DEFAULT_RATIO", "16:9")
DEFAULT_DURATION_MS = int(os.environ.get("ARK_DEFAULT_DURATION_MS", "10000"))
POLL_INTERVAL = 30
POLL_TIMEOUT = 600

# Continuity suffix appended to every prompt
CONTINUITY_SUFFIX = (
    " Maintain strict visual continuity: same outfit, same hairstyle, "
    "same location layout, same lighting, direct continuity with previous/next segment."
)

# Internal monologue patterns (Chinese → English tag)
MONOLOGUE_PATTERNS = [
    (r"心里想[：:]?\s*", "silent internal monologue, lips closed, contemplative expression: "),
    (r"内心独白[：:]?\s*", "silent internal monologue, lips closed, contemplative expression: "),
    (r"心里默默想[：:]?\s*", "silent internal monologue, lips closed, contemplative expression: "),
    (r"暗自心想[：:]?\s*", "silent internal monologue, lips closed, contemplative expression: "),
    (r"心想[：:]?\s*", "silent internal monologue, lips closed, contemplative expression: "),
]


# ═══════════════════════════════════════════════════════════
# Ark API Client
# ═══════════════════════════════════════════════════════════

class ArkClient:
    """HTTP client for BytePlus ModelArk API (Seedance 2.0 + Doubao LLM)."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("ARK_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "ARK_API_KEY is required. "
                "Set it via: export ARK_API_KEY='your-api-key'"
            )
        if not HAS_REQUESTS:
            raise ImportError("requests is required: pip install requests")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        })

    # ── Video Generation ──────────────────────────────────

    def create_video_task(self, model: str, content: List[Dict],
                          ratio: str = DEFAULT_RATIO,
                          duration: int = 10,
                          generate_audio: bool = True,
                          watermark: bool = False,
                          return_last_frame: bool = True) -> Dict:
        """Create a Seedance 2.0 video generation task."""
        payload = {
            "model": model,
            "content": content,
            "generate_audio": generate_audio,
            "ratio": ratio,
            "duration": duration,
            "watermark": watermark,
            "return_last_frame": return_last_frame,
        }
        resp = self.session.post(
            f"{API_BASE}/contents/generations/tasks",
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()

    def get_task(self, task_id: str) -> Dict:
        """Get task status and result."""
        resp = self.session.get(
            f"{API_BASE}/contents/generations/tasks/{task_id}",
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def cancel_task(self, task_id: str) -> Dict:
        """Cancel a running task."""
        resp = self.session.delete(
            f"{API_BASE}/contents/generations/tasks/{task_id}",
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # ── LLM Chat (Doubao) ────────────────────────────────

    def chat_completion(self, model: str, messages: List[Dict],
                        temperature: float = 0.7,
                        max_tokens: int = 2048) -> str:
        """Call Doubao LLM for prompt rewriting. Returns assistant text."""
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resp = self.session.post(
            f"{API_BASE}/chat/completions",
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    # ── File Download ─────────────────────────────────────

    @staticmethod
    def download_file(url: str, output_path: str):
        """Download a file from URL to local path."""
        resp = requests.get(url, stream=True, timeout=180)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)


# ═══════════════════════════════════════════════════════════
# Input Parser
# ═══════════════════════════════════════════════════════════

class InputParser:
    """Parse colloquial and structured Chinese drama scripts into structured segments."""

    def __init__(self, asset_map: Dict[str, str] = None):
        self.asset_map = asset_map or {}

    def resolve_asset(self, ref: str) -> str:
        """Resolve @id to URL via asset_map. Returns raw string if already a URL."""
        ref = ref.strip()
        if ref.startswith("http://") or ref.startswith("https://"):
            return ref
        # Try with and without @ prefix
        url = self.asset_map.get(ref) or self.asset_map.get(ref.lstrip("@"))
        if not url:
            raise ValueError(
                f"Asset '{ref}' not found in asset_map.json. "
                f"Available keys: {list(self.asset_map.keys())[:10]}"
            )
        return url

    def auto_detect_and_parse(self, text: str) -> Dict[str, Any]:
        """Auto-detect format and parse."""
        # Heuristic: structured format uses XML-like tags
        has_xml_tags = bool(re.search(r"<(location|role|duration-ms|style)>", text))
        if has_xml_tags:
            return self.parse_structured(text)
        return self.parse_colloquial(text)

    # ── Colloquial Format ─────────────────────────────────

    def parse_colloquial(self, text: str) -> Dict[str, Any]:
        """Parse colloquial format:
        首帧：@xxx
        尾帧：@xxx
        @xxx 为女主/男主
        分镜1：剧情描述
        """
        result = {
            "format": "colloquial",
            "style": None,
            "first_frame": None,
            "last_frame": None,
            "roles": {},
            "locations": {},
            "segments": [],
        }

        lines = text.strip().split("\n")

        # First pass: extract metadata (首帧, 尾帧, roles, locations, style)
        content_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # 首帧
            m = re.match(r"^首帧\s*[：:]\s*(.+)$", stripped)
            if m:
                result["first_frame"] = self.resolve_asset(m.group(1).strip())
                continue

            # 尾帧
            m = re.match(r"^尾帧\s*[：:]\s*(.+)$", stripped)
            if m:
                result["last_frame"] = self.resolve_asset(m.group(1).strip())
                continue

            # Role definition: @xxx 为/是/扮演 女主/男主/角色
            m = re.match(r"^(@\S+)\s*(?:为|是|扮演)\s*(.+)$", stripped)
            if m:
                asset_id = m.group(1)
                role_desc = m.group(2).strip()
                result["roles"][asset_id] = {
                    "url": self._safe_resolve(asset_id),
                    "description": role_desc,
                }
                continue

            # 场景/地点
            m = re.match(r"^场景\s*[：:]\s*(.+)$", stripped)
            if m:
                loc_id = f"L{len(result['locations']) + 1}"
                result["locations"][loc_id] = m.group(1).strip()
                continue

            # 画面风格
            m = re.match(r"^风格\s*[：:]\s*(.+)$", stripped)
            if m:
                result["style"] = m.group(1).strip()
                continue

            content_lines.append(stripped)

        # Second pass: split content into segments by "分镜" markers
        full_content = "\n".join(content_lines)
        segments = self._split_into_segments(full_content)

        for i, seg in enumerate(segments):
            duration_ms = self._extract_duration(seg) or DEFAULT_DURATION_MS
            clean = self._clean_segment_text(seg)
            if clean:
                result["segments"].append({
                    "index": i,
                    "content": clean,
                    "duration_ms": duration_ms,
                })

        # If no segments found, treat entire content as one segment
        if not result["segments"] and full_content.strip():
            result["segments"].append({
                "index": 0,
                "content": full_content.strip(),
                "duration_ms": DEFAULT_DURATION_MS,
            })

        return result

    # ── Structured Format ─────────────────────────────────

    def parse_structured(self, text: str) -> Dict[str, Any]:
        """Parse structured XML-like format:
        <location>L1</location>
        <role>R3</role>
        分镜1<duration-ms>6000</duration-ms>
        """
        result = {
            "format": "structured",
            "style": None,
            "first_frame": None,
            "last_frame": None,
            "roles": {},
            "locations": {},
            "segments": [],
        }

        # Extract style
        m = re.search(r"画面风格\s*[：:]\s*(.+?)(?:\n|$)", text)
        if m:
            result["style"] = m.group(1).strip()
        m = re.search(r"<style>(.+?)</style>", text)
        if m:
            result["style"] = m.group(1).strip()

        # Extract first/last frame
        m = re.search(r"<first-frame>(.+?)</first-frame>", text)
        if m:
            result["first_frame"] = self.resolve_asset(m.group(1).strip())
        m = re.search(r"<last-frame>(.+?)</last-frame>", text)
        if m:
            result["last_frame"] = self.resolve_asset(m.group(1).strip())

        # Extract locations
        for m in re.finditer(r"<location>(.+?)</location>", text):
            loc_id = f"L{len(result['locations']) + 1}"
            result["locations"][loc_id] = m.group(1).strip()

        # Extract roles (handle <role ref="@id">desc</role> and <role>desc</role>)
        for m in re.finditer(r"<role[^>]*>(.+?)</role>", text):
            role_desc = m.group(1).strip()
            ref_match = re.search(r'ref="([^"]+)"', m.group(0))
            if ref_match:
                asset_id = ref_match.group(1)
                result["roles"][asset_id] = {
                    "url": self._safe_resolve(asset_id),
                    "description": role_desc,
                }
            else:
                role_id = f"R{len(result['roles']) + 1}"
                result["roles"][role_id] = {"description": role_desc}

        # Extract segments (split by "分镜N" markers)
        full_text = text.strip()
        segments = self._split_into_segments(full_text)

        for i, seg in enumerate(segments):
            duration_ms = self._extract_duration(seg) or DEFAULT_DURATION_MS
            # Extract per-segment first/last frame
            seg_first = None
            seg_last = None
            m = re.search(r"<first-frame>(.+?)</first-frame>", seg)
            if m:
                seg_first = self.resolve_asset(m.group(1).strip())
            m = re.search(r"<last-frame>(.+?)</last-frame>", seg)
            if m:
                seg_last = self.resolve_asset(m.group(1).strip())

            clean = self._clean_segment_text(seg)
            if clean:
                seg_data = {
                    "index": i,
                    "content": clean,
                    "duration_ms": duration_ms,
                }
                if seg_first:
                    seg_data["first_frame"] = seg_first
                if seg_last:
                    seg_data["last_frame"] = seg_last
                result["segments"].append(seg_data)

        if not result["segments"]:
            # Fallback: treat entire text as one segment
            clean = self._clean_segment_text(full_text)
            if clean:
                result["segments"].append({
                    "index": 0,
                    "content": clean,
                    "duration_ms": DEFAULT_DURATION_MS,
                })

        return result

    # ── Helpers ────────────────────────────────────────────

    def _safe_resolve(self, ref: str) -> Optional[str]:
        """Resolve asset without raising on failure."""
        try:
            return self.resolve_asset(ref)
        except ValueError:
            return None

    @staticmethod
    def _split_into_segments(text: str) -> List[str]:
        """Split text by segment markers like '分镜1', '镜头1', 'Scene 1'."""
        parts = re.split(
            r"(?=(?:分镜|镜头|Scene|Shot)\s*\d+)",
            text,
            flags=re.IGNORECASE,
        )
        result = []
        for i, p in enumerate(parts):
            p = p.strip()
            if not p:
                continue
            if i == 0 and not re.search(r"(?:分镜|镜头|Scene|Shot)\s*\d+", p, re.IGNORECASE):
                continue
            result.append(p)
        return result

    @staticmethod
    def _extract_duration(text: str) -> Optional[int]:
        """Extract duration in ms from tags or inline markers."""
        # <duration-ms>6000</duration-ms>
        m = re.search(r"<duration-ms\s*>(\d+)</duration-ms>", text)
        if m:
            return int(m.group(1))
        # 时长：6秒 / duration: 6s
        m = re.search(r"(?:时长|duration)\s*[：:]\s*(\d+)\s*(?:秒|s|ms|毫秒)?", text, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            # If value < 100, assume seconds; convert to ms
            return val * 1000 if val < 100 else val
        return None

    @staticmethod
    def _clean_segment_text(text: str) -> str:
        """Remove metadata tags and markers, keep only story content."""
        clean = re.sub(r"<[^>]+>", "", text)
        clean = re.sub(r"^(?:分镜|镜头|Scene|Shot)\s*\d+\s*[：:]?\s*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"(?:时长|duration)\s*[：:]\s*\d+\s*(?:秒|s|ms|毫秒)?", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"^[ \t]*@\S+[ \t]*$", "", clean, flags=re.MULTILINE)
        clean = re.sub(r"^[ \t]*(?:画面风格|风格)\s*[：:].*$", "", clean, flags=re.MULTILINE)
        clean = re.sub(r"^[ \t]*(?:场景|地点)\s*[：:].*$", "", clean, flags=re.MULTILINE)
        clean = re.sub(r"\n{3,}", "\n\n", clean)
        return clean.strip()


# ═══════════════════════════════════════════════════════════
# Prompt Rewriter
# ═══════════════════════════════════════════════════════════

class PromptRewriter:
    """Rewrite Chinese drama scripts to Seedance 2.0 English prompts via Doubao LLM."""

    SYSTEM_PROMPT = """You are a professional video prompt writer for Seedance 2.0, a cinematic AI video generator by ByteDance.

Your task is to rewrite Chinese drama scripts into prompts that produce high-quality, cinematic video.

## CRITICAL RULES:

1. **LANGUAGE POLICY — MOST IMPORTANT**:
   - ALL character dialogue (spoken lines) MUST remain in the ORIGINAL Chinese text, verbatim. Do NOT translate any dialogue to English.
   - Camera directions, shot descriptions, lighting, and visual descriptions should be in English.
   - Internal monologue (心里想/内心独白) content should also remain in Chinese but tagged as silent.
   - End every prompt with this exact sentence: "所有角色对白使用中文普通话 (All character dialogue must be spoken in Mandarin Chinese)."
   
2. **Be extremely visual** — describe only what the CAMERA can see. No abstract concepts.
3. **Cinematic language**: use terms like "close-up shot", "wide shot", "tracking shot", "over-the-shoulder", "slow pan", "push-in", "rack focus".
4. **Character actions over emotions**: instead of "she feels sad", write "her eyes well up with tears, she bites her lower lip, her shoulders drop".
5. **Internal monologue** (心里想/内心独白): ALWAYS rewrite as: "silent internal monologue, the character's lips remain firmly closed, contemplative expression, eyes slightly unfocused in thought" followed by the thought content in Chinese. The character MUST NOT move their lips or speak.
6. **Dialogue**: clearly mark with character name + "says aloud in Mandarin:" or character name + speaking action. Keep the original Chinese dialogue text.
7. **Temporal flow**: use "the scene begins with...", "transitioning to...", "ending with..." to structure the shot.
8. **Present tense** throughout.
9. **Keep each segment focused** on a single shot/scene. Duration should match the described action.
10. **If referencing images**: say "the character from Image 1" or "following the composition of Image 1".

## OUTPUT FORMAT:
Return ONLY the prompt text. No explanations, no markdown formatting, no preamble."""

    def __init__(self, client: ArkClient, model: str = None):
        self.client = client
        self.model = model or DEFAULT_DOUBAO_MODEL
        if not self.model:
            raise ValueError(
                "ARK_DOUBAO_MODEL is required for prompt rewriting. "
                "Set it via: export ARK_DOUBAO_MODEL='your-doubao-endpoint-id'"
            )

    def rewrite_segment(self, chinese_text: str, context: str = "",
                        style: str = None) -> str:
        """Rewrite a single segment. Returns English prompt."""
        user_parts = []

        if style:
            user_parts.append(f"[Visual style: {style}]")

        if context:
            user_parts.append(f"[Adjacent segment context: {context}]")

        user_parts.append(f"[Segment to rewrite]:\n{chinese_text}")

        try:
            result = self.client.chat_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": "\n\n".join(user_parts)},
                ],
                temperature=0.7,
            )
            return result
        except Exception as e:
            print(f"  ⚠️  LLM rewrite failed: {e}")
            print("  ↳ Falling back to rule-based rewrite...")
            return self._fallback_rewrite(chinese_text)

    def rewrite_batch(self, segments: List[Dict], style: str = None,
                      on_progress=None) -> List[str]:
        """Rewrite all segments. Returns list of English prompts in order."""
        prompts = []
        total = len(segments)

        for i, seg in enumerate(segments):
            # Build context from adjacent segments
            ctx_parts = []
            if i > 0:
                prev = segments[i - 1]
                ctx_parts.append(f"Previous: ...{prev['content'][-150:]}")
            if i < total - 1:
                nxt = segments[i + 1]
                ctx_parts.append(f"Next: {nxt['content'][:150]}...")
            context = "; ".join(ctx_parts)

            prompt = self.rewrite_segment(seg["content"], context, style)
            prompts.append(prompt)

            if on_progress:
                on_progress(i + 1, total, prompt)

        return prompts

    @staticmethod
    def _fallback_rewrite(text: str) -> str:
        """Basic rule-based rewrite when LLM is unavailable."""
        result = text
        for pattern, replacement in MONOLOGUE_PATTERNS:
            result = re.sub(pattern, replacement, result)

        # Basic Chinese→English term mapping
        term_map = {
            "女主": "the female lead",
            "男主": "the male lead",
            "特写": "close-up shot of",
            "远景": "wide shot of",
            "中景": "medium shot of",
            "近景": "close shot of",
            "俯拍": "high angle shot of",
            "仰拍": "low angle shot of",
            "跟拍": "tracking shot following",
            "慢慢走向": "slowly walks toward",
            "突然": "suddenly",
            "转身": "turns around",
            "回头看": "looks back at",
        }
        for cn, en in term_map.items():
            result = result.replace(cn, en)

        return result


# ═══════════════════════════════════════════════════════════
# Payload Builder
# ═══════════════════════════════════════════════════════════

class PayloadBuilder:
    """Build Seedance 2.0 API request payloads."""

    @staticmethod
    def detect_mode(first_frame: str = None, last_frame: str = None) -> str:
        """Detect the video generation mode based on available frames."""
        if first_frame and last_frame:
            return "first_last_frame"
        elif first_frame:
            return "first_frame"
        elif last_frame:
            return "last_frame"
        else:
            return "text_to_video"

    @staticmethod
    def build_content(prompt: str,
                      first_frame: str = None,
                      last_frame: str = None,
                      role_images: Dict[str, Dict] = None,
                      reference_video: str = None,
                      reference_audio: str = None) -> List[Dict]:
        """Build the content array for a Seedance 2.0 API call."""
        content = [{"type": "text", "text": prompt}]

        # First / last frame images (strict frame control)
        if first_frame:
            content.append({
                "type": "image_url",
                "image_url": {"url": first_frame},
                "role": "first_frame",
            })
        if last_frame:
            content.append({
                "type": "image_url",
                "image_url": {"url": last_frame},
                "role": "last_frame",
            })

        # Character reference images
        if role_images:
            for role_id, role_info in role_images.items():
                url = (role_info.get("url") if isinstance(role_info, dict) else None)
                if url:
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": url},
                        "role": "reference_image",
                    })

        # Reference video
        if reference_video:
            content.append({
                "type": "video_url",
                "video_url": {"url": reference_video},
                "role": "reference_video",
            })

        # Reference audio
        if reference_audio:
            content.append({
                "type": "audio_url",
                "audio_url": {"url": reference_audio},
                "role": "reference_audio",
            })

        return content

    @staticmethod
    def build_payload(model: str, content: List[Dict],
                      duration: int = 10,
                      ratio: str = DEFAULT_RATIO,
                      generate_audio: bool = True,
                      watermark: bool = False,
                      return_last_frame: bool = True) -> Dict:
        """Build a complete API request payload."""
        return {
            "model": model,
            "content": content,
            "ratio": ratio,
            "duration": max(4, min(15, duration)),
            "generate_audio": generate_audio,
            "return_last_frame": return_last_frame,
            "watermark": watermark,
        }

    @staticmethod
    def build_batch(parsed: Dict[str, Any], prompts: List[str],
                    model: str, ratio: str = DEFAULT_RATIO,
                    generate_audio: bool = True,
                    watermark: bool = False) -> List[Dict]:
        """Build payloads for all segments."""
        payloads = []
        segments = parsed.get("segments", [])
        total_segs = len(segments)
        global_first = parsed.get("first_frame")
        global_last = parsed.get("last_frame")
        roles = parsed.get("roles", {})

        for i, seg in enumerate(segments):
            prompt = prompts[i] if i < len(prompts) else seg["content"]

            # Add continuity constraint
            prompt += CONTINUITY_SUFFIX

            # Duration: convert ms to seconds, clamp to [4, 15]
            duration_ms = seg.get("duration_ms", DEFAULT_DURATION_MS)
            duration_s = max(4, min(15, duration_ms // 1000))

            # Frame assignment:
            #   - Per-segment frames override globals
            #   - Global first_frame → segment 0
            #   - Global last_frame → last segment
            seg_first = seg.get("first_frame")
            seg_last = seg.get("last_frame")

            if seg_first is None and i == 0:
                seg_first = global_first
            if seg_last is None and i == total_segs - 1:
                seg_last = global_last

            content = PayloadBuilder.build_content(
                prompt=prompt,
                first_frame=seg_first,
                last_frame=seg_last,
                role_images=roles,
            )

            mode = PayloadBuilder.detect_mode(seg_first, seg_last)

            payload = PayloadBuilder.build_payload(
                model=model,
                content=content,
                duration=duration_s,
                ratio=ratio,
                generate_audio=generate_audio,
                watermark=watermark,
                return_last_frame=True,
            )
            payload["_meta"] = {
                "segment_index": i,
                "mode": mode,
                "duration_s": duration_s,
            }
            payloads.append(payload)

        return payloads

    @staticmethod
    def build_chain_payload(model: str, prompt: str, prev_video_url: str,
                            role_images: Dict[str, Dict] = None,
                            duration: int = 10, ratio: str = DEFAULT_RATIO,
                            generate_audio: bool = True,
                            return_last_frame: bool = True,
                            watermark: bool = False) -> Dict:
        """Build a payload that continues from a previous video segment (Video Extension).
        
        Uses reference_video role to pass the previous segment's video URL,
        enabling seamless visual continuity between segments.
        """
        content = [{"type": "text", "text": prompt}]

        # Previous video as reference for continuity
        content.append({
            "type": "video_url",
            "video_url": {"url": prev_video_url},
            "role": "reference_video",
        })

        # Character reference images (uploaded separately: face closeup + outfit)
        if role_images:
            for role_id, role_info in role_images.items():
                url = (role_info.get("url") if isinstance(role_info, dict) else None)
                if url:
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": url},
                        "role": "reference_image",
                    })

        return {
            "model": model,
            "content": content,
            "ratio": ratio,
            "duration": max(4, min(15, duration)),
            "generate_audio": generate_audio,
            "return_last_frame": return_last_frame,
            "watermark": watermark,
        }


# ═══════════════════════════════════════════════════════════
# Task Manager
# ═══════════════════════════════════════════════════════════

class TaskManager:
    """Submit, poll, and download Seedance video generation tasks with concurrency control."""

    def __init__(self, client: ArkClient, concurrency: int = DEFAULT_CONCURRENCY):
        self.client = client
        self.concurrency = concurrency
        self._semaphore = threading.Semaphore(concurrency)

    def submit_one(self, payload: Dict) -> Dict:
        """Submit a single video generation task. Returns API response."""
        with self._semaphore:
            meta = payload.pop("_meta", None)
            try:
                result = self.client.create_video_task(
                    model=payload["model"],
                    content=payload["content"],
                    ratio=payload.get("ratio", DEFAULT_RATIO),
                    duration=payload.get("duration", 6),
                    generate_audio=payload.get("generate_audio", True),
                    watermark=payload.get("watermark", False),
                )
                if meta:
                    result["_meta"] = meta
                return result
            except Exception as e:
                return {"error": str(e), "_meta": meta}
            finally:
                if meta:
                    payload["_meta"] = meta

    def submit_batch(self, payloads: List[Dict]) -> List[Dict]:
        """Submit all tasks with semaphore-controlled concurrency."""
        results = [None] * len(payloads)

        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            futures = {
                pool.submit(self.submit_one, p): i
                for i, p in enumerate(payloads)
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = {"error": str(e)}

        return results

    def poll_task(self, task_id: str, timeout: int = POLL_TIMEOUT) -> Dict:
        """Poll a single task until it succeeds, fails, or times out."""
        start = time.time()
        while time.time() - start < timeout:
            result = self.client.get_task(task_id)
            status = result.get("status", "unknown")

            if status == "succeeded":
                return result
            elif status == "failed":
                error = result.get("error", result.get("message", "unknown"))
                raise RuntimeError(f"Task {task_id} failed: {error}")
            elif status in ("cancelled", "canceled"):
                raise RuntimeError(f"Task {task_id} was cancelled")

            elapsed = int(time.time() - start)
            print(f"  ⏳ [{task_id[:16]}...] status={status}  ({elapsed}s elapsed)")
            time.sleep(POLL_INTERVAL)

        raise TimeoutError(f"Task {task_id} timed out after {timeout}s")

    def poll_all(self, task_ids: List[str], timeout: int = POLL_TIMEOUT) -> List[Dict]:
        """Poll all tasks concurrently and return results."""
        results = [None] * len(task_ids)

        def _poll_one(idx, tid):
            try:
                results[idx] = self.poll_task(tid, timeout)
            except Exception as e:
                results[idx] = {"id": tid, "error": str(e)}

        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            futures = [pool.submit(_poll_one, i, tid) for i, tid in enumerate(task_ids)]
            for f in as_completed(futures):
                f.result()  # propagate exceptions

        return results

    def download_result(self, task_result: Dict, output_dir: str,
                        filename: str = None) -> Dict:
        """Download video and last frame from a completed task result.
        
        Returns dict with keys:
          - video_path: local path to downloaded video
          - last_frame_path: local path to downloaded last frame image (or None)
          - video_url: original video URL
          - last_frame_url: original last frame URL (or None)
        """
        content_data = task_result.get("content", {})
        video_url = (
            content_data.get("video_url")
            or task_result.get("video_url")
            or task_result.get("output", {}).get("video_url")
        )
        last_frame_url = content_data.get("last_frame_url")

        if not video_url:
            print(f"  ⚠️  No video URL in result: {json.dumps(task_result, indent=2)[:200]}")
            return None

        task_id = task_result.get("id", "unknown")
        if not filename:
            filename = f"segment_{task_id[:12]}.mp4"

        output_path = os.path.join(output_dir, filename)
        os.makedirs(output_dir, exist_ok=True)
        self.client.download_file(video_url, output_path)

        result = {
            "video_path": output_path,
            "video_url": video_url,
            "last_frame_url": last_frame_url,
            "last_frame_path": None,
        }

        if last_frame_url:
            base, _ = os.path.splitext(filename)
            frame_filename = f"{base}_last_frame.jpg"
            frame_path = os.path.join(output_dir, frame_filename)
            try:
                self.client.download_file(last_frame_url, frame_path)
                result["last_frame_path"] = frame_path
            except Exception as e:
                print(f"  ⚠️  Failed to download last frame: {e}")

        return result


# ═══════════════════════════════════════════════════════════
# Pipeline Commands
# ═══════════════════════════════════════════════════════════

def _read_input(input_arg: str) -> str:
    """Read input from file path or raw string."""
    if os.path.isfile(input_arg):
        with open(input_arg, "r", encoding="utf-8") as f:
            return f.read()
    return input_arg


def _load_asset_map(path: str) -> Dict[str, str]:
    """Load asset_map.json."""
    if not path:
        return {}
    if not os.path.isfile(path):
        print(f"⚠️  asset_map not found: {path}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(data, path):
    """Save data as pretty JSON."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def _save_text(text, path):
    """Save text to file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


# ── cmd: parse ────────────────────────────────────────────

def cmd_parse(args):
    """Parse script into structured segments."""
    text = _read_input(args.input)
    asset_map = _load_asset_map(args.asset_map)

    parser = InputParser(asset_map)
    parsed = parser.auto_detect_and_parse(text)

    os.makedirs(args.output_dir, exist_ok=True)
    out_path = _save_json(parsed, os.path.join(args.output_dir, "parsed_segments.json"))

    print(f"✅ Parsed {len(parsed['segments'])} segments → {out_path}")
    print(f"   Mode: {parsed['format']}")
    print(f"   First frame: {'✅' if parsed.get('first_frame') else '—'}")
    print(f"   Last frame: {'✅' if parsed.get('last_frame') else '—'}")
    print(f"   Roles: {list(parsed.get('roles', {}).keys()) or '—'}")
    print(f"   Locations: {list(parsed.get('locations', {}).keys()) or '—'}")

    if args.verbose:
        print(json.dumps(parsed, ensure_ascii=False, indent=2))

    return 0


# ── cmd: rewrite ──────────────────────────────────────────

def cmd_rewrite(args):
    """Rewrite parsed segments to English prompts via LLM."""
    parsed_path = args.input
    if os.path.isfile(parsed_path):
        with open(parsed_path, "r", encoding="utf-8") as f:
            parsed = json.load(f)
    else:
        print(f"❌ File not found: {parsed_path}")
        return 1

    segments = parsed.get("segments", [])
    if not segments:
        print("❌ No segments found in parsed input")
        return 1

    client = ArkClient()
    rewriter = PromptRewriter(client, args.doubao_model)

    print(f"🔄 Rewriting {len(segments)} segments via Doubao LLM...")

    def on_progress(done, total, prompt):
        print(f"  ✅ [{done}/{total}] {prompt[:80]}...")

    prompts = rewriter.rewrite_batch(segments, style=parsed.get("style"),
                                     on_progress=on_progress)

    os.makedirs(args.output_dir, exist_ok=True)
    prompt_path = _save_text("\n\n---\n\n".join(prompts),
                             os.path.join(args.output_dir, "prompt.txt"))

    # Also save as structured JSON
    prompts_json = []
    for seg, prompt in zip(segments, prompts):
        prompts_json.append({
            "index": seg["index"],
            "original": seg["content"],
            "rewritten": prompt,
        })
    _save_json(prompts_json, os.path.join(args.output_dir, "prompts.json"))

    print(f"✅ Rewritten prompts → {prompt_path}")
    return 0


# ── cmd: build ────────────────────────────────────────────

def cmd_build(args):
    """Build API payloads from parsed segments and prompts."""
    # Load parsed segments
    parsed_path = args.parsed
    if not os.path.isfile(parsed_path):
        print(f"❌ Parsed segments file not found: {parsed_path}")
        return 1
    with open(parsed_path, "r", encoding="utf-8") as f:
        parsed = json.load(f)

    # Load prompts
    prompts_path = args.prompts
    prompts = []
    if os.path.isfile(prompts_path):
        with open(prompts_path, "r", encoding="utf-8") as f:
            raw = f.read()
        # Check if JSON format
        if raw.strip().startswith("["):
            data = json.loads(raw)
            prompts = [p["rewritten"] if isinstance(p, dict) else str(p) for p in data]
        else:
            prompts = [p.strip() for p in raw.split("\n---\n") if p.strip()]
    else:
        # Use original content as-is (no rewrite)
        prompts = [seg["content"] for seg in parsed.get("segments", [])]

    segments = parsed.get("segments", [])
    if len(prompts) < len(segments):
        prompts.extend(seg["content"] for seg in segments[len(prompts):])

    model = args.model or DEFAULT_SEEDANCE_MODEL
    if not model:
        print("❌ ARK_SEEDANCE_MODEL is required. Set it via --model or env var.")
        return 1

    payloads = PayloadBuilder.build_batch(
        parsed=parsed,
        prompts=prompts,
        model=model,
        ratio=args.ratio,
        generate_audio=not args.no_audio,
        watermark=args.watermark,
    )

    os.makedirs(args.output_dir, exist_ok=True)
    out_path = _save_json(payloads, os.path.join(args.output_dir, "payload.json"))

    print(f"✅ Built {len(payloads)} payloads → {out_path}")
    for i, p in enumerate(payloads):
        meta = p.get("_meta", {})
        print(f"   Segment {i}: mode={meta.get('mode', '?')}  "
              f"duration={meta.get('duration_s', '?')}s  "
              f"content_items={len(p.get('content', []))}")

    return 0


# ── cmd: submit ───────────────────────────────────────────

def cmd_submit(args):
    """Submit API payloads and download results."""
    payload_path = args.payload
    if not os.path.isfile(payload_path):
        print(f"❌ Payload file not found: {payload_path}")
        return 1

    with open(payload_path, "r", encoding="utf-8") as f:
        payloads = json.load(f)
    if not isinstance(payloads, list):
        payloads = [payloads]

    client = ArkClient()
    manager = TaskManager(client, concurrency=args.concurrency)
    os.makedirs(args.output_dir, exist_ok=True)

    # Submit
    print(f"🚀 Submitting {len(payloads)} tasks (concurrency={args.concurrency})...")
    results = manager.submit_batch(payloads)

    task_ids = []
    for i, r in enumerate(results):
        if "error" in r:
            print(f"  ❌ Segment {i}: {r['error']}")
        else:
            tid = r.get("id", "?")
            task_ids.append(tid)
            meta = r.get("_meta", {})
            print(f"  🚀 Segment {i}: task_id={tid}  mode={meta.get('mode', '?')}")

    if not task_ids:
        print("❌ All submissions failed")
        return 1

    # Poll
    print(f"\n⏳ Polling {len(task_ids)} tasks (interval={POLL_INTERVAL}s, timeout={POLL_TIMEOUT}s)...")
    final_results = manager.poll_all(task_ids, timeout=POLL_TIMEOUT)

    # Download
    downloaded = 0
    for i, r in enumerate(final_results):
        if "error" in r:
            print(f"  ❌ Task {i}: {r['error']}")
            continue

        local = manager.download_result(
            r, args.output_dir,
            filename=f"segment_{i:03d}.mp4",
        )
        if local:
            print(f"  📹 Saved: {local}")
            r["local_path"] = local
            downloaded += 1

    # Save task results
    result_path = _save_json(final_results,
                             os.path.join(args.output_dir, "task_result.json"))

    print(f"\n{'='*60}")
    print(f"✅ Done: {downloaded}/{len(payloads)} segments downloaded")
    print(f"📁 Output: {os.path.abspath(args.output_dir)}")
    print(f"📋 Results: {result_path}")

    return 0


# ── cmd: run (full pipeline) ──────────────────────────────

def cmd_run(args):
    """Full pipeline: parse → rewrite → build → submit → download."""
    # 1. Parse
    print("═" * 60)
    print("  Phase 1/4: Parsing script")
    print("═" * 60)

    text = _read_input(args.input)
    asset_map = _load_asset_map(args.asset_map)

    parser = InputParser(asset_map)
    parsed = parser.auto_detect_and_parse(text)

    os.makedirs(args.output_dir, exist_ok=True)
    _save_json(parsed, os.path.join(args.output_dir, "parsed_segments.json"))

    segments = parsed.get("segments", [])
    print(f"✅ Parsed {len(segments)} segments (format: {parsed['format']})")

    if not segments:
        print("❌ No segments found in input")
        return 1

    # 2. Rewrite
    print("\n" + "═" * 60)
    print("  Phase 2/4: Rewriting prompts (Chinese → English)")
    print("═" * 60)

    model = args.model or DEFAULT_SEEDANCE_MODEL
    if not model:
        print("❌ ARK_SEEDANCE_MODEL is required. Set it via --model or env var.")
        return 1

    prompts = []
    if args.no_rewrite:
        print("⏩ Skipping LLM rewrite (--no-rewrite)")
        prompts = [seg["content"] for seg in segments]
    else:
        client = ArkClient()
        doubao = args.doubao_model or DEFAULT_DOUBAO_MODEL
        if not doubao:
            print("⚠️  No ARK_DOUBAO_MODEL set. Using fallback rewrite.")
            prompts = [PromptRewriter._fallback_rewrite(seg["content"]) for seg in segments]
        else:
            rewriter = PromptRewriter(client, doubao)
            print(f"🔄 Using Doubao model: {doubao}")

            def on_progress(done, total, prompt):
                print(f"  ✅ [{done}/{total}] {prompt[:80]}...")

            prompts = rewriter.rewrite_batch(segments, style=parsed.get("style"),
                                             on_progress=on_progress)

    _save_text("\n\n---\n\n".join(prompts),
               os.path.join(args.output_dir, "prompt.txt"))

    # 3. Build payloads
    print("\n" + "═" * 60)
    print("  Phase 3/4: Building API payloads")
    print("═" * 60)

    payloads = PayloadBuilder.build_batch(
        parsed=parsed,
        prompts=prompts,
        model=model,
        ratio=args.ratio,
        generate_audio=not args.no_audio,
        watermark=args.watermark,
    )

    _save_json(payloads, os.path.join(args.output_dir, "payload.json"))

    for i, p in enumerate(payloads):
        meta = p.get("_meta", {})
        print(f"  Segment {i}: mode={meta.get('mode', '?')}  "
              f"duration={meta.get('duration_s', '?')}s")

    # 4. Submit and download
    print("\n" + "═" * 60)
    print("  Phase 4/4: Submitting tasks & downloading")
    print("═" * 60)

    client = ArkClient()
    manager = TaskManager(client, concurrency=args.concurrency)

    print(f"🚀 Submitting {len(payloads)} tasks (concurrency={args.concurrency})...")
    results = manager.submit_batch(payloads)

    task_ids = []
    for i, r in enumerate(results):
        if "error" in r:
            print(f"  ❌ Segment {i}: {r['error']}")
        else:
            tid = r.get("id", "?")
            task_ids.append(tid)
            print(f"  🚀 Segment {i}: {tid}")

    if not task_ids:
        print("❌ All submissions failed")
        return 1

    print(f"\n⏳ Polling {len(task_ids)} tasks...")
    final_results = manager.poll_all(task_ids, timeout=POLL_TIMEOUT)

    downloaded = 0
    for i, r in enumerate(final_results):
        if "error" in r:
            print(f"  ❌ Task {i}: {r['error']}")
            continue
        local = manager.download_result(r, args.output_dir,
                                        filename=f"segment_{i:03d}.mp4")
        if local:
            print(f"  📹 Saved: {local}")
            r["local_path"] = local
            downloaded += 1

    _save_json(final_results, os.path.join(args.output_dir, "task_result.json"))

    # Summary
    print(f"\n{'='*60}")
    print(f"  ✅ Pipeline complete!")
    print(f"  Segments: {downloaded}/{len(payloads)} downloaded")
    print(f"  Output: {os.path.abspath(args.output_dir)}")
    print(f"  Files:")
    for name in ["parsed_segments.json", "prompt.txt", "payload.json",
                  "task_result.json"]:
        fpath = os.path.join(args.output_dir, name)
        if os.path.exists(fpath):
            print(f"    📄 {name}")
    for name in sorted(os.listdir(args.output_dir)):
        if name.endswith(".mp4"):
            print(f"    📹 {name}")
    print(f"{'='*60}")

    return 0


# ── cmd: status ───────────────────────────────────────────

def cmd_status(args):
    """Check environment configuration."""
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  Seedance Short Drama Director - 环境检查 / Status       ║")
    print("╠═══════════════════════════════════════════════════════════╣")

    # API Key
    api_key = os.environ.get("ARK_API_KEY", "")
    key_status = f"✅ ...{api_key[-8:]}" if len(api_key) > 8 else "❌ Not set"
    print(f"║  ARK_API_KEY:       {key_status:<38} ║")

    # Seedance model
    seedance = DEFAULT_SEEDANCE_MODEL
    m_status = f"✅ {seedance[:30]}" if seedance else "❌ Not set"
    print(f"║  ARK_SEEDANCE_MODEL:{m_status:<38} ║")

    # Doubao model
    doubao = DEFAULT_DOUBAO_MODEL
    d_status = f"✅ {doubao[:30]}" if doubao else "⚠️  Not set (rewrite disabled)"
    print(f"║  ARK_DOUBAO_MODEL:  {d_status:<38} ║")

    # Concurrency
    print(f"║  ARK_CONCURRENCY:   ✅ {DEFAULT_CONCURRENCY:<37} ║")

    print("╠═══════════════════════════════════════════════════════════╣")

    # Dependencies
    req = "✅ Installed" if HAS_REQUESTS else "❌ Not installed (pip install requests)"
    print(f"║  requests:          {req:<38} ║")

    print("╠═══════════════════════════════════════════════════════════╣")

    # Features
    has_key = bool(api_key)
    has_seedance = bool(seedance)
    has_doubao = bool(doubao)
    print(f"║  {'✅' if has_key else '❌'} API 连接 / API Access                               ║")
    print(f"║  {'✅' if has_seedance else '❌'} 视频生成 / Video Generation                        ║")
    print(f"║  {'✅' if has_doubao else '⚠️ '} Prompt 改写 / Prompt Rewriting                     ║")

    print("╚═══════════════════════════════════════════════════════════╝")

    if not api_key:
        print("\n💡 Set required env vars:")
        print("   export ARK_API_KEY='your-api-key'")
        print("   export ARK_SEEDANCE_MODEL='ep-xxxxx'")
        print("   export ARK_DOUBAO_MODEL='ep-xxxxx'  # Optional, for prompt rewriting")

    return 0


# ═══════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Seedance Short Drama Director - 短剧视频导演工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples / 示例:
  # Full pipeline
  seedance_cli.py run -i script.txt -a asset_map.json -o ./output

  # Step by step
  seedance_cli.py parse -i script.txt -a asset_map.json -o ./output
  seedance_cli.py rewrite -i ./output/parsed_segments.json -o ./output
  seedance_cli.py build -p ./output/parsed_segments.json --prompts ./output/prompt.txt -o ./output
  seedance_cli.py submit -p ./output/payload.json -o ./output

  # Check environment
  seedance_cli.py status
        """,
    )
    sub = parser.add_subparsers(dest="command")

    # ── run ────────────────────────────────
    p = sub.add_parser("run", help="Full pipeline: parse → rewrite → build → submit → download")
    p.add_argument("-i", "--input", required=True,
                   help="Script file path or raw text")
    p.add_argument("-a", "--asset-map",
                   help="Path to asset_map.json")
    p.add_argument("-o", "--output-dir", default="./seedance_output",
                   help="Output directory (default: ./seedance_output)")
    p.add_argument("-m", "--model", default="",
                   help="Seedance model endpoint ID (or set ARK_SEEDANCE_MODEL)")
    p.add_argument("--doubao-model", default="",
                   help="Doubao model endpoint ID for prompt rewriting (or set ARK_DOUBAO_MODEL)")
    p.add_argument("-r", "--ratio", default=DEFAULT_RATIO,
                   choices=["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
                   help="Aspect ratio (default: 16:9)")
    p.add_argument("-c", "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                   help=f"Max concurrent tasks (default: {DEFAULT_CONCURRENCY})")
    p.add_argument("--no-audio", action="store_true",
                   help="Disable audio generation")
    p.add_argument("--watermark", action="store_true",
                   help="Add watermark")
    p.add_argument("--no-rewrite", action="store_true",
                   help="Skip LLM prompt rewriting")

    # ── parse ──────────────────────────────
    p = sub.add_parser("parse", help="Parse script into structured segments")
    p.add_argument("-i", "--input", required=True,
                   help="Script file path or raw text")
    p.add_argument("-a", "--asset-map",
                   help="Path to asset_map.json")
    p.add_argument("-o", "--output-dir", default="./seedance_output")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Print parsed result")

    # ── rewrite ────────────────────────────
    p = sub.add_parser("rewrite", help="Rewrite Chinese prompts to English via LLM")
    p.add_argument("-i", "--input", required=True,
                   help="Path to parsed_segments.json")
    p.add_argument("--doubao-model", default="",
                   help="Doubao model endpoint ID (or set ARK_DOUBAO_MODEL)")
    p.add_argument("-o", "--output-dir", default="./seedance_output")

    # ── build ──────────────────────────────
    p = sub.add_parser("build", help="Build API payloads")
    p.add_argument("-p", "--parsed", required=True,
                   help="Path to parsed_segments.json")
    p.add_argument("--prompts", default="",
                   help="Path to prompt.txt or prompts.json")
    p.add_argument("-m", "--model", default="",
                   help="Seedance model endpoint ID")
    p.add_argument("-r", "--ratio", default=DEFAULT_RATIO,
                   choices=["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"])
    p.add_argument("--no-audio", action="store_true")
    p.add_argument("--watermark", action="store_true")
    p.add_argument("-o", "--output-dir", default="./seedance_output")

    # ── submit ─────────────────────────────
    p = sub.add_parser("submit", help="Submit payloads and download results")
    p.add_argument("-p", "--payload", required=True,
                   help="Path to payload.json")
    p.add_argument("-o", "--output-dir", default="./seedance_output")
    p.add_argument("-c", "--concurrency", type=int, default=DEFAULT_CONCURRENCY)

    # ── status ─────────────────────────────
    sub.add_parser("status", help="Check environment configuration")

    args = parser.parse_args()

    if args.command == "run":
        return cmd_run(args)
    elif args.command == "parse":
        return cmd_parse(args)
    elif args.command == "rewrite":
        return cmd_rewrite(args)
    elif args.command == "build":
        return cmd_build(args)
    elif args.command == "submit":
        return cmd_submit(args)
    elif args.command == "status":
        return cmd_status(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
