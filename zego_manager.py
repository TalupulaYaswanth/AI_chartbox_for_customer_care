"""
ZEGOCLOUD Voice Call / RTC SDK Server-Side Manager
Provides:
1. Official ZEGOCLOUD Token04 cryptographic generation using standard cryptography library.
2. ZegoCallSessionManager for active real-time call tracking, multi-turn conversational memory,
   and low-latency barge-in/interruption state handling.
"""

import os
import time
import json
import random
import struct
import binascii
from datetime import datetime
from dotenv import load_dotenv
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

load_dotenv()

# Error Codes as defined by ZEGOCLOUD Token04 spec
ERROR_CODE_SUCCESS = 0                              # Successfully obtained authentication token
ERROR_CODE_APP_ID_INVALID = 1                       # Invalid appID parameter
ERROR_CODE_USER_ID_INVALID = 3                      # Invalid userID parameter
ERROR_CODE_SECRET_INVALID = 5                       # Invalid secret parameter
ERROR_CODE_EFFECTIVE_TIME_IN_SECONDS_INVALID = 6    # Invalid effective_time_in_seconds parameter


class TokenInfo:
    def __init__(self, token: str, error_code: int, error_message: str):
        self.token = token
        self.error_code = error_code
        self.error_message = error_message

    def to_dict(self):
        return {
            "token": self.token,
            "error_code": self.error_code,
            "error_message": self.error_message
        }


def _make_nonce() -> int:
    """Generate a random 31-bit integer nonce."""
    return random.getrandbits(31)


def _make_random_iv() -> str:
    """Generate a 16-character random IV string for AES CBC."""
    chars = '0123456789abcdefghijklmnopqrstuvwxyz'
    return "".join(random.choice(chars) for _ in range(16))


def _pkcs7_padding(data_bytes: bytes, block_size: int = 16) -> bytes:
    """Apply standard PKCS7 padding to byte sequence."""
    padding_len = block_size - (len(data_bytes) % block_size)
    if padding_len == 0:
        padding_len = block_size
    return data_bytes + bytes([padding_len] * padding_len)


def _aes_encrypt(plain_text: str, key_str: str, iv_str: str) -> bytes:
    """Encrypt plain text using AES-CBC with PKCS7 padding."""
    key_bytes = key_str.encode("utf-8")
    iv_bytes = iv_str.encode("utf-8")
    plain_bytes = plain_text.encode("utf-8")
    
    padded_bytes = _pkcs7_padding(plain_bytes, 16)
    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv_bytes), backend=default_backend())
    encryptor = cipher.encryptor()
    return encryptor.update(padded_bytes) + encryptor.finalize()


def generate_token04(app_id: int, user_id: str, secret: str, effective_time_in_seconds: int = 3600, payload: str = "") -> TokenInfo:
    """
    Generate ZEGOCLOUD Token04 token for authentication and room privilege verification.

    Args:
        app_id: Integer AppID distributed by ZEGOCLOUD
        user_id: User identifier string
        secret: 32-byte secret string for AES encryption
        effective_time_in_seconds: Validity period in seconds
        payload: JSON string for room permissions or empty string

    Returns:
        TokenInfo with token, error_code, error_message
    """
    if not isinstance(app_id, int) or app_id <= 0:
        return TokenInfo("", ERROR_CODE_APP_ID_INVALID, "appID invalid")
    if not isinstance(user_id, str) or not user_id.strip():
        return TokenInfo("", ERROR_CODE_USER_ID_INVALID, "userID invalid")
    if not isinstance(secret, str) or len(secret) != 32:
        return TokenInfo("", ERROR_CODE_SECRET_INVALID, "secret must be a 32 byte string")
    if not isinstance(effective_time_in_seconds, int) or effective_time_in_seconds <= 0:
        return TokenInfo("", ERROR_CODE_EFFECTIVE_TIME_IN_SECONDS_INVALID, "effective_time_in_seconds invalid")

    create_time = int(time.time())
    expire_time = create_time + effective_time_in_seconds
    nonce = _make_nonce()

    token_dict = {
        "app_id": app_id,
        "user_id": user_id,
        "nonce": nonce,
        "ctime": create_time,
        "expire": expire_time,
        "payload": payload
    }
    plain_text = json.dumps(token_dict, separators=(',', ':'), ensure_ascii=False)

    iv = _make_random_iv()
    encrypt_buf = _aes_encrypt(plain_text, secret, iv)

    result_size = len(encrypt_buf) + 28
    result = bytearray(result_size)

    # Big endian packings per ZEGOCLOUD Token04 wire protocol:
    # 0..7: expire_time (int64)
    big_endian_expire_time = struct.pack("!q", expire_time)
    result[0:len(big_endian_expire_time)] = big_endian_expire_time

    # 8..9: iv_size (int16)
    big_endian_iv_size = struct.pack("!h", len(iv))
    result[8:8 + len(big_endian_iv_size)] = big_endian_iv_size

    # 10..25: iv bytes (16 bytes)
    iv_bytes = iv.encode('utf-8')
    result[10:10 + len(iv_bytes)] = iv_bytes

    # 26..27: encrypt_buf_size (int16)
    big_endian_buf_size = struct.pack("!h", len(encrypt_buf))
    result[26:26 + len(big_endian_buf_size)] = big_endian_buf_size

    # 28..: encrypted buffer bytes
    result[28:len(result)] = encrypt_buf

    token = "04" + binascii.b2a_base64(result, newline=False).decode()
    return TokenInfo(token, ERROR_CODE_SUCCESS, "success")


