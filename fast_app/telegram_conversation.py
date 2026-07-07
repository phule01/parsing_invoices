"""
Telegram Conversation State Manager
Tracks multi-step conversations for account management commands
"""

from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# In-memory store for conversation states
# Structure: {chat_id: {"state": str, "data": dict, "timestamp": datetime}}
_conversation_states: Dict[int, Dict[str, Any]] = {}

# Conversation state constants
STATE_IDLE = "idle"
STATE_ADD_USERNAME = "add_username"
STATE_ADD_PASSWORD = "add_password"
STATE_ADD_ROLE = "add_role"
STATE_DELETE_USERNAME = "delete_username"
STATE_CHANGE_USERNAME = "change_username"
STATE_CHANGE_PASSWORD = "change_password"

# Timeout for conversation (5 minutes)
CONVERSATION_TIMEOUT = timedelta(minutes=5)


def start_conversation(chat_id: int, state: str, data: Optional[Dict] = None) -> None:
    """Start a new conversation state"""
    _conversation_states[chat_id] = {
        "state": state,
        "data": data or {},
        "timestamp": datetime.now(),
    }
    logger.info(f"Started conversation state '{state}' for chat {chat_id}")


def get_conversation_state(chat_id: int) -> Optional[str]:
    """Get current conversation state for a chat"""
    if chat_id not in _conversation_states:
        return STATE_IDLE

    conv = _conversation_states[chat_id]
    # Check if conversation has timed out
    if datetime.now() - conv["timestamp"] > CONVERSATION_TIMEOUT:
        logger.info(f"Conversation timed out for chat {chat_id}")
        _conversation_states.pop(chat_id, None)
        return STATE_IDLE

    return conv.get("state", STATE_IDLE)


def get_conversation_data(chat_id: int) -> Dict[str, Any]:
    """Get conversation data"""
    if chat_id not in _conversation_states:
        return {}
    return _conversation_states[chat_id].get("data", {})


def update_conversation_data(chat_id: int, key: str, value: Any) -> None:
    """Update conversation data"""
    if chat_id not in _conversation_states:
        return
    _conversation_states[chat_id]["data"][key] = value
    _conversation_states[chat_id]["timestamp"] = datetime.now()


def end_conversation(chat_id: int) -> None:
    """End current conversation"""
    if chat_id in _conversation_states:
        _conversation_states.pop(chat_id)
        logger.info(f"Ended conversation for chat {chat_id}")


def reset_conversation(chat_id: int) -> None:
    """Reset conversation to idle state"""
    end_conversation(chat_id)
