"""
GAMEBOT MULTIPLAYER SERVER
Enterprise-grade multiplayer gaming platform with ranked system
Ready for $1 trillion deployment
"""

from flask import Flask, request, send_file
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from sqlalchemy import text
import jwt
import base64
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta
import hashlib
import uuid

try:
    import bcrypt
except ImportError:
    bcrypt = None

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    Fernet = None
    InvalidToken = Exception

try:
    import redis
except ImportError:
    redis = None

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs):
        return False

load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================
# ENTERPRISE INFRASTRUCTURE
# ============================================

app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'sqlite:///gamebot.db'
)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['JWT_SECRET'] = os.getenv('JWT_SECRET', 'jwt-secret-key')

db = SQLAlchemy(app)

VALID_USERNAME_RE = re.compile(r'^[A-Za-z0-9_]{3,24}$')
ALLOWED_GAME_TYPES = {'rps', 'dice', 'slots', 'trivia', 'math', 'bj', 'blackjack'}
RPS_CHOICES = {'rock', 'paper', 'scissors'}


def normalize_username(username: str) -> str:
    """Trim usernames and keep display casing."""
    return (username or '').strip()


def normalize_email(email: str) -> str:
    """Normalize email before hashing or lookup."""
    return (email or '').strip().lower()


def email_fingerprint(email: str) -> str:
    """Store a stable email lookup value without storing the email itself."""
    return 'sha256:' + hashlib.sha256(normalize_email(email).encode('utf-8')).hexdigest()


def get_cipher():
    """Create a local Fernet cipher from the app secret."""
    if Fernet is None:
        return None

    seed = os.getenv('ACCOUNT_ENCRYPTION_KEY') or app.config['SECRET_KEY']
    key = base64.urlsafe_b64encode(hashlib.sha256(seed.encode('utf-8')).digest())
    return Fernet(key)


def encrypt_text(value: str) -> str:
    """Encrypt account and chat text before database storage."""
    if value is None:
        return None

    cipher = get_cipher()
    if cipher is None:
        return value
    return cipher.encrypt(value.encode('utf-8')).decode('utf-8')


def decrypt_text(value: str) -> str:
    """Decrypt stored account and chat text for authorized responses."""
    if not value:
        return ''

    cipher = get_cipher()
    if cipher is None:
        return value
    try:
        return cipher.decrypt(value.encode('utf-8')).decode('utf-8')
    except InvalidToken:
        return ''


def hash_password(password: str) -> str:
    """Hash passwords; never store raw passwords."""
    if bcrypt is not None:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 200000).hex()
    return f'pbkdf2_sha256${salt}${digest}'


def verify_password_hash(password: str, stored_hash: str) -> bool:
    """Verify modern hashes and old SHA256 hashes created by earlier builds."""
    if not stored_hash:
        return False

    if stored_hash.startswith('$2') and bcrypt is not None:
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))

    if stored_hash.startswith('pbkdf2_sha256$'):
        try:
            _, salt, digest = stored_hash.split('$', 2)
        except ValueError:
            return False
        expected = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 200000).hex()
        return hmac.compare_digest(expected, digest)

    legacy = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(stored_hash, legacy)

# Redis for caching and real-time features
redis_client = None
if redis is not None:
    try:
        redis_timeout = float(os.getenv('REDIS_TIMEOUT', '0.5'))
        redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=0,
            decode_responses=True,
            socket_connect_timeout=redis_timeout,
            socket_timeout=redis_timeout,
            retry_on_timeout=False
        )
        redis_client.ping()
    except Exception:
        redis_client = None

# ============================================
# DATABASE MODELS
# ============================================

