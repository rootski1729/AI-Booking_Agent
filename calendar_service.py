import os
import pickle
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pytz
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class CalendarService:
    
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    def __init__(self):
        self.service = None
        self.credentials = None
        self.timezone = 'UTC'
        self._authenticate()
    
    def _authenticate(self):
        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    print("refreshed credentials successfully.")
                except Exception as e:
                    print(f"refresh failed: {e}")
                    creds = None
            
            if not creds:
                if not os.path.exists('credentials.json'):
                    raise FileNotFoundError(
                        "credentials.json not found!"
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', self.SCOPES
                )
                creds = flow.run_local_server(port=0)
                print("authentication successful.")
        
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
        
        self.service = build('calendar', 'v3', credentials=creds)
        self.credentials = creds
        
        try:
            calendar = self.service.calendars().get(calendarId='primary').execute()
            self.timezone = calendar.get('timeZone', 'UTC')
            print(f" connected to calendar - timezone: {self.timezone}")
        except Exception as e:
            print(f"could not get calendar info: {e}")
    
    def get_available_slots(self, start_date: datetime, days_ahead: int = 7, 
                        duration_minutes: int = 60) -> List[Dict[str, Any]]:
        
        if not self.service:
            raise Exception("google calendar service not initialized")
        
        try:
            end_date = start_date + timedelta(days=days_ahead)
            busy_times = self._get_busy_times(start_date, end_date)
            
            free_slots = self._calculate_free_slots(
                start_date, end_date, busy_times, duration_minutes
            )
            
            print(f"found {len(free_slots)} available slots")
            return free_slots
            
        except Exception as e:
            print(f"error getting availability: {e}")
            raise
    
    def _get_busy_times(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        time_min = start_date.isoformat() + 'Z'
        time_max = end_date.isoformat() + 'Z'
        
        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            busy_times = []
            
            for event in events:
                start = event['start'].get('dateTime')
                end = event['end'].get('dateTime')
                
                if start and end:
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00')).replace(tzinfo=None)
                    end_dt = datetime.fromisoformat(end.replace('Z', '+00:00')).replace(tzinfo=None)
                    
                    busy_times.append({
                        'start': start_dt,
                        'end': end_dt,
                        'summary': event.get('summary', 'Busy')
                    })
            
            print(f"found {len(busy_times)} existing events")
            return busy_times
            
        except HttpError as e:
            print(f"calendar API not working: {e}")
            raise
    
    def _calculate_free_slots(self, start_date: datetime, end_date: datetime, 
                            busy_times: List[Dict], duration_minutes: int) -> List[Dict[str, Any]]:
        
        free_slots = []
        working_hours = (8, 17)  # 8 AM to 5 PM
        
        current_date = start_date.replace(hour=working_hours[0], minute=0, second=0, microsecond=0)
        
        while current_date < end_date:
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                current_date = current_date.replace(hour=working_hours[0], minute=0)
                continue
            
            day_end = current_date.replace(hour=working_hours[1], minute=0)
            slot_start = current_date
            
            while slot_start + timedelta(minutes=duration_minutes) <= day_end:
                slot_end = slot_start + timedelta(minutes=duration_minutes)
                
                if slot_start <= datetime.now():
                    slot_start += timedelta(minutes=30)
                    continue
                is_free = True
                for busy in busy_times:
                    if (slot_start < busy['end'] and slot_end > busy['start']):
                        is_free = False
                        break
                
                if is_free:
                    free_slots.append({
                        'start':slot_start.isoformat() + 'Z',
                        'end':slot_end.isoformat() + 'Z',
                        'day':slot_start.strftime('%A'),
                        'date':slot_start.strftime('%Y-%m-%d'),
                        'time':slot_start.strftime('%I:%M %p'),
                        'duration': duration_minutes
                    })
                
                slot_start += timedelta(minutes=30)
            
            current_date += timedelta(days=1)
            current_date = current_date.replace(hour=working_hours[0], minute=0)
        
        return free_slots[:20]
    
    def create_event(self, event_details: Dict[str, Any]) -> Dict[str, Any]:
        
        if not self.service:
            raise Exception("calendar service not started")
        
        try:
            event = {
                'summary':event_details.get('summary', 'Meeting'),
                'description':event_details.get('description', 'Meeting scheduled via AI Booking Agent'),
                'start': {
                    'dateTime':event_details['start'],
                    'timeZone':self.timezone,
                },
                'end': {
                    'dateTime':event_details['end'],
                    'timeZone':self.timezone,
                },
                'reminders': {
                    'useDefault':True,
                },
            }
            
            if event_details.get('attendees'):
                event['attendees'] =[{'email': email} for email in event_details['attendees']]
                
            created_event =self.service.events().insert(
                calendarId='primary', 
                body=event
            ).execute()
            
            print(f"calendar event created: {created_event.get('htmlLink', 'No link')}")
            
            return {
                'id': created_event.get('id'),
                'summary': created_event.get('summary'),
                'start': created_event['start'].get('dateTime'),
                'end': created_event['end'].get('dateTime'),
                'status': created_event.get('status'),
                'htmlLink': created_event.get('htmlLink')
            }
            
        except HttpError as e:
            print(f"error creating event: {e}")
            raise Exception(f"failed to create calendar event: {e}")
    
    def get_calendar_info(self) -> Dict[str, Any]:  
        if not self.service:
            return {'status':'Not connected', 'authenticated': False}
        
        try:
            calendar = self.service.calendars().get(calendarId='primary').execute()
            return {
                'status':'Connected to Google Calendar',
                'authenticated': True,
                'calendar_name':calendar.get('summary', 'Primary Calendar'),
                'timezone':calendar.get('timeZone', 'UTC')
            }
        except Exception as e:
            return {'status': f'Error: {str(e)}', 'authenticated': False}

if __name__ == "__main__":
    print("testing Google Calendar Service")
    
    try:
        service = CalendarService()
        info = service.get_calendar_info()
        print(f"Calendar Info: {info}")
        
        start_date = datetime.now()
        slots = service.get_available_slots(start_date, days_ahead=3, duration_minutes=60)
        
        if slots:
            print("sample available slots:")
            for slot in slots[:3]:
                print(f"  - {slot['day']} {slot['time']}")
        else:
            print("no available slots found (this might be normal if calendar is busy)")
        
        print("Google Calendar service working correctly")
        
    except Exception as e:
        print(f"test failed: {e}")