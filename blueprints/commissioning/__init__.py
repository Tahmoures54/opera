"""OPERA commissioning blueprints."""
from flask import Blueprint

commissioning_bp = Blueprint("commissioning", __name__, url_prefix="/commissioning")

from blueprints.commissioning import project  # noqa: E402,F401