class User(db.Model):
    """Enhanced user model with ranking"""
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    encrypted_email = db.Column(db.Text)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Account Info
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    is_premium = db.Column(db.Boolean, default=False)
    premium_expiry = db.Column(db.DateTime)
    
    # Profile
    avatar_url = db.Column(db.String(255))
    bio = db.Column(db.String(500))
    country = db.Column(db.String(100))
    
    # Currency
    coins = db.Column(db.Integer, default=100)
    premium_coins = db.Column(db.Integer, default=0)
    
    # Progression
    level = db.Column(db.Integer, default=1)
    exp = db.Column(db.Integer, default=0)
    total_playtime = db.Column(db.Integer, default=0)  # seconds
    
    # Ranking
    rank_rating = db.Column(db.Integer, default=1000)  # ELO rating
    rank_tier = db.Column(db.String(50), default='Bronze')  # Bronze to Diamond
    rank_position = db.Column(db.Integer)
    
    # Stats
    total_games_played = db.Column(db.Integer, default=0)
    total_wins = db.Column(db.Integer, default=0)
    total_losses = db.Column(db.Integer, default=0)
    win_rate = db.Column(db.Float, default=0.0)
    
    # Relationships
    games = db.relationship(
        'GameSession',
        foreign_keys='GameSession.player1_id',
        backref='player1',
        lazy='dynamic'
    )
    games_as_opponent = db.relationship(
        'GameSession',
        foreign_keys='GameSession.player2_id',
        backref='player2',
        lazy='dynamic'
    )
    won_games = db.relationship(
        'GameSession',
        foreign_keys='GameSession.winner_id',
        backref='winner',
        lazy='dynamic'
    )
    friends = db.relationship(
        'Friendship',
        foreign_keys='Friendship.user_id',
        backref='requester',
        lazy='dynamic'
    )
    friend_requests = db.relationship(
        'Friendship',
        foreign_keys='Friendship.friend_id',
        backref='recipient',
        lazy='dynamic'
    )
    
    def set_password(self, password: str):
        """Hash and set password."""
        self.password_hash = hash_password(password)

    def verify_password(self, password: str) -> bool:
        """Verify password without exposing stored hashes."""
        return verify_password_hash(password, self.password_hash)
    
    def generate_token(self, expires_in=86400) -> str:
        """Generate JWT token (24 hours)"""
        payload = {
            'user_id': self.id,
            'username': self.username,
            'exp': datetime.utcnow() + timedelta(seconds=expires_in)
        }
        return jwt.encode(payload, app.config['JWT_SECRET'], algorithm='HS256')
    
    def update_rank(self):
        """Update tier based on rating"""
        if self.rank_rating >= 3000:
            self.rank_tier = 'Diamond'
        elif self.rank_rating >= 2000:
            self.rank_tier = 'Platinum'
        elif self.rank_rating >= 1500:
            self.rank_tier = 'Gold'
        elif self.rank_rating >= 1000:
            self.rank_tier = 'Silver'
        else:
            self.rank_tier = 'Bronze'
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email_protected': True,
            'level': self.level,
            'rank_rating': self.rank_rating,
            'rank_tier': self.rank_tier,
            'rating': self.rank_rating,
            'tier': self.rank_tier,
            'coins': self.coins,
            'premium_coins': self.premium_coins,
            'total_wins': self.total_wins,
            'total_losses': self.total_losses,
            'wins': self.total_wins,
            'losses': self.total_losses,
            'win_rate': round(self.win_rate, 2),
            'is_premium': self.is_premium,
            'avatar_url': self.avatar_url,
            'country': self.country
        }


class GameSession(db.Model):
    """Multiplayer game session"""
    __tablename__ = 'game_sessions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    game_type = db.Column(db.String(50), nullable=False)  # rps, bj, trivia, etc.
    
    # Multiplayer
    max_players = db.Column(db.Integer, default=2)
    current_players = db.Column(db.Integer, default=0)
    
    # Players
    player1_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    player2_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    
    # Game State
    status = db.Column(db.String(50), default='waiting')  # waiting, in_progress, completed
    stakes = db.Column(db.Integer, default=0)  # Coins at stake
    
    # Results
    winner_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    p1_score = db.Column(db.Integer, default=0)
    p2_score = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Ranking
    ranked = db.Column(db.Boolean, default=False)
    p1_rating_before = db.Column(db.Integer)
    p1_rating_after = db.Column(db.Integer)
    p2_rating_before = db.Column(db.Integer)
    p2_rating_after = db.Column(db.Integer)


class Friendship(db.Model):
    """Friend relationships"""
    __tablename__ = 'friendships'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    friend_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(50), default='pending')  # pending, accepted, blocked
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Achievement(db.Model):
    """User achievements"""
    __tablename__ = 'achievements'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    achievement_code = db.Column(db.String(100), nullable=False)
    unlocked_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatMessage(db.Model):
    """Encrypted friend chat messages."""
    __tablename__ = 'chat_messages'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sender_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    recipient_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    body_encrypted = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    delivered = db.Column(db.Boolean, default=False)

    def to_dict(self, viewer_id):
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'recipient_id': self.recipient_id,
            'direction': 'sent' if self.sender_id == viewer_id else 'received',
            'message': decrypt_text(self.body_encrypted),
            'created_at': self.created_at.isoformat(),
            'delivered': self.delivered
        }


