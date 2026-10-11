"""
Unified transcript source abstraction supporting folder-based batches
and database staging tables behind a single interface.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.db.models import SourceCallsStagingModel
from app.schemas.transcript import TranscriptInput

logger = logging.getLogger(__name__)


class BaseTranscriptSource(ABC):
    """Abstract interface for transcript ingestion sources."""

    @abstractmethod
    def get_pending_transcripts(self) -> List[TranscriptInput]:
        """Retrieves unanalyzed transcripts pending ingestion."""
        pass

    @abstractmethod
    def mark_processed(self, call_id: str, success: bool, error_message: Optional[str] = None) -> None:
        """Updates the ingestion status of a processed transcript."""
        pass


class FolderTranscriptSource(BaseTranscriptSource):
    """
    Reads pending transcript files (JSON or raw TXT) from a local or network filesystem directory.
    """

    def __init__(self, folder_path: str):
        self.folder_path = Path(folder_path)
        self.processed_ids: set = set()

    def get_pending_transcripts(self) -> List[TranscriptInput]:
        if not self.folder_path.exists():
            logger.warning("Configured transcript folder does not exist: %s", self.folder_path)
            return []

        pending: List[TranscriptInput] = []

        # 1. Process JSON transcript files
        for json_file in sorted(self.folder_path.glob("*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Skip files that are benchmark ground truth or metadata
                if "benchmark" in json_file.name.lower() or "ground_truth" in json_file.name.lower():
                    continue

                call_id = data.get("call_id") or json_file.stem
                if call_id in self.processed_ids:
                    continue

                transcript_text = data.get("transcript") or data.get("text") or ""
                if not transcript_text:
                    logger.warning("Empty transcript in file %s", json_file)
                    continue

                parsed_input = TranscriptInput(
                    call_id=call_id,
                    transcript=transcript_text,
                    agent_id=data.get("agent_id"),
                    call_date=data.get("call_date"),
                    call_objective=data.get("call_objective"),
                    source="folder",
                    source_ref=str(json_file.resolve()),
                    metadata=data.get("metadata", {})
                )
                pending.append(parsed_input)
            except Exception as exc:
                logger.error("Error reading transcript file %s: %s", json_file, str(exc))

        # 2. Process plain text transcript files (.txt)
        for txt_file in sorted(self.folder_path.glob("*.txt")):
            try:
                call_id = txt_file.stem
                if call_id in self.processed_ids:
                    continue

                with open(txt_file, "r", encoding="utf-8") as f:
                    text_content = f.read().strip()

                if len(text_content) < 10:
                    continue

                parsed_input = TranscriptInput(
                    call_id=call_id,
                    transcript=text_content,
                    source="folder",
                    source_ref=str(txt_file.resolve()),
                    metadata={"filename": txt_file.name}
                )
                pending.append(parsed_input)
            except Exception as exc:
                logger.error("Error reading plain text file %s: %s", txt_file, str(exc))

        logger.info("Found %d pending transcripts in folder %s", len(pending), self.folder_path)
        return pending

    def mark_processed(self, call_id: str, success: bool, error_message: Optional[str] = None) -> None:
        self.processed_ids.add(call_id)
        if not success:
            logger.error("Call %s failed during folder processing: %s", call_id, error_message)


class DatabaseTranscriptSource(BaseTranscriptSource):
    """
    Reads unanalyzed transcripts directly from a PostgreSQL staging table (source_calls_staging).
    """

    def __init__(self, db_session: Session):
        self.db = db_session

    def get_pending_transcripts(self) -> List[TranscriptInput]:
        rows = (
            self.db.query(SourceCallsStagingModel)
            .filter(SourceCallsStagingModel.status == "pending")
            .all()
        )

        pending = []
        for r in rows:
            meta = {}
            if r.metadata_json:
                try:
                    meta = json.loads(r.metadata_json)
                except Exception:
                    pass

            item = TranscriptInput(
                call_id=r.call_id,
                transcript=r.transcript_text,
                agent_id=r.agent_id,
                call_date=r.call_date,
                call_objective=r.call_objective,
                source="database_staging",
                source_ref=f"staging_id:{r.staging_id}",
                metadata=meta
            )
            pending.append(item)

        logger.info("Retrieved %d pending transcripts from database staging table.", len(pending))
        return pending

    def mark_processed(self, call_id: str, success: bool, error_message: Optional[str] = None) -> None:
        row = (
            self.db.query(SourceCallsStagingModel)
            .filter(SourceCallsStagingModel.call_id == call_id)
            .first()
        )
        if row:
            row.status = "completed" if success else "failed"
            row.error_message = error_message
            row.processed_at = datetime.now(timezone.utc)
            self.db.commit()


def get_transcript_source(source_type: str = "folder", folder_path: Optional[str] = None, db_session: Optional[Session] = None) -> BaseTranscriptSource:
    if source_type == "database":
        if db_session is None:
            raise ValueError("db_session required for DatabaseTranscriptSource")
        return DatabaseTranscriptSource(db_session)
    return FolderTranscriptSource(folder_path or "./data/sample_transcripts")
