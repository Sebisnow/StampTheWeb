from flask import Blueprint

main = Blueprint('main', __name__)

from . import views, errors
from ..models import Permission, Regular

from app.main import downloader


@main.app_context_processor
def inject_permissions():
    return dict(Permission=Permission)
