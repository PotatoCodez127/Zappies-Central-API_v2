# # api/server.py
# import asyncio
# import logging
# import datetime
# import pytz
# import json
# from tools.scheduler import send_meeting_reminders

# from fastapi import FastAPI, HTTPException, Depends, Header, status
# from pydantic import BaseModel, ValidationError
# from supabase.client import Client, create_client
# from config.settings import settings
# from agent.agent_factory import create_agent_executor
# from langchain.memory import ConversationBufferMemory
# from langchain_core.chat_history import BaseChatMessageHistory
# from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, messages_from_dict, messages_to_dict
# from collections import defaultdict
# from fastapi.responses import HTMLResponse, JSONResponse
# from dateutil.parser import parse
# from postgrest.exceptions import APIError
# from tools.notifications import send_sms_confirmation

# # --- Import Harmonized Tools & Schemas ---
# from tools.google_calendar import create_calendar_event, get_available_slots
# from tools.email_sender import send_direct_booking_confirmation
# from tools.action_schemas import (
#     CheckAvailabilityArgs,
#     VoiceBookingRequest,
#     CallLogRequest
# )

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# app = FastAPI(
#     title=settings.API_TITLE,
#     description=settings.API_DESCRIPTION,
#     version=settings.API_VERSION
# )

# # --- Centralized Timezone ---
# SAST_TZ = pytz.timezone(settings.VOICE_AGENT_CONFIG.TIMEZONE)

# # --- API Key Verification ---
# async def verify_api_key(x_api_key: str = Header()):
#     if not settings.API_SECRET_KEY:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="API Secret Key not configured on the server."
#         )
#     if x_api_key != settings.API_SECRET_KEY:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid or missing API Key."
#         )

# # --- Central Supabase Client & Concurrency Locks ---
# agent_semaphore = asyncio.Semaphore(settings.CONCURRENCY_LIMIT)
# supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
# conversation_locks = defaultdict(asyncio.Lock)


# # --- Chat History Class (Unchanged) ---
# class SupabaseChatMessageHistory(BaseChatMessageHistory):
#     def __init__(self, session_id: str, table_name: str):
#         self.session_id = session_id
#         self.table_name = table_name

#     @property
#     def messages(self):
#         """Retrieve and clean messages from Supabase."""
#         response = supabase.table(self.table_name).select("history").eq("conversation_id", self.session_id).execute()
        
#         if not response.data or not response.data[0].get('history'):
#             return []

#         history_data = response.data[0]['history']

#         for message_data in history_data:
#             if message_data.get("type") == "ai":
#                 ai_data = message_data.get("data", {})
#                 tool_calls = ai_data.get("tool_calls")
#                 if tool_calls and isinstance(tool_calls, list):
#                     for tool_call in tool_calls:
#                         if "args" in tool_call and isinstance(tool_call["args"], str):
#                             try:
#                                 tool_call["args"] = json.loads(tool_call["args"])
#                             except json.JSONDecodeError:
#                                 tool_call["args"] = {"query": tool_call["args"]}
        
#         return messages_from_dict(history_data)


#     def add_messages(self, messages: list[BaseMessage]) -> None:
#         """Save messages to Supabase, correctly formatting tool calls."""
#         current_history_dicts = messages_to_dict(self.messages)
        
#         new_history_dicts = []
#         for message in messages:
#             message_dict = messages_to_dict([message])[0]
#             if isinstance(message, AIMessage) and hasattr(message, 'tool_calls') and message.tool_calls:
#                 message_dict['data']['tool_calls'] = message.tool_calls
#             new_history_dicts.append(message_dict)

#         updated_history = current_history_dicts + new_history_dicts
        
#         supabase.table(self.table_name).upsert({
#             "conversation_id": self.session_id, 
#             "history": updated_history,
#             "status": "active"
#         }).execute()

#     def clear(self) -> None:
#         supabase.table(self.table_name).delete().eq("conversation_id", self.session_id).execute()

