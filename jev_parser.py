"""
TypeSafe AI Jev (System One) Parser for WhatsApp Birthday Detection.
Uses TypeSafe AI's Jev model for fast, typed, probabilistic decisions
(candidate selection with probability distributions, timing classification, and confidence scoring).
"""

import os
import re
import json
import logging
import urllib.request
import urllib.error
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from logging_config import get_logger
from models import Message, WishCluster, Participant

logger = get_logger('jev_parser')


class JevParser:
    """TypeSafe AI Jev System One parser for fast, typed birthday analysis."""

    def __init__(self, config_path: str = 'config.json'):
        self.api_key = None
        self.api_url = "https://api.typesafe.ai/v1/systemone"
        self.model = "jev-latest"
        self.timeout = 10
        self.enabled = True
        self.max_messages = 12

        self._load_config(config_path)
        self._initialize_client()

    def _load_config(self, config_path: str):
        """Load configuration from config.json."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            jev_config = config.get('jev', {})
            self.enabled = jev_config.get('enabled', True)
            self.api_url = jev_config.get('api_url', 'https://api.typesafe.ai/v1/systemone')
            self.model = jev_config.get('model', 'jev-latest')
            self.timeout = jev_config.get('timeout', 10)
            self.max_messages = jev_config.get('max_messages', 12)
            logger.info(f"Loaded Jev config: model={self.model}, enabled={self.enabled}, api_url={self.api_url}")
        except Exception as e:
            logger.warning(f"Could not load Jev config from {config_path}: {e}. Using defaults.")

    def _initialize_client(self):
        """Read API key from environment."""
        self.api_key = os.getenv('TYPESAFE_API_KEY')
        if not self.api_key:
            logger.info("TYPESAFE_API_KEY not set. Jev parsing disabled until key is provided.")
        else:
            logger.info("TYPESAFE_API_KEY detected. Jev System One parser ready.")

    def is_available(self) -> bool:
        """Check if Jev parser is configured and ready."""
        return bool(self.enabled and self.api_key)

    def extract_candidates(self, cluster: WishCluster, messages: List[Message], 
                           participants: Optional[List[Participant]] = None) -> List[str]:
        """
        Extract a list of candidate targets (names and phone numbers) from participants and messages.
        Jev's Choice primitive requires a list of options (up to 255).
        """
        candidates = []
        seen = set()

        def add_candidate(val: Optional[str]):
            if not val:
                return
            cleaned = val.strip()
            if cleaned and cleaned.lower() not in seen and len(cleaned) <= 60:
                seen.add(cleaned.lower())
                candidates.append(cleaned)

        # 1. Add participants from the chat (both canonical name and phone number)
        if participants:
            for p in participants:
                # Add phone if present
                if p.phone:
                    add_candidate(p.phone)
                # Add display/canonical name if distinct from phone
                if p.canonical_name and p.canonical_name != p.phone:
                    add_candidate(p.canonical_name)
                elif p.display_name and p.display_name != p.phone:
                    add_candidate(p.display_name)

        # 2. Extract @mentions and phone numbers directly from the cluster's messages
        phone_mention_pattern = re.compile(r'@(\+?\d{9,15})')
        general_phone_pattern = re.compile(r'(\+\d{1,3}[\s\-]?\d{4,5}[\s\-]?\d{4,6})')
        name_wish_pattern = re.compile(r'(?:happy\s+birthday|hbd|bday|bornday)[\s,]+([a-zA-Z]{2,20})', re.IGNORECASE)

        for msg in messages:
            if not msg.text:
                continue
            
            # Direct @phone mentions
            for phone in phone_mention_pattern.findall(msg.text):
                add_candidate(phone)

            # Phone numbers in text
            for phone in general_phone_pattern.findall(msg.text):
                add_candidate(phone)

            # Direct name wishes (e.g. "Happy birthday Sarah")
            for name in name_wish_pattern.findall(msg.text):
                if name.lower() not in ['to', 'you', 'dear', 'all', 'bro', 'everyone', 'advance', 'belated']:
                    add_candidate(name.capitalize())

            # Message senders in this cluster (especially those who might be saying thank you)
            if msg.sender:
                add_candidate(msg.sender)

        # 3. Always include 'Unknown / Someone outside chat'
        add_candidate("Unknown / Someone outside chat")

        # Cap at 250 options to stay within Jev limit
        return candidates[:250]

    def analyze_birthday_cluster(self, cluster: WishCluster, messages: List[Message],
                                 participants: Optional[List[Participant]] = None) -> Dict[str, Any]:
        """
        Analyze a birthday cluster using Jev System One.
        
        Args:
            cluster: The WishCluster to analyze
            messages: List of Message objects in the cluster
            participants: Optional list of Participant objects from the chat
            
        Returns:
            Dictionary matching the standard birthday analysis schema.
        """
        if not self.is_available():
            raise RuntimeError("Jev parser is not available (missing TYPESAFE_API_KEY or disabled).")

        candidates = self.extract_candidates(cluster, messages, participants)

        # Format cluster messages into a clean state text for Jev
        formatted_msgs = []
        for msg in messages[:self.max_messages]:
            t_str = msg.timestamp.strftime("%Y-%m-%d %H:%M") if msg.timestamp else ""
            formatted_msgs.append(f"[{t_str}] {msg.sender}: {msg.text}")
        messages_text = "\n".join(formatted_msgs)

        state = {
            "cluster_date": cluster.date.strftime("%Y-%m-%d") if cluster.date else "Unknown",
            "messages": messages_text,
            "message_count": len(messages),
            "unique_wishers": cluster.unique_wishers
        }

        # Build criteria mappings required by TypeSafe API
        target_criteria = {c: f"Candidate: {c}" for c in candidates}
        timing_criteria = {
            "on_time": "Sent on or for the actual birthday",
            "belated": "Sent late (belated wish)",
            "advance": "Sent early (advance wish)"
        }
        confidence_criteria = [
            "Uncertain / no evidence",
            "Low confidence",
            "Medium confidence",
            "High confidence",
            "Certain with clear wishes or replies"
        ]

        # Jev question primitives
        questions = {
            "target": {
                "type": "choice",
                "instructions": "Whose birthday is being celebrated in these messages? Pick their name or phone number from the options.",
                "criteria": target_criteria
            },
            "timing": {
                "type": "choice",
                "instructions": "Is this birthday wish sent on the actual birthday date, belated (late), or in advance (early)?",
                "criteria": timing_criteria
            },
            "confidence_score": {
                "type": "score",
                "instructions": "Rate how certain it is that this person's birthday is on or around this date based on the evidence (1=very dubious, 5=certain).",
                "criteria": confidence_criteria
            }
        }

        payload = {
            "model": self.model,
            "state": state,
            "questions": questions
        }

        response_data = self._call_jev_api(payload)
        return self._format_jev_response(response_data, cluster, messages, candidates)

    def _call_jev_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP POST request to TypeSafe AI Jev API."""
        req_body = json.dumps(payload).encode('utf-8')
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "WhatsAppBirthdayPredictor/2.0"
        }

        req = urllib.request.Request(self.api_url, data=req_body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                status_code = response.getcode()
                response_body = response.read().decode('utf-8')
                if status_code != 200:
                    raise RuntimeError(f"TypeSafe API returned HTTP {status_code}: {response_body}")
                return json.loads(response_body)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='replace') if hasattr(e, 'read') else str(e)
            logger.error(f"TypeSafe API HTTPError {e.code}: {err_body}")
            raise RuntimeError(f"TypeSafe API HTTP {e.code}: {err_body}")
        except Exception as e:
            logger.error(f"Failed to connect to TypeSafe API: {e}")
            raise

    def _format_jev_response(self, response_data: Dict[str, Any], cluster: WishCluster,
                             messages: List[Message], candidates: List[str]) -> Dict[str, Any]:
        """Format Jev System One answer into app-compatible prediction dictionary."""
        answers = response_data.get("answers", response_data.get("results", {}))

        # 1. Target recipient & probabilities
        target_answer = answers.get("target", {})
        target_val = target_answer.get("choice") or target_answer.get("value")
        target_confidence = target_answer.get("confidence", 0.8)
        probabilities = target_answer.get("probabilities", {})

        # 2. Timing (on_time, belated, advance)
        timing_answer = answers.get("timing", {})
        timing_val = timing_answer.get("choice") or timing_answer.get("value") or "on_time"

        # 3. Confidence score (1-5 scale)
        conf_answer = answers.get("confidence_score", {})
        raw_score = conf_answer.get("score")
        if raw_score is None:
            raw_score = conf_answer.get("value", 4.0)

        # Normalize confidence to 0-100 percentage
        # Combine target_confidence (probability) and rubric score
        if isinstance(raw_score, (int, float)):
            score_normalized = (raw_score / 5.0) * 100
        else:
            score_normalized = 75.0

        if isinstance(target_confidence, float) and 0.0 <= target_confidence <= 1.0:
            final_confidence = int(round((target_confidence * 0.6 + (score_normalized / 100.0) * 0.4) * 100))
        else:
            final_confidence = int(round(score_normalized))
        final_confidence = max(20, min(100, final_confidence))

        # Resolve person and phone_number
        person = None
        phone_number = None

        if target_val and "unknown" not in target_val.lower():
            # Check if target is a phone number
            clean_digits = re.sub(r'[^\d+]', '', target_val)
            if len(clean_digits) >= 10:
                phone_number = target_val
                person = target_val
            else:
                person = target_val

        # Adjust date for belated or advance wishes if relevant
        adjusted_date = cluster.date
        if timing_val == "belated" and adjusted_date:
            adjusted_date = adjusted_date - timedelta(days=1)
        elif timing_val == "advance" and adjusted_date:
            adjusted_date = adjusted_date + timedelta(days=1)

        date_str = adjusted_date.strftime("%m-%d") if adjusted_date else "Unknown"

        # Generate descriptive analysis text from Jev's structured decisions
        target_prob_str = ""
        if target_val and target_val in probabilities:
            prob_pct = int(probabilities[target_val] * 100)
            target_prob_str = f" ({prob_pct}% decision probability)"

        timing_str = {
            "belated": "belated wishes (birthday likely 1 day prior)",
            "advance": "advance wishes (birthday likely 1 day ahead)",
            "on_time": "on-time birthday wishes"
        }.get(timing_val, "wishes")

        analysis = (
            f"Identified '{target_val or 'Unknown'}' based on {len(messages)} messages "
            f"from {cluster.unique_wishers} unique wishers. Categorized as {timing_str} "
            f"with {final_confidence}% confidence."
        )

        return {
            'date': date_str,
            'person': person,
            'phone_number': phone_number,
            'confidence': final_confidence,
            'probabilities': probabilities,
            'year': None,
            'analysis': analysis,
            'source': 'jev-system-one',
            'timing': timing_val,
            'message_count': len(messages),
            'timestamp': datetime.now().isoformat()
        }


# Global instance
jev_parser = JevParser()
