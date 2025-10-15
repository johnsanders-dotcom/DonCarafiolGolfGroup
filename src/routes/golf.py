from flask import Blueprint, request, jsonify
from datetime import datetime, date, timedelta
from src.models.user import User, db
from src.models.golf import GolfEvent, Signup, EmailLog
from sqlalchemy.exc import IntegrityError
import pytz

golf_bp = Blueprint('golf', __name__)

def calculate_cutoff_datetime(event_date):
    """Calculate cutoff datetime (Wednesday 6pm PST of the preceding week for ALL events)"""
    pst = pytz.timezone('US/Pacific')
    
    if event_date.weekday() == 0:  # Monday
        cutoff_date = event_date - timedelta(days=5)  # Go back to Wednesday
    elif event_date.weekday() == 2:  # Wednesday
        cutoff_date = event_date - timedelta(days=7)  # Go back to previous Wednesday
    elif event_date.weekday() == 4:  # Friday
        cutoff_date = event_date - timedelta(days=9)  # Go back to Wednesday of previous week
    else:
        cutoff_date = event_date - timedelta(days=7)
    
    # Set time to 6pm PST (18:00)
    cutoff_datetime = pst.localize(datetime.combine(cutoff_date, datetime.min.time().replace(hour=18)))
    return cutoff_datetime

def calculate_cancellation_deadline(event_date):
    """Calculate cancellation deadline (8am day before event)"""
    deadline_date = event_date - timedelta(days=1)
    deadline_datetime = datetime.combine(deadline_date, datetime.min.time().replace(hour=8))
    return deadline_datetime

def get_rolling_weeks():
    """Get the rolling two-week calendar based on PST Friday 6pm cutoff"""
    # Get current time in PST
    pst = pytz.timezone('US/Pacific')
    now_pst = datetime.now(pst)
    
    # Find current week Monday
    today = now_pst.date()
    days_since_monday = today.weekday()
    current_week_monday = today - timedelta(days=days_since_monday)
    
    # Check if it's past Friday 6pm PST
    current_friday = current_week_monday + timedelta(days=4)  # Friday
    friday_6pm_pst = pst.localize(datetime.combine(current_friday, datetime.min.time().replace(hour=18)))
    
    if now_pst >= friday_6pm_pst:
        # After Friday 6pm PST, advance to next week
        current_week_monday = current_week_monday + timedelta(days=7)
    
    # Calculate the two weeks to display
    week1_start = current_week_monday
    week1_end = week1_start + timedelta(days=6)
    week2_start = week1_start + timedelta(days=7)
    week2_end = week2_start + timedelta(days=6)
    
    return {
        'week1': {'start': week1_start, 'end': week1_end},
        'week2': {'start': week2_start, 'end': week2_end}
    }

@golf_bp.route('/events/rolling', methods=['GET'])
def get_rolling_events():
    """Get golf events for the rolling two-week calendar"""
    weeks = get_rolling_weeks()
    
    # Auto-generate events if they don't exist
    auto_generate_events_for_weeks(weeks)
    
    # Get events for both weeks
    all_events = GolfEvent.query.filter(
        GolfEvent.date >= weeks['week1']['start'],
        GolfEvent.date <= weeks['week2']['end']
    ).order_by(GolfEvent.date).all()
    
    # Flatten events into a single list for the rolling calendar
    events = [event.to_dict() for event in all_events]
    
    return jsonify({
        'events': events,
        'week1_start': weeks['week1']['start'].isoformat(),
        'week1_end': weeks['week1']['end'].isoformat(),
        'week2_start': weeks['week2']['start'].isoformat(),
        'week2_end': weeks['week2']['end'].isoformat()
    })

def auto_generate_events_for_weeks(weeks):
    """Automatically generate events for the rolling weeks if they don't exist"""
    events_created = 0
    
    for week_key in ['week1', 'week2']:
        week = weeks[week_key]
        week_start = week['start']
        
        # Generate Monday, Wednesday, Friday for this week
        for day_offset, day_name in [(0, 'Monday'), (2, 'Wednesday'), (4, 'Friday')]:
            event_date = week_start + timedelta(days=day_offset)
            
            # Check if event already exists
            existing_event = GolfEvent.query.filter_by(date=event_date).first()
            if existing_event:
                continue
            
            # Create new event
            cutoff_datetime = calculate_cutoff_datetime(event_date)
            cancellation_deadline = calculate_cancellation_deadline(event_date)
            
            event = GolfEvent(
                date=event_date,
                day_of_week=day_name,
                max_players=20,
                cutoff_datetime=cutoff_datetime,
                cancellation_deadline=cancellation_deadline
            )
            
            db.session.add(event)
            events_created += 1
    
    if events_created > 0:
        db.session.commit()

