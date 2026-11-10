"""Drafts router."""
from __future__ import annotations

import hashlib
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.roles import require_role
from app.db import get_db
from app.models.claim_receipt import Claim, ClaimReceipt
from app.models.comment import Comment
from app.models.draft import Draft, DraftVersion
from app.models.finding import Finding
from app.models.user import User
from app.services.parsing.parser import parse_document
from app.services.review.engine import execute_full_review
from app.services.review.intent_lock import compute_side_by_side_diff, verify_intent_preservation
from app.services.workflow.approval_service import record_approval_decision, request_human_review

router = APIRouter(prefix="/drafts", tags=["drafts"])


class DraftCreateRequest(BaseModel):
    content: str
    title: Optional[str] = None
    channel: Optional[str] = None
    intent_lock: Optional[Dict[str, Any]] = None


class DraftVersionCreateRequest(BaseModel):
    content: str
    intent_lock: Optional[Dict[str, Any]] = None


class CommentCreateRequest(BaseModel):
    text: str
    range_start: Optional[int] = None
    range_end: Optional[int] = None


class DecisionRequest(BaseModel):
    decision: str
    reason: Optional[str] = None
    override_reason: Optional[str] = None


class DiffRequest(BaseModel):
    original_text: str
    revised_text: str


def _parse_uuid(value: str, label: str = "ID") -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {label}") from exc


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_draft(
    req: DraftCreateRequest,
    current_user: User = Depends(require_role("creator")),
    db: Session = Depends(get_db),
):
    """Create a new draft with initial version 1."""
    draft = Draft(
        organisation_id=current_user.organisation_id,
        owner_id=current_user.id,
        title=req.title,
        channel=req.channel,
        status="draft",
        intent_lock=req.intent_lock or {},
        current_version_number=1,
    )
    db.add(draft)
    db.flush()

    version = DraftVersion(
        organisation_id=current_user.organisation_id,
        draft_id=draft.id,
        version_number=1,
        content=req.content,
        content_hash=_content_hash(req.content),
        created_by=current_user.id,
    )
    db.add(version)
    db.flush()

    log_action(
        db=db,
        organisation_id=current_user.organisation_id,
        user_id=current_user.id,
        action="draft_created",
        entity="draft",
        entity_id=draft.id,
        details={"channel": draft.channel, "content_length": len(req.content)},
    )
    db.commit()
    db.refresh(draft)

    return {
        "id": str(draft.id),
        "organisation_id": str(draft.organisation_id),
        "created_by": str(draft.owner_id),
        "title": draft.title,
        "channel": draft.channel,
        "status": draft.status,
        "created_at": draft.created_at,
    }


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document_draft(
    file: UploadFile = File(...),
    channel: Optional[str] = None,
    current_user: User = Depends(require_role("creator")),
    db: Session = Depends(get_db),
):
    """Upload a PDF, DOCX, or text file and automatically create a new draft."""
    file_bytes = await file.read()
    try:
        extracted_text, detected_type = parse_document(file.filename or "uploaded_doc", file_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse document: {str(exc)}",
        ) from exc

    draft = Draft(
        organisation_id=current_user.organisation_id,
        owner_id=current_user.id,
        title=file.filename,
        channel=channel or f"Upload: {file.filename}",
        status="draft",
        intent_lock={},
        current_version_number=1,
    )
    db.add(draft)
    db.flush()

    version = DraftVersion(
        organisation_id=current_user.organisation_id,
        draft_id=draft.id,
        version_number=1,
        content=extracted_text,
        content_hash=_content_hash(extracted_text),
        created_by=current_user.id,
    )
    db.add(version)
    db.flush()

    log_action(
        db=db,
        organisation_id=current_user.organisation_id,
        user_id=current_user.id,
        action="draft_uploaded",
        entity="draft",
        entity_id=draft.id,
        details={"filename": file.filename, "file_type": detected_type},
    )
    db.commit()
    db.refresh(draft)

    return {
        "id": str(draft.id),
        "filename": file.filename,
        "detected_type": detected_type,
        "content_length": len(extracted_text),
        "status": draft.status,
    }


