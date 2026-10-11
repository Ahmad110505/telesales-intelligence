"""
Pydantic schemas and parsers for telesales call transcripts.
Supports plain text, speaker-tagged, timestamped, and explicit utterance structures.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


SpeakerRole = Literal["agent", "customer", "unknown"]


class TranscriptTurn(BaseModel):
    """Represents a single conversational turn/utterance in a call transcript."""
    turn_index: int = Field(..., description="1-based sequence index of the turn")
    speaker: SpeakerRole = Field("unknown", description="Attributed speaker role")
    timestamp: Optional[str] = Field(None, description="Timestamp marker (e.g., '01:24') if available")
    text: str = Field(..., description="Verbatim dialogue text for this turn")
    raw_line: str = Field(..., description="Original raw line before parsing")


class TranscriptInput(BaseModel):
    """
    Standard input contract for ingesting a call transcript.
    Validates required fields, input sizes, and parses turn references.
    """
    call_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique identifier for the telesales call"
    )
    transcript: str = Field(
        ...,
        min_length=10,
        max_length=250000,
        description="Raw full transcript text in Jordanian Arabic (or mixed AR/EN)"
    )
    agent_id: Optional[str] = Field(
        None,
        max_length=64,
        description="Sales agent identifier"
    )
    call_date: Optional[datetime] = Field(
        None,
        description="Timestamp when the call occurred (ISO format or datetime)"
    )
    call_objective: Optional[str] = Field(
        None,
        max_length=256,
        description="Intended outcome (e.g., 'fiber_subscription_upgrade', 'motor_insurance_renewal')"
    )
    source: str = Field(
        default="batch_folder",
        max_length=64,
        description="Source channel: 'folder', 'database_staging', 'http_api', etc."
    )
    source_ref: Optional[str] = Field(
        None,
        max_length=512,
        description="Specific source reference (file path, DB staging id, queue message id)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Non-sensitive contextual metadata (campaign, product, customer segment, duration)"
    )
    explicit_turns: Optional[List[TranscriptTurn]] = Field(
        None,
        description="Optional pre-structured turn list if upstream system already parsed utterances"
    )

    @field_validator("call_id")
    @classmethod
    def validate_call_id(cls, v: str) -> str:
        v_clean = v.strip()
        if not v_clean:
            raise ValueError("call_id must not be empty or whitespace only.")
        return v_clean

    @field_validator("transcript")
    @classmethod
    def validate_transcript(cls, v: str) -> str:
        v_clean = v.strip()
        if len(v_clean) < 10:
            raise ValueError("transcript text is too short to represent a viable telesales call.")
        return v_clean

    @model_validator(mode="after")
    def set_default_call_date(self) -> "TranscriptInput":
        if self.call_date is None:
            self.call_date = datetime.now(timezone.utc)
        return self

    def parse_turns(self) -> List[TranscriptTurn]:
        """
        Deterministically parses the transcript text into structured turns with turn index,
        speaker role attribution (agent, customer, unknown), timestamps, and verbatim text.
        Preserves original Jordanian Arabic wording and handles Arabic-English code-switching.
        """
        if self.explicit_turns and len(self.explicit_turns) > 0:
            return self.explicit_turns

        lines = [line.strip() for line in self.transcript.splitlines() if line.strip()]
        turns: List[TranscriptTurn] = []

        # Patterns for timestamp: [00:15], (01:23), 00:15 - , etc.
        ts_pattern = re.compile(r"^[\(\[]?(\d{1,2}:\d{2}(?::\d{2})?)[\)\]]?\s*[-:]?\s*")
        
        # Patterns for Agent speaker
        agent_pattern = re.compile(
            r"^(agent|sales|rep|representative|الموظف|وكيل|مندوب|مندوب المبيعات|خدمة العملاء|الكول سنتر)\s*[:：\-]\s*",
            re.IGNORECASE
        )
        # Patterns for Customer speaker
        customer_pattern = re.compile(
            r"^(customer|client|caller|العميل|الزبون|المتصل|المواطن)\s*[:：\-]\s*",
            re.IGNORECASE
        )

        for idx, line in enumerate(lines, start=1):
            cur_line = line
            timestamp: Optional[str] = None
            
            # Extract timestamp if present at beginning of line
            ts_match = ts_pattern.match(cur_line)
            if ts_match:
                timestamp = ts_match.group(1)
                cur_line = cur_line[ts_match.end():].strip()

            speaker: SpeakerRole = "unknown"
            
            # Check speaker prefix
            ag_match = agent_pattern.match(cur_line)
            if ag_match:
                speaker = "agent"
                cur_line = cur_line[ag_match.end():].strip()
            else:
                cust_match = customer_pattern.match(cur_line)
                if cust_match:
                    speaker = "customer"
                    cur_line = cur_line[cust_match.end():].strip()

            # If still starts with another timestamp (e.g., "[Agent] [00:15]: ...")
            if not timestamp:
                ts_match2 = ts_pattern.match(cur_line)
                if ts_match2:
                    timestamp = ts_match2.group(1)
                    cur_line = cur_line[ts_match2.end():].strip()

            turns.append(
                TranscriptTurn(
                    turn_index=idx,
                    speaker=speaker,
                    timestamp=timestamp,
                    text=cur_line,
                    raw_line=line
                )
            )

        return turns
