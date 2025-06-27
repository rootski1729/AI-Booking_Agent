import os
import pickle
from datetime import datetime, timedelta, UTC
from typing import List, Dict, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pytz
from config import Config

class CalendarService:
    SCOPES=['https://www.googleapis.com/auth/calendar']
    
    def __init__(self):
        self.service=None
        self.timezone=pytz.timezone(Config.TIMEZONE)
        self._authenticate()
    
    def _authenticate(self):
        creds=None
        if os.path.exists(Config.GOOGLE_CALENDAR_TOKEN_FILE):
            with open(Config.GOOGLE_CALENDAR_TOKEN_FILE, 'rb') as token:
                creds=pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(Config.GOOGLE_CALENDAR_CREDENTIALS_FILE):
                    raise FileNotFoundError(
                        f"calendar credentials file not found:{Config.GOOGLE_CALENDAR_CREDENTIALS_FILE}"
                    )
                flow=InstalledAppFlow.from_client_secrets_file(
                    Config.GOOGLE_CALENDAR_CREDENTIALS_FILE, self.SCOPES
                )
                creds=flow.run_local_server(port=0)
            with open(Config.GOOGLE_CALENDAR_TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service=build('calendar', 'v3', credentials=creds)
    
    def get_free_busy(self, start_time:datetime, end_time:datetime) -> List[Dict]:
        try:
            if start_time.tzinfo is None:
                ist_tz=pytz.timezone(Config.TIMEZONE)
                start_time=ist_tz.localize(start_time).astimezone(pytz.UTC)
            if end_time.tzinfo is None:
                ist_tz=pytz.timezone(Config.TIMEZONE)
                end_time=ist_tz.localize(end_time).astimezone(pytz.UTC)
            
            body={
                'timeMin':start_time.isoformat(),
                'timeMax':end_time.isoformat(),
                'timeZone':'UTC',
                'items':[{'id':'primary'}]
            }
            freebusy=self.service.freebusy().query(body=body).execute()
            busy_times=freebusy['calendars']['primary'].get('busy', [])
            return busy_times
        except HttpError as error:
            print(f"error getting free/busy info:{error}")
            return []
    
    def find_available_slots(self, start_date:datetime, end_date:datetime, 
                        duration_minutes:int=60) -> List[Dict]:
        ist_tz=pytz.timezone(Config.TIMEZONE)
        current_time_utc=datetime.now(UTC)
        current_time_ist=current_time_utc.astimezone(ist_tz).replace(tzinfo=None)
    
        if start_date <=current_time_ist:
            start_date=current_time_ist + timedelta(hours=1)
            start_date=start_date.replace(minute=0, second=0, microsecond=0)
        
        print(f"[CALENDAR] checking slots from {start_date} to {end_date}")
    
        busy_times=self.get_free_busy(start_date, end_date)
        print(f"[CALENDAR] found {len(busy_times)} busy periods")
        
        available_slots=[]
        busy_periods=[]
        for busy in busy_times:
            try:
                start_str=busy['start']
                end_str=busy['end']
                if isinstance(start_str, dict):
                    start_str=start_str.get('dateTime', start_str.get('date', ''))
                    end_str=end_str.get('dateTime', end_str.get('date', ''))
                if 'T' in start_str:
                    start=datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                    end=datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                    if start.tzinfo:
                        start_ist=start.astimezone(ist_tz).replace(tzinfo=None)
                        end_ist=end.astimezone(ist_tz).replace(tzinfo=None)
                    else:
                        start_ist=start
                        end_ist=end
                else:
                    start_ist=datetime.fromisoformat(start_str)
                    end_ist=datetime.fromisoformat(end_str)
                
                busy_periods.append((start_ist, end_ist))
                print(f"[CALENDAR] busy:{start_ist} to {end_ist}")
                
            except Exception as e:
                print(f"[CALENDAR] error parsing busy time:{e}")
                continue
        
        busy_periods.sort(key=lambda x:x[0])
        current_time=start_date
        duration=timedelta(minutes=duration_minutes)
        
        while current_time + duration <=end_date:
            slot_end=current_time + duration
            is_available=True
            for busy_start, busy_end in busy_periods:
                if (current_time < busy_end and slot_end > busy_start):
                    is_available=False
                    print(f"[CALENDAR] slot {current_time} conflicts with busy period {busy_start}-{busy_end}")
                    break
            
            if is_available:
                if (Config.BUSINESS_HOURS_START <=current_time.hour < Config.BUSINESS_HOURS_END and 
                    current_time > current_time_ist + timedelta(minutes=15) and
                    current_time.weekday() < 5 and
                    not (12 <=current_time.hour < 14)):
                    
                    available_slots.append({
                        'start':current_time,
                        'end':slot_end,
                        'start_str':current_time.strftime(Config.DATETIME_FORMAT),
                        'end_str':slot_end.strftime(Config.DATETIME_FORMAT)
                    })
                    print(f"[CALENDAR] available slot:{current_time} to {slot_end}")
            
            current_time +=timedelta(hours=1)
        
        print(f"[CALENDAR] returning {len(available_slots)} available slots")
        return available_slots
    
    def create_event(self, title:str, start_time:datetime, end_time:datetime, 
                    description:str="", attendees:List[str]=None) -> Optional[str]:

        try:
            if start_time.tzinfo is None:
                ist_tz=pytz.timezone(Config.TIMEZONE)
                start_time=ist_tz.localize(start_time)
            if end_time.tzinfo is None:
                ist_tz=pytz.timezone(Config.TIMEZONE)
                end_time=ist_tz.localize(end_time)
            
            event={
                'summary':title,
                'description':description,
                'start':{
                    'dateTime':start_time.isoformat(),
                    'timeZone':Config.TIMEZONE,
                },
                'end':{
                    'dateTime':end_time.isoformat(),
                    'timeZone':Config.TIMEZONE,
                },
            }
            
            if attendees:
                event['attendees']=[{'email':email} for email in attendees]
            
            event=self.service.events().insert(
                calendarId=Config.CALENDAR_ID, body=event
            ).execute()
            
            return event.get('id')
        except HttpError as error:
            print(f"Error creating event:{error}")
            return None
    
    def get_events_for_day(self, date:datetime) -> List[Dict]:
        try:
            if date.tzinfo is None:
                ist_tz=pytz.timezone(Config.TIMEZONE)
                date=ist_tz.localize(date)
            
            start_of_day=date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day=date.replace(hour=23, minute=59, second=59, microsecond=999999)
            events_result=self.service.events().list(
                calendarId=Config.CALENDAR_ID,
                timeMin=start_of_day.isoformat(),
                timeMax=end_of_day.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events=events_result.get('items', [])
            return events
        except HttpError as error:
            print(f"Error getting events:{error}")
            return []