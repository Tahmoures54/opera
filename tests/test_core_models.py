"""Regression tests for OPERA's retained identity and numbering models."""
import pytest
import pyotp
from werkzeug.security import generate_password_hash

from extensions import db
from models import (
    AccessLevel,
    AccountRecoveryToken,
    DocumentSequence,
    User,
    ValidationError,
)


def make_user(email="user@example.com", company="Acme"):
    return User(
        company_name=company,
        company_email=email,
        company_phone="+989121234567",
        full_name="Test User",
        company_address="Test Address",
        country="IR",
        access_level=AccessLevel.engineering,
        totp_confirmed=True,
    )


def test_user_password_totp_and_serialization(app):
    with app.app_context():
        user = make_user()
        user.set_password("StrongPassword123")
        db.session.add(user)
        db.session.commit()

        assert user.check_password("StrongPassword123")
        assert not user.check_password("wrong")
        secret = pyotp.random_base32()
        user.set_totp_secret(secret)
        assert user.totp_secret.startswith("enc:")
        assert user.decrypt_totp_secret() == secret
        assert "OPERA" in user.get_totp_uri()
        payload = user.to_dict()
        assert payload["company_email"] == user.company_email
        assert secret not in str(payload)
        assert "project_id" not in payload
        assert "store_name" not in payload


def test_user_legacy_werkzeug_hash_is_rehashed(app):
    with app.app_context():
        user = make_user("legacy@example.com")
        user.password_hash = generate_password_hash("LegacyPassword123")
        assert user.check_password("LegacyPassword123")
        assert user.password_hash.startswith("$argon2")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"company_email": "bad"},
        {"company_phone": "0"},
        {"full_name": ""},
        {"company_address": ""},
        {"country": ""},
    ],
)
def test_user_rejects_invalid_identity_data(app, kwargs):
    with app.app_context():
        values = dict(
            company_name="Acme",
            company_email="valid@example.com",
            company_phone="+989121234567",
            full_name="Valid User",
            company_address="Address",
            country="IR",
            access_level=AccessLevel.engineering,
        )
        values.update(kwargs)
        with pytest.raises(ValidationError):
            User(**values)


def test_document_sequences_increment_per_tenant_and_key(app):
    with app.app_context():
        first = DocumentSequence(key="CS-PREA", company_name="Acme", last_value=0)
        second = DocumentSequence(key="CS-PREA", company_name="Other", last_value=0)
        db.session.add_all([first, second])
        db.session.commit()

        assert first.next_value() == 1
        assert first.next_value() == 2
        assert second.next_value() == 1


def test_account_recovery_token_is_linked_to_user(app):
    with app.app_context():
        user = make_user("recovery@example.com")
        db.session.add(user)
        db.session.flush()
        token = AccountRecoveryToken(
            user_id=user.id,
            token_hash="a" * 64,
            expires_at=__import__("datetime").datetime(2030, 1, 1),
        )
        db.session.add(token)
        db.session.commit()
        assert user.recovery_tokens[0].token_hash == "a" * 64
