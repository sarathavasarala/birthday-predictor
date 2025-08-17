"""
Identity resolution module.
Merges observations across chats and years into unified identities.
"""

import json
from datetime import date as Date
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter
from models import WishCluster, Participant, Identity
from logging_config import get_logger, log_function_call, LoggedOperation

logger = get_logger('identity')


class IdentityResolver:
    """Resolves and merges participant identities across chats and years."""
    
    def __init__(self, config_path: str = "config.json"):
        self.logger = get_logger('identity')
        self.config = self._load_config(config_path)
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            self.logger.info(f"Loaded identity resolver configuration from {config_path}")
            return config
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.warning(f"Could not load config from {config_path}: {e}")
            return {}
    
    @log_function_call
    def resolve_identities(self, clusters: List[WishCluster], 
                         all_participants: List[Participant]) -> List[Identity]:
        """
        Resolve participant identities across multiple chats and years.
        
        Args:
            clusters: All wish clusters with inferred targets
            all_participants: All participants from all chats
            
        Returns:
            List of resolved Identity objects
        """
        with LoggedOperation(f"Resolving identities from {len(clusters)} clusters", 'identity'):
            # Group observations by identity
            identity_observations = self._group_observations_by_identity(clusters, all_participants)
            
            # Create Identity objects
            identities = []
            for identity_key, observations in identity_observations.items():
                identity = self._create_identity_from_observations(identity_key, observations)
                if identity:
                    identities.append(identity)
            
            self.logger.info(f"Resolved {len(identities)} unique identities")
            return identities
    
    def _group_observations_by_identity(self, clusters: List[WishCluster], 
                                      all_participants: List[Participant]) -> Dict[str, List[Dict[str, Any]]]:
        """Group wish cluster observations by resolved identity."""
        # Create participant lookup
        participant_lookup = {p.id: p for p in all_participants if p.id}
        
        # Track observations by identity key
        identity_observations = defaultdict(list)
        
        for cluster in clusters:
            if not cluster.target_participant_id or not cluster.date:
                continue
            
            participant = participant_lookup.get(cluster.target_participant_id)
            if not participant:
                continue
            
            # Determine identity key for this participant
            identity_key = self._get_identity_key(participant, all_participants)
            
            observation = {
                'cluster': cluster,
                'participant': participant,
                'date': cluster.date,
                'year': cluster.date.year,
                'month_day': (cluster.date.month, cluster.date.day)
            }
            
            identity_observations[identity_key].append(observation)
            
            self.logger.debug(f"Grouped observation for {identity_key}: {cluster.date}")
        
        return dict(identity_observations)
    
    def _get_identity_key(self, participant: Participant, all_participants: List[Participant]) -> str:
        """
        Generate a unique identity key for a participant.
        
        Priority:
        1. Phone number (highest confidence)
        2. Display name + chat context
        3. Display name only (lowest confidence)
        """
        # Primary key: phone number
        if participant.phone:
            return f"phone:{participant.phone}"
        
        # Secondary key: display name (check for conflicts)
        if participant.display_name:
            # Check if this display name appears in multiple chats with different phones
            same_name_participants = [
                p for p in all_participants 
                if (p.display_name == participant.display_name and 
                    p.chat_id != participant.chat_id)
            ]
            
            phones_for_name = {p.phone for p in same_name_participants if p.phone}
            
            if len(phones_for_name) > 1:
                # Name collision with different phones - use chat-specific key
                return f"name_chat:{participant.display_name}:{participant.chat_id}"
            else:
                # Safe to use name as key
                return f"name:{participant.display_name}"
        
        # Fallback: use chat-specific ID
        return f"participant:{participant.chat_id}:{participant.id}"
    
    def _create_identity_from_observations(self, identity_key: str, 
                                         observations: List[Dict[str, Any]]) -> Optional[Identity]:
        """Create an Identity object from grouped observations."""
        if not observations:
            return None
        
        # Extract basic info
        canonical_name = self._determine_canonical_name(observations)
        phone = self._determine_phone(observations)
        
        # Determine birthday
        birthday_month, birthday_day = self._determine_birthday(observations)
        
        if not birthday_month or not birthday_day:
            self.logger.warning(f"Could not determine birthday for identity {identity_key}")
            return None
        
        # Calculate evidence metrics
        years_observed = len(set(obs['year'] for obs in observations))
        total_wishers = sum(obs['cluster'].unique_wishers for obs in observations)
        
        # Create evidence summary
        evidence_summary = self._create_evidence_summary(observations)
        
        identity = Identity(
            canonical_name=canonical_name,
            phone=phone,
            birthday_month=birthday_month,
            birthday_day=birthday_day,
            years_observed=years_observed,
            total_wishers=total_wishers,
            evidence_summary=evidence_summary
        )
        
        self.logger.debug(f"Created identity: {canonical_name} ({birthday_month}/{birthday_day})")
        return identity
    
    def _determine_canonical_name(self, observations: List[Dict[str, Any]]) -> str:
        """Determine the canonical name for an identity."""
        # Count name variations
        name_counts = Counter()
        
        for obs in observations:
            participant = obs['participant']
            if participant.display_name:
                name_counts[participant.display_name] += 1
        
        if name_counts:
            # Use the most common name
            canonical_name = name_counts.most_common(1)[0][0]
            return canonical_name
        
        # Fallback to phone or participant ID
        first_obs = observations[0]
        participant = first_obs['participant']
        return participant.phone or f"Participant {participant.id}"
    
    def _determine_phone(self, observations: List[Dict[str, Any]]) -> Optional[str]:
        """Determine the phone number for an identity."""
        phones = {obs['participant'].phone for obs in observations if obs['participant'].phone}
        
        if len(phones) == 1:
            return next(iter(phones))
        elif len(phones) > 1:
            self.logger.warning(f"Multiple phone numbers found for identity: {phones}")
            # Return the most common one
            phone_counts = Counter(obs['participant'].phone for obs in observations 
                                 if obs['participant'].phone)
            if phone_counts:
                return phone_counts.most_common(1)[0][0]
        
        return None
    
    @log_function_call
    def _determine_birthday(self, observations: List[Dict[str, Any]]) -> Tuple[Optional[int], Optional[int]]:
        """Determine the birthday month and day from observations."""
        # Count month-day combinations
        date_counts = Counter()
        
        for obs in observations:
            month_day = obs['month_day']
            date_counts[month_day] += 1
        
        if not date_counts:
            return None, None
        
        # Check for consistency
        if len(date_counts) == 1:
            # All observations agree
            month, day = date_counts.most_common(1)[0][0]
            self.logger.debug(f"Consistent birthday found: {month}/{day}")
            return month, day
        
        # Handle conflicts
        most_common = date_counts.most_common(2)
        primary_date, primary_count = most_common[0]
        
        if len(most_common) > 1:
            secondary_date, secondary_count = most_common[1]
            
            # Check if dates are adjacent (could be midnight/timezone issues)
            if self._are_dates_adjacent(primary_date, secondary_date):
                self.logger.debug(f"Adjacent dates found: {primary_date} vs {secondary_date}, choosing {primary_date}")
                return primary_date
            
            # Check for leap year patterns (Feb 28/29 vs Mar 1)
            if self._is_leap_year_pattern(primary_date, secondary_date):
                # Prefer Feb 29 if it appears
                if primary_date == (2, 29) or secondary_date == (2, 29):
                    leap_date = (2, 29)
                    self.logger.debug(f"Leap year pattern detected, choosing Feb 29")
                    return leap_date
        
        # Default to most common date
        month, day = primary_date
        self.logger.debug(f"Conflicting dates, choosing most common: {month}/{day}")
        return month, day
    
    def _are_dates_adjacent(self, date1: Tuple[int, int], date2: Tuple[int, int]) -> bool:
        """Check if two month-day tuples represent adjacent dates."""
        try:
            # Create date objects for comparison (use a non-leap year)
            d1 = Date(2023, date1[0], date1[1])
            d2 = Date(2023, date2[0], date2[1])
            delta = abs((d2 - d1).days)
            return delta <= 1
        except ValueError:
            # Invalid date (like Feb 29 in non-leap year)
            return False
    
    def _is_leap_year_pattern(self, date1: Tuple[int, int], date2: Tuple[int, int]) -> bool:
        """Check if dates represent leap year birthday pattern."""
        leap_patterns = [
            ((2, 28), (2, 29)),  # Feb 28 vs Feb 29
            ((2, 29), (3, 1)),   # Feb 29 vs Mar 1
            ((2, 28), (3, 1))    # Feb 28 vs Mar 1
        ]
        
        return (date1, date2) in leap_patterns or (date2, date1) in leap_patterns
    
    def _create_evidence_summary(self, observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a summary of evidence for this identity."""
        summary = {
            'total_observations': len(observations),
            'years': sorted(list(set(obs['year'] for obs in observations))),
            'chats': len(set(obs['participant'].chat_id for obs in observations)),
            'total_wishers': sum(obs['cluster'].unique_wishers for obs in observations),
            'has_explicit_mentions': any(obs['cluster'].has_explicit_mentions for obs in observations),
            'has_thanks_messages': any(obs['cluster'].has_thanks for obs in observations),
            'date_consistency': len(set(obs['month_day'] for obs in observations)) == 1,
            'best_cluster': None
        }
        
        # Find the best cluster (highest confidence/wishers)
        best_cluster = max(observations, key=lambda x: (x['cluster'].unique_wishers, x['cluster'].total_wish_score))
        summary['best_cluster'] = {
            'date': best_cluster['date'].isoformat(),
            'wishers': best_cluster['cluster'].unique_wishers,
            'score': best_cluster['cluster'].total_wish_score,
            'has_mentions': best_cluster['cluster'].has_explicit_mentions,
            'has_thanks': best_cluster['cluster'].has_thanks
        }
        
        return summary