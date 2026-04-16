# # tools/action_schemas.py
# from pydantic import BaseModel, Field, EmailStr
# from typing import Optional

# # --- Schemas for Agent Tools ---

# class CheckAvailabilityArgs(BaseModel):
#     """Schema for checking available time slots on a given date."""
#     date: str = Field(description="The date to check for available slots, in YYYY-MM-DD format.")

# class BookOnboardingCallArgs(BaseModel):
#     """Schema for booking an official onboarding call with the Zappies AI team (AGENT USE)."""
#     full_name: str = Field(description="The full name of the renovation company owner or decision-maker.")
#     email: EmailStr = Field(description="The business email address where the calendar invite should be sent.")
#     company_name: str = Field(description="The name of their renovation company.")
#     start_time: str = Field(description="The start time for the meeting in ISO 8601 format (e.g., '2023-10-27T09:00:00').")
#     goal: str = Field(description="The user's primary goal or what they hope to achieve with the 'Project Pipeline AI'.")
#     monthly_budget: float = Field(description="The user's approximate monthly budget in Rands for this type of solution.")
#     conversation_id: str = Field(description="The unique identifier for the current user's conversation session. This is ALWAYS available to you.")

# class CancelAppointmentArgs(BaseModel):
#     """Schema for canceling an existing onboarding call."""
#     email: EmailStr = Field(description="The email address used to book the original appointment.")
#     original_start_time: str = Field(description="The original start time of the appointment to be canceled, in ISO 8601 format.")

# class RescheduleAppointmentArgs(BaseModel):
#     """Schema for rescheduling an existing onboarding call."""
#     email: EmailStr = Field(description="The email address used to book the original appointment.")
#     original_start_time: str = Field(description="The original start time of the appointment to be rescheduled, in ISO 8601 format.")
#     new_start_time: str = Field(description="The new desired start time for the appointment, in ISO 8601 format.")

# class RequestHumanHandoverArgs(BaseModel):
#     """Schema for requesting a human handover."""
#     conversation_id: str = Field(description="The unique identifier for the current user's conversation session. This is ALWAYS available to you.")


# # --- Schemas for Voice Agent Endpoints ---

# class VoiceBookingRequest(BaseModel):
#     """
#     Schema for the /book-appointment endpoint (from voice agent).
#     Note: 'email' is Pydantic's EmailStr for validation.
#     """
#     name: str
#     email: EmailStr
#     start_time: str
#     goal: str = "Not provided"
#     monthly_budget: float = 0.0
#     company_name: str = "Not provided"
#     client_number: Optional[str] = None
#     call_duration_seconds: Optional[int] = 0

# class CallLogRequest(BaseModel):
#     """
#     Schema for the /log-call endpoint (from voice agent).
#     Logs calls that did *not* result in a meeting.
#     """
#     full_name: Optional[str] = "Not provided"
#     email: Optional[EmailStr] = None
#     company_name: Optional[str] = "Not provided"
#     goal: Optional[str] = "Not provided"
#     # --- CHANGED TO FLOAT ---
#     monthly_budget: Optional[float] = 0.0
#     # --- END CHANGE ---
#     resulted_in_meeting: bool = False
#     disqualification_reason: Optional[str] = None
#     client_number: Optional[str] = None
#     call_duration_seconds: Optional[int] = 0

from pydantic import BaseModel, Field
from typing import List, Optional

class CalculateCustomQuoteArgs(BaseModel):
    """Schema for calculating the price of a custom video request."""
    duration_minutes: int = Field(description="The requested length of the video in minutes.")
    addons: Optional[List[str]] = Field(default=[], description="A list of specific requests, outfits, or kinks.")

class RequestHumanHandoverArgs(BaseModel):
    """Schema for requesting a human handover when manual intervention is needed."""
    conversation_id: str = Field(description="The unique identifier for the current user's conversation session.")