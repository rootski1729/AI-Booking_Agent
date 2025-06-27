# 🗓️ AI Calendar Booking Agent

A conversational AI agent that assists users in booking appointments on Google Calendar through natural language interactions. The agent engages in back-and-forth conversations, understands user intent, checks calendar availability, suggests time slots, and confirms bookings seamlessly.

## 🚀 Mission

Build a conversational AI agent capable of:
- Engaging in natural conversations about scheduling
- Understanding user intent and guiding toward booking
- Checking real-time calendar availability
- Suggesting suitable time slots
- Confirming and creating calendar bookings

## 🛠 Technical Stack

- **Backend**: Python with FastAPI
- **Agent Framework**: LangGraph (integrated with custom booking logic)
- **Frontend**: Streamlit (interactive chat interface)
- **Calendar Integration**: Google Calendar API
- **Natural Language Processing**: Custom conversation flow management

## 💬 What the Agent Can Do

✅ **Natural Language Understanding**
- Processes conversational input like "Hey, I want to schedule a call for tomorrow afternoon"
- Understands dates, times, and scheduling intent

✅ **Smart Availability Checking**
- Integrates with Google Calendar to check real availability
- Handles business hours (9 AM - 6 PM, weekdays only)
- Provides friendly responses for weekends and after-hours

✅ **Intelligent Booking Flow**
- Guides users through the booking process
- Suggests available time slots
- Confirms bookings before creating calendar events

✅ **Edge Case Handling**
- Past date validation
- Weekend and after-hours messaging
- Conflict detection and resolution
- Error handling with graceful fallbacks

## 🤔 Example Conversations

**Availability Check:**
```
User: "Check my availability for Friday"
Bot: "Here's your availability for Friday, December 20:

🌅 Morning:
  • 09:00 AM - 10:00 AM
  • 10:00 AM - 11:00 AM

☀️ Afternoon:
  • 02:00 PM - 03:00 PM
  • 03:00 PM - 04:00 PM

Would you like to book any of these times?"
```

**Booking Request:**
```
User: "Hey, I want to schedule a call for tomorrow afternoon"
Bot: "I found available slots for tomorrow afternoon:

1. 02:00 PM - 03:00 PM
2. 03:00 PM - 04:00 PM
3. 04:00 PM - 05:00 PM

Which slot works for you? Reply with the number (1-3)."

User: "1"
Bot: "Perfect! I'll book your meeting for:

📅 Friday, December 20
🕐 02:00 PM - 03:00 PM

Should I confirm this booking? Say 'yes' to confirm."

User: "yes"
Bot: "🎉 Booking Confirmed! Your meeting has been added to your calendar!"
```

**Weekend/After Hours:**
```
User: "Do you have any free time this Saturday?"
Bot: "It's a weekend free time! You don't have work slots for Saturday, December 21. 🎉 How about choosing a weekday instead?"

User: "Check availability for today" (after 6 PM)
Bot: "Work day has ended for you! You don't have slots after 6:00 PM. 🌅 Please choose tomorrow or another day."
```

## 📋 Prerequisites

- Python 3.8+
- Google Calendar API credentials
- Gmail account for calendar access

## 🔧 Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd ai-booking-agent
```

2. **Install dependencies**
```bash
pip install fastapi uvicorn streamlit requests google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client pytz python-dateutil python-dotenv
```

3. **Set up Google Calendar API**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable Google Calendar API
   - Create credentials (OAuth 2.0 Client ID)
   - Download `credentials.json` and place in project root

4. **Environment Configuration**
Create a `.env` file:
```env
GEMINI_API_KEY=your_gemini_api_key_here
TIMEZONE=Asia/Kolkata
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000
```

## 🚀 Quick Start

1. **Start the FastAPI backend**
```bash
python main.py
```
The API will be available at `http://localhost:8000`

2. **Launch Streamlit interface** (in another terminal)
```bash
streamlit run streamlit_app.py
```
The chat interface will open in your browser

3. **First-time setup**
   - When you first run the app, it will open a browser for Google OAuth
   - Grant calendar access permissions
   - The `token.pickle` file will be created automatically

## 📁 Project Structure

```
ai-booking-agent/
├── main.py                 # FastAPI backend server
├── booking_agent.py        # Core booking logic and conversation handling
├── calendar_service.py     # Google Calendar API integration
├── config.py              # Configuration settings
├── streamlit_app.py       # Streamlit chat interface
├── credentials.json       # Google API credentials (you need to add this)
├── token.pickle          # Auto-generated OAuth token
├── .env                  # Environment variables
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## 🎯 Core Features

### Natural Language Processing
- Understands conversational booking requests
- Parses dates in multiple formats (tomorrow, Friday, next week, 25/12/2024)
- Recognizes time preferences (morning, afternoon, evening, specific times)

### Calendar Integration
- Real-time availability checking via Google Calendar API
- Conflict detection and prevention
- Automatic event creation with proper metadata

### Conversation Management
- Multi-turn conversation support
- Context awareness and state management
- Graceful error handling and recovery

### Business Logic
- Enforces business hours (9 AM - 6 PM)
- Weekday-only scheduling
- Past date validation
- Meeting duration management

## 🧪 Testing

Test the booking flow:
```bash
python test_bot.py
```

## 🎛 Configuration

Key settings in `config.py`:
- `BUSINESS_HOURS_START`: 9 (9 AM)
- `BUSINESS_HOURS_END`: 18 (6 PM)
- `TIMEZONE`: "Asia/Kolkata"
- `DEFAULT_MEETING_DURATION`: 60 minutes

## 🚨 Troubleshooting

**Common Issues:**

1. **Calendar API Errors**
   - Ensure `credentials.json` is in the project root
   - Check Google Calendar API is enabled
   - Verify OAuth permissions

2. **Connection Errors**
   - Make sure FastAPI server is running on port 8000
   - Check firewall settings

3. **Time Zone Issues**
   - Verify `TIMEZONE` setting in config
   - Ensure system time is correct

## 🎉 Features Highlight

- **Smart Weekend Detection**: Friendly messages for weekend requests
- **After-Hours Handling**: Appropriate responses for post-work requests
- **Natural Conversation Flow**: Guides users through booking step-by-step
- **Real-time Validation**: Checks calendar conflicts before booking
- **Error Recovery**: Graceful handling of invalid inputs

## 📝 API Endpoints

- `GET /`: Health check
- `GET /health`: Detailed system status
- `POST /chat`: Main conversation endpoint

## 🔗 Live Demo

Access the live Streamlit interface at: `http://localhost:8501`

## 📧 Support

For issues or questions, please check the troubleshooting section or review the error logs in the console output.

---

**Built with ❤️ for seamless calendar management through AI conversations**