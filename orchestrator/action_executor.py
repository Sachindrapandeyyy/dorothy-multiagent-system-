"""
Dorothy OS v2.0 — Action Executor
Layer 2 Agentic Execution: Intercepts routed intents and executes real
system actions BEFORE sending to LLM. The LLM then narrates what was done.

This is the bridge between "talking about actions" and "performing actions".
"""

import re
import logging
import webbrowser
import asyncio
from typing import Dict, Any, Optional, Tuple
from orchestrator.intent_router import IntentRouter, IntentMatch

logger = logging.getLogger("Dorothy.ActionExecutor")

# Singleton router
_router = IntentRouter()


# ── URL Patterns for "play X on Y" ──────────────────────────────────────────

PLAY_TARGETS: Dict[str, str] = {
    "youtube":  "https://www.youtube.com/results?search_query={}",
    "spotify":  "https://open.spotify.com/search/{}",
    "soundcloud": "https://soundcloud.com/search?q={}",
    "jiosaavn": "https://www.jiosaavn.com/search/{}",
    "gaana":    "https://gaana.com/search/{}",
    "wynk":     "https://wynk.in/music/search?q={}",
}

SEARCH_TARGETS: Dict[str, str] = {
    "google":   "https://www.google.com/search?q={}",
    "bing":     "https://www.bing.com/search?q={}",
    "youtube":  "https://www.youtube.com/results?search_query={}",
    "github":   "https://github.com/search?q={}",
    "stack overflow": "https://stackoverflow.com/search?q={}",
    "stackoverflow": "https://stackoverflow.com/search?q={}",
    "amazon":   "https://www.amazon.in/s?k={}",
    "flipkart": "https://www.flipkart.com/search?q={}",
    "wikipedia": "https://en.wikipedia.org/w/index.php?search={}",
}


async def _get_youtube_video_url(song_name: str) -> str:
    """Search YouTube and return the first video watch URL, or search results page as fallback."""
    search_url = f"https://www.youtube.com/results?search_query={song_name.replace(' ', '+')}"
    try:
        import httpx
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(search_url, headers=headers)
            if resp.status_code == 200:
                import re
                matches = re.findall(r'/watch\?v=[a-zA-Z0-9_-]{11}', resp.text)
                if matches:
                    return f"https://www.youtube.com{matches[0]}"
    except Exception as e:
        logger.warning(f"Failed to fetch YouTube video URL: {e}")
    return search_url


