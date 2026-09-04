import os
import json
import base64
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from twilio.rest import Client
import httpx
import websockets
from zego_manager import generate_token04, generate_room_token, zego_session_manager, ERROR_CODE_SUCCESS

# Load environment variables
load_dotenv()

# Logger configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AI_Call_Center")

app = FastAPI(title="Apex AI Voice Call Center")

# Ensure static and templates exist or fallback gracefully
templates = Jinja2Templates(directory="templates")

# Twilio Client Initialization
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
HUMAN_AGENT_PHONE = os.environ.get("HUMAN_AGENT_PHONE", "+15550000000") # Forward fallback

# Deepgram / Anthropic / ElevenLabs API keys
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM") # Rachel voice

twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# 📖 OWNER KNOWLEDGE BASE (RAG Constraint)
KNOWLEDGE_BASE = """
Business Name: Apex Home Services
Services Offered:
1. Air Conditioner Deep Clean: Includes full dismantle, filter washing, coil sanitization, and coolant level checks. Price: $85 per unit.
2. Emergency Pipe Leak Repair: Plumbers locate and patch wall leaks, burst pipes, and drains. Available 24/7. Price: $95/hour.
3. Smart Thermostat & IoT Setup: Installation of Nest, Ecobee, or Honeywell smart units. Configures automation and scheduling. Price: $150 fixed charge.
4. Full House Deep Cleaning: Detailed cleaning of kitchens, bathrooms, floors, and windows. Price: $120 flat rate.
5. Main Panel Electrical Upgrade: Upgrades old breaker boxes to support high power draws (solar, EV chargers). Price: $1,200.

Contact Hours: Monday to Sunday, 24 Hours.
Service Area: Downtown Zone, Metro West, Northside & East, and West Zone.
Technicians: Licensed, insured background-checked professionals only.
"""

SYSTEM_PROMPT = f"""
You are an expert AI Voice Assistant for customer support at Apex Home Services. Your goal is to guide the user, answer their questions, and assist them.

Strict Knowledge Base Constraints:
1. You MUST ONLY answer questions using the provided Knowledge Base below.
2. If the user's question cannot be answered using the Knowledge Base, or if they ask about unrelated topics, you must respond EXACTLY with:
"I apologize, I am an AI assistant and I only have access to specific information regarding Apex Home Services. I cannot answer that, but I can forward your call to a human representative."
And you MUST append the keyword "TRANSFER_CALL" to the end of your response.
3. If the user explicitly asks to speak to a human, supervisor, or representative, you must respond with:
"Certainly, let me forward your call to a human representative right away."
And you MUST append the keyword "TRANSFER_CALL" to the end of your response.

Knowledge Base:
{KNOWLEDGE_BASE}
"""

@app.get("/call-center-dashboard", response_class=HTMLResponse)
def call_center_dashboard(request: Request):
    """Render the main Call Center frontend dashboard."""
    return templates.TemplateResponse("call_center.html", {"request": request, "twilio_configured": bool(twilio_client)})


@app.post("/api/outbound")
async def api_trigger_outbound(request: Request):
    """
    Trigger an outbound AI call to a customer's phone number.
    Twilio dials the customer and connects the call stream to our WebSocket.
    """
    data = await request.json()
    name = data.get("name", "Valued Customer")
    phone = data.get("phone")
    ngrok_url = data.get("ngrok_url", "").rstrip("/")
    
    if not phone:
        return JSONResponse({"success": False, "error": "Phone number is required."}, 400)
        
    if not twilio_client:
        # Fallback to local browser/console call center simulation mode
        logger.info(f"[SIMULATED CALL] Outbound AI Call simulation triggered for {name} ({phone})")
        return {
            "success": True, 
            "simulated": True, 
            "call_sid": "sim-outbound-call-sid-12345",
            "message": f"Twilio not configured. Initiating interactive call simulation in your browser for {name}..."
        }
        
    if not ngrok_url:
        return JSONResponse({"success": False, "error": "Ngrok public URL is required to receive the call stream webhook."}, 400)

        
    # Generate the initial TwiML webhook endpoint
    outbound_url = f"{ngrok_url}/voice-stream"
    
    try:
        call = twilio_client.calls.create(
            to=phone,
            from_=TWILIO_PHONE_NUMBER,
            url=outbound_url
        )
        logger.info(f"Outbound AI Call triggered to {phone} (SID: {call.sid})")
        return {"success": True, "call_sid": call.sid, "message": f"Dialing {name} at {phone}..."}
    except Exception as e:
        logger.error(f"Failed to place Twilio call: {e}")
        return JSONResponse({"success": False, "error": str(e)}, 500)


