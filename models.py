"""
Data models for the WhatsApp Birthday Detection App.
Contains dataclasses and database schema definitions.
"""

from dataclasses import dataclass, field
from datetime import datetime, date as Date
from typing import List, Optional, Dict, Any
from enum import Enum
import sqlite3
import json
from logging_config import get_logger, log_function_call

logger = get_logger('models')


class MessageType(Enum):
    """Types of messages in WhatsApp chats."""
    NORMAL = "normal"
    SYSTEM = "system"
    MEDIA_OMITTED = "media_omitted"


class ChatType(Enum):
    """Types of WhatsApp chats."""
    DIRECT = "direct"
    GROUP = "group"
    UNKNOWN = "unknown"


@dataclass
class Message:
    """Represents a single WhatsApp message."""
    id: Optional[int] = None
    chat_id: Optional[int] = None
    timestamp: Optional[datetime] = None
    sender: Optional[str] = None
    text: Optional[str] = None
    message_type: MessageType = MessageType.NORMAL
    original_line: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'sender': self.sender,
            'text': self.text,
            'message_type': self.message_type.value,
            'original_line': self.original_line
        }


@dataclass
class Participant:
    """Represents a chat participant."""
    id: Optional[int] = None
    chat_id: Optional[int] = None
    display_name: Optional[str] = None
    phone: Optional[str] = None
    canonical_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'display_name': self.display_name,
            'phone': self.phone,
            'canonical_name': self.canonical_name
        }


@dataclass
class Chat:
    """Represents a WhatsApp chat."""
    id: Optional[int] = None
    name: Optional[str] = None
    chat_type: ChatType = ChatType.UNKNOWN
    file_path: Optional[str] = None
    participants: List[Participant] = field(default_factory=list)
    message_count: int = 0
    date_range: Optional[tuple] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'chat_type': self.chat_type.value,
            'file_path': self.file_path,
            'participants': [p.to_dict() for p in self.participants],
            'message_count': self.message_count,
            'date_range': [d.isoformat() if d else None for d in self.date_range] if self.date_range else None
        }


@dataclass
class WishMessage:
    """Represents a birthday wish message with analysis results."""
    message_id: int
    wish_score: float
    mentioned_names: List[str] = field(default_factory=list)
    is_thanks: bool = False
    modifiers: List[str] = field(default_factory=list)  # 'belated', 'advance', etc.
    patterns_matched: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'message_id': self.message_id,
            'wish_score': self.wish_score,
            'mentioned_names': self.mentioned_names,
            'is_thanks': self.is_thanks,
            'modifiers': self.modifiers,
            'patterns_matched': self.patterns_matched
        }


@dataclass
class WishCluster:
    """Represents a cluster of birthday wishes on a specific date."""
    id: Optional[int] = None
    chat_id: int = None
    date: Optional[Date] = None
    target_participant_id: Optional[int] = None
    confidence: float = 0.0
    wish_messages: List[WishMessage] = field(default_factory=list)
    unique_wishers: int = 0
    total_wish_score: float = 0.0
    has_thanks: bool = False
    has_explicit_mentions: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'date': self.date.isoformat() if self.date else None,
            'target_participant_id': self.target_participant_id,
            'confidence': self.confidence,
            'wish_messages': [w.to_dict() for w in self.wish_messages],
            'unique_wishers': self.unique_wishers,
            'total_wish_score': self.total_wish_score,
            'has_thanks': self.has_thanks,
            'has_explicit_mentions': self.has_explicit_mentions
        }


@dataclass
class Identity:
    """Represents a resolved identity across multiple chats and years."""
    id: Optional[int] = None
    canonical_name: Optional[str] = None
    phone: Optional[str] = None
    birthday_month: Optional[int] = None
    birthday_day: Optional[int] = None
    confidence: float = 0.0
    years_observed: int = 0
    total_wishers: int = 0
    evidence_summary: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def birthday_date(self) -> Optional[str]:
        """Get formatted birthday date."""
        if self.birthday_month and self.birthday_day:
            return f"{self.birthday_month:02d}-{self.birthday_day:02d}"
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'canonical_name': self.canonical_name,
            'phone': self.phone,
            'birthday_month': self.birthday_month,
            'birthday_day': self.birthday_day,
            'birthday_date': self.birthday_date,
            'confidence': self.confidence,
            'years_observed': self.years_observed,
            'total_wishers': self.total_wishers,
            'evidence_summary': self.evidence_summary
        }