@router.get("")
async def list_drafts(
    current_user: User = Depends(require_role("creator", "reviewer", "admin")),
    db: Session = Depends(get_db),
):
    """List drafts for current organisation."""
    drafts = db.scalars(
        select(Draft)
        .where(Draft.organisation_id == current_user.organisation_id)
        .order_by(desc(Draft.created_at))
    ).all()

    items = []
    for d in drafts:
        latest_ver = db.scalars(
            select(DraftVersion)
            .where(DraftVersion.draft_id == d.id)
            .order_by(desc(DraftVersion.version_number))
        ).first()

        items.append(
            {
                "id": str(d.id),
                "title": d.title,
                "channel": d.channel,
                "status": d.status,
                "created_at": d.created_at,
                "created_by": str(d.owner_id),
                "latest_version": latest_ver.version_number if latest_ver else 1,
                "content_preview": (latest_ver.content[:120] + "...") if latest_ver else "",
            }
        )

    return items


@router.get("/{draft_id}")
async def get_draft(
    draft_id: str,
    current_user: User = Depends(require_role("creator", "reviewer", "admin")),
    db: Session = Depends(get_db),
):
    """Retrieve draft details and latest version content."""
    draft_uuid = _parse_uuid(draft_id, "draft_id")
    draft = db.get(Draft, draft_uuid)
    if not draft or draft.organisation_id != current_user.organisation_id:
        raise HTTPException(status_code=404, detail="Draft not found")

    latest_ver = db.scalars(
        select(DraftVersion)
        .where(DraftVersion.draft_id == draft.id)
        .order_by(desc(DraftVersion.version_number))
    ).first()

    return {
        "id": str(draft.id),
        "title": draft.title,
        "channel": draft.channel,
        "status": draft.status,
        "intent_lock": draft.intent_lock,
        "created_at": draft.created_at,
        "created_by": str(draft.owner_id),
        "latest_version": latest_ver.version_number if latest_ver else 1,
        "content": latest_ver.content if latest_ver else "",
    }


@router.post("/{draft_id}/versions", status_code=status.HTTP_201_CREATED)
async def create_draft_version(
    draft_id: str,
    req: DraftVersionCreateRequest,
    current_user: User = Depends(require_role("creator")),
    db: Session = Depends(get_db),
):
    """Create a new immutable version for an existing draft."""
    draft_uuid = _parse_uuid(draft_id, "draft_id")
    draft = db.get(Draft, draft_uuid)
    if not draft or draft.organisation_id != current_user.organisation_id:
        raise HTTPException(status_code=404, detail="Draft not found")

    next_ver_num = (draft.current_version_number or 1) + 1
    draft.current_version_number = next_ver_num
    if req.intent_lock is not None:
        draft.intent_lock = req.intent_lock
    draft.status = "draft"

    version = DraftVersion(
        organisation_id=draft.organisation_id,
        draft_id=draft.id,
        version_number=next_ver_num,
        content=req.content,
        content_hash=_content_hash(req.content),
        created_by=current_user.id,
    )
    db.add(version)
    db.flush()

    log_action(
        db=db,
        organisation_id=draft.organisation_id,
        user_id=current_user.id,
        action="draft_version_created",
        entity="draft_version",
        entity_id=version.id,
        details={"draft_id": str(draft.id), "version_number": next_ver_num},
    )
    db.commit()

    return {
        "draft_id": str(draft.id),
        "version_id": str(version.id),
        "version_number": next_ver_num,
    }


@router.post("/{draft_id}/review", status_code=status.HTTP_202_ACCEPTED)
async def trigger_review(
    draft_id: str,
    current_user: User = Depends(require_role("creator")),
    db: Session = Depends(get_db),
):
    """Trigger automated 4-layer review of draft's latest version."""
    draft_uuid = _parse_uuid(draft_id, "draft_id")
    draft = db.get(Draft, draft_uuid)
    if not draft or draft.organisation_id != current_user.organisation_id:
        raise HTTPException(status_code=404, detail="Draft not found")

    latest_ver = db.scalars(
        select(DraftVersion)
        .where(DraftVersion.draft_id == draft.id)
        .order_by(desc(DraftVersion.version_number))
    ).first()

    if not latest_ver:
        raise HTTPException(status_code=400, detail="Draft has no content versions")

    return execute_full_review(db, draft, latest_ver, current_user.id)