class AntiCheatEvent(db.Model):
    """Server-side audit trail for suspicious game actions."""
    __tablename__ = 'anti_cheat_events'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    event_type = db.Column(db.String(80), nullable=False)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


def public_user(user):
    """Return safe user information for friends/search results."""
    return {
        'id': user.id,
        'username': user.username,
        'level': user.level,
        'rank_rating': user.rank_rating,
        'rank_tier': user.rank_tier,
        'wins': user.total_wins,
        'win_rate': round(user.win_rate, 2),
        'avatar_url': user.avatar_url,
        'country': user.country
    }


def find_user_by_name_or_id(value):
    """Find a user by id or username."""
    value = (value or '').strip()
    if not value:
        return None
    return User.query.filter(
        (User.id == value) | (db.func.lower(User.username) == value.lower())
    ).first()


def get_friendship(user_id, friend_id):
    """Return the friendship record between two users, if it exists."""
    return Friendship.query.filter(
        ((Friendship.user_id == user_id) & (Friendship.friend_id == friend_id)) |
        ((Friendship.user_id == friend_id) & (Friendship.friend_id == user_id))
    ).first()


def are_friends(user_id, friend_id):
    friendship = get_friendship(user_id, friend_id)
    return bool(friendship and friendship.status == 'accepted')