class DatabaseManager:
    """Manages SQLite database operations."""
    
    def __init__(self, db_path: str = "hbd_app.db"):
        self.db_path = db_path
        self.logger = get_logger('database')
        self.init_database()
    
    @log_function_call
    def init_database(self):
        """Initialize the database with required tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.executescript("""
                    -- Chats table
                    CREATE TABLE IF NOT EXISTS chats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        type TEXT NOT NULL,
                        file_path TEXT,
                        message_count INTEGER DEFAULT 0,
                        date_range_start TEXT,
                        date_range_end TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    -- Messages table
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id INTEGER,
                        timestamp TIMESTAMP,
                        sender TEXT,
                        text TEXT,
                        message_type TEXT DEFAULT 'normal',
                        original_line TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (chat_id) REFERENCES chats (id)
                    );
                    
                    -- Participants table
                    CREATE TABLE IF NOT EXISTS participants (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id INTEGER,
                        display_name TEXT,
                        phone TEXT,
                        canonical_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (chat_id) REFERENCES chats (id)
                    );
                    
                    -- Wish clusters table
                    CREATE TABLE IF NOT EXISTS wish_clusters (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id INTEGER,
                        date TEXT,
                        target_participant_id INTEGER,
                        confidence REAL,
                        unique_wishers INTEGER,
                        total_wish_score REAL,
                        has_thanks BOOLEAN,
                        has_explicit_mentions BOOLEAN,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (chat_id) REFERENCES chats (id),
                        FOREIGN KEY (target_participant_id) REFERENCES participants (id)
                    );
                    
                    -- Wish messages table
                    CREATE TABLE IF NOT EXISTS wish_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        cluster_id INTEGER,
                        message_id INTEGER,
                        wish_score REAL,
                        mentioned_names TEXT,  -- JSON array
                        is_thanks BOOLEAN,
                        modifiers TEXT,  -- JSON array
                        patterns_matched TEXT,  -- JSON array
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (cluster_id) REFERENCES wish_clusters (id),
                        FOREIGN KEY (message_id) REFERENCES messages (id)
                    );
                    
                    -- Identities table
                    CREATE TABLE IF NOT EXISTS identities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        canonical_name TEXT,
                        phone TEXT,
                        birthday_month INTEGER,
                        birthday_day INTEGER,
                        confidence REAL,
                        years_observed INTEGER,
                        total_wishers INTEGER,
                        evidence_summary TEXT,  -- JSON
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    -- Identity observations table (many-to-many)
                    CREATE TABLE IF NOT EXISTS identity_observations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        identity_id INTEGER,
                        cluster_id INTEGER,
                        observed_date TEXT,
                        year INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (identity_id) REFERENCES identities (id),
                        FOREIGN KEY (cluster_id) REFERENCES wish_clusters (id)
                    );
                    
                    -- Create indexes for better performance
                    CREATE INDEX IF NOT EXISTS idx_messages_chat_timestamp ON messages (chat_id, timestamp);
                    CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages (sender);
                    CREATE INDEX IF NOT EXISTS idx_participants_name ON participants (display_name);
                    CREATE INDEX IF NOT EXISTS idx_participants_phone ON participants (phone);
                    CREATE INDEX IF NOT EXISTS idx_wish_clusters_date ON wish_clusters (date);
                    CREATE INDEX IF NOT EXISTS idx_identities_name ON identities (canonical_name);
                    CREATE INDEX IF NOT EXISTS idx_identities_phone ON identities (phone);
                """)
                conn.commit()
            self.logger.info("Database initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {str(e)}", exc_info=True)
            raise
    
    @log_function_call
    def save_chat(self, chat: Chat) -> int:
        """Save a chat to the database and return its ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO chats (name, type, file_path, message_count, date_range_start, date_range_end)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    chat.name,
                    chat.chat_type.value,
                    chat.file_path,
                    chat.message_count,
                    chat.date_range[0].isoformat() if chat.date_range and chat.date_range[0] else None,
                    chat.date_range[1].isoformat() if chat.date_range and chat.date_range[1] else None
                ))
                chat_id = cursor.lastrowid
                conn.commit()
                self.logger.info(f"Saved chat '{chat.name}' with ID {chat_id}")
                return chat_id
        except Exception as e:
            self.logger.error(f"Failed to save chat: {str(e)}", exc_info=True)
            raise
    
    @log_function_call
    def save_messages(self, messages: List[Message]) -> List[int]:
        """Save multiple messages to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                message_data = [
                    (msg.chat_id, msg.sender, msg.text, msg.timestamp)
                    for msg in messages
                ]
                cursor.executemany("""
                    INSERT INTO messages (chat_id, sender, text, timestamp)
                    VALUES (?, ?, ?, ?)
                """, message_data)
                
                # Get the IDs of inserted messages
                # Since executemany doesn't give reliable lastrowid, query for the IDs
                first_id = cursor.lastrowid
                if first_id is None and messages:
                    # Fallback: get the highest ID and work backwards
                    cursor.execute("SELECT MAX(id) FROM messages WHERE chat_id = ?", (messages[0].chat_id,))
                    max_id = cursor.fetchone()[0]
                    if max_id:
                        message_ids = list(range(max_id - len(messages) + 1, max_id + 1))
                    else:
                        # If no messages exist, start from 1
                        message_ids = list(range(1, len(messages) + 1))
                else:
                    message_ids = list(range(first_id - len(messages) + 1, first_id + 1))
                
                conn.commit()
                self.logger.info(f"Saved {len(messages)} messages")
                return message_ids
        except Exception as e:
            self.logger.error(f"Failed to save messages: {str(e)}", exc_info=True)
            raise
    
    @log_function_call
    def get_all_identities(self) -> List[Identity]:
        """Retrieve all identities from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, canonical_name, phone, birthday_month, birthday_day,
                           confidence, years_observed, total_wishers, evidence_summary
                    FROM identities
                    ORDER BY confidence DESC
                """)
                
                identities = []
                for row in cursor.fetchall():
                    evidence = json.loads(row[8]) if row[8] else {}
                    identity = Identity(
                        id=row[0],
                        canonical_name=row[1],
                        phone=row[2],
                        birthday_month=row[3],
                        birthday_day=row[4],
                        confidence=row[5],
                        years_observed=row[6],
                        total_wishers=row[7],
                        evidence_summary=evidence
                    )
                    identities.append(identity)
                
                self.logger.info(f"Retrieved {len(identities)} identities")
                return identities
        except Exception as e:
            self.logger.error(f"Failed to retrieve identities: {str(e)}", exc_info=True)
            raise
    
    @log_function_call
    def clear_all_data(self):
        """Clear all data from the database (for testing)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                tables = ['identity_observations', 'wish_messages', 'wish_clusters', 
                         'identities', 'participants', 'messages', 'chats']
                for table in tables:
                    cursor.execute(f"DELETE FROM {table}")
                conn.commit()
                self.logger.info("Cleared all data from database")
        except Exception as e:
            self.logger.error(f"Failed to clear database: {str(e)}", exc_info=True)
            raise