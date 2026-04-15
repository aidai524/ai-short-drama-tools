#!/usr/bin/env python3
"""
Kling Short Drama Director - 短剧视频导演工具
基于 Kling AI v3 Omni API 的短剧视频生成工具

Usage:
    python kling_cli.py run -i script.txt -a asset_map.json -o ./output
    python kling_cli.py parse -i script.txt -a asset_map.json
    python kling_cli.py rewrite -i parsed_segments.json
    python kling_cli.py build -i parsed_segments.json -p prompts.txt
    python kling_cli.py submit -p payload.json -o ./output
    python kling_cli.py status
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

try:
    import jwt
    HAS_PYJWT = True
except ImportError:
    HAS_PYJWT = False


# ═══════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════

KLING_API_BASE = os.environ.get("KLING_API_BASE", "https://api-beijing.klingai.com")
KLING_MODEL = os.environ.get("KLING_MODEL", "kling-v3-omni")
KLING_MODE = os.environ.get("KLING_MODE", "std")
DEFAULT_RATIO = os.environ.get("KLING_DEFAULT_RATIO", "9:16")
DEFAULT_DURATION = os.environ.get("KLING_DEFAULT_DURATION", "10")
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_DOUBAO_MODEL = os.environ.get("ARK_DOUBAO_MODEL", "")
DEFAULT_CONCURRENCY = int(os.environ.get("ARK_CONCURRENCY", "3"))
DEFAULT_DURATION_MS = int(os.environ.get("ARK_DEFAULT_DURATION_MS", "10000"))
POLL_INTERVAL = 10
POLL_TIMEOUT = 600

CONTINUITY_SUFFIX = (
    " Maintain strict visual continuity: same outfit, same hairstyle, "
    "same location layout, same lighting, direct continuity with previous/next segment."
)

MONOLOGUE_PATTERNS = [
    (r"心里想[：:]?\s*", "silent internal monologue, lips closed, contemplative expression: "),
    (r"内心独白[：:]?\s*", "silent internal monologue, lips closed, contemplative expression: "),
    (r"心里默默想[：:]?\s*", "silent internal monologue, lips closed, contemplative expression: "),
    (r"暗自心想[：:]?\s*", "silent internal monologue, lips closed, contemplative expression: "),
    (r"心想[：:]?\s*", "silent internal monologue, lips closed, contemplative expression: "),
]


# ═══════════════════════════════════════════════════════════
# Kling API Client
# ═══════════════════════════════════════════════════════════

class KlingClient:
    """HTTP client for Kling AI v3 Omni API."""

    def __init__(self, access_key: str = None, secret_key: str = None):
        self.access_key = access_key or os.environ.get("KLING_ACCESS_KEY", "")
        self.secret_key = secret_key or os.environ.get("KLING_SECRET_KEY", "")
        if not self.access_key or not self.secret_key:
            raise ValueError(
                "KLING_ACCESS_KEY and KLING_SECRET_KEY are required. "
                "Set them via: export KLING_ACCESS_KEY='your-access-key' && "
                "export KLING_SECRET_KEY='your-secret-key'"
            )
        if not HAS_REQUESTS:
            raise ImportError("requests is required: pip install requests")
        if not HAS_PYJWT:
            raise ImportError("PyJWT is required: pip install PyJWT")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
        })

    def _generate_jwt(self) -> str:
        """Generate JWT token for Kling API authentication."""
        now = int(time.time())
        payload = {
            "iss": self.access_key,
            "exp": now + 1800,
            "nbf": now - 5,
        }
        headers = {
            "alg": "HS256",
            "typ": "JWT",
        }
        return jwt.encode(payload, self.secret_key, headers=headers, algorithm="HS256")

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers with JWT token."""
        token = self._generate_jwt()
        return {"Authorization": f"Bearer {token}"}

    # ── Video Generation ──────────────────────────────────

    def create_text2video_task(self, model: str, prompt: str,
                               duration: str = "5",
                               ratio: str = DEFAULT_RATIO,
                               mode: str = KLING_MODE,
                               negative_prompt: str = None,
                               cfg_scale: float = 0.5) -> Dict:
        """Create a text-to-video task."""
        payload = {
            "model": model,
            "prompt": prompt,
            "duration": duration,
            "mode": mode,
            "aspect_ratio": ratio,
            "cfg_scale": cfg_scale,
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        headers = self._get_auth_headers()
        resp = self.session.post(
            f"{KLING_API_BASE}/v1/videos/text2video",
            json=payload,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()

    def create_image2video_task(self, model: str, prompt: str, image: str,
                               duration: str = "5",
                               ratio: str = DEFAULT_RATIO,
                               mode: str = KLING_MODE,
                               cfg_scale: float = 0.5) -> Dict:
        """Create an image-to-video task."""
        payload = {
            "model": model,
            "prompt": prompt,
            "image": image,
            "duration": duration,
            "mode": mode,
            "aspect_ratio": ratio,
            "cfg_scale": cfg_scale,
        }
        headers = self._get_auth_headers()
        resp = self.session.post(
            f"{KLING_API_BASE}/v1/videos/image2video",
            json=payload,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()

    def create_extend_video_task(self, model: str, prompt: str, video: str,
                                duration: str = "5",
                                mode: str = KLING_MODE) -> Dict:
        """Create a video extension task."""
        payload = {
            "model": model,
            "prompt": prompt,
            "video": video,
            "duration": duration,
            "mode": mode,
        }
        headers = self._get_auth_headers()
        resp = self.session.post(
            f"{KLING_API_BASE}/v1/videos/extend-video",
            json=payload,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()

    def get_task(self, task_id: str, task_type: str = "text2video") -> Dict:
        """Get task status and result."""
        headers = self._get_auth_headers()
        endpoint_map = {
            "text2video": "/v1/videos/text2video",
            "image2video": "/v1/videos/image2video",
            "extend-video": "/v1/videos/extend-video",
        }
        endpoint = endpoint_map.get(task_type, "/v1/videos/text2video")
        resp = self.session.get(
            f"{KLING_API_BASE}{endpoint}/{task_id}",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

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
        url = self.asset_map.get(ref) or self.asset_map.get(ref.lstrip("@"))
        if not url:
            raise ValueError(
                f"Asset '{ref}' not found in asset_map.json. "
                f"Available keys: {list(self.asset_map.keys())[:10]}"
            )
        return url

    def auto_detect_and_parse(self, text: str) -> Dict[str, Any]:
        """Auto-detect format and parse."""
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

        content_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            m = re.match(r"^首帧\s*[：:]\s*(.+)$", stripped)
            if m:
                result["first_frame"] = self.resolve_asset(m.group(1).strip())
                continue

            m = re.match(r"^尾帧\s*[：:]\s*(.+)$", stripped)
            if m:
                result["last_frame"] = self.resolve_asset(m.group(1).strip())
                continue

            m = re.match(r"^(@\S+)\s*(?:为|是|扮演)\s*(.+)$", stripped)
            if m:
                asset_id = m.group(1)
                role_desc = m.group(2).strip()
                result["roles"][asset_id] = {
                    "url": self._safe_resolve(asset_id),
                    "description": role_desc,
                }
                continue

            m = re.match(r"^场景\s*[：:]\s*(.+)$", stripped)
            if m:
                loc_id = f"L{len(result['locations']) + 1}"
                result["locations"][loc_id] = m.group(1).strip()
                continue

            m = re.match(r"^风格\s*[：:]\s*(.+)$", stripped)
            if m:
                result["style"] = m.group(1).strip()
                continue

            content_lines.append(stripped)

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

        m = re.search(r"画面风格\s*[：:]\s*(.+?)(?:\n|$)", text)
        if m:
            result["style"] = m.group(1).strip()
        m = re.search(r"<style>(.+?)</style>", text)
        if m:
            result["style"] = m.group(1).strip()

        m = re.search(r"<first-frame>(.+?)</first-frame>", text)
        if m:
            result["first_frame"] = self.resolve_asset(m.group(1).strip())
        m = re.search(r"<last-frame>(.+?)</last-frame>", text)
        if m:
            result["last_frame"] = self.resolve_asset(m.group(1).strip())

        for m in re.finditer(r"<location>(.+?)</location>", text):
            loc_id = f"L{len(result['locations']) + 1}"
            result["locations"][loc_id] = m.group(1).strip()

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

        full_text = text.strip()
        segments = self._split_into_segments(full_text)

        for i, seg in enumerate(segments):
            duration_ms = self._extract_duration(seg) or DEFAULT_DURATION_MS
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
        m = re.search(r"<duration-ms\s*>(\d+)</duration-ms>", text)
        if m:
            return int(m.group(1))
        m = re.search(r"(?:时长|duration)\s*[：:]\s*(\d+)\s*(?:秒|s|ms|毫秒)?", text, re.IGNORECASE)
        if m:
            val = int(m.group(1))
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
    """Rewrite Chinese drama scripts to English prompts via Doubao LLM."""

    SYSTEM_PROMPT = """You are a professional video prompt writer for Kling AI, a cinematic AI video generator.

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

    def __init__(self, client, model: str = None):
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
# Doubao LLM Client (for prompt rewriting)
# ═══════════════════════════════════════════════════════════

class DoubaoClient:
    """HTTP client for Doubao LLM API (used for prompt rewriting)."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("ARK_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "ARK_API_KEY is required for prompt rewriting. "
                "Set it via: export ARK_API_KEY='your-api-key'"
            )
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        })
        self.api_base = "https://ark.ap-southeast.bytepluses.com/api/v3"

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
            f"{self.api_base}/chat/completions",
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


# ═══════════════════════════════════════════════════════════
# Payload Builder
# ═══════════════════════════════════════════════════════════

class KlingPayloadBuilder:
    """Build Kling AI v3 Omni API request payloads."""

    @staticmethod
    def _duration_ms_to_kling(duration_ms: int) -> str:
        """Convert duration in ms to Kling format string ('5' or '10')."""
        duration_s = duration_ms / 1000
        if duration_s <= 5:
            return "5"
        else:
            return "10"

    @staticmethod
    def detect_mode(first_frame: str = None, last_frame: str = None) -> str:
        """Detect the video generation mode based on available frames."""
        if first_frame and last_frame:
            return "image2video"
        elif first_frame:
            return "image2video"
        elif last_frame:
            return "image2video"
        else:
            return "text2video"

    @staticmethod
    def build_payload(model: str, prompt: str,
                      duration: str = "10",
                      ratio: str = DEFAULT_RATIO,
                      mode: str = KLING_MODE,
                      first_frame: str = None,
                      last_frame: str = None,
                      negative_prompt: str = None,
                      cfg_scale: float = 0.5) -> Dict:
        """Build a complete API request payload for text-to-video or image-to-video."""
        payload = {
            "model": model,
            "prompt": prompt,
            "duration": duration,
            "mode": mode,
            "aspect_ratio": ratio,
            "cfg_scale": cfg_scale,
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if first_frame:
            payload["image"] = first_frame
        return payload

    @staticmethod
    def build_batch(parsed: Dict[str, Any], prompts: List[str],
                    model: str, ratio: str = DEFAULT_RATIO,
                    mode: str = KLING_MODE) -> List[Dict]:
        """Build payloads for all segments."""
        payloads = []
        segments = parsed.get("segments", [])
        total_segs = len(segments)
        global_first = parsed.get("first_frame")
        global_last = parsed.get("last_frame")

        for i, seg in enumerate(segments):
            prompt = prompts[i] if i < len(prompts) else seg["content"]

            prompt += CONTINUITY_SUFFIX

            duration_ms = seg.get("duration_ms", DEFAULT_DURATION_MS)
            duration_str = KlingPayloadBuilder._duration_ms_to_kling(duration_ms)

            seg_first = seg.get("first_frame")
            seg_last = seg.get("last_frame")

            if seg_first is None and i == 0:
                seg_first = global_first
            if seg_last is None and i == total_segs - 1:
                seg_last = global_last

            mode_type = KlingPayloadBuilder.detect_mode(seg_first, seg_last)

            payload = KlingPayloadBuilder.build_payload(
                model=model,
                prompt=prompt,
                duration=duration_str,
                ratio=ratio,
                mode=mode,
                first_frame=seg_first,
                last_frame=seg_last,
            )
            payload["_meta"] = {
                "segment_index": i,
                "mode": mode_type,
                "duration": duration_str,
                "duration_ms": duration_ms,
            }
            payloads.append(payload)

        return payloads

    @staticmethod
    def build_chain_payload(model: str, prompt: str, prev_video_url: str,
                            duration: str = "10",
                            mode: str = KLING_MODE) -> Dict:
        """Build a payload for video extension (continuing from previous video)."""
        return {
            "model": model,
            "prompt": prompt,
            "video": prev_video_url,
            "duration": duration,
            "mode": mode,
        }


# ═══════════════════════════════════════════════════════════
# Task Manager
# ═══════════════════════════════════════════════════════════

class KlingTaskManager:
    """Submit, poll, and download Kling video generation tasks with concurrency control."""

    def __init__(self, client: KlingClient, concurrency: int = DEFAULT_CONCURRENCY):
        self.client = client
        self.concurrency = concurrency
        self._semaphore = threading.Semaphore(concurrency)

    def submit_one(self, payload: Dict) -> Dict:
        """Submit a single video generation task. Returns API response."""
        with self._semaphore:
            meta = payload.pop("_meta", None)
            task_type = meta.get("mode", "text2video") if meta else "text2video"
            try:
                if task_type == "image2video" and payload.get("image"):
                    result = self.client.create_image2video_task(
                        model=payload["model"],
                        prompt=payload["prompt"],
                        image=payload["image"],
                        duration=payload.get("duration", "5"),
                        ratio=payload.get("aspect_ratio", DEFAULT_RATIO),
                        mode=payload.get("mode", KLING_MODE),
                        cfg_scale=payload.get("cfg_scale", 0.5),
                    )
                    result["_meta"] = meta or {}
                    result["_meta"]["task_type"] = "image2video"
                else:
                    result = self.client.create_text2video_task(
                        model=payload["model"],
                        prompt=payload["prompt"],
                        duration=payload.get("duration", "5"),
                        ratio=payload.get("aspect_ratio", DEFAULT_RATIO),
                        mode=payload.get("mode", KLING_MODE),
                        cfg_scale=payload.get("cfg_scale", 0.5),
                    )
                    result["_meta"] = meta or {}
                    result["_meta"]["task_type"] = "text2video"
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

    def poll_task(self, task_id: str, task_type: str = "text2video",
                  timeout: int = POLL_TIMEOUT) -> Dict:
        """Poll a single task until it succeeds, fails, or times out."""
        start = time.time()
        while time.time() - start < timeout:
            result = self.client.get_task(task_id, task_type)
            status = result.get("data", {}).get("task_status", "unknown")

            if status == "succeed":
                return result
            elif status == "failed":
                error = result.get("message", result.get("error", "unknown"))
                raise RuntimeError(f"Task {task_id} failed: {error}")

            elapsed = int(time.time() - start)
            print(f"  ⏳ [{task_id[:16]}...] status={status}  ({elapsed}s elapsed)")
            time.sleep(POLL_INTERVAL)

        raise TimeoutError(f"Task {task_id} timed out after {timeout}s")

    def poll_all(self, task_infos: List[Tuple[str, str]],
                 timeout: int = POLL_TIMEOUT) -> List[Dict]:
        """Poll all tasks concurrently and return results."""
        results = [None] * len(task_infos)

        def _poll_one(idx, tid, ttype):
            try:
                results[idx] = self.poll_task(tid, ttype, timeout)
            except Exception as e:
                results[idx] = {"id": tid, "error": str(e)}

        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            futures = [
                pool.submit(_poll_one, i, tid, ttype)
                for i, (tid, ttype) in enumerate(task_infos)
            ]
            for f in as_completed(futures):
                f.result()

        return results

    def download_result(self, task_result: Dict, output_dir: str,
                        filename: str = None) -> Dict:
        """Download video from a completed task result.
        
        Returns dict with keys:
          - video_path: local path to downloaded video
          - video_url: original video URL
        """
        task_data = task_result.get("data", {})
        task_result_info = task_data.get("task_result", {})
        videos = task_result_info.get("videos", [])

        if not videos:
            print(f"  ⚠️  No video URL in result")
            return None

        video_info = videos[0]
        video_url = video_info.get("url")
        if not video_url:
            print(f"  ⚠️  No video URL in result")
            return None

        task_id = task_data.get("task_id", "unknown")
        if not filename:
            filename = f"segment_{task_id[:12]}.mp4"

        output_path = os.path.join(output_dir, filename)
        os.makedirs(output_dir, exist_ok=True)
        self.client.download_file(video_url, output_path)

        return {
            "video_path": output_path,
            "video_url": video_url,
        }


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

    client = DoubaoClient()
    rewriter = PromptRewriter(client, args.doubao_model)

    print(f"🔄 Rewriting {len(segments)} segments via Doubao LLM...")

    def on_progress(done, total, prompt):
        print(f"  ✅ [{done}/{total}] {prompt[:80]}...")

    prompts = rewriter.rewrite_batch(segments, style=parsed.get("style"),
                                     on_progress=on_progress)

    os.makedirs(args.output_dir, exist_ok=True)
    prompt_path = _save_text("\n\n---\n\n".join(prompts),
                             os.path.join(args.output_dir, "prompt.txt"))

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
    parsed_path = args.parsed
    if not os.path.isfile(parsed_path):
        print(f"❌ Parsed segments file not found: {parsed_path}")
        return 1
    with open(parsed_path, "r", encoding="utf-8") as f:
        parsed = json.load(f)

    prompts_path = args.prompts
    prompts = []
    if os.path.isfile(prompts_path):
        with open(prompts_path, "r", encoding="utf-8") as f:
            raw = f.read()
        if raw.strip().startswith("["):
            data = json.loads(raw)
            prompts = [p["rewritten"] if isinstance(p, dict) else str(p) for p in data]
        else:
            prompts = [p.strip() for p in raw.split("\n---\n") if p.strip()]
    else:
        prompts = [seg["content"] for seg in parsed.get("segments", [])]

    segments = parsed.get("segments", [])
    if len(prompts) < len(segments):
        prompts.extend(seg["content"] for seg in segments[len(prompts):])

    model = args.model or KLING_MODEL
    if not model:
        print("❌ KLING_MODEL is required. Set it via --model or env var.")
        return 1

    payloads = KlingPayloadBuilder.build_batch(
        parsed=parsed,
        prompts=prompts,
        model=model,
        ratio=args.ratio,
        mode=args.mode,
    )

    os.makedirs(args.output_dir, exist_ok=True)
    out_path = _save_json(payloads, os.path.join(args.output_dir, "payload.json"))

    print(f"✅ Built {len(payloads)} payloads → {out_path}")
    for i, p in enumerate(payloads):
        meta = p.get("_meta", {})
        has_image = "image" in p
        print(f"   Segment {i}: type={'i2v' if has_image else 't2v'}  "
              f"duration={meta.get('duration', '?')}s  "
              f"prompt_len={len(p.get('prompt', ''))}")

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

    client = KlingClient()
    manager = KlingTaskManager(client, concurrency=args.concurrency)
    os.makedirs(args.output_dir, exist_ok=True)

    print(f"🚀 Submitting {len(payloads)} tasks (concurrency={args.concurrency})...")
    results = manager.submit_batch(payloads)

    task_infos = []
    for i, r in enumerate(results):
        if "error" in r:
            print(f"  ❌ Segment {i}: {r['error']}")
        else:
            data = r.get("data", {})
            tid = data.get("task_id", "?")
            task_type = r.get("_meta", {}).get("task_type", "text2video")
            task_infos.append((tid, task_type))
            print(f"  🚀 Segment {i}: task_id={tid}  type={task_type}")

    if not task_infos:
        print("❌ All submissions failed")
        return 1

    print(f"\n⏳ Polling {len(task_infos)} tasks (interval={POLL_INTERVAL}s, timeout={POLL_TIMEOUT}s)...")
    final_results = manager.poll_all(task_infos, timeout=POLL_TIMEOUT)

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

    print("\n" + "═" * 60)
    print("  Phase 2/4: Rewriting prompts (Chinese → English)")
    print("═" * 60)

    model = args.model or KLING_MODEL
    if not model:
        print("❌ KLING_MODEL is required. Set it via --model or env var.")
        return 1

    prompts = []
    if args.no_rewrite:
        print("⏩ Skipping LLM rewrite (--no-rewrite)")
        prompts = [seg["content"] for seg in segments]
    else:
        doubao = args.doubao_model or DEFAULT_DOUBAO_MODEL
        if not doubao:
            print("⚠️  No ARK_DOUBAO_MODEL set. Using fallback rewrite.")
            prompts = [PromptRewriter._fallback_rewrite(seg["content"]) for seg in segments]
        else:
            client = DoubaoClient()
            rewriter = PromptRewriter(client, doubao)
            print(f"🔄 Using Doubao model: {doubao}")

            def on_progress(done, total, prompt):
                print(f"  ✅ [{done}/{total}] {prompt[:80]}...")

            prompts = rewriter.rewrite_batch(segments, style=parsed.get("style"),
                                             on_progress=on_progress)

    _save_text("\n\n---\n\n".join(prompts),
               os.path.join(args.output_dir, "prompt.txt"))

    print("\n" + "═" * 60)
    print("  Phase 3/4: Building API payloads")
    print("═" * 60)

    payloads = KlingPayloadBuilder.build_batch(
        parsed=parsed,
        prompts=prompts,
        model=model,
        ratio=args.ratio,
        mode=args.mode,
    )

    _save_json(payloads, os.path.join(args.output_dir, "payload.json"))

    for i, p in enumerate(payloads):
        meta = p.get("_meta", {})
        has_image = "image" in p
        print(f"  Segment {i}: type={'i2v' if has_image else 't2v'}  "
              f"duration={meta.get('duration', '?')}s")

    print("\n" + "═" * 60)
    print("  Phase 4/4: Submitting tasks & downloading")
    print("═" * 60)

    client = KlingClient()
    manager = KlingTaskManager(client, concurrency=args.concurrency)

    print(f"🚀 Submitting {len(payloads)} tasks (concurrency={args.concurrency})...")
    results = manager.submit_batch(payloads)

    task_infos = []
    for i, r in enumerate(results):
        if "error" in r:
            print(f"  ❌ Segment {i}: {r['error']}")
        else:
            data = r.get("data", {})
            tid = data.get("task_id", "?")
            task_type = r.get("_meta", {}).get("task_type", "text2video")
            task_infos.append((tid, task_type))
            print(f"  🚀 Segment {i}: {tid}")

    if not task_infos:
        print("❌ All submissions failed")
        return 1

    print(f"\n⏳ Polling {len(task_infos)} tasks...")
    final_results = manager.poll_all(task_infos, timeout=POLL_TIMEOUT)

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
    print("║  Kling Short Drama Director - 环境检查 / Status          ║")
    print("╠═══════════════════════════════════════════════════════════╣")

    access_key = os.environ.get("KLING_ACCESS_KEY", "")
    secret_key = os.environ.get("KLING_SECRET_KEY", "")
    key_status = f"✅ ...{access_key[-8:]}" if len(access_key) > 8 else "❌ Not set"
    print(f"║  KLING_ACCESS_KEY:   {key_status:<38} ║")
    sk_status = f"✅ ...{secret_key[-8:]}" if len(secret_key) > 8 else "❌ Not set"
    print(f"║  KLING_SECRET_KEY:    {sk_status:<38} ║")

    kling_model = KLING_MODEL
    m_status = f"✅ {kling_model[:30]}" if kling_model else "❌ Not set"
    print(f"║  KLING_MODEL:        {m_status:<38} ║")

    kling_mode = KLING_MODE
    print(f"║  KLING_MODE:         ✅ {kling_mode:<37} ║")

    kling_ratio = DEFAULT_RATIO
    print(f"║  KLING_DEFAULT_RATIO: ✅ {kling_ratio:<36} ║")

    doubao = DEFAULT_DOUBAO_MODEL
    d_status = f"✅ {doubao[:30]}" if doubao else "⚠️  Not set (rewrite disabled)"
    print(f"║  ARK_DOUBAO_MODEL:   {d_status:<38} ║")

    arki_key = os.environ.get("ARK_API_KEY", "")
    ark_status = f"✅ ...{arki_key[-8:]}" if len(arki_key) > 8 else "⚠️  Not set (rewrite disabled)"
    print(f"║  ARK_API_KEY:        {ark_status:<38} ║")

    print(f"║  ARK_CONCURRENCY:    ✅ {DEFAULT_CONCURRENCY:<37} ║")

    print("╠═══════════════════════════════════════════════════════════╣")

    req = "✅ Installed" if HAS_REQUESTS else "❌ Not installed (pip install requests)"
    print(f"║  requests:           {req:<38} ║")

    jwt_lib = "✅ Installed" if HAS_PYJWT else "❌ Not installed (pip install PyJWT)"
    print(f"║  PyJWT:              {jwt_lib:<38} ║")

    print("╠═══════════════════════════════════════════════════════════╣")

    has_access = bool(access_key and secret_key)
    has_model = bool(kling_model)
    has_doubao = bool(doubao and arki_key)
    print(f"║  {'✅' if has_access else '❌'} API 连接 / API Access                               ║")
    print(f"║  {'✅' if has_model else '❌'} 视频生成 / Video Generation                        ║")
    print(f"║  {'✅' if has_doubao else '⚠️ '} Prompt 改写 / Prompt Rewriting                     ║")

    print("╚═══════════════════════════════════════════════════════════╝")

    if not access_key or not secret_key:
        print("\n💡 Set required env vars:")
        print("   export KLING_ACCESS_KEY='your-access-key'")
        print("   export KLING_SECRET_KEY='your-secret-key'")
        print("   export KLING_MODEL='kling-v3-omni'")
        print("   # Optional, for prompt rewriting:")
        print("   export ARK_DOUBAO_MODEL='ep-xxxxx'")
        print("   export ARK_API_KEY='your-api-key'")

    return 0


# ═══════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Kling Short Drama Director - 短剧视频导演工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples / 示例:
  # Full pipeline
  kling_cli.py run -i script.txt -a asset_map.json -o ./output

  # Step by step
  kling_cli.py parse -i script.txt -a asset_map.json -o ./output
  kling_cli.py rewrite -i ./output/parsed_segments.json -o ./output
  kling_cli.py build -p ./output/parsed_segments.json --prompts ./output/prompt.txt -o ./output
  kling_cli.py submit -p ./output/payload.json -o ./output

  # Check environment
  kling_cli.py status
        """,
    )
    sub = parser.add_subparsers(dest="command")

    # ── run ────────────────────────────────
    p = sub.add_parser("run", help="Full pipeline: parse → rewrite → build → submit → download")
    p.add_argument("-i", "--input", required=True,
                   help="Script file path or raw text")
    p.add_argument("-a", "--asset-map",
                   help="Path to asset_map.json")
    p.add_argument("-o", "--output-dir", default="./kling_output",
                   help="Output directory (default: ./kling_output)")
    p.add_argument("-m", "--model", default="",
                   help="Kling model name (or set KLING_MODEL)")
    p.add_argument("--doubao-model", default="",
                   help="Doubao model endpoint ID for prompt rewriting (or set ARK_DOUBAO_MODEL)")
    p.add_argument("-r", "--ratio", default=DEFAULT_RATIO,
                   choices=["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
                   help=f"Aspect ratio (default: {DEFAULT_RATIO})")
    p.add_argument("--mode", default=KLING_MODE,
                   choices=["std", "pro"],
                   help=f"Generation mode (default: {KLING_MODE})")
    p.add_argument("-c", "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                   help=f"Max concurrent tasks (default: {DEFAULT_CONCURRENCY})")
    p.add_argument("--no-rewrite", action="store_true",
                   help="Skip LLM prompt rewriting")

    # ── parse ──────────────────────────────
    p = sub.add_parser("parse", help="Parse script into structured segments")
    p.add_argument("-i", "--input", required=True,
                   help="Script file path or raw text")
    p.add_argument("-a", "--asset-map",
                   help="Path to asset_map.json")
    p.add_argument("-o", "--output-dir", default="./kling_output")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Print parsed result")

    # ── rewrite ────────────────────────────
    p = sub.add_parser("rewrite", help="Rewrite Chinese prompts to English via LLM")
    p.add_argument("-i", "--input", required=True,
                   help="Path to parsed_segments.json")
    p.add_argument("--doubao-model", default="",
                   help="Doubao model endpoint ID (or set ARK_DOUBAO_MODEL)")
    p.add_argument("-o", "--output-dir", default="./kling_output")

    # ── build ──────────────────────────────
    p = sub.add_parser("build", help="Build API payloads")
    p.add_argument("-p", "--parsed", required=True,
                   help="Path to parsed_segments.json")
    p.add_argument("--prompts", default="",
                   help="Path to prompt.txt or prompts.json")
    p.add_argument("-m", "--model", default="",
                   help="Kling model name")
    p.add_argument("-r", "--ratio", default=DEFAULT_RATIO,
                   choices=["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"])
    p.add_argument("--mode", default=KLING_MODE,
                   choices=["std", "pro"])
    p.add_argument("-o", "--output-dir", default="./kling_output")

    # ── submit ─────────────────────────────
    p = sub.add_parser("submit", help="Submit payloads and download results")
    p.add_argument("-p", "--payload", required=True,
                   help="Path to payload.json")
    p.add_argument("-o", "--output-dir", default="./kling_output")
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