# # --- ======================================= ---
# # --- WHATSAPP / TEXT AGENT ENDPOINTS (EXISTING)
# # --- ======================================= ---

# class ChatRequest(BaseModel):
#     conversation_id: str
#     query: str

# @app.post("/chat", dependencies=[Depends(verify_api_key)])
# async def chat_with_agent(request: ChatRequest):
#     lock = conversation_locks[request.conversation_id]

#     async with lock:
#         try:
#             status_response = supabase.table("conversation_history").select("status").eq("conversation_id", request.conversation_id).execute()
            
#             if status_response.data and status_response.data[0].get('status') == 'handover':
#                 logger.info(f"Conversation {request.conversation_id} is in handover. Bypassing agent.")
#                 message_history = SupabaseChatMessageHistory(session_id=request.conversation_id, table_name=settings.DB_CONVERSATION_HISTORY_TABLE)
#                 message_history.add_messages([HumanMessage(content=request.query)])
#                 return {"response": "A human agent will be with you shortly. Thank you for your patience."}
#         except Exception:
#             pass
        
#         async with agent_semaphore:
#             try:
#                 message_history = SupabaseChatMessageHistory(
#                     session_id=request.conversation_id,
#                     table_name=settings.DB_CONVERSATION_HISTORY_TABLE
#                 )
                
#                 memory = ConversationBufferMemory(
#                     memory_key="history",
#                     chat_memory=message_history,
#                     return_messages=True,
#                     input_key="input"
#                 )

#                 agent_executor, tool_callback = create_agent_executor(memory, conversation_id=request.conversation_id)

#                 current_time_sast = datetime.datetime.now(SAST_TZ).strftime('%A, %Y-%m-%d %H:%M:%S %Z')

#                 agent_input = {
#                     "input": request.query,
#                     "current_time": current_time_sast,
#                     "conversation_id": request.conversation_id
#                 }
                
#                 response = await agent_executor.ainvoke(agent_input)
#                 agent_output = response.get("output")
                
#                 tool_calls = tool_callback.tool_calls
#                 ai_message = AIMessage(content=agent_output)
#                 if tool_calls:
#                     ai_message.tool_calls = tool_calls

#                 if not agent_output or not agent_output.strip():
#                     logger.warning(f"Agent for convo ID {request.conversation_id} generated an empty response. Sending a default message.")
#                     agent_output = "I'm sorry, I seem to have lost my train of thought. Could you please tell me a little more about what you're looking for?"

#                 return {"response": agent_output}
#             except Exception as e:
#                 logger.error(f"Error in /chat for conversation_id {request.conversation_id}: {e}", exc_info=True)
#                 raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# @app.get("/confirm-meeting/{meeting_id}", response_class=HTMLResponse)
# async def confirm_meeting(meeting_id: str):
#     """Endpoint to confirm a meeting, create a calendar event, and update the DB."""
#     try:
#         response = supabase.table("meetings").select("*").eq("id", meeting_id).single().execute()
        
#         if not response.data:
#             return "<h1>Meeting Not Found</h1><p>This confirmation link is invalid or has expired.</p>"
        
#         meeting_details = response.data
        
#         if meeting_details['status'] == 'confirmed':
#             return "<h1>Meeting Already Confirmed</h1><p>Your spot was already secured. We look forward to seeing you!</p>"

#         summary = f"Onboard Call with {meeting_details['company_name']} | Zappies AI"
#         description = (
#             f"Onboarding call with {meeting_details['full_name']} from {meeting_details['company_name']} to discuss the 'Project Pipeline AI'.\n\n"
#             f"Stated Goal: {meeting_details['goal']}\n"
#             f"Stated Budget: R{meeting_details['monthly_budget']}/month"
#             f"Lead Phone: {meeting_details.get('client_number', 'N/A')}"
#         )
        
