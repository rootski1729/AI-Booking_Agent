from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import uvicorn

from booking_agent import BookingAgent
from config import Config

Config.validate()

app=FastAPI(title="AI Booking Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

booking_agent=BookingAgent()

class ChatMessage(BaseModel):
    role:str
    content:str

class ChatRequest(BaseModel):
    message:str
    conversation_history:Optional[List[ChatMessage]]=[]

class ChatResponse(BaseModel):
    response:str
    conversation_history:List[ChatMessage]
    booking_confirmed:bool=False

@app.get("/")
async def root():
    return {"message":"AI Booking Agent is running"}

@app.get("/health")
async def health_check():
    return {"status":"healthy", "message":"Booking agent is operational"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request:ChatRequest):
    try:
        conversation_history=[
            {"role":msg.role, "content":msg.content}
            for msg in request.conversation_history
        ]
        result=booking_agent.process_message(
            message=request.message,
            conversation_history=conversation_history
        )
        
        updated_history=[
            ChatMessage(role=msg["role"], content=msg["content"])
            for msg in result["state"]["messages"]
        ]
        
        return ChatResponse(
            response=result["response"],
            conversation_history=updated_history,
            booking_confirmed=result.get("booking_confirmed", False)
        )
    
    except Exception as e:
        error_response="i had trouble processing your request.try again?"
        
        preserved_history=list(request.conversation_history)
        preserved_history.append(ChatMessage(role="user", content=request.message))
        preserved_history.append(ChatMessage(role="assistant", content=error_response))
        
        return ChatResponse(
            response=error_response,
            conversation_history=preserved_history,
            booking_confirmed=False
        )

if __name__=="__main__":
    uvicorn.run(
        "main:app",
        host=Config.FASTAPI_HOST,
        port=Config.FASTAPI_PORT,
        reload=True
    )