@golf_bp.route('/events/week/<int:offset>', methods=['GET'])
def get_events_by_week(offset):
    """Get events for a specific week offset (for backward compatibility)"""
    weeks = get_rolling_weeks()
    
    if offset == 0:
        week_start = weeks['week1']['start']
        week_end = weeks['week1']['end']
    elif offset == 1:
        week_start = weeks['week2']['start']
        week_end = weeks['week2']['end']
    else:
        return jsonify({'error': 'Only weeks 0 and 1 are supported in rolling calendar'}), 400
    
    events = GolfEvent.query.filter(
        GolfEvent.date >= week_start,
        GolfEvent.date <= week_end
    ).order_by(GolfEvent.date).all()
    
    return jsonify({
        'events': [event.to_dict() for event in events],
        'week_start': week_start.isoformat(),
        'week_end': week_end.isoformat()
    })

@golf_bp.route('/signup', methods=['POST'])
def signup_for_event():
    """Sign up for a golf event with optional guest"""
    data = request.get_json()
    
    if not data or 'name' not in data or 'email' not in data or 'event_id' not in data:
        return jsonify({'error': 'Name, email, and event_id are required'}), 400
    
    name = data['name'].strip()
    email = data['email'].strip().lower()
    event_id = data['event_id']
    guest_name = data.get('guest_name', '').strip() if data.get('guest_name') else None
    
    if not name or not email:
        return jsonify({'error': 'Name and email cannot be empty'}), 400
    
    # Find or create user
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(name=name, email=email)
        db.session.add(user)
        db.session.flush()  # Get the user ID
    
    # Find the event
    event = GolfEvent.query.get(event_id)
    if not event:
        return jsonify({'error': 'Event not found'}), 404
    
    # Check if user is already signed up for this event
    existing_signup = Signup.query.filter_by(
        user_id=user.id, 
        event_id=event_id,
        is_cancelled=False
    ).first()
    
    if existing_signup:
        return jsonify({'error': 'You are already signed up for this event'}), 400
    
    # Determine if this should be waitlist based on cutoff and capacity
    confirmed_signups = len(event.confirmed_signups)
    is_waitlist = event.is_cutoff_passed or confirmed_signups >= event.max_players
    
    # Create the signup
    signup = Signup(
        user_id=user.id,
        event_id=event_id,
        is_waitlist=is_waitlist,
        guest_name=guest_name
    )
    
    try:
        db.session.add(signup)
        db.session.commit()
        
        # Send confirmation email (mock implementation)
        send_signup_confirmation_email(user, event, signup)
        
        status = 'waitlist' if is_waitlist else 'confirmed'
        guest_info = f' with guest {guest_name}' if guest_name else ''
        
        return jsonify({
            'message': f'Successfully signed up for {event.day_of_week}, {event.date}{guest_info}',
            'status': status,
            'signup_id': signup.id
        }), 201
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'You are already signed up for this event'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Signup failed: {str(e)}'}), 500

@golf_bp.route('/signup/<int:signup_id>/cancel', methods=['POST'])
def cancel_signup(signup_id):
    """Cancel a signup"""
    signup = Signup.query.get(signup_id)
    if not signup:
        return jsonify({'error': 'Signup not found'}), 404
    
    if signup.is_cancelled:
        return jsonify({'error': 'Signup is already cancelled'}), 400
    
    # Check cancellation deadline
    if not signup.event.can_cancel:
        return jsonify({'error': 'Cancellation deadline has passed'}), 400
    
    # Cancel the signup
    signup.is_cancelled = True
    signup.cancelled_at = datetime.utcnow()
    
    # Promote waitlist if this was a confirmed signup
    if not signup.is_waitlist:
        promote_from_waitlist(signup.event)
    
    db.session.commit()
    
    return jsonify({'message': 'Signup cancelled successfully'}), 200

def promote_from_waitlist(event):
    """Promote the first waitlist signup to confirmed"""
    waitlist_signup = Signup.query.filter_by(
        event_id=event.id,
        is_waitlist=True,
        is_cancelled=False
    ).order_by(Signup.signup_date).first()
    
    if waitlist_signup:
        waitlist_signup.is_waitlist = False
        # Send promotion email
        send_promotion_email(waitlist_signup.user, event, waitlist_signup)

