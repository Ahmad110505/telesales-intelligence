"""
Unit tests for batch transcript sources (folder and database staging).
"""

from pathlib import Path
from app.db.models import SourceCallsStagingModel
from app.ingestion.sources import FolderTranscriptSource, DatabaseTranscriptSource


def test_folder_transcript_source():
    folder_path = str(Path(__file__).resolve().parent.parent / "data" / "sample_transcripts")
    source = FolderTranscriptSource(folder_path=folder_path)
    pending = source.get_pending_transcripts()

    assert len(pending) >= 5
    call_ids = [p.call_id for p in pending]
    assert "CALL-JO-2026-001" in call_ids
    assert "CALL-JO-2026-004" in call_ids

    # Mark one processed
    source.mark_processed("CALL-JO-2026-001", success=True)
    pending_after = source.get_pending_transcripts()
    assert "CALL-JO-2026-001" not in [p.call_id for p in pending_after]


def test_database_transcript_source(db_session):
    # Insert staging call
    staging_item = SourceCallsStagingModel(
        call_id="STAGING-CALL-01",
        transcript_text="[00:01] الموظف: مرحبا\n[00:05] العميل: يا هلا",
        agent_id="AGT-STAGING",
        status="pending"
    )
    db_session.add(staging_item)
    db_session.commit()

    source = DatabaseTranscriptSource(db_session=db_session)
    pending = source.get_pending_transcripts()
    assert any(p.call_id == "STAGING-CALL-01" for p in pending)

    # Mark processed
    source.mark_processed("STAGING-CALL-01", success=True)
    db_session.refresh(staging_item)
    assert staging_item.status == "completed"