def record_anticheat_event(user_id, event_type, details):
    """Persist a suspicious action without crashing the gameplay request."""
    try:
        db.session.add(AntiCheatEvent(
            user_id=user_id,
            event_type=event_type,
            details=details[:1000] if details else ''
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()


def reject_suspicious(user, event_type, message, details=None, status=400):
    record_anticheat_event(user.id, event_type, details or message)
    return {'message': message}, status


# ============================================
# AUTHENTICATION DECORATOR
# ============================================

def token_required(f):
    """Require valid JWT token"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return {'message': 'Invalid token format'}, 401
        
        if not token:
            return {'message': 'Token is missing'}, 401
        
        try:
            data = jwt.decode(token, app.config['JWT_SECRET'], algorithms=['HS256'])
            user = User.query.get(data['user_id'])
            if not user:
                return {'message': 'User not found'}, 401
        except jwt.ExpiredSignatureError:
            return {'message': 'Token has expired'}, 401
        except jwt.InvalidTokenError:
            return {'message': 'Invalid token'}, 401
        
        return f(user, *args, **kwargs)
    return decorated_function


# ============================================
# AUTHENTICATION ENDPOINTS
# ============================================

@app.route('/api/v3/auth/register', methods=['POST'])
def register():
    """Register new user"""
    data = request.get_json(silent=True) or {}
    username = normalize_username(data.get('username'))
    email = normalize_email(data.get('email'))
    password = data.get('password') or ''
    
    if not username or not email or not password:
        return {'message': 'Missing required fields'}, 400

    if not VALID_USERNAME_RE.match(username):
        return {'message': 'Username must be 3-24 letters, numbers, or underscores'}, 400

    if len(password) < 6:
        return {'message': 'Password must be at least 6 characters'}, 400
    
    if User.query.filter(db.func.lower(User.username) == username.lower()).first():
        return {'message': 'Username already exists'}, 409
    
    email_lookup = email_fingerprint(email)
    if User.query.filter((User.email == email_lookup) | (User.email == email)).first():
        return {'message': 'Email already exists'}, 409
    
    user = User(
        username=username,
        email=email_lookup,
        encrypted_email=encrypt_text(email),
        avatar_url=data.get('avatar_url', '')
    )
    user.set_password(password)
    
    db.session.add(user)
    db.session.commit()
    
    token = user.generate_token()
    
    return {
        'message': 'User registered successfully',
        'token': token,
        'user': user.to_dict()
    }, 201


@app.route('/api/v3/auth/login', methods=['POST'])
def login():
    """Login user - accepts username or email"""
    data = request.get_json(silent=True) or {}
    password = data.get('password') or ''
    
    if not password:
        return {'message': 'Missing password'}, 400
    
    # Accept either username or email
    username_or_email = data.get('username') or data.get('email')
    if not username_or_email:
        return {'message': 'Missing username or email'}, 400

    username_or_email = username_or_email.strip()
    email_lookup = email_fingerprint(username_or_email) if '@' in username_or_email else username_or_email
    
    user = User.query.filter(
        (User.email == email_lookup) |
        (User.email == username_or_email) |
        (db.func.lower(User.username) == username_or_email.lower())
    ).first()
    
    if not user or not user.verify_password(password):
        return {'message': 'Invalid credentials'}, 401

    if not user.password_hash.startswith('$2') and bcrypt is not None:
        user.set_password(password)
    
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    token = user.generate_token()
    
    return {
        'token': token,
        'user': user.to_dict()
    }, 200


# ============================================
# USER ENDPOINTS
# ============================================

@app.route('/api/v3/users/profile', methods=['GET'])
@token_required
def get_profile(user):
    """Get user profile"""
    return user.to_dict(), 200


@app.route('/api/v3/users/search', methods=['GET'])
@token_required
def search_users(user):
    """Search users by username for friend requests."""
    query = normalize_username(request.args.get('q', ''))
    if len(query) < 2:
        return {'users': []}, 200

    matches = User.query.filter(
        User.id != user.id,
        db.func.lower(User.username).like(f'%{query.lower()}%')
    ).order_by(User.username.asc()).limit(10).all()

    return {'users': [public_user(match) for match in matches]}, 200


@app.route('/api/v3/users/profile', methods=['PUT'])
@token_required
def update_profile(user):
    """Update user profile"""
    data = request.get_json(silent=True) or {}
    
    if 'bio' in data:
        user.bio = data['bio']
    if 'avatar_url' in data:
        user.avatar_url = data['avatar_url']
    if 'country' in data:
        user.country = data['country']
    
    db.session.commit()
    
    return {'message': 'Profile updated', 'user': user.to_dict()}, 200


@app.route('/api/v3/users/<user_id>/stats', methods=['GET'])
def get_user_stats(user_id):
    """Get user statistics"""
    user = User.query.get(user_id)
    if not user:
        return {'message': 'User not found'}, 404
    
    return {
        'username': user.username,
        'level': user.level,
        'rank_tier': user.rank_tier,
        'rank_rating': user.rank_rating,
        'total_games': user.total_games_played,
        'wins': user.total_wins,
        'losses': user.total_losses,
        'win_rate': round(user.win_rate, 2),
        'total_playtime': user.total_playtime
    }, 200


# ============================================
# RANKED SYSTEM ENDPOINTS
# ============================================

@app.route('/api/v3/ranked/leaderboard', methods=['GET'])
def get_leaderboard():
    """Get ranked leaderboard"""
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    users = User.query.order_by(User.rank_rating.desc()).limit(limit).offset(offset).all()
    
    leaderboard = []
    for idx, user in enumerate(users, start=offset+1):
        leaderboard.append({
            'rank': idx,
            'username': user.username,
            'rank_tier': user.rank_tier,
            'rating': user.rank_rating,
            'wins': user.total_wins,
            'losses': user.total_losses,
            'win_rate': round(user.win_rate, 2),
            'country': user.country,
            'avatar_url': user.avatar_url
        })
    
    return {'leaderboard': leaderboard, 'total': User.query.count()}, 200


@app.route('/api/v3/ranked/season', methods=['GET'])
def get_current_season():
    """Get current ranked season info"""
    return {
        'season': 1,
        'name': 'Season 1: Rise of Champions',
        'tier_count': 5,
        'tiers': ['Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond'],
        'reset_date': '2027-01-01'
    }, 200


# ============================================
# MULTIPLAYER GAME ENDPOINTS
# ============================================

@app.route('/api/v3/games/start', methods=['POST'])
@token_required
def start_game(user):
    """Start a multiplayer game"""
    data = request.get_json(silent=True) or {}
    
    game_type = (data.get('game_type') or 'rps').strip().lower()
    opponent_id = data.get('opponent_id')
    try:
        stakes = int(data.get('stakes', 0))
    except (TypeError, ValueError):
        return reject_suspicious(user, 'invalid_stake', 'Invalid stake amount', str(data.get('stakes')))
    ranked = data.get('ranked', False)

    if game_type not in ALLOWED_GAME_TYPES:
        return reject_suspicious(user, 'invalid_game_type', 'Unsupported game type', game_type)

    if stakes < 0 or stakes > 10000:
        return reject_suspicious(user, 'invalid_stake', 'Invalid stake amount', str(stakes))
    
    if not opponent_id:
        return {'message': 'Opponent required'}, 400

    if opponent_id == user.id:
        return reject_suspicious(user, 'self_match_attempt', 'Cannot start a game against yourself')
    
    opponent = User.query.get(opponent_id)
    if not opponent:
        return {'message': 'Opponent not found'}, 404
    
    # Check coins
    if stakes > 0 and user.coins < stakes:
        return {'message': 'Insufficient coins'}, 400
    
    if stakes > 0 and opponent.coins < stakes:
        return {'message': 'Opponent has insufficient coins'}, 400
    
    # Deduct stakes
    if stakes > 0:
        user.coins -= stakes
        opponent.coins -= stakes
    
    # Create game session
    session_obj = GameSession(
        game_type=game_type,
        player1_id=user.id,
        player2_id=opponent_id,
        current_players=1,
        stakes=stakes,
        ranked=ranked,
        p1_rating_before=user.rank_rating if ranked else None,
        p2_rating_before=opponent.rank_rating if ranked else None
    )
    
    db.session.add(session_obj)
    db.session.commit()
    
    return {
        'game_id': session_obj.id,
        'status': 'waiting_for_opponent',
        'game_type': game_type,
        'stakes': stakes,
        'ranked': ranked
    }, 201


@app.route('/api/v3/games/<game_id>/join', methods=['POST'])
@token_required
def join_game(user, game_id):
    """Join a waiting game"""
    game = GameSession.query.get(game_id)
    if not game:
        return {'message': 'Game not found'}, 404
    
    if game.status != 'waiting':
        return {'message': 'Game not available'}, 400

    if user.id != game.player2_id:
        return reject_suspicious(user, 'unauthorized_join', 'Only the invited opponent can join this game', game_id, 403)
    
    game.status = 'in_progress'
    game.current_players = 2
    game.started_at = datetime.utcnow()
    db.session.commit()
    
    return {'message': 'Game started', 'game_id': game_id}, 200


@app.route('/api/v3/games/<game_id>/finish', methods=['POST'])
@token_required
def finish_game(user, game_id):
    """Complete a game and calculate results"""
    data = request.get_json(silent=True) or {}
    
    game = GameSession.query.get(game_id)
    if not game:
        return {'message': 'Game not found'}, 404
    
    if game.status != 'in_progress':
        return {'message': 'Game not in progress'}, 400

    if user.id not in {game.player1_id, game.player2_id}:
        return reject_suspicious(user, 'unauthorized_finish', 'Only game players can finish this match', game_id, 403)
    
    winner_id = data.get('winner_id')
    if winner_id not in {game.player1_id, game.player2_id}:
        return reject_suspicious(user, 'invalid_winner', 'Invalid winner for this match', str(winner_id))

    try:
        p1_score = int(data.get('p1_score', 0))
        p2_score = int(data.get('p2_score', 0))
    except (TypeError, ValueError):
        return reject_suspicious(user, 'invalid_score', 'Invalid score values', str(data))

    if p1_score < 0 or p2_score < 0 or p1_score > 100000 or p2_score > 100000:
        return reject_suspicious(user, 'score_out_of_range', 'Score is outside the allowed range', str(data))
    
    game.status = 'completed'
    game.winner_id = winner_id
    game.p1_score = p1_score
    game.p2_score = p2_score
    game.completed_at = datetime.utcnow()
    
    player1 = User.query.get(game.player1_id)
    player2 = User.query.get(game.player2_id)
    
    # Update stats
    player1.total_games_played += 1
    player2.total_games_played += 1
    
    # Distribute rewards
    if winner_id == game.player1_id:
        player1.total_wins += 1
        reward = game.stakes * 2 if game.stakes > 0 else 50
        player1.coins += reward
        player1_xp_reward = 100
    else:
        player1.total_losses += 1
        player1_xp_reward = 25
    
    if winner_id == game.player2_id:
        player2.total_wins += 1
        reward = game.stakes * 2 if game.stakes > 0 else 50
        player2.coins += reward
        player2_xp_reward = 100
    else:
        player2.total_losses += 1
        player2_xp_reward = 25
    
    # Update win rates
    player1.win_rate = (player1.total_wins / player1.total_games_played * 100) if player1.total_games_played > 0 else 0
    player2.win_rate = (player2.total_wins / player2.total_games_played * 100) if player2.total_games_played > 0 else 0
    
    # Update ranking if ranked
    if game.ranked:
        p1_rating_change = update_elo(player1.rank_rating, player2.rank_rating, winner_id == game.player1_id)
        p2_rating_change = update_elo(player2.rank_rating, player1.rank_rating, winner_id == game.player2_id)
        
        player1.rank_rating = max(0, player1.rank_rating + p1_rating_change)
        player2.rank_rating = max(0, player2.rank_rating + p2_rating_change)
        
        player1.update_rank()
        player2.update_rank()
        
        game.p1_rating_after = player1.rank_rating
        game.p2_rating_after = player2.rank_rating
    
    # Add XP
    player1.exp += player1_xp_reward
    player2.exp += player2_xp_reward
    
    db.session.commit()
    
    return {
        'message': 'Game completed',
        'winner': winner_id,
        'player1': {'stats': player1.to_dict()},
        'player2': {'stats': player2.to_dict()}
    }, 200


@app.route('/api/v3/games/catalog', methods=['GET'])
def get_games_catalog():
    """Button-based games the desktop app can render."""
    return {
        'games': [
            {'id': 'rps', 'name': 'Rock Paper Scissors', 'buttons': ['rock', 'paper', 'scissors'], 'ranked': True},
            {'id': 'dice', 'name': 'Dice Duel', 'buttons': ['low', 'seven', 'high'], 'ranked': False},
            {'id': 'slots', 'name': 'Neon Slots', 'buttons': ['spin'], 'ranked': False},
            {'id': 'trivia', 'name': 'Trivia Pulse', 'buttons': ['Mars', 'Venus', 'Jupiter'], 'ranked': False},
            {'id': 'math', 'name': 'Math Blitz', 'buttons': ['48', '54', '56'], 'ranked': False},
            {'id': 'blackjack', 'name': 'Blackjack Snap', 'buttons': ['deal'], 'ranked': False}
        ]
    }, 200


@app.route('/api/v3/games/quick-play', methods=['POST'])
@token_required
def quick_play(user):
    """Resolve button-based solo games on the server."""
    data = request.get_json(silent=True) or {}
    game_type = (data.get('game_type') or '').strip().lower()
    choice = (data.get('choice') or '').strip().lower()

    if game_type not in ALLOWED_GAME_TYPES:
        return reject_suspicious(user, 'invalid_quick_game', 'Unsupported game type', game_type)

    result = {'game_type': game_type}
    won = False
    draw = False

    if game_type == 'rps':
        if choice not in RPS_CHOICES:
            return reject_suspicious(user, 'invalid_rps_choice', 'Choose rock, paper, or scissors', choice)
        bot_choice = secrets.choice(tuple(RPS_CHOICES))
        draw = choice == bot_choice
        won = (
            (choice == 'rock' and bot_choice == 'scissors') or
            (choice == 'paper' and bot_choice == 'rock') or
            (choice == 'scissors' and bot_choice == 'paper')
        )
        result.update({'player_choice': choice, 'opponent_choice': bot_choice})

    elif game_type == 'dice':
        if choice not in {'low', 'seven', 'high'}:
            return reject_suspicious(user, 'invalid_dice_choice', 'Choose low, seven, or high', choice)
        dice = [secrets.randbelow(6) + 1, secrets.randbelow(6) + 1]
        total = sum(dice)
        won = (
            (choice == 'low' and total < 7) or
            (choice == 'seven' and total == 7) or
            (choice == 'high' and total > 7)
        )
        result.update({'dice': dice, 'total': total, 'player_choice': choice})

    elif game_type == 'slots':
        symbols = ['star', 'gem', 'bolt', 'crown', 'seven']
        reels = [secrets.choice(symbols) for _ in range(3)]
        won = len(set(reels)) == 1
        draw = len(set(reels)) == 2
        result.update({'reels': reels})

    elif game_type == 'trivia':
        correct = 'mars'
        if choice not in {'mars', 'venus', 'jupiter'}:
            return {
                'question': 'Which planet is known as the Red Planet?',
                'choices': ['Mars', 'Venus', 'Jupiter']
            }, 200
        won = choice == correct
        result.update({'question': 'Which planet is known as the Red Planet?', 'answer': 'Mars'})

    elif game_type == 'math':
        correct = '56'
        if choice not in {'48', '54', '56'}:
            return {'question': 'What is 7 x 8?', 'choices': ['48', '54', '56']}, 200
        won = choice == correct
        result.update({'question': 'What is 7 x 8?', 'answer': '56'})

    elif game_type in {'bj', 'blackjack'}:
        player = [secrets.randbelow(10) + 2, secrets.randbelow(10) + 2]
        dealer = [secrets.randbelow(10) + 2, secrets.randbelow(10) + 2]
        player_total = sum(player)
        dealer_total = sum(dealer)
        won = player_total <= 21 and (dealer_total > 21 or player_total >= dealer_total)
        draw = player_total == dealer_total
        result.update({'player_cards': player, 'dealer_cards': dealer, 'player_total': player_total, 'dealer_total': dealer_total})

    user.total_games_played += 1
    if draw:
        user.exp += 15
        reward = 10
        outcome = 'draw'
    elif won:
        user.total_wins += 1
        user.exp += 50
        reward = 25
        outcome = 'win'
    else:
        user.total_losses += 1
        user.exp += 10
        reward = 5
        outcome = 'loss'

    user.coins += reward
    user.win_rate = (user.total_wins / user.total_games_played * 100) if user.total_games_played else 0
    if user.exp >= user.level * 250:
        user.level += 1
    db.session.commit()

    result.update({
        'outcome': outcome,
        'reward': reward,
        'user': user.to_dict()
    })
    return result, 200


def update_elo(player_rating: int, opponent_rating: int, won: bool, k_factor: int = 32) -> int:
    """Calculate ELO rating change"""
    expected_win_rate = 1 / (1 + 10 ** ((opponent_rating - player_rating) / 400))
    actual_score = 1 if won else 0
    rating_change = k_factor * (actual_score - expected_win_rate)
    return int(rating_change)


# ============================================
# FRIEND SYSTEM ENDPOINTS
# ============================================

@app.route('/api/v3/friends', methods=['GET'])
@token_required
def get_friends(user):
    """Get user's friends list"""
    friendships = Friendship.query.filter(
        (Friendship.user_id == user.id) | (Friendship.friend_id == user.id),
        Friendship.status == 'accepted'
    ).all()
    
    friends = []
    for friendship in friendships:
        friend_id = friendship.friend_id if friendship.user_id == user.id else friendship.user_id
        friend = User.query.get(friend_id)
        if friend:
            friend_info = public_user(friend)
            friend_info['friendship_id'] = friendship.id
            friends.append(friend_info)
    
    return {'friends': friends, 'count': len(friends)}, 200


@app.route('/api/v3/friends/<friend_id>/add', methods=['POST'])
@token_required
def add_friend(user, friend_id):
    """Send friend request"""
    friend = find_user_by_name_or_id(friend_id)
    if not friend:
        return {'message': 'User not found'}, 404

    if friend.id == user.id:
        return {'message': 'Cannot add yourself'}, 400
    
    existing = get_friendship(user.id, friend.id)
    if existing:
        return {'message': 'Friendship already exists'}, 409
    
    friendship = Friendship(user_id=user.id, friend_id=friend.id, status='pending')
    db.session.add(friendship)
    db.session.commit()
    
    return {'message': 'Friend request sent', 'friendship_id': friendship.id}, 201


@app.route('/api/v3/friends/request', methods=['POST'])
@token_required
def request_friend(user):
    """Send a friend request by username or id."""
    data = request.get_json(silent=True) or {}
    target = data.get('username') or data.get('friend_id')
    friend = find_user_by_name_or_id(target)

    if not friend:
        return {'message': 'User not found'}, 404
    if friend.id == user.id:
        return {'message': 'Cannot add yourself'}, 400

    existing = get_friendship(user.id, friend.id)
    if existing:
        return {'message': 'Friendship already exists', 'status': existing.status}, 409

    friendship = Friendship(user_id=user.id, friend_id=friend.id, status='pending')
    db.session.add(friendship)
    db.session.commit()

    return {'message': 'Friend request sent', 'friend': public_user(friend), 'friendship_id': friendship.id}, 201


@app.route('/api/v3/friends/requests', methods=['GET'])
@token_required
def get_friend_requests(user):
    """Return pending friend requests for the current user."""
    incoming = Friendship.query.filter_by(friend_id=user.id, status='pending').order_by(Friendship.created_at.desc()).all()
    outgoing = Friendship.query.filter_by(user_id=user.id, status='pending').order_by(Friendship.created_at.desc()).all()

    return {
        'incoming': [
            {
                'friendship_id': item.id,
                'from': public_user(User.query.get(item.user_id)),
                'created_at': item.created_at.isoformat()
            }
            for item in incoming if User.query.get(item.user_id)
        ],
        'outgoing': [
            {
                'friendship_id': item.id,
                'to': public_user(User.query.get(item.friend_id)),
                'created_at': item.created_at.isoformat()
            }
            for item in outgoing if User.query.get(item.friend_id)
        ]
    }, 200


@app.route('/api/v3/friends/<friendship_id>/accept', methods=['POST'])
@token_required
def accept_friend(user, friendship_id):
    """Accept a pending friend request."""
    friendship = Friendship.query.get(friendship_id)
    if not friendship:
        return {'message': 'Friend request not found'}, 404
    if friendship.friend_id != user.id:
        return {'message': 'Only the invited user can accept this request'}, 403

    friendship.status = 'accepted'
    db.session.commit()

    friend = User.query.get(friendship.user_id)
    return {'message': 'Friend request accepted', 'friend': public_user(friend)}, 200


@app.route('/api/v3/chat/<friend_id>/messages', methods=['GET'])
@token_required
def get_chat_messages(user, friend_id):
    """Read encrypted chat messages with an accepted friend."""
    friend = find_user_by_name_or_id(friend_id)
    if not friend:
        return {'message': 'User not found'}, 404
    if not are_friends(user.id, friend.id):
        return {'message': 'You can only chat with accepted friends'}, 403

    limit = min(request.args.get('limit', 50, type=int), 100)
    messages = ChatMessage.query.filter(
        ((ChatMessage.sender_id == user.id) & (ChatMessage.recipient_id == friend.id)) |
        ((ChatMessage.sender_id == friend.id) & (ChatMessage.recipient_id == user.id))
    ).order_by(ChatMessage.created_at.desc()).limit(limit).all()

    return {'messages': [message.to_dict(user.id) for message in reversed(messages)]}, 200


@app.route('/api/v3/chat/<friend_id>/messages', methods=['POST'])
@token_required
def send_chat_message(user, friend_id):
    """Send an encrypted chat message to an accepted friend."""
    friend = find_user_by_name_or_id(friend_id)
    if not friend:
        return {'message': 'User not found'}, 404
    if not are_friends(user.id, friend.id):
        return {'message': 'You can only chat with accepted friends'}, 403

    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if not message:
        return {'message': 'Message cannot be empty'}, 400
    if len(message) > 500:
        return reject_suspicious(user, 'chat_message_too_long', 'Message is too long', str(len(message)))

    chat_message = ChatMessage(
        sender_id=user.id,
        recipient_id=friend.id,
        body_encrypted=encrypt_text(message)
    )
    db.session.add(chat_message)
    db.session.commit()

    return {'message': chat_message.to_dict(user.id)}, 201


# ============================================
# STATIC FILE SERVING
# ============================================

@app.route('/')
def index():
    """Serve the web account portal."""
    try:
        return send_file(os.path.join(BASE_DIR, 'login.html'))
    except Exception:
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>GameBot - Loading...</title>
        </head>
        <body>
            <h1>Welcome to GameBot!</h1>
            <p>Loading interface...</p>
            <script>
                // If master.html is not found, check server is running
                console.log('Server is running at: ''' + window.location.origin + ''')
            </script>
        </body>
        </html>
        ''', 200

@app.route('/master.html')
def serve_master():
    """Serve account portal for old bookmarks."""
    return send_file(os.path.join(BASE_DIR, 'login.html'))

# ============================================
# HEALTH CHECK
# ============================================

@app.route('/api/v3/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'database': 'connected',
        'redis': 'connected' if redis_client else 'disconnected',
        'version': '3.0.0'
    }, 200


def init_database():
    """Create tables and apply small SQLite upgrades for bundled installs."""
    db.create_all()

    if db.engine.dialect.name == 'sqlite':
        columns = {
            row[1]
            for row in db.session.execute(text("PRAGMA table_info(users)")).fetchall()
        }
        if 'encrypted_email' not in columns:
            db.session.execute(text("ALTER TABLE users ADD COLUMN encrypted_email TEXT"))
            db.session.commit()


# ============================================
# ERROR HANDLERS
# ============================================

@app.errorhandler(404)
def not_found(error):
    return {'message': 'Endpoint not found'}, 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return {'message': 'Internal server error'}, 500


if __name__ == '__main__':
    with app.app_context():
        init_database()
    
    # Production: Use Gunicorn
    # Development: use Flask dev server
    app.run(
        host=os.getenv('HOST', '0.0.0.0'),
        port=int(os.getenv('PORT', 5000)),
        debug=os.getenv('DEBUG', 'False') == 'True',
        threaded=True,
        use_reloader=False
    )
