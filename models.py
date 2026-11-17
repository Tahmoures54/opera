import enum
import re
from datetime import datetime
import pytz
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from config.config import Config
from flask_login import UserMixin
from sqlalchemy import Enum
from extensions import db


class ValidationError(Exception):
    """Custom exception for model validation errors."""


class AccessLevel(enum.Enum):
    project_manager = 'project_manager'
    engineering = 'engineering'
    purchase = 'purchase'
    quality = 'quality'
    delivery = 'delivery'
    warehouse = 'warehouse'
    supplier = 'supplier'


class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    company_email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    company_phone = db.Column(db.String(20), nullable=True)
    full_name = db.Column(db.String(100), nullable=False)
    company_address = db.Column(db.String(200), nullable=False)
    country = db.Column(db.String(2), nullable=False)
    access_level = db.Column(Enum(AccessLevel), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    password_hash = db.Column(db.String(128), nullable=True)
    totp_secret = db.Column(db.String(512), nullable=True)
    qr_code_base64 = db.Column(db.Text, nullable=True)
    totp_confirmed = db.Column(db.Boolean, default=False)
    # Incrementing this revokes already-issued Flask-Login sessions.
    auth_version = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    trial_started_at = db.Column(db.DateTime, nullable=True, index=True)
    trial_ends_at = db.Column(db.DateTime, nullable=True, index=True)
    subscription_plan = db.Column(db.String(30), nullable=False, default='trial')
    subscription_status = db.Column(db.String(20), nullable=False, default='trial')

    def __init__(self, **kwargs):
        password = kwargs.pop('password', None)
        super().__init__(**kwargs)
        self.validate(kwargs)
        if password:
            self.set_password(password)

    def validate(self, kwargs):
        if 'company_email' in kwargs:
            self.validate_email(kwargs['company_email'])
        if 'company_phone' in kwargs and kwargs['company_phone']:
            self.validate_phone(kwargs['company_phone'])
        if 'password' in kwargs:
            self.set_password(kwargs['password'])
        if 'full_name' in kwargs and not kwargs['full_name'].strip():
            raise ValidationError('Full name cannot be empty')
        if 'company_address' in kwargs and not kwargs['company_address'].strip():
            raise ValidationError('Company address cannot be empty')
        if 'country' in kwargs and not kwargs['country'].strip():
            raise ValidationError('Country cannot be empty')

    @staticmethod
    def _password_hasher():
        from argon2 import PasswordHasher
        return PasswordHasher()

    @staticmethod
    def _totp_cipher():
        key_material = Config.SECRET_KEY.encode('utf-8')
        key = base64.urlsafe_b64encode(hashlib.sha256(key_material).digest())
        return Fernet(key)

    @classmethod
    def encrypt_totp_secret(cls, secret):
        if not secret:
            return None
        return 'enc:' + cls._totp_cipher().encrypt(secret.encode('utf-8')).decode('ascii')

    def decrypt_totp_secret(self):
        if not self.totp_secret:
            raise ValidationError('TOTP secret not set')
        if not self.totp_secret.startswith('enc:'):
            return self.totp_secret
        try:
            return self._totp_cipher().decrypt(
                self.totp_secret[4:].encode('ascii')
            ).decode('utf-8')
        except (InvalidToken, ValueError, UnicodeDecodeError) as exc:
            raise ValidationError('Stored TOTP secret cannot be decrypted') from exc

    def set_totp_secret(self, secret):
        self.totp_secret = self.encrypt_totp_secret(secret)

    def set_password(self, password):
        if password:
            if len(password) < 8:
                raise ValidationError('Password must be at least 8 characters long')
            self.password_hash = self._password_hasher().hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        hasher = self._password_hasher()
        try:
            valid = hasher.verify(self.password_hash, password)
        except Exception:
            from werkzeug.security import check_password_hash
            try:
                valid = check_password_hash(self.password_hash, password)
            except Exception:
                return False
            if valid:
                self.password_hash = hasher.hash(password)
        else:
            if valid and hasher.check_needs_rehash(self.password_hash):
                self.password_hash = hasher.hash(password)
        return bool(valid)

    def validate_email(self, email):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValidationError('Invalid email format')
        return email

    def validate_phone(self, phone):
        pattern = r'^\+?[1-9]\d{1,14}$'
        if not re.match(pattern, phone):
            raise ValidationError('Invalid phone number format')
        return phone

    def get_totp_uri(self):
        if not self.totp_secret:
            raise ValidationError('TOTP secret not set')
        secret = self.decrypt_totp_secret()
        return f"otpauth://totp/OPERA:{self.company_email}?secret={secret}&issuer=OPERA"

    def to_dict(self):
        return {
            'id': self.id,
            'company_name': self.company_name,
            'company_email': self.company_email,
            'company_phone': self.company_phone,
            'full_name': self.full_name,
            'company_address': self.company_address,
            'country': self.country,
            'access_level': self.access_level.value,
            'is_admin': self.is_admin,
            'totp_confirmed': self.totp_confirmed,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    @property
    def trial_active(self):
        if self.subscription_status == 'active':
            return True
        if self.subscription_status != 'trial' or not self.trial_ends_at:
            return False
        end = self.trial_ends_at
        if end.tzinfo is None:
            end = pytz.UTC.localize(end)
        return datetime.now(pytz.UTC) < end

    @property
    def trial_days_remaining(self):
        if self.subscription_status == 'active':
            return None
        if not self.trial_ends_at:
            return 0
        end = self.trial_ends_at
        if end.tzinfo is None:
            end = pytz.UTC.localize(end)
        return max(0, (end - datetime.now(pytz.UTC)).days)

    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f"<User {self.company_email}: {self.access_level.value}>"


class ContactInquiry(db.Model):
    """Inbound demo / sales requests from the public growth funnel."""
    __tablename__ = 'contact_inquiry'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    # Keep these limits aligned with the public contact form and practical email limits.
    email = db.Column(db.String(254), nullable=False, index=True)
    company = db.Column(db.String(160), nullable=True)
    message = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(50), nullable=False, default='website')
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'company': self.company,
            'message': self.message,
            'source': self.source,
            'created_at': self.created_at.isoformat(),
        }

    def __repr__(self):
        return f"<ContactInquiry {self.email}>"



class AccountRecoveryToken(db.Model):
    """Single-use, short-lived token for recovering a user's TOTP authenticator."""
    __tablename__ = "account_recovery_token"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used_at = db.Column(db.DateTime, nullable=True)
    pending_totp_secret = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    user = db.relationship("User", backref=db.backref("recovery_tokens", lazy=True, cascade="all, delete-orphan"))
