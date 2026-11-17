"""OPERA commissioning blueprints."""
from flask import Blueprint

commissioning_bp = Blueprint("commissioning", __name__, url_prefix="/commissioning")

from blueprints.commissioning import project  # noqa: E402,F401

from blueprints.commissioning import workflow  # noqa: E402,F401
from blueprints.commissioning import import_export  # noqa: E402,F401

from blueprints.commissioning import preservation  # noqa: E402,F401
