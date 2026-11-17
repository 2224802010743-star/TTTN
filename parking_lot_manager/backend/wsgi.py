"""WSGI entrypoint for Waitress. Keeps runtime checks active when imported."""
from app import app, validate_runtime_config

validate_runtime_config()