#         created_event = create_calendar_event(
#             start_time=meeting_details['start_time'],
#             summary=summary,
#             description=description,
#             attendees=[]
#         )
        
#         supabase.table("meetings").update({
#             "status": "confirmed",
#             "google_calendar_event_id": created_event.get('id')
#         }).eq("id", meeting_id).execute()
        
#         logger.info(f"Meeting {meeting_id} confirmed and calendar event created successfully.")
        
#         # --- ADD SMS CONFIRMATION ---
#         client_number = meeting_details.get("client_number")
#         if client_number: # Only send if number exists in the meeting record
#             try:
#                 start_time_sast = parse(meeting_details['start_time']).astimezone(SAST_TZ)
#                 human_readable_time = start_time_sast.strftime('%A, %B %d at %I:%M %p %Z').replace(' 0', ' ')
#                 send_sms_confirmation(
#                     recipient_phone_number=client_number,
#                     full_name=meeting_details['full_name'],
#                     start_time_str=human_readable_time
#                 )
#             except Exception as sms_error:
#                  logger.error(f"Failed to send SMS confirmation for confirmed meeting {meeting_id} to {client_number}: {sms_error}", exc_info=True)

#         return "<h1>Thank You!</h1><p>Your meeting has been successfully confirmed. We've added it to our calendar and look forward to speaking with you!</p>"

#     except APIError as e:
#         # Specifically catch the error when .single() finds 0 rows
#         if "The result contains 0 rows" in str(e):
#              logger.warning(f"Meeting confirmation attempt for non-existent ID: {meeting_id}")
#              return "<h1>Meeting Not Found</h1><p>This confirmation link is invalid or has expired.</p>"
#         else:
#              # Re-raise other API errors or handle them generally
#              logger.error(f"Supabase API Error during meeting confirmation {meeting_id}: {e}", exc_info=True)
#              return "<h1>Error</h1><p>Sorry, a database error occurred while confirming your meeting. Please try again later.</p>"
#     except Exception as e:
#         # Catch other potential errors (like Google Calendar issues)
#         logger.error(f"Error confirming meeting {meeting_id}: {e}", exc_info=True)
#         return "<h1>Error</h1><p>Sorry, something went wrong while confirming your meeting. Please try again later.</p>"

# # --- ================================= ---
# # --- VOICE AGENT ENDPOINTS (NEW)
# # --- ================================= ---

# @app.post("/get-availability", dependencies=[Depends(verify_api_key)])
# async def get_voice_availability(request: CheckAvailabilityArgs):
#     """
#     Provides available slots for a given date.
#     This is a direct, procedural endpoint for the voice agent.
#     """
#     try:
#         # 1. Check if the requested date is valid
#         now_sast = datetime.datetime.now(SAST_TZ)
#         requested_date = datetime.datetime.fromisoformat(request.date).date()

#         if requested_date < now_sast.date():
#             return JSONResponse(
#                 status_code=400,
#                 content={"status": "unavailable", "message": "Sorry, that date is in the past."}
#             )
        
#         # 2. Get available slots using the harmonized function
#         slots = get_available_slots(request.date)
        
#         if not slots:
#             return {"status": "unavailable", "message": "Sorry, I couldn't find any open 1-hour slots on that day."}
        
#         # 3. Format slots for the voice agent
#         formatted_suggestions = []
#         for slot_iso in slots:
#             dt_sast = parse(slot_iso).astimezone(SAST_TZ)
#             human_readable = dt_sast.strftime('%A, %B %d at %I:%M %p').replace(' 0', ' ') # Format with padding, then remove leading 0 if present
#             formatted_suggestions.append({"human_readable": human_readable, "iso_8061": slot_iso})

#         return {
#             "status": "available_slots_found",
#             "message": "Sure, here are some available times for that day:",
#             "next_available_slots": formatted_suggestions
#         }
        
#     except Exception as e:
#         logger.error(f"Error in /get-availability: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")