def generate_room_token(user_id: str, room_id: str = None, effective_time: int = 3600) -> TokenInfo:
    """
    Convenience method to generate a privilege-scoped Token04 for a specific room.
    Reads ZEGO_APP_ID and ZEGO_SERVER_SECRET from environment variables,
    with safe development sandbox fallbacks.
    """
    app_id_str = os.environ.get("ZEGO_APP_ID", "123456789")
    try:
        app_id = int(app_id_str)
    except (ValueError, TypeError):
        app_id = 123456789

    secret = os.environ.get("ZEGO_SERVER_SECRET", "0123456789abcdef0123456789abcdef")
    if len(secret) != 32:
        # Pad or normalize to exactly 32 bytes for valid AES key
        secret = (secret + "0" * 32)[:32]

    payload = ""
    if room_id:
        payload_dict = {
            "room_id": room_id,
            "privilege": {
                1: 1,  # Room login privilege
                2: 1   # Stream publish privilege
            },
            "stream_id_list": None
        }
        payload = json.dumps(payload_dict)

    return generate_token04(app_id, user_id, secret, effective_time, payload)


# ==============================================================================
# REAL-TIME CALL SESSION & MULTI-TURN CONVERSATIONAL MEMORY MANAGER
# ==============================================================================

class ZegoCallSession:
    """Represents a single active or completed ZEGOCLOUD voice call session."""
    def __init__(self, room_id: str, customer_name: str = "Valued Customer", customer_phone: str = "+15551234567"):
        self.room_id = room_id
        self.call_id = f"call_{int(time.time())}_{random.randint(1000, 9999)}"
        self.customer_name = customer_name
        self.customer_phone = customer_phone
        self.status = "dialing"  # dialing -> connected -> in_progress -> ended
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.connected_at = None
        self.ended_at = None
        self.history = []  # List of {"role": str, "text": str, "timestamp": str, "interrupted": bool}
        self.is_speaking_ai = False
        self.barge_in_count = 0
        self.last_ai_turn_id = None

    def mark_connected(self):
        self.status = "connected"
        self.connected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def add_turn(self, role: str, text: str, interrupted: bool = False):
        timestamp = datetime.now().strftime("%H:%M:%S")
        turn = {
            "role": role,
            "text": text,
            "timestamp": timestamp,
            "interrupted": interrupted
        }
        self.history.append(turn)
        if role == "ai":
            self.is_speaking_ai = True
            self.last_ai_turn_id = f"turn_{len(self.history)}"
        elif role == "caller":
            self.status = "in_progress"

    def trigger_barge_in(self) -> dict:
        """Called when caller speaks while AI audio is actively playing."""
        self.is_speaking_ai = False
        self.barge_in_count += 1
        # Mark the last AI turn as interrupted if applicable
        if self.history and self.history[-1]["role"] == "ai":
            self.history[-1]["interrupted"] = True
        return {
            "interrupted": True,
            "barge_in_count": self.barge_in_count,
            "last_ai_turn_id": self.last_ai_turn_id
        }

    def finish_ai_speech(self):
        self.is_speaking_ai = False

    def mark_ended(self):
        self.status = "ended"
        self.is_speaking_ai = False
        self.ended_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_full_transcript(self) -> str:
        lines = []
        for h in self.history:
            suffix = " [INTERRUPTED BY CALLER]" if h.get("interrupted") else ""
            lines.append(f"[{h['timestamp']}] {h['role'].upper()}: {h['text']}{suffix}")
        return "\n".join(lines)

    def to_dict(self):
        return {
            "room_id": self.room_id,
            "call_id": self.call_id,
            "customer_name": self.customer_name,
            "customer_phone": self.customer_phone,
            "status": self.status,
            "created_at": self.created_at,
            "connected_at": self.connected_at,
            "ended_at": self.ended_at,
            "history_count": len(self.history),
            "history": self.history,
            "is_speaking_ai": self.is_speaking_ai,
            "barge_in_count": self.barge_in_count
        }


class ZegoCallSessionManager:
    """Manages all active ZEGOCLOUD call sessions in memory."""
    def __init__(self):
        self._sessions = {}  # { room_id: ZegoCallSession }

    def create_or_get_session(self, room_id: str, customer_name: str = "Valued Customer", customer_phone: str = "+15551234567") -> ZegoCallSession:
        if room_id not in self._sessions:
            self._sessions[room_id] = ZegoCallSession(room_id, customer_name, customer_phone)
        return self._sessions[room_id]

    def get_session(self, room_id: str) -> ZegoCallSession:
        return self._sessions.get(room_id)

    def end_session(self, room_id: str) -> ZegoCallSession:
        session = self._sessions.get(room_id)
        if session:
            session.mark_ended()
        return session

    def list_active_sessions(self):
        return [sess.to_dict() for sess in self._sessions.values() if sess.status != "ended"]


# Global session manager instance
zego_session_manager = ZegoCallSessionManager()
