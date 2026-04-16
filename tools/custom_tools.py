# # tools/custom_tools.py
# from config.settings import settings
# from supabase.client import Client, create_client
# import logging
# import json
# from langchain.tools import StructuredTool
# from langchain_core.tools import Tool
# from pydantic import ValidationError
# from .action_schemas import (
#     BookOnboardingCallArgs,
#     CheckAvailabilityArgs,
#     CancelAppointmentArgs,
#     RescheduleAppointmentArgs,
#     RequestHumanHandoverArgs
# )
# from .google_calendar import (
#     get_available_slots,
#     create_calendar_event,
#     find_event_by_details,
#     update_calendar_event,
#     delete_calendar_event
# )
# from .email_sender import send_confirmation_email
# import datetime
# from dateutil.parser import parse 

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # Use the schema to define the input type correctly for LangChain
# def check_availability(date: str) -> str: # <--- FIX 1: Match the schema argument name 'date'
#     """Checks availability for a given date and returns a concise summary."""
#     logger.info(f"--- ACTION: Checking availability for date: {date} ---") # Log the correct variable
#     try:
#         date_to_check = date # <--- FIX 2: Use the 'date' argument directly, remove JSON parsing

#         # Validate date format before passing to get_available_slots
#         try:
#             datetime.datetime.fromisoformat(date_to_check)
#         except ValueError:
#             logger.warning(f"Invalid date format received by check_availability: {date_to_check}")
#             return f"I couldn't check availability because '{date_to_check}' doesn't look like a valid date in YYYY-MM-DD format."

#         # Fetch all available slots (still gets the full list internally)
#         available_slots_iso = get_available_slots(date_to_check)
#         logger.info(f"Raw available slots found: {available_slots_iso}")

#         if not available_slots_iso:
#             return f"I'm sorry, but there are no available 1-hour slots on {date_to_check}. Please suggest another date."

#         # --- CONCISE RESPONSE LOGIC ---
#         # Format only the first few slots for the user
#         suggestions_count = 5 # Show up to 5 suggestions
#         formatted_slots = []
#         hourly_slots_added = set() # Keep track of hours already added

#         for slot_iso in available_slots_iso:
#              if len(formatted_slots) >= suggestions_count:
#                  break
#              try:
#                  slot_dt = parse(slot_iso).astimezone(SAST_TZ)
#                  # Only add the top of the hour if not already added
#                  if slot_dt.minute == 0 and slot_dt.hour not in hourly_slots_added:
#                      # Format like "10:00 AM"
#                      formatted_time = slot_dt.strftime('%I:%M %p').lstrip('0') # Use %I, remove leading 0
#                      formatted_slots.append(formatted_time)
#                      hourly_slots_added.add(slot_dt.hour)
#                  # Optionally add half-hour slots if needed, e.g., if slot_dt.minute == 30: ...

#              except Exception as e:
#                  logger.error(f"Error parsing/formatting slot '{slot_iso}': {e}")
#                  continue # Skip problematic slots

#         if not formatted_slots:
#              # This might happen if only non-hourly slots were found within the limit
#              return f"Yes, there are slots available on {date_to_check}. You can ask the user to pick a specific time or suggest one like 9:00 AM."

#         # Construct the final response string
#         slots_str = ", ".join(formatted_slots)
#         response = f"Okay, I found some available times on {date_to_check}. The first few available start times are: {slots_str}. Let me know which one works best, or suggest another time."
#         return response

#     except Exception as e:
#         logger.error(f"Unexpected error in check_availability for '{date_input}': {e}", exc_info=True)
#         return "I encountered an error trying to check the availability. Please try again."

# def book_zappies_onboarding_call_from_json(json_string: str) -> str:
#     logger.info(f"--- ACTION: Booking Zappies AI Onboarding Call ---")
#     try:
#         data = json.loads(json_string)
#         validated_args = BookOnboardingCallArgs(**data)
#     except (json.JSONDecodeError, ValidationError) as e:
#         return f"I'm sorry, there was a problem with the booking details. Error: {e}"
#     # Check budget threshold
#     MINIMUM_BUDGET = 8000.0 # Define minimum budget clearly
#     if validated_args.monthly_budget < MINIMUM_BUDGET:
#         logger.info(f"Booking attempt disqualified for budget below {MINIMUM_BUDGET}. Provided: {validated_args.monthly_budget}")
#         # Return the polite disqualification message directly
#         disqualification_message = (
#             f"Okay, thank you for sharing that. Based on the R{validated_args.monthly_budget:.0f}/month budget provided, "
#             "it seems our 'Project Pipeline AI' might not be the best fit right now, as it's designed for businesses "
#             f"with budgets typically starting around R{MINIMUM_BUDGET:.0f}/month for this type of automation. "
#             "I really appreciate your time and honesty!"
#         )
#         return disqualification_message # Return the message directly

#     # Deconstruct the validated arguments
#     full_name = validated_args.full_name
#     email = validated_args.email
#     company_name = validated_args.company_name
#     start_time = validated_args.start_time
#     goal = validated_args.goal
#     monthly_budget = validated_args.monthly_budget
#     conversation_id = validated_args.conversation_id 