# @app.post("/log-call", dependencies=[Depends(verify_api_key)])
# async def log_call_history(request: CallLogRequest):
#     """
#     Logs the details of a call that did NOT result in a meeting.
#     To be called by the voice agent upon disqualification or call termination.
#     """
#     try:
#         call_data = request.model_dump(exclude_unset=True)
#         # Ensure the key flag is explicitly set, even if default
#         call_data["resulted_in_meeting"] = request.resulted_in_meeting 

#         supabase.table("call_history").insert(call_data).execute()
#         logger.info(f"Successfully logged call for {request.client_number or 'Unknown'}.")
#         return {"message": "Call log received."}
        
#     except Exception as e:
#         logger.error(f"Error in /log-call: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")

# @app.post("/book-appointment", dependencies=[Depends(verify_api_key)])
# async def book_voice_appointment(request: VoiceBookingRequest):
#     """
#     Books an appointment *immediately* (synchronously).
#     Used by the voice agent.
#     1. Creates Google Calendar event.
#     2. Sends a *direct* confirmation email (no link).
#     3. Logs to 'meetings' table as 'confirmed'.
#     4. Logs to 'call_history' table as 'resulted_in_meeting: True'.
#     """
#     try:
#         # 1. Prepare event details
#         summary = f"Onboarding call with {request.name} from {request.company_name} to discuss the 'Project Pipeline AI'."
#         description = (
#             f"Stated Goal: {request.goal}\n"
#             f"Stated Budget: R{request.monthly_budget}/month\n\n"
#             f"Lead Contact: {request.email}\n"
#             f"Lead Phone: {request.client_number}"
#         )
        
#         # 2. Create Google Calendar event *immediately*
#         created_event = create_calendar_event(
#             start_time=request.start_time,
#             summary=summary,
#             description=description,
#             attendees=[request.email]
#         )
#         logger.info(f"Successfully created Google Calendar event for {request.email}.")
        
#         # 3. Log to 'meetings' table with 'confirmed' status
#         meeting_data = {
#             "full_name": request.name,
#             "email": request.email,
#             "company_name": request.company_name,
#             "start_time": request.start_time,
#             "goal": request.goal,
#             "monthly_budget": request.monthly_budget,
#             "client_number": request.client_number,
#             "google_calendar_event_id": created_event.get('id'),
#             "status": "confirmed" # Directly confirmed
#         }
#         supabase.table("meetings").insert(meeting_data).execute()
#         logger.info(f"Successfully saved confirmed meeting to 'meetings' table for {request.email}.")

#         # 4. Log to 'call_history' table
#         call_data = {
#             "full_name": request.name,
#             "email": request.email,
#             "company_name": request.company_name,
#             "goal": request.goal,
#             "monthly_budget": request.monthly_budget,
#             "client_number": request.client_number,
#             "call_duration_seconds": request.call_duration_seconds,
#             "resulted_in_meeting": True,
#             "disqualification_reason": None
#         }
#         supabase.table("call_history").insert(call_data).execute()
#         logger.info(f"Successfully logged booked call to 'call_history' for {request.email}.")
        
#     # 5. Prepare human-readable time (do this BEFORE try blocks)
#         human_readable_time = "the scheduled time" # Default
#         try:
#             start_time_sast = parse(request.start_time).astimezone(SAST_TZ)
#             # Format for email and SMS
#             human_readable_time = start_time_sast.strftime('%A, %B %d at %I:%M %p %Z').replace(' 0', ' ')
#         except Exception as time_parse_error:
#              logger.error(f"Error parsing start_time for notifications {request.email}: {time_parse_error}")
#              # Proceed with default time string if parsing fails for notifications

#         # 6. Send direct confirmation email
#         email_sent_successfully = False # Track success specifically
#         try:
#             send_direct_booking_confirmation( # Use boolean return value
#                 recipient_email=request.email,
#                 full_name=request.name,
#                 start_time=human_readable_time # Use pre-calculated time
#             )
#             email_sent_successfully = True # Mark as successful if no exception
#         except Exception as email_error:
#             logger.error(f"Failed to send direct confirmation email for {request.email}: {email_error}", exc_info=True)