def send_signup_confirmation_email(user, event, signup):
    """Send signup confirmation email (mock implementation)"""
    # Log the email
    email_log = EmailLog(
        user_id=user.id,
        event_id=event.id,
        email_type='signup_confirmation',
        email_address=user.email
    )
    db.session.add(email_log)
    
    # In a real implementation, you would integrate with an email service
    print(f"MOCK EMAIL: Confirmation sent to {user.email}")
    print(f"Subject: Golf Signup Confirmation - {event.day_of_week}, {event.date}")
    
    status = "waitlist" if signup.is_waitlist else "confirmed"
    guest_info = f" with guest {signup.guest_name}" if signup.guest_name else ""
    
    print(f"Body: Hello {user.name}, you are {status} for golf on {event.day_of_week}, {event.date}{guest_info}")

def send_promotion_email(user, event, signup):
    """Send waitlist promotion email"""
    email_log = EmailLog(
        user_id=user.id,
        event_id=event.id,
        email_type='waitlist_promotion',
        email_address=user.email
    )
    db.session.add(email_log)
    
    print(f"MOCK EMAIL: Promotion sent to {user.email}")
    print(f"Subject: You've been promoted from waitlist - {event.day_of_week}, {event.date}")
    print(f"Body: Hello {user.name}, you've been promoted from waitlist to confirmed for golf on {event.day_of_week}, {event.date}")

@golf_bp.route('/user-signups/<email>', methods=['GET'])
def get_user_signups(email):
    """Get all signups for a user by email"""
    user = User.query.filter_by(email=email.lower()).first()
    if not user:
        return jsonify({'signups': []}), 200
    
    signups = Signup.query.filter_by(user_id=user.id, is_cancelled=False).all()
    
    signup_data = []
    for signup in signups:
        signup_dict = signup.to_dict()
        signup_dict['event'] = signup.event.to_dict()
        signup_data.append(signup_dict)
    
    return jsonify({'signups': signup_data}), 200

@golf_bp.route('/events/<int:event_id>/roster', methods=['GET'])
def get_event_roster(event_id):
    """Get the comprehensive roster for a specific event including cancellations"""
    event = GolfEvent.query.get(event_id)
    if not event:
        return jsonify({'error': 'Event not found'}), 404
    
    # Get all signups (including cancelled ones)
    all_signups = Signup.query.filter_by(event_id=event_id).order_by(Signup.signup_date).all()
    
    confirmed_players = []
    waitlist_players = []
    cancelled_players = []
    
    for signup in all_signups:
        player_data = {
            'name': signup.user.name,
            'email': signup.user.email,
            'guest_name': signup.guest_name,
            'signup_date': signup.signup_date.isoformat(),
            'signup_id': signup.id
        }
        
        if signup.is_cancelled:
            player_data['cancelled_at'] = signup.cancelled_at.isoformat() if signup.cancelled_at else None
            cancelled_players.append(player_data)
        elif signup.is_waitlist:
            waitlist_players.append(player_data)
        else:
            confirmed_players.append(player_data)
    
    return jsonify({
        'event': event.to_dict(),
        'confirmed_players': confirmed_players,
        'waitlist_players': waitlist_players,
        'cancelled_players': cancelled_players,
        'total_signups': len(confirmed_players),
        'total_waitlist': len(waitlist_players),
        'total_cancelled': len(cancelled_players)
    }), 200

@golf_bp.route('/generate-weekly-events', methods=['POST'])
def generate_weekly_events():
    """Generate golf events for the rolling calendar"""
    weeks = get_rolling_weeks()
    
    # Generate events for both weeks
    events_created = 0
    
    for week_key in ['week1', 'week2']:
        week = weeks[week_key]
        week_start = week['start']
        
        # Generate Monday, Wednesday, Friday for this week
        for day_offset, day_name in [(0, 'Monday'), (2, 'Wednesday'), (4, 'Friday')]:
            event_date = week_start + timedelta(days=day_offset)
            
            # Check if event already exists
            existing_event = GolfEvent.query.filter_by(date=event_date).first()
            if existing_event:
                continue
            
            # Create new event
            cutoff_datetime = calculate_cutoff_datetime(event_date)
            cancellation_deadline = calculate_cancellation_deadline(event_date)
            
            event = GolfEvent(
                date=event_date,
                day_of_week=day_name,
                max_players=20,
                cutoff_datetime=cutoff_datetime,
                cancellation_deadline=cancellation_deadline
            )
            
            db.session.add(event)
            events_created += 1
    
    db.session.commit()
    
    return jsonify({
        'message': f'Created {events_created} events',
        'events': events_created
    }), 201