#     summary = f"Onboard Call with {company_name} | Zappies AI"
#     description = (
#         f"Onboarding call with {full_name} from {company_name} to discuss the 'Project Pipeline AI'.\n\n"
#         f"Stated Goal: {goal}\n"
#         f"Stated Budget: R{monthly_budget}/month"
#     )
    
#     try:
        
#         supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        
#         # Insert the meeting details into Supabase without a calendar event ID
#         response = supabase.table("meetings").insert({
#             # "google_calendar_event_id" is now omitted
#             "full_name": full_name,
#             "email": email,
#             "company_name": company_name,
#             "start_time": start_time,
#             "goal": goal,
#             "monthly_budget": monthly_budget,
#             "status": "pending_confirmation"
#         }).execute()
        
#         meeting_id = response.data[0]['id']

#         try:
#             supabase.table("conversation_history").update(
#                 {"meeting_booked": True}
#             ).eq("conversation_id", conversation_id).execute()
#             logger.info(f"Successfully marked conversation {conversation_id} as 'meeting_booked = true'.")
#         except Exception as e:
#             # Log this error, but don't stop the user-facing process
#             logger.error(f"Error updating conversation_history for {conversation_id}: {e}", exc_info=True)

#         send_confirmation_email(
#             recipient_email=email,
#             full_name=full_name,
#             start_time=start_time,
#             meeting_id=meeting_id
#         )

#         return (f"Excellent, {full_name}! I've provisionally booked your onboarding call. "
#                 "I've just sent you an email to confirm your spot. Please click the link in the email to finalize everything. ✨")
#     except (ValueError, Exception) as e:
#         logger.error(f"Booking/validation error: {e}", exc_info=True)
#         return f"I'm sorry, I cannot book that appointment. {e}"

# # tools/custom_tools.py

# def request_human_handover(json_string: str) -> str:
#     """Handles the human handover process."""
#     logger.info(f"--- ACTION: Requesting Human Handover ---")
#     try:
#         data = json.loads(json_string)
#         conversation_id = data["conversation_id"]
#     except (json.JSONDecodeError, KeyError) as e:
#         return f"Sorry, there was an internal error processing the handover request. Error: {e}"

#     try:
#         supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

#         # --- THIS IS THE FIX ---
#         # 1. Fetch the conversation history without using .single()
#         response = supabase.table("conversation_history").select("history").eq("conversation_id", conversation_id).execute()
        
#         history_messages = []
#         if response.data and response.data[0].get('history'):
#             from langchain_core.messages import messages_from_dict
#             history_messages = messages_from_dict(response.data[0]['history'])
#         else:
#             logger.warning(f"No previous history found for conversation {conversation_id}. Handover will proceed with an empty history.")

#         # 2. Send the notification email
#         send_handover_email(conversation_id, history_messages)

#         # 3. Update the conversation status. Use upsert to create the record if it doesn't exist.
#         supabase.table("conversation_history").upsert({
#             "conversation_id": conversation_id,
#             "status": "handover"
#         }).execute()
        
#         return "Okay, I've notified a member of our team. They will review our conversation and get back to you here as soon as possible."

#     except Exception as e:
#         logger.error(f"Error during handover for convo {conversation_id}: {e}", exc_info=True)
#         return "Sorry, I encountered an error while trying to reach a human. Please try again."

# def cancel_appointment_from_json(json_string: str) -> str:
#     """Cancels an appointment from a JSON string."""
#     logger.info(f"--- ACTION: Canceling appointment from JSON ---")
#     try:
#         data = json.loads(json_string)
#         validated_args = CancelAppointmentArgs(**data)
#     except (json.JSONDecodeError, ValidationError) as e:
#         return f"Sorry, the details provided for cancellation were not valid. Error: {e}"

#     email = validated_args.email
#     original_start_time = validated_args.original_start_time
    
#     event_id = find_event_by_details(email, original_start_time)
#     if not event_id:
#         return f"I couldn't find an appointment for {email} at that time. Please check the details."
#     try:
#         delete_calendar_event(event_id)
#         return "Your appointment has been successfully canceled."
#     except Exception as e:
#         logger.error(f"Error canceling event: {e}", exc_info=True)
#         return f"Sorry, there was an error canceling your appointment: {str(e)}"

# def reschedule_appointment_from_json(json_string: str) -> str:
#     """Reschedules an appointment from a JSON string."""
#     logger.info(f"--- ACTION: Rescheduling appointment from JSON ---")
#     try:
#         data = json.loads(json_string)
#         validated_args = RescheduleAppointmentArgs(**data)
#     except (json.JSONDecodeError, ValidationError) as e:
#         return f"Sorry, the details provided for rescheduling were not valid. Error: {e}"

#     email = validated_args.email
#     original_start_time = validated_args.original_start_time
#     new_start_time = validated_args.new_start_time