#         # 7. Send SMS confirmation
#         sms_attempted = False # Track if SMS was attempted
#         if request.client_number:
#             sms_attempted = True # Mark as attempted
#             try:
#                 send_sms_confirmation(
#                     recipient_phone_number=request.client_number,
#                     full_name=request.name,
#                     start_time_str=human_readable_time # Use pre-calculated time
#                 )
#             except Exception as sms_error:
#                 logger.error(f"Failed to send SMS confirmation to {request.client_number}: {sms_error}", exc_info=True)
#                 # sms_attempted remains True as it was attempted

#         # 8. Return the specific success message (Conditional)
#         first_name = request.name.strip().split(' ')[0]
#         email_part = "a confirmation email" if email_sent_successfully else "attempted to send a confirmation email"
#         # --- MODIFIED SMS PART ---
#         sms_part = " and SMS" if sms_attempted else "" # Only include "and SMS" if it was ATTEMPTED
#         # --- END MODIFICATION ---
#         success_message = (
#             f"Perfect, {first_name}! I've successfully booked your 1-hour call. "
#             f"I've just sent {email_part}{sms_part}, and a calendar invitation to {request.email} will follow shortly."
#         )
#         return {"message": success_message}

#     except ValidationError as e:
#         logger.warning(f"Validation error in /book-appointment: {e.errors()}")
#         return JSONResponse(
#             status_code=400,
#             content={"error": "Missing or invalid required fields.", "details": e.errors()}
#         )
#     except ValueError as e: # Catch booking in the past
#         logger.warning(f"Booking validation error: {str(e)}")
#         return JSONResponse(
#             status_code=400,
#             content={"error": str(e)}
#         )
#     except Exception as e:
#         logger.error(f"A general error occurred in /book-appointment: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")
    
# # --- ================================= ---
# # --- SCHEDULED TASK ENDPOINT (NEW)
# # --- ================================= ---

# @app.post("/tasks/send-reminders", dependencies=[Depends(verify_api_key)])
# async def trigger_send_reminders():
#     """
#     Secure endpoint to be called by a cron job (e.g., Railway Cron)
#     to trigger the sending of meeting reminders.
#     """
#     try:
#         logger.info("Task: /tasks/send-reminders endpoint triggered.")
#         # Call your scheduler function directly
#         send_meeting_reminders()
#         return {"status": "success", "message": "Reminder job executed."}
#     except Exception as e:
#         logger.error(f"Error in /tasks/send-reminders endpoint: {e}", exc_info=True)
#         # Return a 500 error so the cron job log shows a failure
#         raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")

# api/server.py
import asyncio
import logging
import datetime
import json

from fastapi import FastAPI, HTTPException, Depends, Header, status
from pydantic import BaseModel
from supabase.client import Client, create_client
from config.settings import settings
from agent.agent_factory import create_agent_executor
from langchain.memory import ConversationBufferMemory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, messages_from_dict, messages_to_dict
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Creator AI Bot API",
    description="API for the Creator AI assistant.",
    version="2.0.0"
)

# --- API Key Verification ---
async def verify_api_key(x_api_key: str = Header()):
    if not settings.API_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API Secret Key not configured on the server."
        )
    if x_api_key != settings.API_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key."
        )

# --- Central Supabase Client & Concurrency Locks ---
agent_semaphore = asyncio.Semaphore(settings.CONCURRENCY_LIMIT)
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
conversation_locks = defaultdict(asyncio.Lock)

