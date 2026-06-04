import os
import logging
import asyncio
from typing import Dict, Any, List

logger = logging.getLogger("JARVIS.VisionTools")

# Use absolute path inside backend temp_audio directory for vision output assets
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VISION_OUTPUT_DIR = os.path.join(BACKEND_DIR, "temp_audio")

async def detect_objects(image_path: str) -> Dict[str, Any]:
    """
    Run local YOLOv8 object detection on a specific image file path.
    Downloads the tiny pre-trained yolov8n.pt model automatically on first run.
    """
    if not os.path.exists(image_path):
        return {"success": False, "error": f"Image file not found: {image_path}"}
        
    try:
        # Import inside tool to prevent server startup crash if ultralytics is still installing
        from ultralytics import YOLO
        import cv2
        
        logger.info(f"Loading YOLOv8 model for image: {image_path}")
        # Run synchronous YOLO detection inside an async thread pool
        def _detect():
            # Automatically downloads weights file to current directory on first execution (~6MB)
            model = YOLO("yolov8n.pt")
            results = model(image_path)
            
            detected = []
            img = cv2.imread(image_path)
            h, w, _ = img.shape
            
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    # Class name
                    cls_id = int(box.cls[0])
                    name = model.names[cls_id]
                    # Confidence score
                    conf = float(box.conf[0])
                    # Bounding box coords (x1, y1, x2, y2)
                    coords = box.xyxy[0].tolist()
                    
                    detected.append({
                        "object": name,
                        "confidence": round(conf, 2),
                        "box_xyxy": [round(c, 1) for c in coords]
                    })
                    
                    # Draw a nice cyan bounding box on the original image as visual feedback
                    x1, y1, x2, y2 = map(int, coords)
                    # Glowing Cyan (BGR in OpenCV is B=255, G=255, R=0)
                    cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 0), 2)
                    label = f"{name} {round(conf, 2)}"
                    cv2.putText(img, label, (x1, max(y1 - 10, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            
            # Save annotated image back
            output_name = f"detected_{os.path.basename(image_path)}"
            output_path = os.path.join(VISION_OUTPUT_DIR, output_name)
            os.makedirs(VISION_OUTPUT_DIR, exist_ok=True)
            cv2.imwrite(output_path, img)
            
            return detected, output_name
            
        detected_objects, output_filename = await asyncio.to_thread(_detect)
        return {
            "success": True,
            "detected_objects": detected_objects,
            "count": len(detected_objects),
            "annotated_image_url": f"/temp_audio/{output_filename}",
            "message": f"Object detection complete, Sir. Found {len(detected_objects)} targets."
        }
    except Exception as e:
        logger.error(f"Error in YOLO object detection: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

async def capture_webcam_and_detect_objects() -> Dict[str, Any]:
    """
    Capture a live frame from your default laptop webcam using OpenCV, 
    run YOLOv8 object detection on it, annotate bounding boxes, 
    and save the visual readout to the static temp directory.
    """
    try:
        import cv2
        
        # Access default webcam
        logger.info("Accessing system camera capture device...")
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) # Use DSHOW for rapid access on Windows
        
        # Give camera 0.5 seconds to auto-focus and calibrate exposure
        await asyncio.sleep(0.5)
        
        ret, frame = cap.read()
        cap.release() # Release webcam resource immediately to avoid locks
        
        if not ret or frame is None:
            return {
                "success": False, 
                "error": "Could not access or read frame from system camera, Boss. Ensure the camera is connected and not locked by another application."
            }
            
        # Save raw frame temporarily
        os.makedirs(VISION_OUTPUT_DIR, exist_ok=True)
        raw_path = os.path.join(VISION_OUTPUT_DIR, "webcam_raw.jpg")
        cv2.imwrite(raw_path, frame)
        logger.info(f"Webcam frame captured successfully at {raw_path}. Dispatched for YOLO analysis.")
        
        # Run YOLO detection on the captured frame
        result = await detect_objects(raw_path)
        
        # Cleanup raw frame
        if os.path.exists(raw_path):
            os.remove(raw_path)
            
        if result.get("success"):
            return {
                "success": True,
                "detected_objects": result["detected_objects"],
                "count": result["count"],
                "image_url": "/temp_audio/detected_webcam_raw.jpg",
                "message": f"Audible optical scan complete, Sir. Bounding boxes annotated and broadcasted to HUD."
            }
        else:
            return result
            
    except Exception as e:
        logger.error(f"Failed webcam optical capture: {e}", exc_info=True)
        return {
            "success": False, 
            "error": f"Failed webcam optical capture: {str(e)}. (Ensure opencv-python is installed in venv)."
        }