#     event_id = find_event_by_details(email, original_start_time)
#     if not event_id:
#         return f"I couldn't find an appointment for {email} at the original time. Please check the details."
#     try:
#         update_calendar_event(event_id, new_start_time)
#         return f"Your appointment has been successfully rescheduled to {new_start_time}."
#     except Exception as e:
#         logger.error(f"Error rescheduling event: {e}", exc_info=True)
#         return f"Sorry, there was an error rescheduling your appointment: {str(e)}"

# def get_custom_tools() -> list:
#     """Returns a list of all custom tools available to the agent."""
#     tools = [
#         StructuredTool(
#             name="check_availability",
#             func=check_availability,
#             args_schema=CheckAvailabilityArgs,
#             description="Use to check for available 1-hour time slots on a specific date (YYYY-MM-DD)."
#         ),
#         Tool(
#             name="book_zappies_onboarding_call",
#             func=book_zappies_onboarding_call_from_json,
#             description=(
#                 "Use to book a NEW onboarding call after you have collected all required information. The input must be a single, "
#                 "valid JSON string with keys: 'full_name', 'email', 'company_name', 'start_time', 'goal', and 'monthly_budget'."
#             )
#         ),
#         Tool(
#             name="cancel_appointment",
#             func=cancel_appointment_from_json,
#             description=(
#                 "Use to cancel an existing appointment. The input must be a single, valid JSON string with keys: "
#                 "'email' and 'original_start_time'."
#             )
#         ),
#         Tool(
#             name="reschedule_appointment",
#             func=reschedule_appointment_from_json,
#             description=(
#                 "Use to reschedule an existing appointment. The input must be a single, valid JSON string with keys: "
#                 "'email', 'original_start_time', and 'new_start_time'."
#             )
#         ),
#         Tool(
#             name="request_human_handover",
#             func=request_human_handover,
#             description=(
#                 "Use this tool when the user explicitly asks to speak to a human, a person, or a team member. "
#                 "The input MUST be a single, valid JSON string with the key: 'conversation_id'."
#             )
#         )
#     ]
#     return tools

# tools/custom_tools.py
import logging
import json
from langchain_core.tools import Tool
from pydantic import ValidationError
from supabase.client import Client, create_client
from config.settings import settings
from .action_schemas import CalculateCustomQuoteArgs, RequestHumanHandoverArgs

logger = logging.getLogger(__name__)

def calculate_custom_quote(json_string: str) -> str:
    """Calculates the price for a custom video based on creator rules."""
    logger.info(f"--- ACTION: Calculating Custom Quote ---")
    try:
        data = json.loads(json_string)
        validated_args = CalculateCustomQuoteArgs(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        return f"I need to know how many minutes you want and if there are any special requests to give you a price!"

    # Creator Business Logic
    BASE_RATE_PER_MINUTE = 10
    MINIMUM_MINUTES = 3
    ADDON_FLAT_FEE = 20

    minutes = validated_args.duration_minutes
    addons = validated_args.addons

    if minutes < MINIMUM_MINUTES:
        return f"My custom videos have a minimum length of {MINIMUM_MINUTES} minutes, babe! Let me know if you want to bump it up to {MINIMUM_MINUTES}."

    total_price = minutes * BASE_RATE_PER_MINUTE

    # If there are specific requests, apply the flat fee surcharge
    if addons and len(addons) > 0:
        total_price += ADDON_FLAT_FEE
        addon_text = ", ".join(addons)
        return f"For a {minutes}-minute video including your special requests ({addon_text}), the total would be ${total_price}. Should I set that up for you?"
    else:
        return f"For a {minutes}-minute custom video, it would be exactly ${total_price}. Does that sound good to you?"

def request_human_handover(json_string: str) -> str:
    """Handles the human handover process and sets the DB status."""
    logger.info(f"--- ACTION: Requesting Human Handover ---")
    try:
        data = json.loads(json_string)
        conversation_id = data["conversation_id"]
    except (json.JSONDecodeError, KeyError) as e:
        return f"Sorry, there was an internal error processing the handover request. Error: {e}"

    try:
        supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

        # Update the conversation status to 'handover' so the bot stops responding
        supabase.table("conversation_history").upsert({
            "conversation_id": conversation_id,
            "status": "handover"
        }).execute()
        
        # Persona-matched response
        return "Okay, I'm going to grab the real me to take over this chat! Give me just a little bit to reply personally. 💕"

    except Exception as e:
        logger.error(f"Error during handover for convo {conversation_id}: {e}", exc_info=True)
        return "Sorry babe, my system is acting up a little. Let me try again later!"

def get_custom_tools() -> list:
    """Returns a list of all custom tools available to the agent."""
    tools = [
        Tool(
            name="calculate_custom_quote",
            func=calculate_custom_quote,
            description=(
                "Use this tool to calculate the price of a custom video when a user tells you "
                "how many minutes they want. Input must be a valid JSON string with 'duration_minutes' "
                "and an optional 'addons' list."
            )
        ),
        Tool(
            name="request_human_handover",
            func=request_human_handover, 
            description=(
                "Use when the user explicitly asks to speak to the real creator or requires complex manual negotiation. "
                "Input MUST be a single, valid JSON string with the key: 'conversation_id'."
            )
        )
    ]
    return tools