# --- Chat History Class ---
class SupabaseChatMessageHistory(BaseChatMessageHistory):
    def __init__(self, session_id: str, table_name: str):
        self.session_id = session_id
        self.table_name = table_name

    @property
    def messages(self):
        """Retrieve and clean messages from Supabase."""
        response = supabase.table(self.table_name).select("history").eq("conversation_id", self.session_id).execute()
        
        if not response.data or not response.data[0].get('history'):
            return []

        history_data = response.data[0]['history']

        for message_data in history_data:
            if message_data.get("type") == "ai":
                ai_data = message_data.get("data", {})
                tool_calls = ai_data.get("tool_calls")
                if tool_calls and isinstance(tool_calls, list):
                    for tool_call in tool_calls:
                        if "args" in tool_call and isinstance(tool_call["args"], str):
                            try:
                                tool_call["args"] = json.loads(tool_call["args"])
                            except json.JSONDecodeError:
                                tool_call["args"] = {"query": tool_call["args"]}
        
        return messages_from_dict(history_data)

    def add_messages(self, messages: list[BaseMessage]) -> None:
        """Save messages to Supabase, correctly formatting tool calls."""
        current_history_dicts = messages_to_dict(self.messages)
        
        new_history_dicts = []
        for message in messages:
            message_dict = messages_to_dict([message])[0]
            if isinstance(message, AIMessage) and hasattr(message, 'tool_calls') and message.tool_calls:
                message_dict['data']['tool_calls'] = message.tool_calls
            new_history_dicts.append(message_dict)

        updated_history = current_history_dicts + new_history_dicts
        
        supabase.table(self.table_name).upsert({
            "conversation_id": self.session_id, 
            "history": updated_history,
            "status": "active"
        }).execute()

    def clear(self) -> None:
        supabase.table(self.table_name).delete().eq("conversation_id", self.session_id).execute()

# --- ======================================= ---
# --- CORE CHAT ENDPOINT
# --- ======================================= ---

class ChatRequest(BaseModel):
    conversation_id: str
    query: str

@app.post("/chat", dependencies=[Depends(verify_api_key)])
async def chat_with_agent(request: ChatRequest):
    lock = conversation_locks[request.conversation_id]

    async with lock:
        try:
            status_response = supabase.table("conversation_history").select("status").eq("conversation_id", request.conversation_id).execute()
            
            # Check for Handover Status
            if status_response.data and status_response.data[0].get('status') == 'handover':
                logger.info(f"Conversation {request.conversation_id} is in handover. Bypassing agent.")
                message_history = SupabaseChatMessageHistory(session_id=request.conversation_id, table_name=settings.DB_CONVERSATION_HISTORY_TABLE)
                message_history.add_messages([HumanMessage(content=request.query)])
                return {"response": "A human will be with you shortly. Thank you for your patience."}
        except Exception:
            pass
        
        async with agent_semaphore:
            try:
                message_history = SupabaseChatMessageHistory(
                    session_id=request.conversation_id,
                    table_name=settings.DB_CONVERSATION_HISTORY_TABLE
                )
                
                memory = ConversationBufferMemory(
                    memory_key="history",
                    chat_memory=message_history,
                    return_messages=True,
                    input_key="input"
                )

                agent_executor, tool_callback = create_agent_executor(memory, conversation_id=request.conversation_id)

                current_time = datetime.datetime.now().strftime('%A, %Y-%m-%d %H:%M:%S')

                agent_input = {
                    "input": request.query,
                    "current_time": current_time,
                    "conversation_id": request.conversation_id
                }
                
                response = await agent_executor.ainvoke(agent_input)
                agent_output = response.get("output")
                
                tool_calls = tool_callback.tool_calls
                ai_message = AIMessage(content=agent_output)
                if tool_calls:
                    ai_message.tool_calls = tool_calls

                if not agent_output or not agent_output.strip():
                    logger.warning(f"Agent for convo ID {request.conversation_id} generated an empty response.")
                    agent_output = "Oops, I lost my train of thought. What were we talking about? 😘"

                return {"response": agent_output}
            except Exception as e:
                logger.error(f"Error in /chat for conversation_id {request.conversation_id}: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")