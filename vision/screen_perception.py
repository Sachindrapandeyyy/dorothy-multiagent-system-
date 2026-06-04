"""
Dorothy OS v2.0 — Screen Perception & VLM Navigation Service.
Captures screen workspace, analyzes UI structures using cloud VLM (Gemini) or 
local template matching (OpenCV), and maps to PyAutoGUI click coordinates.
"""

import os
import time
import logging
import asyncio
import pyautogui
from PIL import Image
from typing import Dict, Any, List, Optional, Tuple

from configs import settings
from api.llm_service import is_internet_available

logger = logging.getLogger("Dorothy.Vision.Perception")

class ScreenPerceptionService:
    """Enterprise-grade multimodal screen navigation and visual control interface."""

    def __init__(self) -> None:
        self.captures_dir = settings.CAPTURES_DIR
        os.makedirs(self.captures_dir, exist_ok=True)
        pyautogui.FAILSAFE = True  # Move mouse to corner to abort

    def capture_screen(self, filename: Optional[str] = None) -> str:
        """Capture active desktop display and save as temporary image."""
        if not filename:
            filename = f"screenshot_{int(time.time())}.png"
        
        filepath = os.path.join(self.captures_dir, filename)
        try:
            # Pillow-based screenshot capture
            screenshot = pyautogui.screenshot()
            screenshot.save(filepath)
            logger.info(f"Active display successfully captured to: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to capture display: {e}")
            raise RuntimeError(f"Screen capture failure: {e}")

    async def locate_element_vlm(self, query: str) -> Optional[Tuple[int, int]]:
        """
        Sends the active screenshot to Gemini Multimodal API with custom instructions
        requesting pixel coordinates for a specific UI element.
        """
        api_key = settings.GEMINI_API_KEY
        if not api_key or not is_internet_available():
            logger.warning("VLM Screen Perception requested but cloud uplink is unavailable.")
            return None

        # Capture display first
        screenshot_path = self.capture_screen("vlm_perception.png")

        # Encode image to base64
        import base64
        import httpx
        try:
            with open(screenshot_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode("utf-8")

            # Structured coordinate request prompt
            prompt = (
                f"You are a computer vision navigation assistant. "
                f"Identify the screen pixel center coordinates [x, y] of the target: '{query}'. "
                f"Examine the image carefully. Respond ONLY with a valid JSON block containing: "
                f"\"coordinates\": [x, y], where x and y are the exact pixel coordinates. "
                f"Example: {{\"coordinates\": [520, 310]}}"
            )

            # Gemini Multimodal API endpoint
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": image_data
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json"
                }
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    text_out = data["candidates"][0]["content"]["parts"][0]["text"]
                    logger.info(f"Gemini VLM returned vision navigation response: {text_out}")
                    
                    import json
                    parsed = json.loads(text_out)
                    coords = parsed.get("coordinates")
                    if isinstance(coords, list) and len(coords) == 2:
                        x, y = int(coords[0]), int(coords[1])
                        # Sanity bound checks
                        screen_w, screen_h = pyautogui.size()
                        if 0 <= x <= screen_w and 0 <= y <= screen_h:
                            return x, y
                        else:
                            logger.warning(f"VLM returned coordinates [{x}, {y}] outside screen bounds: {screen_w}x{screen_h}")
                else:
                    logger.error(f"Gemini visual API error {res.status_code}: {res.text}")
        except Exception as e:
            logger.error(f"Multimodal screen perception failed: {e}")
        return None

    def locate_element_cv(self, template_path: str) -> Optional[Tuple[int, int]]:
        """
        Offline fallback: Performs OpenCV normalized cross-correlation template matching
        to search the screenshot for a matching local sub-image (e.g. icon).
        """
        try:
            import cv2
            import numpy as np
            
            # Capture display
            screenshot_path = self.capture_screen("cv_perception.png")
            
            # Load images
            img = cv2.imread(screenshot_path, cv2.IMREAD_GRAYSCALE)
            template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
            
            if img is None or template is None:
                logger.warning("Failed to load CV source or template image.")
                return None
                
            w, h = template.shape[::-1]
            
            # Correlation matching
            res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            
            # Minimum similarity threshold
            if max_val >= 0.8:
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                logger.info(f"CV template matched successfully (Score: {max_val:.2f}) at [{center_x}, {center_y}]")
                return center_x, center_y
            
            logger.warning(f"CV template match failed. Best score: {max_val:.2f} (required >= 0.80)")
        except ImportError:
            logger.warning("opencv-python not available for local template matching.")
        except Exception as e:
            logger.error(f"CV perception search crashed: {e}")
        return None

    async def click_element(self, query: str, use_vlm: bool = True) -> bool:
        """Autonomously locate and perform a physical click on screen."""
        coords = None
        if use_vlm:
            coords = await self.locate_element_vlm(query)
        
        if not coords:
            # Fallback search if template path matches
            if os.path.exists(query):
                coords = self.locate_element_cv(query)

        if coords:
            x, y = coords
            logger.info(f"Autonomous Vision Control executing click at: [{x}, {y}]")
            
            # Perform smooth mouse glide and click
            pyautogui.moveTo(x, y, duration=1.0, tween=pyautogui.easeInOutQuad)
            pyautogui.click()
            return True
            
        logger.warning(f"Could not locate target '{query}' on active display.")
        return False

screen_perception = ScreenPerceptionService()