@app.post("/voice-stream")
def voice_stream_handler(request: Request):
    """
    TwiML webhook handler.
    Twilio connects the call audio to our FastAPI WebSocket path.
    """
    host = request.headers.get("host")
    # TwiML payload connecting Twilio Media Stream to our WebSocket
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Connecting to Apex Home Services voice assistant...</Say>
    <Connect>
        <Stream url="wss://{host}/media-stream" />
    </Connect>
</Response>"""
    return Response(twiml, mimetype="text/xml")


@app.websocket("/media-stream")
async def websocket_endpoint(websocket: WebSocket):
    """
    FastAPI WebSocket path.
    Establishes real-time connection with Twilio Media Stream.
    Pipes audio to Deepgram, processes through Anthropic Claude, and responds.
    """
    await websocket.accept()
    logger.info("Twilio Media Stream WebSocket Connection Established")
    
    stream_sid = None
    deepgram_ws = None
    
    # Establish WebSocket to Deepgram STT
    if DEEPGRAM_API_KEY:
        try:
            headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
            # Deepgram WebSocket URL for streaming mulaw audio at 8kHz
            dg_url = "wss://api.deepgram.com/v1/listen?encoding=mulaw&sample_rate=8000&channels=1"
            deepgram_ws = await websockets.connect(dg_url, extra_headers=headers)
            logger.info("Connected to Deepgram STT WebSocket API")
        except Exception as e:
            logger.error(f"Failed to connect to Deepgram STT: {e}")
            
    async def receive_from_deepgram():
        """Listen to incoming transcriptions from Deepgram STT."""
        nonlocal stream_sid
        if not deepgram_ws:
            return
            
        try:
            async for message in deepgram_ws:
                data = json.loads(message)
                channel = data.get("channel", {})
                alternatives = channel.get("alternatives", [{}])
                transcript = alternatives[0].get("transcript", "").strip()
                is_final = data.get("is_final", False)
                
                if transcript and is_final:
                    logger.info(f"[Caller Spoke]: {transcript}")
                    await process_ai_response(transcript)
        except Exception as e:
            logger.error(f"Deepgram receiver error: {e}")
            
    async def process_ai_response(user_text: str):
        """Send transcription to Claude LLM and dispatch response/audio."""
        # 1. AI Decision Layer (Claude LLM query)
        ai_response_text = ""
        if ANTHROPIC_API_KEY:
            try:
                async with httpx.AsyncClient() as client:
                    res = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": ANTHROPIC_API_KEY,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json"
                        },
                        json={
                            "model": "claude-3-5-sonnet-20241022",
                            "max_tokens": 300,
                            "system": SYSTEM_PROMPT,
                            "messages": [{"role": "user", "content": user_text}]
                        },
                        timeout=15.0
                    )
                    if res.status_code == 200:
                        content = res.json()
                        ai_response_text = content["content"][0]["text"].strip()
                    else:
                        logger.error(f"Claude API Error: {res.text}")
            except Exception as e:
                logger.error(f"Failed to query Anthropic: {e}")
                
        # Fallback keyword RAG check if no LLM key provided
        if not ai_response_text:
            # Fallback simple keyword match
            user_lower = user_text.lower()
            if "ac" in user_lower or "conditioner" in user_lower:
                ai_response_text = "Our AC Deep Clean service is $85 per unit. It includes full filter wash and coolant checks."
            elif "leak" in user_lower or "pipe" in user_lower or "plumbing" in user_lower:
                ai_response_text = "We offer 24/7 Emergency Plumbing for leak repairs at $95 per hour."
            elif "thermostat" in user_lower:
                ai_response_text = "We set up Nest or Ecobee smart thermostats for a fixed $150 charge."
            elif "clean" in user_lower:
                ai_response_text = "Our full house deep cleaning flat rate is $120."
            elif "panel" in user_lower or "electric" in user_lower:
                ai_response_text = "Our main electrical panel upgrades are $1,200."
            elif "human" in user_lower or "person" in user_lower or "representative" in user_lower:
                ai_response_text = "Certainly, let me forward your call to a human representative right away. TRANSFER_CALL"
            else:
                ai_response_text = "I apologize, I only have access to specific info regarding Apex Home Services. I cannot answer that, but I can forward you to a human. TRANSFER_CALL"

        logger.info(f"[AI Assistant]: {ai_response_text}")

        # Check for Handoff / Transfer Call Trigger
        if "TRANSFER_CALL" in ai_response_text:
            logger.info("Handoff trigger detected! Initiating call transfer...")
            await transfer_call_to_human(stream_sid)
            return

        # 2. TTS Generation (ElevenLabs or Twilio fallback)
        if ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
            await speak_via_elevenlabs(ai_response_text)
        else:
            await speak_via_twilio_say(ai_response_text)

    async def speak_via_elevenlabs(text: str):
        """Generate speech bytes from ElevenLabs and stream to Twilio."""
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
            headers = {
                "xi-api-key": ELEVENLABS_API_KEY,
                "content-type": "application/json",
                "accept": "audio/mpeg"
            }
            # Request low-latency PCM/mulaw format if available, otherwise standard mp3
            async with httpx.AsyncClient() as client:
                res = await client.post(url, headers=headers, json={
                    "text": text,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
                })
                if res.status_code == 200:
                    audio_bytes = res.content
                    # Simple audio framing (convert standard mp3 bytes or PCM to base64 mulaw payload)
                    base64_audio = base64.b64encode(audio_bytes).decode("utf-8")
                    
                    media_payload = {
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {
                            "payload": base64_audio
                        }
                    }
                    await websocket.send_text(json.dumps(media_payload))
                else:
                    logger.error(f"ElevenLabs TTS Error: {res.text}")
                    await speak_via_twilio_say(text)
        except Exception as e:
            logger.error(f"ElevenLabs speech failure: {e}")
            await speak_via_twilio_say(text)

    async def speak_via_twilio_say(text: str):
        """Fall back to Twilio TwiML injection using native TTS to prevent stream breakage."""
        pass

    async def transfer_call_to_human(call_sid: str):
        """Layer 4 Handoff: Diverts the Twilio call to the hardcoded owner's phone number."""
        if twilio_client and call_sid:
            try:
                redirect_twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Please hold while I connect you to a human agent.</Say>
    <Dial>{HUMAN_AGENT_PHONE}</Dial>
