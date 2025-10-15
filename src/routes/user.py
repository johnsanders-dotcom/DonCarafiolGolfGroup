from flask import Blueprint, request, jsonify
from src.models.user import User, db

user_bp = Blueprint('user', __name__)

@user_bp.route('/users', methods=['GET'])
def get_users():
    """Get all users"""
    users = User.query.all()
    return jsonify([user.to_dict() for user in users]), 200

@user_bp.route('/users', methods=['POST'])
def create_user():
    """Create a new user"""
    data = request.get_json()
    
    if not data or 'name' not in data or 'email' not in data:
        return jsonify({'error': 'Name and email are required'}), 400
    
    # Check if user already exists
    existing_user = User.query.filter_by(email=data['email'].lower()).first()
    if existing_user:
        return jsonify(existing_user.to_dict()), 200
    
    # Create new user
    user = User(
        name=data['name'],
        email=data['email'].lower()
    )
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify(user.to_dict()), 201
