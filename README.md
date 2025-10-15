# Don Carafiol Golfing Group Sign-Up Website

A full-stack web application for managing golf sign-ups for the Don Carafiol Golfing Group of MHCC.

## Features

- **Rolling Two-Week Calendar**: Automatically displays current and next week's golf sessions
- **Smart Sign-Up System**: 16-player capacity with automatic waitlist management
- **Guest Registration**: Members can register guests for golf sessions
- **Cutoff Management**: Sign-ups close Wednesday 6pm of the preceding week
- **Cancellation System**: Members can cancel up to 8am the day before their session
- **Event Rosters**: View confirmed players and waitlist for each session
- **Mobile Responsive**: Works perfectly on desktop, tablet, and mobile devices

## Technology Stack

- **Backend**: Flask (Python)
- **Frontend**: React with modern CSS
- **Database**: SQLite (development) / PostgreSQL (production)
- **Deployment**: Railway.app

## Golf Schedule

- **Days**: Monday, Wednesday, Friday
- **Capacity**: 16 players per session
- **Sign-up Cutoff**: Wednesday 6pm of the preceding week
- **Cancellation Deadline**: 8am the day before the session

## Local Development

1. Install dependencies:
   ```bash
   cd golf_signup_backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Run the Flask backend:
   ```bash
   python src/main.py
   ```

3. The application will be available at `http://localhost:5000`

## Deployment

This application is configured for deployment on Railway.app. See the deployment instructions for detailed steps.

## Project Structure

```
golf_signup_backend/
├── src/
│   ├── main.py              # Flask application entry point
│   ├── models/              # Database models
│   │   ├── user.py         # User model
│   │   └── golf.py         # Golf events and signup models
│   ├── routes/              # API routes
│   │   ├── user.py         # User-related endpoints
│   │   └── golf.py         # Golf-related endpoints
│   ├── static/              # Built React frontend files
│   └── database/            # SQLite database files
├── requirements.txt         # Python dependencies
├── Dockerfile              # Docker configuration for Railway
├── railway.json            # Railway deployment configuration
└── README.md               # This file
```

## API Endpoints

- `GET /api/events/rolling` - Get current and next week's events
- `POST /api/signup` - Sign up for an event
- `POST /api/signup/<id>/cancel` - Cancel a signup
- `GET /api/events/<id>/roster` - Get event roster
- `GET /api/user-signups/<email>` - Get user's signups

## Admin

- **Group**: Don Carafiol Golfing Group of MHCC
- **Administrator**: John Sanders

---

Built with ❤️ for the golf community

