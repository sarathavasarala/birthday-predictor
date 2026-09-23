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
        
        # Require minimum message length for context
        words = text.split()
        if len(words) < 3:
            return 0.0  # Too short to be meaningful
        
        # Strong wish patterns - REQUIRED for any score
        strong_matches = len(self.strong_wish_pattern.findall(text_lower))
        if strong_matches == 0:
            return 0.0  # Must have at least one strong pattern
        
        # Base score for strong patterns
        score = 0.8 * strong_matches
        
        # Weak signals (emojis) - only as supplement to strong patterns
        weak_signals = self.patterns.get('weak_signals', [])
        emoji_count = sum(1 for emoji in weak_signals if emoji in text)
        if emoji_count > 0:
            score += min(0.2, emoji_count * 0.1)  # Cap emoji bonus at 0.2
        
        # Bonus for explicit name mentions
        if self.name_mention_pattern.search(text):
            score += 0.2
        
        # Bonus for multiple strong indicators
        if strong_matches > 1:
            score += 0.1
        
        # Bonus for longer, more contextual messages
        if len(words) > 6:
            score += 0.1
        
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
            min_wishers = self.clustering_config.get('min_wishers', 1)
            max_clusters_per_day = self.clustering_config.get('max_clusters_per_day', 3)
            
            # Sort dates for processing
            sorted_dates = sorted(date_groups.keys())
            processed_dates = set()
            daily_cluster_counts = defaultdict(int)
            
            for current_date in sorted_dates:
                if current_date in processed_dates:
                    continue
                
                # Check daily limit
                if daily_cluster_counts[current_date] >= max_clusters_per_day:
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
                
                # Count unique wishers for this cluster
                unique_wishers = self._count_unique_wishers(cluster_wishes, message_lookup)
                total_score = sum(w.wish_score for w in cluster_wishes)
                
                # Only create cluster if it meets ALL minimum criteria
                if (total_score >= min_wish_score and 
                    unique_wishers >= min_wishers and
                    len(cluster_wishes) >= min_wishers):
                    
                    # Find the peak date (date with highest wish density)
                    peak_date = self._find_peak_date(cluster_wishes, message_lookup, cluster_dates)
                    
                    cluster = WishCluster(
                        chat_id=chat_id,
                        date=peak_date,
                        wish_messages=cluster_wishes,
                        unique_wishers=unique_wishers,
                        total_wish_score=total_score,
                        has_thanks=any(w.is_thanks for w in cluster_wishes),
                        has_explicit_mentions=any(w.mentioned_names for w in cluster_wishes)
                    )
                    
                    clusters.append(cluster)
                    processed_dates.update(cluster_dates)
                    
                    # Update daily counts for all affected dates
                    for date in cluster_dates:
                        daily_cluster_counts[date] += 1
                    
                    self.logger.debug(f"Created cluster for {peak_date} with {len(cluster_wishes)} wishes, {unique_wishers} wishers")
                else:
                    self.logger.debug(f"Rejected cluster for {current_date}: score={total_score:.2f}, wishers={unique_wishers}, min_score={min_wish_score}, min_wishers={min_wishers}")
            
            self.logger.info(f"Created {len(clusters)} wish clusters (enforced limits: max_per_day={max_clusters_per_day}, min_wishers={min_wishers})")
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
    
    @log_function_call
    def calculate_confidence(self, cluster: WishCluster, target_participant: Optional[Participant] = None) -> float:
        """
        Calculate confidence score for a birthday prediction cluster.
        
        Args:
            cluster: WishCluster object
            target_participant: Optional participant info for additional context
            
        Returns:
            Confidence score between 0 and 1
        """
        # Start with base score
        confidence = self.config.get('confidence', {}).get('base_score', 0.3)
        
        # Unique wishers bonus
        unique_wishers_bonus = self.config.get('confidence', {}).get('unique_wishers_bonus', 0.2)
        if cluster.unique_wishers >= 5:
            confidence += unique_wishers_bonus
            self.logger.debug(f"High wishers bonus: +{unique_wishers_bonus:.3f} ({cluster.unique_wishers} wishers)")
        elif cluster.unique_wishers >= 3:
            confidence += unique_wishers_bonus * 0.5
            self.logger.debug(f"Medium wishers bonus: +{unique_wishers_bonus * 0.5:.3f}")
        
        # Explicit mention bonus
        if cluster.has_explicit_mentions:
            explicit_bonus = self.config.get('confidence', {}).get('explicit_mention_bonus', 0.1)
            confidence += explicit_bonus
            self.logger.debug(f"Explicit mention bonus: +{explicit_bonus:.3f}")
        
        # Thanks message bonus
        if cluster.has_thanks:
            thanks_bonus = self.config.get('confidence', {}).get('thanks_bonus', 0.15)
            confidence += thanks_bonus
            self.logger.debug(f"Thanks message bonus: +{thanks_bonus:.3f}")
        
        # Phone number confidence
        if target_participant and target_participant.phone:
            phone_bonus = 0.1
            confidence += phone_bonus
            self.logger.debug(f"Phone number bonus: +{phone_bonus:.3f}")
        
        # High wish score bonus
        if cluster.total_wish_score >= 3.0:
            high_score_bonus = 0.15
            confidence += high_score_bonus
            self.logger.debug(f"High wish score bonus: +{high_score_bonus:.3f}")
        
        # Ensure confidence is within bounds
        confidence = max(0.0, min(1.0, confidence))
        
        self.logger.debug(f"Final confidence for cluster {cluster.date}: {confidence:.3f}")
        return confidence
    
    @log_function_call
    def simple_identity_resolution(self, clusters: List[WishCluster], 
                                 all_participants: List[Participant]) -> List[Dict[str, Any]]:
        """
        Simplified identity resolution - just group by name and phone.
        
        Args:
            clusters: All wish clusters with inferred targets
            all_participants: All participants from all chats
            
        Returns:
            List of simplified identity dictionaries
        """
        # Create participant lookup
        participant_lookup = {p.id: p for p in all_participants if p.id}
        
        # Group by identity
        identities = defaultdict(list)
        
        for cluster in clusters:
            if not cluster.target_participant_id or not cluster.date:
                continue
            
            participant = participant_lookup.get(cluster.target_participant_id)
            if not participant:
                continue
            
            # Simple identity key: phone first, then name
            identity_key = participant.phone or participant.display_name or f"unknown_{participant.id}"
            
            identities[identity_key].append({
                'cluster': cluster,
                'participant': participant,
                'date': cluster.date
            })
        
        # Convert to final format
        resolved_identities = []
        min_threshold = self.config.get('confidence', {}).get('min_threshold', 0.6)
        
        for identity_key, observations in identities.items():
            if not observations:
                continue
            
            # Get best observation
            best_obs = max(observations, key=lambda x: x['cluster'].unique_wishers)
            participant = best_obs['participant']
            
            # Calculate simple confidence
            total_wishers = sum(obs['cluster'].unique_wishers for obs in observations)
            years_observed = len(set(obs['date'].year for obs in observations))
            
            confidence = self.calculate_confidence(best_obs['cluster'], participant)
            
            # Add multi-year bonus
            if years_observed > 1:
                confidence += 0.2 * min(years_observed - 1, 2) / 2  # Cap at 2 extra years
            
            confidence = min(1.0, confidence)
            
            # Only include if above threshold
            if confidence >= min_threshold:
                identity = {
                    'name': participant.display_name or identity_key,
                    'phone': participant.phone,
                    'birthday_month': best_obs['date'].month,
                    'birthday_day': best_obs['date'].day,
                    'confidence': confidence,
                    'years_observed': years_observed,
                    'total_wishers': total_wishers,
                    'best_cluster_date': best_obs['date'].isoformat(),
                    'observations_count': len(observations)
                }
                resolved_identities.append(identity)
        
        # Sort by confidence
        resolved_identities.sort(key=lambda x: x['confidence'], reverse=True)
        
        self.logger.info(f"Resolved {len(resolved_identities)} identities above threshold")
        return resolved_identities