@router.get("/{draft_id}/versions/{version}/findings")
async def get_findings(
    draft_id: str,
    version: int,
    current_user: User = Depends(require_role("creator", "reviewer")),
    db: Session = Depends(get_db),
):
    """Get all findings for a specific draft version."""
    draft_uuid = _parse_uuid(draft_id, "draft_id")
    draft = db.get(Draft, draft_uuid)
    if not draft or draft.organisation_id != current_user.organisation_id:
        raise HTTPException(status_code=404, detail="Draft not found")

    target_ver = db.scalars(
        select(DraftVersion).where(
            DraftVersion.draft_id == draft.id,
            DraftVersion.version_number == version,
        )
    ).first()

    if not target_ver:
        return []

    findings = db.scalars(
        select(Finding).where(Finding.version_id == target_ver.id)
    ).all()

    return [
        {
            "id": str(f.id),
            "draft_id": str(f.draft_id),
            "version_id": str(f.version_id),
            "quoted_text": f.quoted_text or "",
            "start": f.start_offset,
            "end": f.end_offset,
            "severity": f.severity,
            "reason": f.reason,
            "source_type": f.source_type,
            "source_ref": f.source_ref,
            "source_version": f.source_version or 1,
            "confidence": f.confidence,
            "suggestion": f.suggestion,
            "status": f.status,
            "dismissal_reason": f.dismissal_reason,
        }
        for f in findings
    ]


@router.get("/{draft_id}/versions/{version}/claims")
async def get_claims(
    draft_id: str,
    version: int,
    current_user: User = Depends(require_role("creator", "reviewer")),
    db: Session = Depends(get_db),
):
    """Get Claim Ledger items for a specific draft version."""
    draft_uuid = _parse_uuid(draft_id, "draft_id")
    draft = db.get(Draft, draft_uuid)
    if not draft or draft.organisation_id != current_user.organisation_id:
        raise HTTPException(status_code=404, detail="Draft not found")

    target_ver = db.scalars(
        select(DraftVersion).where(
            DraftVersion.draft_id == draft.id,
            DraftVersion.version_number == version,
        )
    ).first()

    if not target_ver:
        return []

    claims = db.scalars(
        select(Claim).where(Claim.version_id == target_ver.id)
    ).all()

    return [
        {
            "id": str(c.id),
            "draft_id": str(draft.id),
            "version_id": str(c.version_id),
            "quoted_text": c.claim_text,
            "status": c.status,
            "source_ref": c.evidence_fact_key,
            "evidence_version": c.evidence_version,
            "created_at": c.created_at,
        }
        for c in claims
    ]


@router.post("/{draft_id}/diff")
async def compute_diff(
    draft_id: str,
    req: DiffRequest,
    current_user: User = Depends(require_role("creator", "reviewer", "admin")),
    db: Session = Depends(get_db),
):
    """Compute visual side-by-side diff and check Intent Lock message preservation."""
    draft_uuid = _parse_uuid(draft_id, "draft_id")
    draft = db.get(Draft, draft_uuid)
    if not draft or draft.organisation_id != current_user.organisation_id:
        raise HTTPException(status_code=404, detail="Draft not found")

    diff_tokens = compute_side_by_side_diff(req.original_text, req.revised_text)
    intent_eval = verify_intent_preservation(req.original_text, req.revised_text, draft.intent_lock)

    return {
        "diff_tokens": diff_tokens,
        "intent_preservation": intent_eval,
    }


@router.post("/{draft_id}/request-review", status_code=status.HTTP_202_ACCEPTED)
async def trigger_request_review(
    draft_id: str,
    current_user: User = Depends(require_role("creator")),
    db: Session = Depends(get_db),
):
    """Request human review of the draft, evaluating risk tier."""
    draft_uuid = _parse_uuid(draft_id, "draft_id")
    draft = db.get(Draft, draft_uuid)
    if not draft or draft.organisation_id != current_user.organisation_id:
        raise HTTPException(status_code=404, detail="Draft not found")

    return request_human_review(db, draft, current_user)


