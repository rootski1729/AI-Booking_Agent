from datetime import datetime, timedelta, timezone, UTC
from typing import Dict, List, Optional
import re
import pytz
from dateutil import parser

from calendar_service import CalendarService
from config import Config

class BookingAgent:
    def __init__(self):
        self.calendar_service=CalendarService()
        self.timezone=pytz.timezone(Config.TIMEZONE)
        self.current_slots=[]
        self.selected_slot=None
        self.booking_details={}
        
    def process_message(self, message:str, conversation_history:List[Dict]=None) -> Dict:
        history=conversation_history or []
        user_input=message.lower().strip()
        if self._is_slot_selection(message, history):
            return self._handle_slot_selection(message, history)
        elif self._is_confirmation(message, history):
            return self._handle_confirmation(message, history)
        elif self._is_availability_check(user_input):
            return self._check_availability(message, history)
        elif self._is_booking_request(user_input):
            return self._handle_booking(message, history)
        else:
            return self._handle_general(message, history)
    
    def _is_availability_check(self, message:str) -> bool:
        patterns=[
            r'(check|show|see|what|when).*(availability|available|free|time)',
            r'(availability|available|free).*(today|tomorrow|monday|tuesday|wednesday|thursday|friday)',
            r'(do you have|any).*(free time|available|open)',
            r'free time.*on',
            r'available.*on'
        ]
        return any(re.search(pattern, message, re.IGNORECASE) for pattern in patterns)
    
    def _is_booking_request(self, message:str) -> bool:
        patterns=[
            r'(schedule|book|set up|arrange).*(meeting|call|appointment)',
            r'(want to|need to|would like to).*(schedule|book|meet)',
            r'book.*meeting',
            r'schedule.*call',
            r'meeting.*between',
            r'call.*tomorrow'
        ]
        return any(re.search(pattern, message, re.IGNORECASE) for pattern in patterns)
    
    def _is_slot_selection(self, message:str, history:List[Dict]) -> bool:
        last_bot_message=""
        for msg in reversed(history[-3:]):
            if msg.get("role")=="assistant":
                last_bot_message=msg.get("content", "").lower()
                break
        if "reply with the number" in last_bot_message or "which slot" in last_bot_message:
            return bool(re.search(r'\b[1-9]\b', message))
        return False
    
    def _is_confirmation(self, message:str, history:List[Dict]) -> bool:
        last_bot_message=""
        for msg in reversed(history[-3:]):
            if msg.get("role")=="assistant":
                last_bot_message=msg.get("content", "").lower()
                break
        if "confirm" in last_bot_message or "say yes" in last_bot_message:
            return any(word in message.lower() for word in ["yes", "no", "confirm", "cancel"])
        return False
    
    def _check_availability(self, message:str, history:List[Dict]) -> Dict:
        date_str=self._extract_date(message)
        if not date_str:
            date_str="today"
        target_date=self._parse_date(date_str)
        if not target_date:
            return self._create_response(
                "I couldn't understand the date. can you specify (e.g., 'today', 'tomorrow', 'Friday')",
                history, message
            )

        current_time=self._get_current_time()
        if target_date.date() < current_time.date():
            return self._create_response(
                f"this is the past date!",
                history, message
            )
        
        if target_date.weekday() >=5:
            day_name=target_date.strftime("%A, %B %d")
            return self._create_response(
                f"It's a weekend free time! You don't have work slots for {day_name}. Enjoy your time off!",
                history, message
            )
        slots=self._get_available_slots(target_date)
        if not slots:
            return self._create_response(
                f"Your calendar is fully booked for {target_date.strftime('%A, %B %d')}. Would you like to try a different day?",
                history, message
            )
        day_name=target_date.strftime("%A, %B %d")
        response=f"Here's your availability for {day_name}:\n\n"
        
        morning_slots=[s for s in slots if s["start"].hour < 12]
        afternoon_slots=[s for s in slots if 12 <=s["start"].hour < 17]
        evening_slots=[s for s in slots if s["start"].hour >=17]
        
        if morning_slots:
            response +="Morning:\n"
            for slot in morning_slots:
                response +=f"  • {slot['start'].strftime('%I:%M %p')} - {slot['end'].strftime('%I:%M %p')}\n"
            response +="\n"
        
        if afternoon_slots:
            response +="Afternoon:\n"
            for slot in afternoon_slots:
                response +=f"  • {slot['start'].strftime('%I:%M %p')} - {slot['end'].strftime('%I:%M %p')}\n"
            response +="\n"
        
        if evening_slots:
            response +="Evening:\n"
            for slot in evening_slots:
                response +=f"  • {slot['start'].strftime('%I:%M %p')} - {slot['end'].strftime('%I:%M %p')}\n"
            response +="\n"
        
        response +="would you like to book any of these times?"
        
        return self._create_response(response, history, message)
    
    def _handle_booking(self, message:str, history:List[Dict]) -> Dict:
        details=self._extract_booking_details(message)
        if not details.get("date"):
            return self._create_response(
                "I'd be happy to help you schedule a meeting! What day would you like to meet? (e.g., 'tomorrow', 'Friday', 'next Monday')",
                history, message
            )
        if not details.get("time") and not details.get("time_period"):
            self.booking_details=details
            return self._create_response(
                f"Great! For {details['date']}, what time works best? (e.g., 'morning', '2 PM', 'between 3-5 PM')",
                history, message
            )
        target_date=self._parse_date(details["date"])
        if not target_date:
            return self._create_response(
                "i couldn't understand the date. Could you be more specific?",
                history, message
            )
        
        current_time=self._get_current_time()
        if target_date.date() < current_time.date():
            return self._create_response(
                "that date has already passed. Please choose a future date.",
                history, message
            )
        if target_date.weekday() >=5:
            day_name=target_date.strftime("%A, %B %d")
            return self._create_response(
                f"it's a weekend free time! You don't have work slots for {day_name}.How about choosing a weekday instead?",
                history, message
            )
        if target_date.date()==current_time.date() and current_time.hour >=18:
            return self._create_response(
                f"work day has ended for you! You don't have slots after 6:00 PM. Please choose tomorrow or another day.",
                history, message
            )
        if target_date.weekday() >=5:
            day_name=target_date.strftime("%A, %B %d")
            return self._create_response(
                f"It's a weekend free time! You don't have work slots for {day_name}.how about choosing a weekday instead?",
                history, message
            )
        if target_date.date()==current_time.date() and current_time.hour >=18:
            return self._create_response(
                f"work day has ended for you! You don't have slots after 6:00 PM. please choose tomorrow or another day.",
                history, message
            )
        start_time, end_time=self._get_time_range(target_date, details)
        if start_time <=current_time:
            start_time=current_time + timedelta(hours=1)
            start_time=start_time.replace(minute=0, second=0, microsecond=0)
        
        slots=self.calendar_service.find_available_slots(start_time, end_time, 60)
        
        if not slots:
            return self._create_response(
                f"no available slots found for {details['date']} {details.get('time_period', details.get('time', ''))}. Would you like to try a different time?",
                history, message
            )
        self.current_slots=slots
        self.booking_details=details

        day_name=target_date.strftime("%A, %B %d")
        response=f"I found available slots for {day_name}:\n\n"
        
        for i, slot in enumerate(slots[:5], 1):
            time_str=slot["start"].strftime("%I:%M %p")
            end_str=slot["end"].strftime("%I:%M %p")
            response +=f"{i}. {time_str} - {end_str}\n"
        
        response +=f"\n which slot works for you? Reply with the number (1-{min(len(slots), 5)})."
        
        return self._create_response(response, history, message)
    
    def _handle_slot_selection(self, message:str, history:List[Dict]) -> Dict:
        match=re.search(r'\b([1-9])\b', message)
        if not match:
            return self._create_response(
                "Please select a valid slot number.",
                history, message
            )
        
        slot_num=int(match.group(1))
        
        if not self.current_slots or slot_num > len(self.current_slots):
            return self._create_response(
                f"Please select a number between 1 and {len(self.current_slots) if self.current_slots else 1}.",
                history, message
            )
    
        self.selected_slot=self.current_slots[slot_num - 1]
        start_time=self.selected_slot["start"]
        end_time=self.selected_slot["end"]
        day_name=start_time.strftime("%A, %B %d")
        time_str=start_time.strftime("%I:%M %p")
        end_str=end_time.strftime("%I:%M %p")
        
        response=f"perfect! I'll book your meeting for:\n\n"
        response +=f"{day_name}\n"
        response +=f"{time_str} - {end_str}\n\n"
        response +="Should I confirm this booking? Say 'yes' to confirm."
        
        return self._create_response(response, history, message)
    
    def _handle_confirmation(self, message:str, history:List[Dict]) -> Dict:
        user_response=message.lower().strip()
        
        if any(word in user_response for word in ["yes", "confirm", "ok", "sure"]):
            if not self.selected_slot:
                return self._create_response(
                    "I don't have a slot selected. Please start over.",
                    history, message
                )
    
            event_id=self.calendar_service.create_event(
                title="Meeting",
                start_time=self.selected_slot["start"],
                end_time=self.selected_slot["end"],
                description="Scheduled via AI Booking Agent"
            )
            
            if event_id:
                start_time=self.selected_slot["start"]
                day_name=start_time.strftime("%A, %B %d")
                time_str=start_time.strftime("%I:%M %p")
                end_str=self.selected_slot["end"].strftime("%I:%M %p")
                
                response=f"Booking Confirmed!\n\n"
                response +=f"Your meeting is scheduled for:\n"
                response +=f"{day_name}\n"
                response +=f"{time_str} - {end_str}\n\n"
                response +="The meeting has been added to your calendar!"
                
                # Clear state
                self.current_slots=[]
                self.selected_slot=None
                self.booking_details={}
                
                return self._create_response(response, history, message, booking_confirmed=True)
            else:
                return self._create_response(
                    "There was an error creating the calendar event. Please try again.",
                    history, message
                )
        
        elif any(word in user_response for word in ["no", "cancel"]):
            self.current_slots=[]
            self.selected_slot=None
            self.booking_details={}
            
            return self._create_response(
                "No problem! The booking has been cancelled. Is there anything else I can help you with?",
                history, message
            )
        
        else:
            return self._create_response(
                "Please say 'yes' to confirm the booking or 'no' to cancel.",
                history, message
            )
    
    def _handle_general(self, message:str, history:List[Dict]) -> Dict:
        user_input=message.lower().strip()
        
        if any(word in user_input for word in ["hi", "hello", "hey"]):
            response="Hello! I'm your booking assistant. I can help you:\n\n"
            response +="Check your availability for any day\n"
            response +="Schedule meetings and calls\n"
            response +="Book time slots in your calendar\n\n"
            response +="What would you like to do?"
        

        elif any(word in user_input for word in ["help", "what can you do"]):
            response="I can help you with:\n\n"
            response +="check availability:'What's my availability for Friday?'\n"
            response +="schedule meetings:'Book a meeting tomorrow afternoon'\n"
            response +="schedule calls:'Schedule a call for next Monday morning'\n\n"
            response +="Just tell me what you need!"

        else:
            response="I'm here to help you schedule meetings and check availability. You can say:\n\n"
            response +="• 'Check my availability for tomorrow'\n"
            response +="• 'Schedule a meeting Friday afternoon'\n"
            response +="• 'Book a call for next week'\n\n"
            response +="What would you like to do?"
        
        return self._create_response(response, history, message)
    
    def _extract_date(self, message:str) -> Optional[str]:
        text=message.lower()
        
        if "today" in text:
            return "today"
        elif "tomorrow" in text:
            return "tomorrow"
        
        days=["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day in days:
            if day in text:
                if "next" in text:
                    return f"next {day}"
                return day
            
        date_patterns=[
            r'\b(\d{1,2})/(\d{1,2})\b',
            r'\b(\d{1,2})-(\d{1,2})\b',
            r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})\b'
        ]
        
        for pattern in date_patterns:
            match=re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return None
    
    def _extract_booking_details(self, message:str) -> Dict:
        details={}
        text=message.lower()
        
        date_str=self._extract_date(message)
        if date_str:
            details["date"]=date_str
        
        if "morning" in text:
            details["time_period"]="morning"
        elif "afternoon" in text:
            details["time_period"]="afternoon"
        elif "evening" in text:
            details["time_period"]="evening"


        time_match=re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)', text)
        if time_match:
            details["time"]=time_match.group(0)

        range_match=re.search(r'between\s+(\d{1,2})\s*-?\s*(\d{1,2})', text)
        if range_match:
            details["time_range"]=(int(range_match.group(1)), int(range_match.group(2)))
        
        return details
    
    def _parse_date(self, date_str:str) -> Optional[datetime]:
        if not date_str:
            return None
        
        current_time=self._get_current_time()
        date_str=date_str.lower().strip()
        
        try:
            if date_str=="today":
                return current_time
            elif date_str=="tomorrow":
                return current_time + timedelta(days=1)
            days=["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            for i, day in enumerate(days):
                if day in date_str:
                    days_ahead=(i - current_time.weekday()) % 7
                    if days_ahead==0:
                        days_ahead=7 if "next" in date_str else 0
                    elif "next" in date_str:
                        days_ahead +=7
                    
                    return current_time + timedelta(days=days_ahead)
            parsed=parser.parse(date_str, default=current_time)
            return parsed
            
        except:
            return None
    
    def _get_time_range(self, target_date:datetime, details:Dict) -> tuple:
        if details.get("time_range"):
            start_hour, end_hour=details["time_range"]
            end_hour=min(end_hour, 18)
            start_time=target_date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            end_time=target_date.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        elif details.get("time_period")=="morning":
            start_time=target_date.replace(hour=9, minute=0, second=0, microsecond=0)
            end_time=target_date.replace(hour=12, minute=0, second=0, microsecond=0)
        elif details.get("time_period")=="afternoon":
            start_time=target_date.replace(hour=13, minute=0, second=0, microsecond=0)
            end_time=target_date.replace(hour=17, minute=0, second=0, microsecond=0)
        elif details.get("time_period")=="evening":
            start_time=target_date.replace(hour=17, minute=0, second=0, microsecond=0)
            end_time=target_date.replace(hour=18, minute=0, second=0, microsecond=0)  
        elif details.get("time"):
            try:
                time_obj=parser.parse(details["time"])
                hour=min(time_obj.hour, 17) 
                start_time=target_date.replace(hour=hour, minute=time_obj.minute, second=0, microsecond=0)
                end_time=start_time + timedelta(hours=1)
                if end_time.hour > 18:
                    end_time=target_date.replace(hour=18, minute=0, second=0, microsecond=0)
            except:
                start_time=target_date.replace(hour=9, minute=0, second=0, microsecond=0)
                end_time=target_date.replace(hour=18, minute=0, second=0, microsecond=0)
        else:
            start_time=target_date.replace(hour=9, minute=0, second=0, microsecond=0)
            end_time=target_date.replace(hour=18, minute=0, second=0, microsecond=0)
        
        return start_time, end_time
    
    def _get_available_slots(self, target_date:datetime) -> List[Dict]:
        if target_date.weekday() >=5:
            return []
        
        start_time=target_date.replace(hour=9, minute=0, second=0, microsecond=0)
        end_time=target_date.replace(hour=18, minute=0, second=0, microsecond=0)
        current_time=self._get_current_time()
        if start_time <=current_time:
            start_time=current_time + timedelta(hours=1)
            start_time=start_time.replace(minute=0, second=0, microsecond=0)
        if target_date.date()==current_time.date() and current_time.hour >=18:
            return []
        
        return self.calendar_service.find_available_slots(start_time, end_time, 60)
    
    def _get_current_time(self) -> datetime:
        try:
            utc_now=datetime.now(UTC)
            ist_time=utc_now.astimezone(self.timezone)
            return ist_time.replace(tzinfo=None)
        except:
            return datetime.now()
    
    def _create_response(self, response:str, history:List[Dict], user_message:str, booking_confirmed:bool=False) -> Dict:
        updated_history=history + [
            {"role":"user", "content":user_message},
            {"role":"assistant", "content":response}
        ]
        
        return {
            "response":response,
            "state":{"messages":updated_history},
            "booking_confirmed":booking_confirmed
        }