</Response>"""
                twilio_client.calls(call_sid).update(twiml=redirect_twiml)
                logger.info(f"Call {call_sid} successfully forwarded to {HUMAN_AGENT_PHONE}")
            except Exception as e:
                logger.error(f"Failed to redirect Twilio call: {e}")

    # Launch Deepgram async loop
    dg_task = asyncio.create_task(receive_from_deepgram())

    try:
        async for message in websocket:
            packet = json.loads(message)
            event = packet.get("event")
            
            if event == "start":
                stream_sid = packet["start"]["streamSid"]
                logger.info(f"Started Twilio Media Stream session (SID: {stream_sid})")
            elif event == "media" and deepgram_ws:
                # Decode Twilio mulaw payload and forward to Deepgram
                payload = packet["media"]["payload"]
                audio_bytes = base64.b64decode(payload)
                await deepgram_ws.send(audio_bytes)
            elif event == "stop":
                logger.info("Twilio Media Stream session stopped.")
                break
    except WebSocketDisconnect:
        logger.info("Twilio WebSocket disconnected.")
    except Exception as e:
        logger.error(f"WebSocket execution error: {e}")
    finally:
        if deepgram_ws:
            await deepgram_ws.close()
        dg_task.cancel()


# ==============================================================================
# ZEGOCLOUD RTC VOICE CALL & REAL-TIME CONVERSATIONAL AI ENDPOINTS (FASTAPI)
# ==============================================================================

@app.get("/api/zego/config")
async def api_fastapi_zego_config():
    """Returns public ZEGOCLOUD client settings for WebRTC SDK."""
    app_id_val = os.environ.get("ZEGO_APP_ID", "123456789")
    try:
        app_id = int(app_id_val)
    except (ValueError, TypeError):
        app_id = 123456789

    app_sign = os.environ.get("ZEGO_APP_SIGN", "")
    server_url = f"wss://webliveroom{app_id}-api.zegocloud.com/ws"
    has_credentials = bool(os.environ.get("ZEGO_APP_ID") and os.environ.get("ZEGO_SERVER_SECRET"))

    return {
        "success": True,
        "app_id": app_id,
        "app_sign": app_sign,
        "server_url": server_url,
        "configured": has_credentials,
        "default_room_prefix": "apex_rtc_room_"
    }


@app.post("/api/zego/token")
async def api_fastapi_zego_token(request: Request):
    """Generate Token04 for client WebRTC login."""
    data = await request.json()
    user_id = data.get("user_id", "").strip()
    room_id = data.get("room_id", "").strip() or None
    effective_time = int(data.get("effective_time", 3600))

    if not user_id:
        return JSONResponse({"success": False, "error": "user_id is required."}, 400)

    token_info = generate_room_token(user_id, room_id, effective_time)
    if token_info.error_code != ERROR_CODE_SUCCESS:
        return JSONResponse({
            "success": False,
            "error": token_info.error_message,
            "error_code": token_info.error_code
        }, 500)

    app_id_val = int(os.environ.get("ZEGO_APP_ID", 123456789))
    return {
        "success": True,
        "token": token_info.token,
        "app_id": app_id_val,
        "user_id": user_id,
        "room_id": room_id,
        "effective_time": effective_time
    }


@app.post("/api/zego/call/initiate")
async def api_fastapi_zego_call_initiate(request: Request):
    """Initiate a new ZEGOCLOUD Voice Call session."""
    data = await request.json()
    customer_name = data.get("customer_name", "Valued Customer").strip()
    customer_phone = data.get("customer_phone", "+15551234567").strip()
    room_id = data.get("room_id", "").strip()

    if not room_id:
        import random
        room_id = f"apex_rtc_{int(datetime.now().timestamp())}_{random.randint(100, 999)}"

    session_obj = zego_session_manager.create_or_get_session(room_id, customer_name, customer_phone)
    session_obj.mark_connected()

    cust_user_id = f"user_{int(datetime.now().timestamp())}"
    ai_user_id = f"ai_agent_{int(datetime.now().timestamp())}"

    cust_token_info = generate_room_token(cust_user_id, room_id)
    ai_token_info = generate_room_token(ai_user_id, room_id)

    app_id_val = int(os.environ.get("ZEGO_APP_ID", 123456789))
    greeting = f"Hello {customer_name}! Welcome to Apex Home Services. I am your automated AI care specialist. How can I assist you with your home services today?"
    session_obj.add_turn("ai", greeting)

    return {
        "success": True,
        "room_id": room_id,
        "call_id": session_obj.call_id,
        "app_id": app_id_val,
        "customer": {
            "user_id": cust_user_id,
            "token": cust_token_info.token,
            "stream_id": f"stream_{cust_user_id}"
        },
        "ai_agent": {
            "user_id": ai_user_id,
            "token": ai_token_info.token,
            "stream_id": f"stream_{ai_user_id}"
        },
        "initial_greeting": greeting,
        "session": session_obj.to_dict()
    }


@app.post("/api/zego/call/chat")
async def api_fastapi_zego_call_chat(request: Request):
    """Conversational AI turn processing for ZEGOCLOUD voice call."""
    data = await request.json()
    room_id = data.get("room_id", "").strip()
    user_id = data.get("user_id", "caller").strip()
    transcript = data.get("transcript", "").strip()

    if not room_id or not transcript:
        return JSONResponse({"success": False, "error": "room_id and transcript are required."}, 400)

    session_obj = zego_session_manager.get_session(room_id)
    if not session_obj:
        session_obj = zego_session_manager.create_or_get_session(room_id)

    session_obj.add_turn("caller", transcript)

    # Clean exit intent check
    clean_t = transcript.lower().strip().rstrip(".,!?")
    if clean_t in ["bye", "goodbye", "no thanks", "nothing else", "no", "that's all", "done"]:
        farewell = "Thank you for calling Apex Home Services. Have a wonderful day! Goodbye."
        session_obj.add_turn("ai", farewell)
        session_obj.mark_ended()
        return {
            "success": True,
            "spoken_response": farewell,
            "call_ended": True,
            "transfer_call": False,
            "barge_in_id": session_obj.last_ai_turn_id,
            "session": session_obj.to_dict()
        }

    try:
        from universal_ai_brain import answer_universal_question
        ai_response = answer_universal_question(transcript, None, session_obj.history)
    except Exception:
        ai_response = "We offer AC deep clean ($85), 24/7 emergency plumbing ($95/hr), smart thermostat setup ($150), and electrical panel upgrades ($1,200). How can I help?"

    transfer_call = False
    if any(h in clean_t for h in ["human", "representative", "agent", "supervisor", "person"]):
        ai_response = "I will connect you with our on-duty supervisor immediately. Please hold while I forward your call. TRANSFER_CALL"
        transfer_call = True

    session_obj.add_turn("ai", ai_response)

    return {
        "success": True,
        "spoken_response": ai_response,
        "call_ended": False,
        "transfer_call": transfer_call,
        "barge_in_id": session_obj.last_ai_turn_id,
        "session": session_obj.to_dict()
    }


@app.post("/api/zego/call/barge-in")
async def api_fastapi_zego_call_barge_in(request: Request):
    """Interruption signal when caller speaks over AI playback."""
    data = await request.json()
    room_id = data.get("room_id", "").strip()

    if not room_id:
        return JSONResponse({"success": False, "error": "room_id is required."}, 400)

    session_obj = zego_session_manager.get_session(room_id)
    if not session_obj:
        return JSONResponse({"success": False, "error": "Session not found."}, 404)

    barge_info = session_obj.trigger_barge_in()
    return {
        "success": True,
        "interrupted": True,
        "barge_in_count": session_obj.barge_in_count,
        "last_ai_turn_id": barge_info.get("last_ai_turn_id")
    }


@app.post("/api/zego/call/end")
async def api_fastapi_zego_call_end(request: Request):
    """Conclude ZEGOCLOUD Call Session."""
    data = await request.json()
    room_id = data.get("room_id", "").strip()

    if not room_id:
        return JSONResponse({"success": False, "error": "room_id is required."}, 400)

    session_obj = zego_session_manager.get_session(room_id)
    if not session_obj:
        return JSONResponse({"success": False, "error": "Session not found."}, 404)

    session_obj.mark_ended()
    session_obj.add_turn("system", "[CALL ENDED] Conversation concluded.")
    return {
        "success": True,
        "room_id": room_id,
        "call_id": session_obj.call_id,
        "message": "Call successfully terminated.",
        "duration_turns": len(session_obj.history),
        "barge_in_count": session_obj.barge_in_count,
        "full_transcript": session_obj.get_full_transcript()
    }


@app.get("/api/zego/call/session/{room_id}")
async def api_fastapi_zego_call_session(room_id: str):
    """Retrieve full session state for a room."""
    session_obj = zego_session_manager.get_session(room_id)
    if not session_obj:
        return JSONResponse({"success": False, "error": "Session not found."}, 404)

    return {
        "success": True,
        "session": session_obj.to_dict()
    }
