"""
Confidence scoring module.
Calculates confidence scores for birthday predictions based on evidence quality.
"""

import json
from typing import List, Dict, Any
from models import Identity
from logging_config import get_logger, log_function_call

logger = get_logger('confidence')


class ConfidenceScorer:
    """Calculates confidence scores for birthday predictions."""
    
    def __init__(self, config_path: str = "config.json"):
        self.logger = get_logger('confidence')
        self.config = self._load_config(config_path)
        self.confidence_config = self.config.get('confidence', {})
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            self.logger.info(f"Loaded confidence scorer configuration from {config_path}")
            return config
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.warning(f"Could not load config from {config_path}: {e}")
            return {}
    
    @log_function_call
    def calculate_confidence(self, identity: Identity) -> float:
        """
        Calculate confidence score for a birthday prediction.
        
        Args:
            identity: Identity object with evidence summary
            
        Returns:
            Confidence score between 0 and 1
        """
        # Start with base score
        confidence = self.confidence_config.get('base_score', 0.3)
        
        evidence = identity.evidence_summary
        
        # Multi-year observation bonus
        if identity.years_observed > 1:
            multi_year_bonus = self.confidence_config.get('multi_year_bonus', 0.2)
            year_factor = min(identity.years_observed - 1, 3) / 3  # Cap at 3 years
            confidence += multi_year_bonus * year_factor
            self.logger.debug(f"Multi-year bonus: +{multi_year_bonus * year_factor:.3f} "
                            f"({identity.years_observed} years)")
        
        # Unique wishers bonus
        unique_wishers_bonus = self.confidence_config.get('unique_wishers_bonus', 0.2)
        if identity.total_wishers >= 5:
            confidence += unique_wishers_bonus
            self.logger.debug(f"High wishers bonus: +{unique_wishers_bonus:.3f} "
                            f"({identity.total_wishers} total wishers)")
        elif identity.total_wishers >= 3:
            confidence += unique_wishers_bonus * 0.5
            self.logger.debug(f"Medium wishers bonus: +{unique_wishers_bonus * 0.5:.3f}")
        
        # Explicit mention bonus
        if evidence.get('has_explicit_mentions', False):
            explicit_bonus = self.confidence_config.get('explicit_mention_bonus', 0.1)
            confidence += explicit_bonus
            self.logger.debug(f"Explicit mention bonus: +{explicit_bonus:.3f}")
        
        # Thanks message bonus
        if evidence.get('has_thanks_messages', False):
            thanks_bonus = self.confidence_config.get('thanks_bonus', 0.15)
            confidence += thanks_bonus
            self.logger.debug(f"Thanks message bonus: +{thanks_bonus:.3f}")
        
        # Phone number confidence
        phone_bonus = self._calculate_phone_confidence_bonus(identity)
        confidence += phone_bonus
        if phone_bonus > 0:
            self.logger.debug(f"Phone confidence bonus: +{phone_bonus:.3f}")
        
        # Date consistency bonus
        if evidence.get('date_consistency', False):
            consistency_bonus = 0.1
            confidence += consistency_bonus
            self.logger.debug(f"Date consistency bonus: +{consistency_bonus:.3f}")
        
        # Apply penalties
        confidence = self._apply_penalties(confidence, identity)
        
        # Ensure confidence is within bounds
        confidence = max(0.0, min(1.0, confidence))
        
        self.logger.debug(f"Final confidence for {identity.canonical_name}: {confidence:.3f}")
        return confidence
    
    def _calculate_phone_confidence_bonus(self, identity: Identity) -> float:
        """Calculate bonus based on phone number availability and reliability."""
        if not identity.phone:
            return 0.0
        
        # Basic phone bonus
        phone_bonus = 0.05
        
        # Additional bonus if phone appears consistent across evidence
        evidence = identity.evidence_summary
        if evidence.get('chats', 0) > 1:
            # Phone number consistent across multiple chats
            phone_bonus += 0.05
        
        return phone_bonus
    
    def _apply_penalties(self, confidence: float, identity: Identity) -> float:
        """Apply confidence penalties based on evidence quality issues."""
        evidence = identity.evidence_summary
        
        # Date inconsistency penalty
        if not evidence.get('date_consistency', True):
            inconsistency_penalty = self.confidence_config.get('conflicting_dates_penalty', -0.2)
            confidence += inconsistency_penalty  # Adding negative value
            self.logger.debug(f"Date inconsistency penalty: {inconsistency_penalty:.3f}")
        
        # Low evidence penalty
        if identity.years_observed == 1 and identity.total_wishers < 3:
            low_evidence_penalty = -0.1
            confidence += low_evidence_penalty
            self.logger.debug(f"Low evidence penalty: {low_evidence_penalty:.3f}")
        
        # No explicit identification penalty (group chats without mentions/thanks)
        if (not evidence.get('has_explicit_mentions', False) and 
            not evidence.get('has_thanks_messages', False) and
            evidence.get('chats', 1) > 0):
            
            # Check if this was inferred in group chats
            best_cluster = evidence.get('best_cluster', {})
            if not best_cluster.get('has_mentions', False) and not best_cluster.get('has_thanks', False):
                inference_penalty = -0.15
                confidence += inference_penalty
                self.logger.debug(f"Group inference penalty: {inference_penalty:.3f}")
        
        return confidence
    
    @log_function_call
    def score_all_identities(self, identities: List[Identity]) -> List[Identity]:
        """
        Calculate confidence scores for all identities.
        
        Args:
            identities: List of Identity objects
            
        Returns:
            List of identities with updated confidence scores
        """
        min_threshold = self.confidence_config.get('min_threshold', 0.6)
        
        scored_identities = []
        for identity in identities:
            confidence = self.calculate_confidence(identity)
            identity.confidence = confidence
            
            if confidence >= min_threshold:
                scored_identities.append(identity)
                self.logger.info(f"Identity '{identity.canonical_name}' passed threshold: {confidence:.3f}")
            else:
                self.logger.info(f"Identity '{identity.canonical_name}' below threshold: {confidence:.3f}")
        
        # Sort by confidence (highest first)
        scored_identities.sort(key=lambda x: x.confidence, reverse=True)
        
        self.logger.info(f"Scored {len(scored_identities)}/{len(identities)} identities above threshold")
        return scored_identities
    
    def get_confidence_explanation(self, identity: Identity) -> Dict[str, Any]:
        """
        Get a detailed explanation of how the confidence score was calculated.
        
        Args:
            identity: Identity object
            
        Returns:
            Dictionary explaining confidence calculation
        """
        explanation = {
            'final_score': identity.confidence,
            'base_score': self.confidence_config.get('base_score', 0.3),
            'bonuses': [],
            'penalties': [],
            'evidence_summary': identity.evidence_summary
        }
        
        evidence = identity.evidence_summary
        
        # Calculate bonuses
        if identity.years_observed > 1:
            multi_year_bonus = self.confidence_config.get('multi_year_bonus', 0.2)
            year_factor = min(identity.years_observed - 1, 3) / 3
            bonus_value = multi_year_bonus * year_factor
            explanation['bonuses'].append({
                'type': 'multi_year',
                'value': bonus_value,
                'reason': f'{identity.years_observed} years observed'
            })
        
        if identity.total_wishers >= 5:
            bonus_value = self.confidence_config.get('unique_wishers_bonus', 0.2)
            explanation['bonuses'].append({
                'type': 'high_wishers',
                'value': bonus_value,
                'reason': f'{identity.total_wishers} total wishers'
            })
        elif identity.total_wishers >= 3:
            bonus_value = self.confidence_config.get('unique_wishers_bonus', 0.2) * 0.5
            explanation['bonuses'].append({
                'type': 'medium_wishers',
                'value': bonus_value,
                'reason': f'{identity.total_wishers} total wishers'
            })
        
        if evidence.get('has_explicit_mentions', False):
            bonus_value = self.confidence_config.get('explicit_mention_bonus', 0.1)
            explanation['bonuses'].append({
                'type': 'explicit_mentions',
                'value': bonus_value,
                'reason': 'Has explicit name mentions'
            })
        
        if evidence.get('has_thanks_messages', False):
            bonus_value = self.confidence_config.get('thanks_bonus', 0.15)
            explanation['bonuses'].append({
                'type': 'thanks_messages',
                'value': bonus_value,
                'reason': 'Has thank you messages'
            })
        
        if identity.phone:
            phone_bonus = self._calculate_phone_confidence_bonus(identity)
            if phone_bonus > 0:
                explanation['bonuses'].append({
                    'type': 'phone_number',
                    'value': phone_bonus,
                    'reason': 'Phone number available'
                })
        
        if evidence.get('date_consistency', False):
            explanation['bonuses'].append({
                'type': 'date_consistency',
                'value': 0.1,
                'reason': 'Consistent dates across observations'
            })
        
        # Calculate penalties
        if not evidence.get('date_consistency', True):
            penalty_value = self.confidence_config.get('conflicting_dates_penalty', -0.2)
            explanation['penalties'].append({
                'type': 'date_inconsistency',
                'value': penalty_value,
                'reason': 'Conflicting dates found'
            })
        
        if identity.years_observed == 1 and identity.total_wishers < 3:
            explanation['penalties'].append({
                'type': 'low_evidence',
                'value': -0.1,
                'reason': 'Limited evidence (single year, few wishers)'
            })
        
        return explanation