async def execute_intent(query: str) -> Optional[Dict[str, Any]]:
    """
    Attempt to execute a user query directly via intent matching.
    Returns an action result dict if executed, or None to fall through to LLM.
    """
    query_lower = query.lower().strip()

    # Exclude generic media control queries from YouTube search routing
    EXCLUDED_PLAY_QUERIES = {"it", "it buddy", "playing", "song", "music", "something", "media", "video", "", "now"}

    # ── 1. Robust platform & play command extraction ──────────────────────────
    platforms = list(PLAY_TARGETS.keys())
    platform = None
    for p in platforms:
        if p in query_lower:
            platform = p
            break

    is_play_intent = any(w in query_lower for w in ["play", "music", "song", "बजाओ", "चलाओ", "गाना", "sing"])

    # Default platform to YouTube if playing a specific song query
    if is_play_intent and not platform:
        words = query_lower.split()
        if len(words) > 1:
            m = re.search(r"(?:play|बजा(?:ओ)?|चला(?:ओ)?)\s+(.+)", query_lower)
            if m:
                potential_song = m.group(1).strip()
                potential_song = re.sub(r"^(?:a\s+)?(?:song\s+)?(?:name\s+)?(?:is\s+)?", "", potential_song, flags=re.IGNORECASE).strip()
                potential_song = re.sub(r"^(?:music|a\s+music)\s+", "", potential_song, flags=re.IGNORECASE).strip()
                if potential_song not in EXCLUDED_PLAY_QUERIES:
                    platform = "youtube"

    if is_play_intent and platform:
        song = ""
        # Match "play <song> on/in <platform>"
        m1 = re.search(r"(?:play|बजा(?:ओ)?|चला(?:ओ)?)\s+(.+?)\s+(?:on|in|पर|of)\s+" + platform, query_lower)
        if m1:
            song = m1.group(1).strip()
        else:
            # Match "open/use <platform> ... play/search ... <song>"
            m2 = re.search(r"(?:open|use|go to)\s+" + platform + r".*?(?:play|search|find|run)\s+(?:for\s+)?(?:a\s+)?(?:song\s+)?(?:name\s+)?(.+)", query_lower)
            if m2:
                song = m2.group(1).strip()
            else:
                # Fallback: extract whatever is after "play" and remove platform name
                m3 = re.search(r"(?:play|बजा(?:ओ)?|चला(?:ओ)?)\s+(.+)", query_lower)
                if m3:
                    song = m3.group(1).replace(platform, "").replace("on", "").replace("in", "").strip()

        # Clean song name prefixes
        if song:
            song = re.sub(r"^(?:a\s+)?(?:song\s+)?(?:name\s+)?(?:is\s+)?", "", song, flags=re.IGNORECASE).strip()
            song = re.sub(r"^(?:music|a\s+music)\s+", "", song, flags=re.IGNORECASE).strip()
            if not song or song in ["song", "music", "something"]:
                song = "latest hit songs"
            
            # For YouTube, search and get the first watch video link
            if platform == "youtube":
                url = await _get_youtube_video_url(song)
                message = f"✅ Handed over task to Browser Agent. Opened YouTube and playing video for \"{song}\"."
            else:
                url = PLAY_TARGETS[platform].format(song.replace(" ", "+"))
                message = f"✅ Handed over task to Browser Agent. Opened {platform.title()} and playing \"{song}\"."

            await _open_url_async(url)
            return {
                "action": "play_media",
                "agent_id": "browser",
                "success": True,
                "platform": platform,
                "query": song,
                "url": url,
                "message": message,
            }

    # ── 2. Robust platform & search command extraction ────────────────────────
    is_search_intent = any(w in query_lower for w in ["search", "find", "look up", "google", "खोज", "ढूंढ"])
    search_platform = None
    for p in SEARCH_TARGETS.keys():
        if p in query_lower:
            search_platform = p
            break

    if is_search_intent and search_platform:
        term = ""
        # Match "search <term> on/in <platform>"
        m1 = re.search(r"(?:search|find|look up|खोज(?:ो)?|ढूंढ(?:ो)?)\s+(?:for\s+)?(.+?)\s+(?:on|in|पर)\s+" + search_platform, query_lower)
        if m1:
            term = m1.group(1).strip()
        else:
            # Fallback
            m2 = re.search(r"(?:search|find|look up|खोज(?:ो)?|ढूंढ(?:ो)?)\s+(?:for\s+)?(.+)", query_lower)
            if m2:
                term = m2.group(1).replace(search_platform, "").replace("on", "").replace("in", "").strip()

        if term:
            url = SEARCH_TARGETS[search_platform].format(term.replace(" ", "+"))
            await _open_url_async(url)
            return {
                "action": "search_web",
                "agent_id": "browser",
                "success": True,
                "platform": search_platform,
                "query": term,
                "url": url,
                "message": f"✅ Handed over task to Browser Agent. Searching \"{term}\" on {search_platform.title()}.",
            }

    # ── 3. "open <website>" pattern ──────────────────────────────────────
    open_url_match = re.match(
        r"(?:open|go to|visit)\s+(?:the\s+)?(?:website\s+)?((?:https?://)?(?:www\.)?[\w\-]+\.[\w\-.]+(?:/\S*)?)",
        query_lower, re.IGNORECASE
    )
    if open_url_match:
        url = open_url_match.group(1).strip()
        if not url.startswith("http"):
            url = "https://" + url
        await _open_url_async(url)
        return {
            "action": "open_url",
            "agent_id": "browser",
            "success": True,
            "url": url,
            "message": f"✅ Handed over task to Browser Agent. Opened {url} in your browser.",
        }

    # ── 4. Intent router dispatch ────────────────────────────────────────
    intent = _router.route(query)
    if intent and intent.confidence >= 0.85:
        return await _execute_routed_intent(intent, query)

    # ── 5. No match — fall through to LLM ────────────────────────────────
    return None


