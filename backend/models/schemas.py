from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

class HealthResponse(BaseModel):
    status: str
    ollama_connected: bool
    model: str
    message: str

class ModelInfo(BaseModel):
    name: str
    details: Dict[str, Any]

class ModelListResponse(BaseModel):
    models: List[ModelInfo]

class WSMessage(BaseModel):
    type: str = Field(..., description="Message type: chat_response, system_stats, agent_status, thinking, tts_audio, connected, tool_result, error")
    data: Dict[str, Any] = Field(..., description="Payload data specific to the message type")

class ChatMessageData(BaseModel):
    text: str

class CommandData(BaseModel):
    action: str = Field(..., description="Action to perform: get_system_stats, execute_terminal, tts_speak")
    command: Optional[str] = None
    text: Optional[str] = None
    language: Optional[str] = None