@router.post("/{draft_id}/comments", status_code=status.HTTP_201_CREATED)
async def add_comment(
    draft_id: str,
    req: CommentCreateRequest,
    current_user: User = Depends(require_role("creator", "reviewer")),
    db: Session = Depends(get_db),
):
    """Add a comment to a draft."""
    draft_uuid = _parse_uuid(draft_id, "draft_id")
    draft = db.get(Draft, draft_uuid)
    if not draft or draft.organisation_id != current_user.organisation_id:
        raise HTTPException(status_code=404, detail="Draft not found")

    latest_ver = db.scalars(
        select(DraftVersion)
        .where(DraftVersion.draft_id == draft.id)
        .order_by(desc(DraftVersion.version_number))
    ).first()
    if not latest_ver:
        raise HTTPException(status_code=400, detail="Draft has no version")

    comment = Comment(
        organisation_id=draft.organisation_id,
        draft_id=draft.id,
        version_id=latest_ver.id,
        author_id=current_user.id,
        body=req.text,
        range_start=req.range_start,
        range_end=req.range_end,
    )
    db.add(comment)
    db.flush()

    log_action(
        db=db,
        organisation_id=draft.organisation_id,
        user_id=current_user.id,
        action="comment_added",
        entity="comment",
        entity_id=comment.id,
        details={"draft_id": str(draft.id)},
    )
    db.commit()
    db.refresh(comment)

    return {
        "id": str(comment.id),
        "draft_id": str(comment.draft_id),
        "user_id": str(comment.author_id),
        "text": comment.body,
        "range_start": comment.range_start,
        "range_end": comment.range_end,
        "created_at": comment.created_at,
    }


@router.get("/{draft_id}/comments")
async def list_comments(
    draft_id: str,
    current_user: User = Depends(require_role("creator", "reviewer", "admin")),
    db: Session = Depends(get_db),
):
    """List comments on a draft."""
    draft_uuid = _parse_uuid(draft_id, "draft_id")
    draft = db.get(Draft, draft_uuid)
    if not draft or draft.organisation_id != current_user.organisation_id:
        raise HTTPException(status_code=404, detail="Draft not found")

    comments = db.scalars(
        select(Comment)
        .where(Comment.draft_id == draft_uuid)
        .order_by(Comment.created_at)
    ).all()

    return [
        {
            "id": str(c.id),
            "draft_id": str(c.draft_id),
            "user_id": str(c.author_id),
            "text": c.body,
            "range_start": c.range_start,
            "range_end": c.range_end,
            "created_at": c.created_at,
        }
        for c in comments
    ]


@router.post("/{draft_id}/decision", status_code=status.HTTP_201_CREATED)
async def record_decision(
    draft_id: str,
    req: DecisionRequest,
    current_user: User = Depends(require_role("reviewer")),
    db: Session = Depends(get_db),
):
    """Record an approval decision on a draft."""
    draft_uuid = _parse_uuid(draft_id, "draft_id")
    draft = db.get(Draft, draft_uuid)
    if not draft or draft.organisation_id != current_user.organisation_id:
        raise HTTPException(status_code=404, detail="Draft not found")

    approval = record_approval_decision(
        db, draft, current_user, req.decision, req.reason, req.override_reason
    )
    return {
        "id": str(approval.id),
        "draft_id": str(approval.draft_id),
        "user_id": str(approval.reviewer_id),
        "decision": approval.decision,
        "reason": approval.note,
        "override_reason": approval.override_reason,
        "created_at": approval.created_at,
    }


@router.get("/{draft_id}/receipt")
async def get_receipt(
    draft_id: str,
    current_user: User = Depends(require_role("creator", "reviewer", "admin")),
    db: Session = Depends(get_db),
):
    """Get the Claim Receipts generated for an approved draft."""
    draft_uuid = _parse_uuid(draft_id, "draft_id")
    draft = db.get(Draft, draft_uuid)
    if not draft or draft.organisation_id != current_user.organisation_id:
        raise HTTPException(status_code=404, detail="Draft not found")

    receipts = db.scalars(
        select(ClaimReceipt).where(
            ClaimReceipt.organisation_id == draft.organisation_id,
            ClaimReceipt.draft_id == draft.id,
        )
    ).all()

    formatted = [
        {
            "id": str(r.id),
            "draft_id": str(r.draft_id),
            "version_id": str(r.version_id),
            "organisation_id": str(r.organisation_id),
            "approved_by": str(r.approved_by),
            "approved_at": r.approved_at,
            "content_hash": r.content_hash,
            "guideline_versions": r.guideline_versions,
            "override_reasons": r.override_reasons,
            "receipt_data": r.claims_snapshot,
        }
        for r in receipts
    ]

    return {
        "draft_id": str(draft.id),
        "status": draft.status,
        "receipts_count": len(formatted),
        "receipts": formatted,
    }
