import os
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from dotenv import load_dotenv
load_dotenv()


from langgraph.graph import StateGraph, END
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from typing_extensions import Annotated, TypedDict

from calendar_service import CalendarService
from dateutil import parser

calendar_service = CalendarService()
openai_key = os.getenv('OPENAI_API_KEY')
if not openai_key:
    raise ValueError("OpenAI Key not found")

llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.3, api_key=openai_key)

@asynccontextmanager
async def lifespan(app: FastAPI):
    calendar_info=calendar_service.get_calendar_info()
    if calendar_info.get("authenticated"):
        print(f"google calendar connected: {calendar_info.get('calendar_name', 'Unknown')}")
    else:
        print(f"connection failed with calendar: {calendar_info.get('status', 'Unknown')}")
    
    print("reday for requests")
    
    yield
    print("shutting down app")

# FastAPI 
app = FastAPI(
    title="AI Booking Agent API",
    description="booking agent api",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    message: str= Field(..., description="User message")
    session_id: str= Field(default="default", description="Session ID")

class ChatResponse(BaseModel):
    response: str =Field(..., description="AI response")
    session_id: str= Field(..., description="Session ID")
    state: str=Field(..., description="Conversation state")
    suggestions:List[str] = Field(default=[], description="Quick suggestions")
    booking_details:Optional[Dict[str, Any]] = Field(default=None)

class ConversationState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    session_id: str
    current_intent: str
    proposed_datetime: Optional[str]
    duration: int
    meeting_title: Optional[str]
    available_slots: List[Dict[str, Any]]
    selected_slot: Optional[Dict[str, Any]]
    booking_confirmed: bool
    user_preferences: Dict[str, Any]

class BookingAgent:
    def __init__(self):
        self.sessions = {}
        self.graph = self._create_conversation_graph()
    def _create_conversation_graph(self):
        workflow = StateGraph(ConversationState)
        
        workflow.add_node("understand_intent",self._understand_intent)
        workflow.add_node("check_availability", self._check_availability)
        workflow.add_node("suggest_times",self._suggest_times)
        workflow.add_node("confirm_booking",self._confirm_booking)
        workflow.add_node("complete_booking",self._complete_booking)
        workflow.add_node("handle_modification",self._handle_modification)
        
        
        workflow.set_entry_point("understand_intent")
        
        workflow.add_conditional_edges(
            "understand_intent",
            self._route_conversation,
            {
                "availability_check":"check_availability",
                "booking_request":"check_availability",
                "confirmation":"confirm_booking",
                "modification":"handle_modification",
                "greeting":"suggest_times"
            }
        )
        
        workflow.add_edge("check_availability","suggest_times")
        workflow.add_edge("suggest_times",END)
        workflow.add_edge("handle_modification","check_availability")
        workflow.add_edge("confirm_booking","complete_booking")
        workflow.add_edge("complete_booking",END)
        
        return workflow.compile()
    
    def _understand_intent(self, state: ConversationState) -> ConversationState:
        last_message =state["messages"][-1].content
        
        intent_prompt =ChatPromptTemplate.from_messages([
            ("system", """Classify the user's intent. Respond with just one word:
            - "greeting" for hello, hi, help
            - "availability_check" for "do you have time", "when are you free"
            - "booking_request" for "schedule", "book", "meeting at specific time"
            - "confirmation" for "yes", "that works", "confirmed"
            
            User message: {message}
            Intent:"""),
            ("human", last_message)
        ])
        
        try:
            response=llm.invoke(intent_prompt.format_messages(message=last_message))
            intent=response.content.strip().lower()
            
            if "tomorrow" in last_message.lower():
                state["proposed_datetime"] ="tomorrow"
            elif "friday" in last_message.lower():
                state["proposed_datetime"]="friday"
            
            if "client" in last_message.lower():
                state["meeting_title"]="Client Meeting"
            elif "call" in last_message.lower():
                state["meeting_title"]="Call"
            else:
                state["meeting_title"]="Meeting"
            
            if "30" in last_message:
                state["duration"]=30
            else:
                state["duration"]=60
            
            state["current_intent"]=intent
            
        except Exception as e:
            print(f"Intent error: {e}")
            state["current_intent"] ="greeting"
        
        return state
    
    def _route_conversation(self, state: ConversationState) -> str:
        return state.get("current_intent", "greeting")
    
    def _check_availability(self, state: ConversationState) -> ConversationState:
        target_date=datetime.now() + timedelta(days=1) 
        if state.get("proposed_datetime"):
            target_date=self._parse_datetime(state["proposed_datetime"])
        
        slots=calendar_service.get_available_slots(
            start_date=target_date,
            days_ahead=7,
            duration_minutes=state.get("duration", 60)
        )
        state["available_slots"] = slots
        return state
    
    def _suggest_times(self, state: ConversationState) -> ConversationState:
        slots=state.get("available_slots", [])
        intent=state.get("current_intent", "greeting")
        
        # Default response
        if intent=="greeting":
            response="""Hi! I'm your AI booking assistant connected to your Google Calendar. 
            I can help you:
            • Schedule meetings and appointments
            • Check your availability  
            • Book calls and presentations
            What would you like to do?"""
        
        elif not slots:
            response ="i couldn't find any available slots for that time. Would you like to try a different day or time?"
        
        else:
            response ="I+i found some available times for you:\n"
            for i, slot in enumerate(slots[:3], 1):
                start_time=datetime.fromisoformat(slot['start'].replace('Z', '+00:00'))
                response +=f"{i}. {slot['day']} at {slot['time']}\n"
            
            response += "\nwhich time works best for you?"
        

        state["messages"].append(AIMessage(content=response))
        return state
    
    def _confirm_booking(self, state: ConversationState) -> ConversationState:
        
        last_message = state["messages"][-1].content.lower()
        if any(word in last_message for word in ['yes', 'that works', 'confirmed', 'book it', '1', 'first']):
            state["booking_confirmed"]=True
            if state.get("available_slots"):
                state["selected_slot"]=state["available_slots"][0]
        else:
            state["booking_confirmed"]=False
        
        return state
    
    def _complete_booking(self, state: ConversationState) -> ConversationState:
        
        if not state.get("booking_confirmed"):
            return state
        
        selected_slot = state.get("selected_slot")
        if selected_slot:
            event_details = {
                'summary':state.get("meeting_title", "Meeting"),
                'start':selected_slot['start'],
                'end':selected_slot['end'],
                'description':'Meeting scheduled via AI Booking Agent'
            }
            try:
                event=calendar_service.create_event(event_details)
                start_time=datetime.fromisoformat(selected_slot['start'].replace('Z', '+00:00'))
                response=f"""perfect! I've booked your meeting for {start_time.strftime('%A, %B %d at %I:%M %p')}.
                Event created in your Google Calendar
                can view it at: {event.get('htmlLink', 'Check your Google Calendar')}
                Is there anything else I can help you with?"""
                state["messages"].append(AIMessage(content=response))
            
            except Exception as e:
                error_response=f"I encountered an issue while creating your calendar event. Please try again."
                state["messages"].append(AIMessage(content=error_response))
        
        return state
    
    def _handle_modification(self, state:ConversationState) ->ConversationState:
        response = """No problem! Let me help you find a different time.
        What would work better for you? You can tell me:
        • A different day ("try next Monday")
        • A different time ("afternoon instead")
        • A different duration ("30 minutes")"""
        
        state["messages"].append(AIMessage(content=response))
        
        state["proposed_datetime"]=None
        state["available_slots"]=[]
        state["selected_slot"]=None
        state["booking_confirmed"]=False
        
        return state
    def _parse_datetime(self, datetime_str: str) -> datetime:
        now = datetime.now()
        if "tomorrow" in datetime_str.lower():
            return now + timedelta(days=1)
        elif "friday" in datetime_str.lower():
            days_ahead = 4 - now.weekday()  
            if days_ahead <= 0:
                days_ahead += 7
            return now + timedelta(days=days_ahead)
        else:
            return now + timedelta(days=1)
    
    def process_message(self, message: str, session_id: str) -> Dict[str, Any]:
        
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "messages":[SystemMessage(content="You are a helpful AI booking assistant.")],
                "session_id": session_id,
                "current_intent":"greeting",
                "proposed_datetime":None,
                "duration": 60,
                "meeting_title":None,
                "available_slots":[],
                "selected_slot":None,
                "booking_confirmed":False,
                "user_preferences":{}
            }
    
        self.sessions[session_id]["messages"].append(HumanMessage(content=message))
        
        try:
            result = self.graph.invoke(self.sessions[session_id])
            self.sessions[session_id] = result
            ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
            response = ai_messages[-1].content if ai_messages else "How can I help you schedule meetings?"
            
            suggestions = self._generate_suggestions(result.get("current_intent", "greeting"))
            
            return {
                "response":response,
                "session_id":session_id,
                "state":result.get("current_intent", "unknown"),
                "suggestions":suggestions,
                "booking_details":None
            }    
        except Exception as e:
            print(f"processing error: {e}")
            return {
                "response":"I'm sorry, I'm having trouble right now. Please try again.",
                "session_id":session_id,
                "state": "error",
                "suggestions": ["Try again", "Check availability", "Schedule meeting"],
                "booking_details": None
            }
    
    def _generate_suggestions(self, intent: str) -> List[str]:
        if intent=="greeting":
            return["Schedule a meeting tomorrow", "Check my availability", "Book a call"]
        elif intent=="availability_check":
            return["Book the first option", "Show more times", "Try different day"]
        elif intent=="booking_request":
            return["Yes, book it", "Different time", "30 minutes instead"]
        else:
            return["Schedule meeting", "Check calendar", "Help"]

booking_agent = BookingAgent()

@app.get("/")
async def root():
    return {
        "message": "hello",
        "docs": "/docs",
        "version": "1.0.0"
    }

""" @app.get("/health")
async def health_check():
    calendar_info = calendar_service.get_calendar_info()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "google_calendar": calendar_info.get("status", "Unknown"),
        "authenticated": calendar_info.get("authenticated", False)
    } """

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(chat_message: ChatMessage):
    try:
        result=booking_agent.process_message(chat_message.message, chat_message.session_id)
        return ChatResponse(**result)
    except Exception as e:
        print(f"chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/calendar/info")
async def get_calendar_info():
    return calendar_service.get_calendar_info()

if __name__ == "__main__":
    port = int(os.getenv('PORT', 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)