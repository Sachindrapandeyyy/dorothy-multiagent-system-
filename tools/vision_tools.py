"""
Dorothy OS v2.0 — Vision & Object Detection Tools
YOLOv8 object detection with OpenCV webcam capture and neon annotation overlays.
"""

import os
import uuid
import logging
import asyncio
from typing import Dict, Any, List, Optional

logger = logging.getLogger("Dorothy.Tools.Vision")

# Output directory for captured frames — configured at startup
_captures_dir: str = ""


def configure(captures_dir: str) -> None:
    """Configure the output directory for vision captures."""
    global _captures_dir
    _captures_dir = captures_dir
    os.makedirs(_captures_dir, exist_ok=True)
    logger.info(f"Vision tools configured: captures={_captures_dir}")


async def capture_webcam_and_detect_objects() -> Dict[str, Any]:
    """Capture a frame from the default webcam, run YOLOv8 detection, annotate, and save."""
    if not _captures_dir:
        return {"success": False, "error": "Vision not configured. Call vision_tools.configure() first."}
    return await asyncio.to_thread(_capture_and_detect_sync)


def _capture_and_detect_sync() -> Dict[str, Any]:
    """Synchronous webcam capture + YOLOv8 detection pipeline."""
    try:
        import cv2
    except ImportError:
        return {"success": False, "error": "opencv-python is not installed."}

    try:
        from ultralytics import YOLO
    except ImportError:
        return {"success": False, "error": "ultralytics is not installed."}

    cap = None
    try:
        # Open default webcam (index 0) with DirectShow on Windows
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            return {"success": False, "error": "Could not access webcam. Check hardware permissions."}

        # Read a single frame
        ret, frame = cap.read()
        if not ret or frame is None:
            return {"success": False, "error": "Failed to capture frame from webcam."}

        # Save raw frame
        raw_filename = f"raw_{uuid.uuid4().hex[:8]}.jpg"
        raw_path = os.path.join(_captures_dir, raw_filename)
        cv2.imwrite(raw_path, frame)

        # Run YOLOv8 detection
        model = YOLO("yolov8n.pt")
        results = model(frame, verbose=False)

        detected_objects: List[Dict[str, Any]] = []
        annotated_frame = frame.copy()

        if results and len(results) > 0:
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        # Extract bounding box coordinates
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        confidence = float(box.conf[0])
                        class_id = int(box.cls[0])
                        class_name = model.names.get(class_id, f"class_{class_id}")

                        detected_objects.append({
                            "class": class_name,
                            "confidence": round(confidence, 3),
                            "bbox": [x1, y1, x2, y2],
                        })

                        # Draw neon cyan bounding box
                        color = (255, 194, 0)  # BGR for cyan (#00C2FF)
                        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)

                        # Draw label background
                        label = f"{class_name} {confidence:.1%}"
                        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                        cv2.rectangle(annotated_frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
                        cv2.putText(
                            annotated_frame,
                            label,
                            (x1 + 2, y1 - 4),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (0, 0, 0),
                            1,
                            cv2.LINE_AA,
                        )

        # Save annotated frame
        annotated_filename = f"detect_{uuid.uuid4().hex[:8]}.jpg"
        annotated_path = os.path.join(_captures_dir, annotated_filename)
        cv2.imwrite(annotated_path, annotated_frame)

        # Return web-accessible URL path (relative to static mount)
        image_url = f"/captures/{annotated_filename}"

        logger.info(f"Vision scan complete: {len(detected_objects)} objects detected.")
        return {
            "success": True,
            "count": len(detected_objects),
            "detected_objects": detected_objects,
            "image_path": annotated_path,
            "image_url": image_url,
            "raw_path": raw_path,
            "message": f"Optical scan complete. {len(detected_objects)} objects detected.",
        }

    except Exception as e:
        logger.error(f"Vision pipeline error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        if cap is not None:
            cap.release()


async def detect_objects(image_path: str) -> Dict[str, Any]:
    """Run YOLOv8 object detection on an existing image file."""
    if not os.path.isfile(image_path):
        return {"success": False, "error": f"Image not found: '{image_path}'."}
    return await asyncio.to_thread(_detect_objects_sync, image_path)


def _detect_objects_sync(image_path: str) -> Dict[str, Any]:
    """Synchronous YOLOv8 detection on a file."""
    try:
        import cv2
        from ultralytics import YOLO
    except ImportError as e:
        return {"success": False, "error": f"Missing dependency: {e}"}

    try:
        frame = cv2.imread(image_path)
        if frame is None:
            return {"success": False, "error": f"Could not read image: '{image_path}'."}

        model = YOLO("yolov8n.pt")
        results = model(frame, verbose=False)

        detected_objects: List[Dict[str, Any]] = []
        if results and len(results) > 0:
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        confidence = float(box.conf[0])
                        class_id = int(box.cls[0])
                        class_name = model.names.get(class_id, f"class_{class_id}")
                        detected_objects.append({
                            "class": class_name,
                            "confidence": round(confidence, 3),
                            "bbox": [x1, y1, x2, y2],
                        })

        return {
            "success": True,
            "count": len(detected_objects),
            "detected_objects": detected_objects,
            "image_path": image_path,
        }
    except Exception as e:
        logger.error(f"Object detection failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