async def _execute_routed_intent(intent: IntentMatch, query: str) -> Optional[Dict[str, Any]]:
    """Execute a matched intent by calling the appropriate tool directly."""
    from tools.registry import execute_tool

    logger.info(f"Executing intent: {intent.intent_name} (confidence: {intent.confidence})")

    try:
        if intent.intent_name == "open_app":
            # Extract app name from query
            app_name = _extract_after_keywords(query, ["open", "launch", "start", "run", "चालू करो", "खोलो"])
            if app_name:
                result = await execute_tool("open_application", {"name": app_name})
                return {
                    "action": "open_app",
                    "agent_id": "desktop",
                    "success": result.get("success", False),
                    "app": app_name,
                    "message": result.get("message", f"Opening {app_name}..."),
                    "result": result,
                }

        elif intent.intent_name == "close_app":
            app_name = _extract_after_keywords(query, ["close", "exit", "quit", "kill", "बंद करो"])
            if app_name:
                result = await execute_tool("close_application", {"name": app_name})
                return {
                    "action": "close_app",
                    "agent_id": "desktop",
                    "success": result.get("success", False),
                    "app": app_name,
                    "message": result.get("message", f"Closing {app_name}..."),
                    "result": result,
                }

        elif intent.intent_name == "get_time":
            result = await execute_tool("get_current_time", {})
            return {
                "action": "get_time",
                "agent_id": "system",
                "success": True,
                "message": result.get("message", ""),
                "result": result,
            }

        elif intent.intent_name == "system_stats":
            result = await execute_tool("get_system_stats", {})
            return {
                "action": "system_stats",
                "agent_id": "system",
                "success": True,
                "message": f"CPU: {result.get('cpu')}%, RAM: {result.get('ram', {}).get('percent')}%, Battery: {result.get('battery', {}).get('percent')}%",
                "result": result,
            }

        elif intent.intent_name == "list_processes":
            result = await execute_tool("get_active_processes", {})
            return {
                "action": "list_processes",
                "agent_id": "system",
                "success": True,
                "message": "Here are the running processes.",
                "result": result,
            }

        elif intent.intent_name == "set_volume":
            level = _extract_number(query)
            if level is not None:
                result = await execute_tool("set_volume", {"level": level})
                return {
                    "action": "set_volume",
                    "agent_id": "system",
                    "success": result.get("success", False),
                    "level": level,
                    "message": result.get("message", f"Volume set to {level}%"),
                    "result": result,
                }

        elif intent.intent_name == "set_brightness":
            level = _extract_number(query)
            if level is not None:
                result = await execute_tool("set_brightness", {"level": level})
                return {
                    "action": "set_brightness",
                    "agent_id": "system",
                    "success": result.get("success", False),
                    "level": level,
                    "message": result.get("message", f"Brightness set to {level}%"),
                    "result": result,
                }

        elif intent.intent_name == "shutdown":
            result = await execute_tool("shutdown_system", {})
            return {
                "action": "shutdown",
                "agent_id": "system",
                "success": True,
                "message": "⚠️ Immediate force shutdown initiated. Terminating all active applications and shutting down PC.",
                "result": result,
            }

        elif intent.intent_name == "play_media":
            action = "play"
            q_lower = query.lower()
            if "pause" in q_lower or "रोक" in q_lower:
                action = "pause"
            elif "stop" in q_lower or "off" in q_lower or "shut" in q_lower or "बंद" in q_lower:
                action = "stop"
            elif "next" in q_lower or "अगला" in q_lower:
                action = "next"
            elif "prev" in q_lower or "पिछला" in q_lower:
                action = "previous"

            result = await execute_tool("media_control", {"action": action})
            return {
                "action": "media_control",
                "agent_id": "system",
                "success": result.get("success", False),
                "media_action": action,
                "message": result.get("message", f"Sent media key for {action}."),
                "result": result,
            }

        elif intent.intent_name == "webcam_scan":
            result = await execute_tool("capture_webcam_and_detect", {})
            return {
                "action": "webcam_scan",
                "agent_id": "vision",
                "success": result.get("success", False),
                "message": result.get("message", ""),
                "result": result,
            }

        elif intent.intent_name == "screenshot":
            result = await execute_tool("capture_desktop_screenshot", {})
            return {
                "action": "screenshot",
                "agent_id": "vision",
                "success": result.get("success", False),
                "message": result.get("message", "Captured screen successfully."),
                "result": result,
            }

        elif intent.intent_name == "terminal_command":
            cmd = _extract_after_keywords(query, ["run", "execute", "terminal", "shell", "cmd", "कमांड"])
            if cmd:
                result = await execute_tool("execute_terminal", {"command": cmd})
                return {
                    "action": "terminal_command",
                    "agent_id": "system",
                    "success": result.get("success", False),
                    "command": cmd,
                    "message": result.get("message", ""),
                    "result": result,
                }

    except Exception as e:
        logger.error(f"Intent execution error: {e}", exc_info=True)
        return {
            "action": intent.intent_name,
            "agent_id": "system",
            "success": False,
            "message": f"❌ Action failed: {str(e)}",
        }

    return None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_after_keywords(query: str, keywords: list) -> str:
    """Extract the text after any of the given keywords."""
    q_lower = query.lower().strip()
    for kw in keywords:
        kw_lower = kw.lower()
        idx = q_lower.find(kw_lower)
        if idx != -1:
            after = query[idx + len(kw):].strip()
            # Remove leading articles
            after = re.sub(r"^(?:the|a|an)\s+", "", after, flags=re.IGNORECASE).strip()
            if after:
                return after
    return ""


def _extract_number(query: str) -> Optional[int]:
    """Extract the first number from a query string."""
    match = re.search(r"\d+", query)
    if match:
        return int(match.group())
    return None


async def _open_url_async(url: str) -> None:
    """Open a URL in the default browser asynchronously."""
    await asyncio.to_thread(webbrowser.open, url)
