"""
Dorothy OS v2.0 — LLM Service
Dual-mode orchestrator: Cloud Gemini Flash (with search grounding) + Local Ollama (offline fallback).
Handles streaming responses, tool calling, and automatic failover.
"""

import os
import json
import socket
import logging
import asyncio
import time
from typing import AsyncGenerator, Dict, Any, List, Optional

logger = logging.getLogger("Dorothy.LLM")


def is_internet_available() -> bool:
    """Fast connectivity check by attempting DNS resolution to Google's public DNS."""
    try:
        socket.setdefaulttimeout(2.0)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("8.8.8.8", 53))
        sock.close()
        return True
    except Exception:
        return False


def format_messages_for_gemini(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert conversation history to Gemini API format, handling tool calls and responses."""
    gemini_contents = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "system":
            continue
        
        if role == "user":
            gemini_contents.append({
                "role": "user",
                "parts": [{"text": content or ""}],
            })
        elif role in ("assistant", "model"):
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                parts = []
                for tc in tool_calls:
                    func = tc.get("function", {})
                    args = func.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    parts.append({
                        "functionCall": {
                            "name": func.get("name"),
                            "args": args
                        }
                    })
                gemini_contents.append({
                    "role": "model",
                    "parts": parts
                })
            else:
                gemini_contents.append({
                    "role": "model",
                    "parts": [{"text": content or ""}]
                })
        elif role == "tool":
            try:
                resp_data = json.loads(content) if isinstance(content, str) else content
            except Exception:
                resp_data = {"result": content}
            
            if not isinstance(resp_data, dict):
                resp_data = {"result": resp_data}
                
            gemini_contents.append({
                "role": "tool",
                "parts": [{
                    "functionResponse": {
                        "name": msg.get("name", "tool"),
                        "response": resp_data
                    }
                }]
            })
        else:
            gemini_contents.append({
                "role": "user",
                "parts": [{"text": content or ""}],
            })
            
    return gemini_contents


# ─── Gemini Cloud Streaming ──────────────────────────────────────────────────

async def stream_gemini(
    messages: List[Dict[str, Any]],
    system_prompt: str,
    api_key: str,
    model: str = "gemini-2.5-flash",
) -> AsyncGenerator[str, None]:
    """Stream response tokens from Google Gemini Flash API with native search grounding."""
    import httpx

    # Convert conversation history to Gemini format
    gemini_contents = format_messages_for_gemini(messages)

    payload = {
        "contents": gemini_contents,
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
        "tools": [{"googleSearch": {}}],
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?key={api_key}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    err_text = await response.aread()
                    err_msg = err_text.decode("utf-8", errors="replace")
                    logger.error(f"Gemini API error {response.status_code}: {err_msg[:200]}")
                    raise RuntimeError(f"Gemini API error code {response.status_code}")

                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk

                    # Extract complete JSON objects using brace counting
                    while True:
                        start_idx = buffer.find("{")
                        if start_idx == -1:
                            break

                        brace_count = 0
                        end_idx = -1
                        in_string = False
                        escape = False

                        for i in range(start_idx, len(buffer)):
                            char = buffer[i]
                            if escape:
                                escape = False
                                continue
                            if char == "\\":
                                escape = True
                                continue
                            if char == '"':
                                in_string = not in_string
                                continue
                            if not in_string:
                                if char == "{":
                                    brace_count += 1
                                elif char == "}":
                                    brace_count -= 1
                                    if brace_count == 0:
                                        end_idx = i
                                        break

                        if end_idx != -1:
                            json_str = buffer[start_idx : end_idx + 1]
                            buffer = buffer[end_idx + 1 :]

                            try:
                                data = json.loads(json_str)
                                candidates = data.get("candidates", [])
                                if candidates:
                                    parts = candidates[0].get("content", {}).get("parts", [])
                                    if parts:
                                        token = parts[0].get("text", "")
                                        if token:
                                            yield token
                            except json.JSONDecodeError as e:
                                logger.debug(f"Skipping malformed Gemini chunk: {e}")
                        else:
                            break

    except Exception as e:
        logger.error(f"Gemini streaming failed: {e}", exc_info=True)
        raise RuntimeError(f"Gemini connection failed: {str(e)}")


async def stream_claude(
    messages: List[Dict[str, Any]],
    system_prompt: str,
    api_key: str,
    model: str = "claude-3-5-sonnet-20241022",
) -> AsyncGenerator[str, None]:
    """Stream response tokens from Anthropic Claude API."""
    import httpx

    # Convert conversation history to Anthropic format
    claude_messages = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "system":
            continue
        claude_messages.append({
            "role": "user" if role == "user" else "assistant",
            "content": content,
        })

    payload = {
        "model": model,
        "messages": claude_messages,
        "system": system_prompt,
        "max_tokens": 4096,
        "stream": True,
    }

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    url = "https://api.anthropic.com/v1/messages"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    err_text = await response.aread()
                    err_msg = err_text.decode("utf-8", errors="replace")
                    logger.error(f"Claude API error {response.status_code}: {err_msg[:200]}")
                    raise RuntimeError(f"Claude API error code {response.status_code}")

                # Read events from stream
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            event_type = data.get("type")
                            if event_type == "content_block_delta":
                                token = data.get("delta", {}).get("text", "")
                                if token:
                                    yield token
                        except json.JSONDecodeError:
                            continue
    except Exception as e:
        logger.error(f"Claude streaming failed: {e}", exc_info=True)
        raise RuntimeError(f"Claude connection failed: {str(e)}")


# ─── LLM Service ─────────────────────────────────────────────────────────────

class LLMService:
    """Dual-mode LLM service with automatic cloud/local failover."""

    def __init__(
        self,
        ollama_base_url: str = "http://localhost:11434",
        ollama_model: str = "qwen2.5:7b",
        gemini_api_key: str = "",
        anthropic_api_key: str = "",
        system_prompt: str = "",
    ):
        self.ollama_base_url = ollama_base_url
        self.ollama_model = ollama_model
        self.gemini_api_key = gemini_api_key
        self.anthropic_api_key = anthropic_api_key
        self.system_prompt = system_prompt
        self.active_provider = "auto"  # Can be: 'auto', 'claude', 'gemini', 'ollama'

        # Lazy-init Ollama client
        self._ollama_client = None
        logger.info(
            f"LLM Service initialized: ollama={ollama_base_url}, model={ollama_model}, "
            f"gemini={'configured' if gemini_api_key else 'not configured'}, "
            f"anthropic={'configured' if anthropic_api_key else 'not configured'}, "
            f"active_provider={self.active_provider}"
        )

    @property
    def ollama_client(self):
        """Lazy-initialize the Ollama AsyncClient."""
        if self._ollama_client is None:
            from ollama import AsyncClient
            self._ollama_client = AsyncClient(host=self.ollama_base_url)
        return self._ollama_client

    async def health_check(self) -> bool:
        """Check if Ollama service is reachable."""
        try:
            await self.ollama_client.list()
            return True
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    async def get_models(self) -> List[Dict[str, Any]]:
        """List models available in local Ollama."""
        try:
            res = await self.ollama_client.list()
            return res.get("models", [])
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []

    async def detect_tool_calls(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Detect tool calls using the active provider hierarchy (Claude -> Gemini -> Ollama).
        Returns a list of dicts: [{"name": tool_name, "args": tool_args}]
        """
        online = is_internet_available()
        provider = getattr(self, "active_provider", "auto")

        use_claude = False
        use_gemini = False

        if provider == "claude":
            use_claude = bool(self.anthropic_api_key) and online
        elif provider == "gemini":
            use_gemini = bool(self.gemini_api_key) and online
        elif provider == "ollama":
            pass
        else: # "auto"
            use_claude = bool(self.anthropic_api_key) and online
            use_gemini = bool(self.gemini_api_key) and online

        # Try Claude first
        if use_claude:
            try:
                logger.info("[COGNITIVE] Checking tool calls via Claude...")
                tool_calls = await self._detect_tool_calls_claude(messages, tools)
                if tool_calls is not None:
                    return tool_calls
            except Exception as e:
                logger.warning(f"Claude tool detection failed: {e}. Falling back...")
                use_claude = False

        # Try Gemini next
        if not use_claude and use_gemini:
            try:
                logger.info("[COGNITIVE] Checking tool calls via Gemini...")
                tool_calls = await self._detect_tool_calls_gemini(messages, tools)
                if tool_calls is not None:
                    return tool_calls
            except Exception as e:
                logger.warning(f"Gemini tool detection failed: {e}. Falling back to Ollama...")

        # Fallback to Ollama
        try:
            logger.info("[COGNITIVE] Checking tool calls via Ollama...")
            return await self._detect_tool_calls_ollama(messages, tools)
        except Exception as e:
            logger.error(f"Ollama tool detection failed: {e}")
            return []

    async def _detect_tool_calls_gemini(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Optional[List[Dict[str, Any]]]:
        import httpx
        
        # Format messages for Gemini
        gemini_contents = format_messages_for_gemini(messages)

        # Format tools for Gemini
        def convert_type(schema: any) -> any:
            if isinstance(schema, dict):
                new_schema = {}
                for k, v in schema.items():
                    if k == "type" and isinstance(v, str):
                        new_schema[k] = v.upper()
                    else:
                        new_schema[k] = convert_type(v)
                return new_schema
            elif isinstance(schema, list):
                return [convert_type(item) for item in schema]
            return schema

        gemini_tools = []
        for t in tools:
            func = t.get("function", {})
            openai_params = func.get("parameters", {})
            gemini_params = convert_type(openai_params)
            
            decl = {
                "name": func.get("name"),
                "description": func.get("description"),
            }
            if gemini_params:
                decl["parameters"] = gemini_params
            gemini_tools.append(decl)

        payload = {
            "contents": gemini_contents,
            "systemInstruction": {"parts": [{"text": self.system_prompt}]},
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 2048},
            "tools": [{"functionDeclarations": gemini_tools}]
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_api_key}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.warning(f"Gemini API tool check returned {resp.status_code}: {resp.text[:200]}")
                return None
            
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return []
            
            parts = candidates[0].get("content", {}).get("parts", [])
            detected = []
            for part in parts:
                fc = part.get("functionCall")
                if fc:
                    detected.append({
                        "name": fc.get("name"),
                        "args": fc.get("args", {})
                    })
            return detected

    async def _detect_tool_calls_claude(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Optional[List[Dict[str, Any]]]:
        import httpx
        
        # Convert messages to Claude format
        claude_messages = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                continue
            
            # Map role
            if role == "user":
                c_role = "user"
            elif role in ("assistant", "model"):
                c_role = "assistant"
            elif role == "tool":
                claude_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", "toolu_01"),
                        "content": content
                    }]
                })
                continue
            else:
                c_role = "user"
                
            claude_messages.append({
                "role": c_role,
                "content": content,
            })

        # Format tools for Claude
        claude_tools = []
        for t in tools:
            func = t.get("function", {})
            claude_tools.append({
                "name": func.get("name"),
                "description": func.get("description"),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}})
            })

        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": claude_messages,
            "system": self.system_prompt,
            "max_tokens": 2048,
            "tools": claude_tools
        }

        headers = {
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        url = "https://api.anthropic.com/v1/messages"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.warning(f"Claude API tool check returned {resp.status_code}: {resp.text[:200]}")
                return None
            
            data = resp.json()
            content_blocks = data.get("content", [])
            detected = []
            for block in content_blocks:
                if block.get("type") == "tool_use":
                    detected.append({
                        "name": block.get("name"),
                        "args": block.get("input", {})
                    })
            return detected

    async def _detect_tool_calls_ollama(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        ollama_messages = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "tool":
                ollama_messages.append({
                    "role": "tool",
                    "content": content,
                    "name": msg.get("name", "")
                })
            elif role in ("assistant", "model"):
                t_calls = msg.get("tool_calls")
                if t_calls:
                    ollama_messages.append({
                        "role": "assistant",
                        "content": content or "",
                        "tool_calls": t_calls
                    })
                else:
                    ollama_messages.append({
                        "role": "assistant",
                        "content": content or ""
                    })
            else:
                ollama_messages.append({
                    "role": role,
                    "content": content
                })
                
        kwargs = {
            "model": self.ollama_model,
            "messages": ollama_messages,
            "tools": tools,
        }
        res = await self.ollama_client.chat(**kwargs)
        tool_calls = getattr(res.message, "tool_calls", []) or []
        
        detected = []
        for tc in tool_calls:
            detected.append({
                "name": tc.function.name,
                "args": tc.function.arguments,
            })

        if not detected:
            try:
                detected = await self._detect_tool_calls_prompt_fallback(messages, tools)
            except Exception as e:
                logger.warning(f"Ollama prompt-based tool routing fallback failed: {e}")

        return detected


    async def _detect_tool_calls_prompt_fallback(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Fallback tool selection utilizing structured JSON formatting for small models."""
        user_query = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_query = msg.get("content", "")
                break
        if not user_query:
            return []

        import re
        import json

        # Format tool descriptions for prompt injection
        tool_desc = []
        for t in tools:
            func = t.get("function", {})
            name = func.get("name")
            desc = func.get("description", "")
            params = func.get("parameters", {}).get("properties", {})
            param_names = ", ".join(params.keys())
            tool_desc.append(f"- Tool Name: '{name}'\n  Description: {desc}\n  Args: {param_names}")

        tool_list = "\n".join(tool_desc)

        prompt = (
            f"You are the routing system for Dorothy OS.\n"
            f"Given the user query: \"{user_query}\"\n\n"
            f"Select the most appropriate tool from the registry to execute this task:\n"
            f"{tool_list}\n\n"
            f"Rules:\n"
            f"1. Choose EXACTLY one tool, or output 'NONE' if no tool matches.\n"
            f"2. Output your response STRICTLY in this JSON format:\n"
            f"{{\"name\": \"tool_name\", \"args\": {{\"parameter_name\": \"value\"}}}}\n"
            f"Do not include any thinking, markdown blocks, or other text. Just output the JSON."
        )

        res = await self.ollama_client.chat(
            model=self.ollama_model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0}
        )
        content = res.message.content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n", "", content)
            content = re.sub(r"\n```$", "", content)
            content = content.strip()

        if content == "NONE" or not content:
            return []

        try:
            data = json.loads(content)
            if isinstance(data, dict) and "name" in data:
                return [{
                    "name": data["name"],
                    "args": data.get("args", {})
                }]
        except Exception as e:
            logger.debug(f"Prompt tool selection fallback parsing failed: {e}")
        return []


    async def chat_stream(
        self,
        conversation_history: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Primary chat orchestrator. Automatically routes between Claude (cloud), Gemini (cloud), and Ollama (local).
        Yields event dicts: {type: "token"/"thinking"/"cognitive_log"/"tool_result"/"error"}
        """
        messages = list(conversation_history)
        if not messages or messages[0].get("role") != "system":
            messages.insert(0, {"role": "system", "content": self.system_prompt})

        online = is_internet_available()
        provider = getattr(self, "active_provider", "auto")
        
        use_claude = False
        use_gemini = False
        
        if provider == "claude":
            use_claude = bool(self.anthropic_api_key) and online
        elif provider == "gemini":
            use_gemini = bool(self.gemini_api_key) and online
        elif provider == "ollama":
            pass  # Force fallback local Ollama by keeping both as False
        else:  # "auto" or empty
            use_claude = bool(self.anthropic_api_key) and online
            use_gemini = bool(self.gemini_api_key) and online

        if use_claude:
            yield {
                "type": "cognitive_log",
                "content": "[COGNITIVE] Uplink stable. Routing to Claude Sonnet.",
            }
            try:
                yield {"type": "thinking", "data": {"active": True}}
                sys_prompt = messages[0].get("content", self.system_prompt)

                async for token in stream_claude(messages, sys_prompt, self.anthropic_api_key):
                    yield {"type": "token", "content": token}

                yield {"type": "thinking", "data": {"active": False}}
            except Exception as e:
                logger.error(f"Claude routing failed: {e}")
                yield {
                    "type": "cognitive_log",
                    "content": f"[COGNITIVE] Claude exception: {str(e)[:100]}. Falling back to Gemini...",
                }
                use_claude = False  # Set to false to trigger downstream paths

        # Fall through to Gemini if Claude failed or was not configured
        if not use_claude:
            if use_gemini:
                yield {
                    "type": "cognitive_log",
                    "content": "[COGNITIVE] Routing to Gemini Flash with search grounding.",
                }
                try:
                    yield {"type": "thinking", "data": {"active": True}}
                    sys_prompt = messages[0].get("content", self.system_prompt)

                    async for token in stream_gemini(messages, sys_prompt, self.gemini_api_key):
                        yield {"type": "token", "content": token}

                    yield {"type": "thinking", "data": {"active": False}}
                except Exception as e:
                    logger.error(f"Gemini routing failed: {e}")
                    yield {
                        "type": "cognitive_log",
                        "content": f"[COGNITIVE] Gemini exception: {str(e)[:100]}. Falling back to local Ollama.",
                    }
                    async for event in self._chat_stream_local(messages, tools):
                        yield event
            else:
                reason = "No API key." if not (self.gemini_api_key or self.anthropic_api_key) else "Network offline."
                yield {
                    "type": "cognitive_log",
                    "content": f"[COGNITIVE] Fallback active ({reason}). Invoking local Ollama.",
                }
                async for event in self._chat_stream_local(messages, tools):
                    yield event

    async def _chat_stream_local(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Local Ollama streaming with two-pass tool calling pipeline."""
        try:
            logger.info("Sending chat request to Ollama...")

            # Pass 1: Call with tools to detect if actions are needed
            kwargs: Dict[str, Any] = {
                "model": self.ollama_model,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools

            response = await self.ollama_client.chat(**kwargs)

            tool_calls = getattr(response.message, "tool_calls", [])

            if tool_calls:
                logger.info(f"Model requested tools: {[t.function.name for t in tool_calls]}")
                yield {"type": "thinking", "data": {"active": True}}

                # Append model's tool-calling decision
                messages.append(response.message)

                # Execute each tool
                from tools.registry import execute_tool

                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = tool_call.function.arguments

                    result = await execute_tool(tool_name, tool_args)

                    yield {
                        "type": "tool_result",
                        "data": {"tool": tool_name, "result": result},
                    }

                    messages.append({
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps(result),
                    })

                yield {"type": "thinking", "data": {"active": False}}

                # Pass 2: Stream final synthesis with tool results
                logger.info("Streaming final response after tool execution...")
                async for chunk in await self.ollama_client.chat(
                    model=self.ollama_model,
                    messages=messages,
                    stream=True,
                ):
                    token = chunk.message.content or ""
                    if token:
                        yield {"type": "token", "content": token}
            else:
                # Direct conversational response (no tool calls)
                logger.info("Direct response — simulating smooth stream.")
                text = response.message.content or ""
                words = text.split(" ")
                for i, word in enumerate(words):
                    space = " " if i < len(words) - 1 else ""
                    yield {"type": "token", "content": word + space}
                    await asyncio.sleep(0.015)

        except Exception as e:
            logger.error(f"Local LLM stream error: {e}", exc_info=True)
            yield {"type": "error", "message": f"Neural processing error: {str(e)}"}
