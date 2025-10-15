from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, Text
from datetime import datetime, timedelta
from src.models.user import db
import pytz

class GolfEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    day_of_week = db.Column(db.String(10), nullable=False)  # Monday, Wednesday, Friday
    max_players = db.Column(db.Integer, default=20, nullable=False)  # Updated to 20 for the group
    cutoff_datetime = db.Column(db.DateTime, nullable=False)  # Wednesday 6pm of preceding week
    cancellation_deadline = db.Column(db.DateTime, nullable=False)  # 8am day before event
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to signups
    signups = db.relationship('Signup', backref='event', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<GolfEvent {self.date} ({self.day_of_week})>'

    @property
    def is_cutoff_passed(self):
        """Check if the cutoff time has passed (PST timezone aware)"""
        pst = pytz.timezone('US/Pacific')
        now_pst = datetime.now(pst)
        
        # Convert cutoff_datetime to PST if it's not already timezone aware
        if self.cutoff_datetime.tzinfo is None:
            cutoff_pst = pst.localize(self.cutoff_datetime)
        else:
            cutoff_pst = self.cutoff_datetime.astimezone(pst)
            
        return now_pst > cutoff_pst

    @property
    def can_cancel(self):
        """Check if cancellations are still allowed"""
        return datetime.utcnow() < self.cancellation_deadline

    @property
    def confirmed_signups(self):
        """Get only confirmed (non-waitlist) signups"""
        return [s for s in self.signups if not s.is_waitlist and not s.is_cancelled]

    @property
    def waitlist_signups(self):
        """Get only waitlist signups"""
        return [s for s in self.signups if s.is_waitlist and not s.is_cancelled]

    def to_dict(self):
        confirmed = self.confirmed_signups
        waitlist = self.waitlist_signups
        
        return {
            'id': self.id,
            'date': self.date.isoformat(),
            'day_of_week': self.day_of_week,
            'max_players': self.max_players,
            'current_signups': len(confirmed),
            'waitlist_count': len(waitlist),
            'available_spots': max(0, self.max_players - len(confirmed)),
            'is_full': len(confirmed) >= self.max_players,
            'cutoff_datetime': self.cutoff_datetime.isoformat(),
            'cancellation_deadline': self.cancellation_deadline.isoformat(),
            'is_cutoff_passed': self.is_cutoff_passed,
            'can_cancel': self.can_cancel,
            'created_at': self.created_at.isoformat()
        }

class Signup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('golf_event.id'), nullable=False)
    signup_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_waitlist = db.Column(db.Boolean, default=False, nullable=False)
    is_cancelled = db.Column(db.Boolean, default=False, nullable=False)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    guest_name = db.Column(db.String(100), nullable=True)  # New field for guest registration
    
    # Relationship to user (no backref to avoid conflict)
    user = db.relationship('User')
    
    # Unique constraint to prevent duplicate signups (including cancelled ones)
    __table_args__ = (db.UniqueConstraint('user_id', 'event_id', name='unique_user_event'),)

    def __repr__(self):
        status = "Waitlist" if self.is_waitlist else "Confirmed"
        if self.is_cancelled:
            status = "Cancelled"
        guest_info = f" (Guest: {self.guest_name})" if self.guest_name else ""
        return f'<Signup User:{self.user_id} Event:{self.event_id} Status:{status}{guest_info}>'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'event_id': self.event_id,
            'signup_date': self.signup_date.isoformat(),
            'is_waitlist': self.is_waitlist,
            'is_cancelled': self.is_cancelled,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'guest_name': self.guest_name,
            'user': self.user.to_dict() if self.user else None
        }

class EmailLog(db.Model):
    """Track sent emails to prevent duplicates and for debugging"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('golf_event.id'), nullable=False)
    email_type = db.Column(db.String(50), nullable=False)  # 'signup_confirmation', 'cancellation', etc.
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    email_address = db.Column(db.String(120), nullable=False)
    
    # Relationships
    user = db.relationship('User', backref='email_logs')
    event = db.relationship('GolfEvent', backref='email_logs')

    def __repr__(self):
        return f'<EmailLog {self.email_type} to {self.email_address} at {self.sent_at}>'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'event_id': self.event_id,
            'email_type': self.email_type,
            'sent_at': self.sent_at.isoformat(),
            'email_address': self.email_address
        }

