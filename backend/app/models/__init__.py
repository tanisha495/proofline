"""ProofLine SQLAlchemy models.

Import all models here so Alembic's env.py can discover every table's
metadata via ``Base.metadata`` after a single ``import app.models``.
"""
from app.models._base import Base  # noqa: F401 – re-exported for convenience

# Core tables (order matters for FK resolution in metadata)
from app.models.organisation import Organisation  # noqa: F401
from app.models.user import User  # noqa: F401

# Source / knowledge-base tables
from app.models.source import GuidelineRule, Fact, Term  # noqa: F401

# Draft lifecycle
from app.models.draft import Draft, DraftVersion  # noqa: F401

# Review artefacts
from app.models.finding import Finding  # noqa: F401
from app.models.claim_receipt import Claim, ClaimReceipt  # noqa: F401

# Workflow
from app.models.comment import Comment  # noqa: F401
from app.models.approval import Approval  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401

__all__ = [
    "Base",
    "Organisation",
    "User",
    "GuidelineRule",
    "Fact",
    "Term",
    "Draft",
    "DraftVersion",
    "Finding",
    "Claim",
    "ClaimReceipt",
    "Comment",
    "Approval",
    "AuditLog",
]
