"""
Birthday wish detection and analysis module.
Identifies birthday wishes, clusters them by date, and infers targets.
"""

import re
import json
from datetime import datetime, date as Date, timedelta
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import defaultdict, Counter
from models import Message, WishMessage, WishCluster, Participant, MessageType
from logging_config import get_logger, log_function_call, LoggedOperation

logger = get_logger('analyzer')


class BirthdayAnalyzer:
    """Analyzes messages to detect birthday wishes and cluster them."""
    
    def __init__(self, config_path: str = "config.json"):
        self.logger = get_logger('analyzer')
        self.config = self._load_config(config_path)
        self.patterns = self.config.get('patterns', {})
        self.clustering_config = self.config.get('clustering', {})
        
        # Compile regex patterns for efficiency
        self._compile_patterns()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            self.logger.info(f"Loaded analyzer configuration from {config_path}")
            return config
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.warning(f"Could not load config from {config_path}: {e}")
            return {}
    
    def _compile_patterns(self):
        """Compile regex patterns for better performance."""
        # Strong wish patterns
        strong_wishes = self.patterns.get('strong_wishes', [])
        self.strong_wish_pattern = re.compile(
            r'\b(?:' + '|'.join(re.escape(pattern) for pattern in strong_wishes) + r')\b',
            re.IGNORECASE
        )
        
        # Thanks patterns
        thanks_patterns = self.patterns.get('thanks_patterns', [])
        self.thanks_pattern = re.compile(
            r'\b(?:' + '|'.join(re.escape(pattern) for pattern in thanks_patterns) + r')\b',
            re.IGNORECASE
        )
        
        # Modifier patterns
        modifiers = self.patterns.get('modifiers', {})
        self.belated_pattern = re.compile(
            r'\b(?:' + '|'.join(re.escape(pattern) for pattern in modifiers.get('belated', [])) + r')\b',
            re.IGNORECASE
        )
        self.advance_pattern = re.compile(
            r'\b(?:' + '|'.join(re.escape(pattern) for pattern in modifiers.get('advance', [])) + r')\b',
            re.IGNORECASE
        )
        
        # Negative patterns
        negative_patterns = self.patterns.get('negative_patterns', [])
        self.negative_pattern = re.compile(
            r'\b(?:' + '|'.join(re.escape(pattern) for pattern in negative_patterns) + r')\b',
            re.IGNORECASE
        )
        
        # Name mention patterns - updated to handle phone mentions
        self.name_mention_pattern = re.compile(
            r'(?:@(\d{10,15})|@(\w+)|(?:happy\s+birthday|hbd|bday)[\s,]+(\w+)|(?:to|for)\s+(\w+))',
            re.IGNORECASE
        )
        
        # Phone mention pattern for @phone format
        self.phone_mention_pattern = re.compile(r'@(\d{10,15})', re.IGNORECASE)
        
        self.logger.debug("Compiled all regex patterns for wish detection")
    
    @log_function_call
    def analyze_messages(self, messages: List[Message]) -> List[WishMessage]:
        """
        Analyze messages to detect birthday wishes.
        
        Args:
            messages: List of messages to analyze
            
        Returns:
            List of WishMessage objects for detected birthday wishes
        """
        with LoggedOperation(f"Analyzing {len(messages)} messages for birthday wishes", 'analyzer'):
            wish_messages = []
            
            for message in messages:
                if message.message_type != MessageType.NORMAL or not message.text:
                    continue
                
                wish_score = self._calculate_wish_score(message.text)
                
                if wish_score > 0:
                    mentioned_names = self._extract_mentioned_names(message.text)
                    is_thanks = self._is_thanks_message(message.text)
                    modifiers = self._extract_modifiers(message.text)
                    patterns_matched = self._get_matched_patterns(message.text)
                    
                    wish_message = WishMessage(
                        message_id=message.id,
                        wish_score=wish_score,
                        mentioned_names=mentioned_names,
                        is_thanks=is_thanks,
                        modifiers=modifiers,
                        patterns_matched=patterns_matched
                    )
                    
                    wish_messages.append(wish_message)
                    self.logger.debug(f"Detected wish: '{message.text[:50]}...' (score: {wish_score:.2f})")
            
            self.logger.info(f"Detected {len(wish_messages)} birthday wish messages")
            return wish_messages
    
    def _calculate_wish_score(self, text: str) -> float:
        """Calculate how likely a message is a birthday wish."""
        if not text:
            return 0.0
        
        text_lower = text.lower()
        score = 0.0
        
        # Check for negative patterns first
        if self.negative_pattern.search(text_lower):
            return 0.0
        
        # Strong wish patterns
        strong_matches = len(self.strong_wish_pattern.findall(text_lower))
        score += strong_matches * 0.8
        
        # Weak signals (emojis)
        weak_signals = self.patterns.get('weak_signals', [])
        for emoji in weak_signals:
            if emoji in text:
                score += 0.1
        
        # Bonus for multiple indicators
        if strong_matches > 1:
            score += 0.2
        
        # Penalty for very short messages without strong indicators
        if len(text.split()) < 3 and strong_matches == 0:
            score *= 0.5
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _extract_mentioned_names(self, text: str) -> List[str]:
        """Extract explicitly mentioned names from birthday wish."""
        names = []
        
        # Find phone mentions first (like @1234567890)
        phone_matches = self.phone_mention_pattern.findall(text)
        for phone in phone_matches:
            names.append(f"@{phone}")  # Keep @ prefix to distinguish phone mentions
        
        # Find all name mentions using regex
        matches = self.name_mention_pattern.findall(text)
        for match in matches:
            # match is a tuple, find the non-empty group
            name = next((group for group in match if group), None)
            if name and len(name) > 1:  # Avoid single characters
                # Don't duplicate phone mentions
                if not name.isdigit() or len(name) < 10:
                    names.append(name.strip())
        
        return list(set(names))  # Remove duplicates
    
    def _is_thanks_message(self, text: str) -> bool:
        """Check if message is a thanks/appreciation message."""
        return bool(self.thanks_pattern.search(text.lower()))
    
    def _extract_modifiers(self, text: str) -> List[str]:
        """Extract timing modifiers (belated, advance, etc.)."""
        modifiers = []
        
        if self.belated_pattern.search(text.lower()):
            modifiers.append('belated')
        
        if self.advance_pattern.search(text.lower()):
            modifiers.append('advance')
        
        return modifiers
    
    def _get_matched_patterns(self, text: str) -> List[str]:
        """Get list of patterns that matched in the text."""
        patterns = []
        
        # Check which strong patterns matched
        strong_wishes = self.patterns.get('strong_wishes', [])
        for pattern in strong_wishes:
            if pattern.lower() in text.lower():
                patterns.append(pattern)
        
        # Check weak signals
        weak_signals = self.patterns.get('weak_signals', [])
        for signal in weak_signals:
            if signal in text:
                patterns.append(signal)
        
        return patterns
    
    @log_function_call
    def cluster_wishes_by_date(self, messages: List[Message], wish_messages: List[WishMessage], 
                             chat_id: int) -> List[WishCluster]:
        """
        Cluster birthday wishes by date and chat.
        
        Args:
            messages: All messages (for context and timestamp lookup)
            wish_messages: Detected wish messages
            chat_id: ID of the chat these messages belong to
            
        Returns:
            List of WishCluster objects
        """
        with LoggedOperation(f"Clustering {len(wish_messages)} wishes by date", 'analyzer'):
            # Create message lookup for timestamps
            message_lookup = {msg.id: msg for msg in messages if msg.id}
            self.logger.debug(f"Created message lookup with {len(message_lookup)} messages")
            
            # Group wishes by date
            date_groups = defaultdict(list)
            
            for wish in wish_messages:
                message = message_lookup.get(wish.message_id)
                self.logger.debug(f"Looking up wish message_id {wish.message_id}: found={message is not None}")
                if message and message.timestamp:
                    message_date = message.timestamp.date()
                    date_groups[message_date].append(wish)
                    self.logger.debug(f"Added wish to date group {message_date}")
                else:
                    if message:
                        self.logger.debug(f"Message found but no timestamp: {message}")
                    else:
                        self.logger.debug(f"No message found for wish.message_id {wish.message_id}")
            
            self.logger.debug(f"Date groups: {len(date_groups)} dates with wishes")
            
            # Create clusters using sliding window
            clusters = []
            window_hours = self.clustering_config.get('window_hours', 36)
            min_wish_score = self.clustering_config.get('min_wish_score', 0.3)
            
            # Sort dates for processing
            sorted_dates = sorted(date_groups.keys())
            processed_dates = set()
            
            for current_date in sorted_dates:
                if current_date in processed_dates:
                    continue
                
                # Find all wishes within the window
                window_start = datetime.combine(current_date, datetime.min.time())
                window_end = window_start + timedelta(hours=window_hours)
                
                cluster_wishes = []
                cluster_dates = set()
                
                for check_date in sorted_dates:
                    check_datetime = datetime.combine(check_date, datetime.min.time())
                    if window_start <= check_datetime <= window_end:
                        cluster_wishes.extend(date_groups[check_date])
                        cluster_dates.add(check_date)
                
                # Only create cluster if it meets minimum criteria
                total_score = sum(w.wish_score for w in cluster_wishes)
                if total_score >= min_wish_score:
                    # Find the peak date (date with highest wish density)
                    peak_date = self._find_peak_date(cluster_wishes, message_lookup, cluster_dates)
                    
                    cluster = WishCluster(
                        chat_id=chat_id,
                        date=peak_date,
                        wish_messages=cluster_wishes,
                        unique_wishers=self._count_unique_wishers(cluster_wishes, message_lookup),
                        total_wish_score=total_score,
                        has_thanks=any(w.is_thanks for w in cluster_wishes),
                        has_explicit_mentions=any(w.mentioned_names for w in cluster_wishes)
                    )
                    
                    clusters.append(cluster)
                    processed_dates.update(cluster_dates)
                    
                    self.logger.debug(f"Created cluster for {peak_date} with {len(cluster_wishes)} wishes")
            
            self.logger.info(f"Created {len(clusters)} wish clusters")
            return clusters
    
    def _find_peak_date(self, wishes: List[WishMessage], message_lookup: Dict[int, Message], 
                       candidate_dates: Set[Date]) -> Date:
        """Find the date with the highest wish density in a cluster."""
        date_scores = defaultdict(float)
        date_counts = defaultdict(int)
        
        for wish in wishes:
            message = message_lookup.get(wish.message_id)
            if message and message.timestamp:
                message_date = message.timestamp.date()
                if message_date in candidate_dates:
                    date_scores[message_date] += wish.wish_score
                    date_counts[message_date] += 1
        
        # Find date with highest combined score and count
        best_date = max(candidate_dates, 
                       key=lambda d: (date_scores[d], date_counts[d]))
        
        return best_date
    
    def _count_unique_wishers(self, wishes: List[WishMessage], 
                            message_lookup: Dict[int, Message]) -> int:
        """Count unique people who sent birthday wishes."""
        wishers = set()
        
        for wish in wishes:
            message = message_lookup.get(wish.message_id)
            if message and message.sender:
                wishers.add(message.sender)
        
        return len(wishers)
    
    @log_function_call
    def infer_birthday_target(self, cluster: WishCluster, participants: List[Participant],
                            messages: List[Message], chat_type: str) -> Optional[int]:
        """
        Infer who the birthday wishes are for.
        
        Args:
            cluster: The wish cluster to analyze
            participants: List of chat participants
            messages: All messages for context
            chat_type: Type of chat ('direct' or 'group')
            
        Returns:
            Participant ID of the inferred target, or None if unclear
        """
        with LoggedOperation(f"Inferring birthday target for cluster on {cluster.date}", 'analyzer'):
            message_lookup = {msg.id: msg for msg in messages if msg.id}
            participant_lookup = {p.display_name: p for p in participants}
            
            if chat_type == 'direct':
                return self._infer_target_direct_chat(cluster, participants, message_lookup)
            else:
                return self._infer_target_group_chat(cluster, participants, message_lookup, participant_lookup)
    
    def _infer_target_direct_chat(self, cluster: WishCluster, participants: List[Participant],
                                message_lookup: Dict[int, Message]) -> Optional[int]:
        """Infer target in a direct (1:1) chat."""
        # In direct chats, look at who sent vs received wishes
        wishers = set()
        thanks_senders = set()
        
        for wish in cluster.wish_messages:
            message = message_lookup.get(wish.message_id)
            if message and message.sender:
                if wish.is_thanks:
                    thanks_senders.add(message.sender)
                else:
                    wishers.add(message.sender)
        
        # If someone said thanks, they're likely the target
        if len(thanks_senders) == 1:
            thanks_sender = next(iter(thanks_senders))
            target = next((p for p in participants if p.display_name == thanks_sender), None)
            if target:
                self.logger.debug(f"Direct chat target identified by thanks: {thanks_sender}")
                return target.id
        
        # Otherwise, assume the target is the participant who didn't send wishes
        all_participants = {p.display_name for p in participants}
        non_wishers = all_participants - wishers
        
        if len(non_wishers) == 1:
            target_name = next(iter(non_wishers))
            target = next((p for p in participants if p.display_name == target_name), None)
            if target:
                self.logger.debug(f"Direct chat target identified by process of elimination: {target_name}")
                return target.id
        
        self.logger.warning("Could not determine target in direct chat")
        return None
    
    def _infer_target_group_chat(self, cluster: WishCluster, participants: List[Participant],
                               message_lookup: Dict[int, Message], 
                               participant_lookup: Dict[str, Participant]) -> Optional[int]:
        """Infer target in a group chat."""
        # Strategy 1: Phone mentions (like @1234567890)
        phone_mentions = []
        name_mentions = []
        
        for wish in cluster.wish_messages:
            for mention in wish.mentioned_names:
                if mention.startswith('@') and mention[1:].isdigit():
                    phone_mentions.append(mention[1:])  # Remove @ prefix
                else:
                    name_mentions.append(mention)
        
        # Try to match phone mentions to participants
        if phone_mentions:
            phone_counts = Counter(phone_mentions)
            most_mentioned_phone = phone_counts.most_common(1)[0][0]
            
            # Look for participant with this phone number
            for participant in participants:
                if (participant.phone and 
                    most_mentioned_phone in participant.phone.replace('+', '').replace(' ', '')):
                    self.logger.debug(f"Group chat target identified by phone mention: {most_mentioned_phone}")
                    return participant.id
        
        # Strategy 2: Explicit name mentions
        if name_mentions:
            # Find the most mentioned name
            name_counts = Counter(name_mentions)
            most_mentioned = name_counts.most_common(1)[0][0]
            
            # Try to match to a participant
            for participant in participants:
                if (participant.display_name and 
                    most_mentioned.lower() in participant.display_name.lower()):
                    self.logger.debug(f"Group chat target identified by name mentions: {most_mentioned}")
                    return participant.id
        
        # Strategy 3: Thanks messages
        thanks_senders = set()
        for wish in cluster.wish_messages:
            if wish.is_thanks:
                message = message_lookup.get(wish.message_id)
                if message and message.sender:
                    thanks_senders.add(message.sender)
        
        if len(thanks_senders) == 1:
            thanks_sender = next(iter(thanks_senders))
            target = participant_lookup.get(thanks_sender)
            if target:
                self.logger.debug(f"Group chat target identified by thanks: {thanks_sender}")
                return target.id
        
        # Strategy 4: Process of elimination (risky in groups)
        wishers = set()
        for wish in cluster.wish_messages:
            if not wish.is_thanks:  # Don't count thanks as wishes
                message = message_lookup.get(wish.message_id)
                if message and message.sender:
                    wishers.add(message.sender)
        
        all_participants = {p.display_name for p in participants}
        non_wishers = all_participants - wishers
        
        if len(non_wishers) == 1:
            target_name = next(iter(non_wishers))
            target = participant_lookup.get(target_name)
            if target:
                self.logger.debug(f"Group chat target identified by elimination: {target_name}")
                return target.id
        
        self.logger.warning(f"Could not determine target in group chat for date {cluster.date}")
        return None
    
    @log_function_call
    def adjust_birthday_date(self, cluster: WishCluster, messages: List[Message]) -> Date:
        """
        Adjust the birthday date based on timing modifiers.
        
        Args:
            cluster: The wish cluster
            messages: All messages for context
            
        Returns:
            Adjusted birthday date
        """
        message_lookup = {msg.id: msg for msg in messages if msg.id}
        
        # Count modifiers
        belated_count = 0
        advance_count = 0
        total_wishes = 0
        
        for wish in cluster.wish_messages:
            total_wishes += 1
            if 'belated' in wish.modifiers:
                belated_count += 1
            if 'advance' in wish.modifiers:
                advance_count += 1
        
        adjusted_date = cluster.date
        
        # Apply adjustments if majority indicates timing offset
        if belated_count > total_wishes * 0.5:  # Majority are belated
            adjusted_date = cluster.date - timedelta(days=1)
            self.logger.debug(f"Adjusted date backwards for belated wishes: {adjusted_date}")
        elif advance_count > total_wishes * 0.5:  # Majority are advance
            adjusted_date = cluster.date + timedelta(days=1)
            self.logger.debug(f"Adjusted date forwards for advance wishes: {adjusted_date}")
        
        return adjusted_date