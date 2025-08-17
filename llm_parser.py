"""
LLM Parser Module for WhatsApp Birthday Detection.
Uses Azure OpenAI GPT-4.1 to analyze birthday messages and extract structured information.
"""

import os
import json
import logging
import time
from typing import List, Dict, Optional, Any
from datetime import datetime
from dotenv import load_dotenv
from openai import AzureOpenAI

# Load environment variables from .env file
load_dotenv()

from logging_config import get_logger
from models import Message, WishCluster

logger = get_logger('llm_parser')


class LLMParser:
    """LLM-powered parser for analyzing birthday messages and extracting structured data."""
    
    def __init__(self, config_path: str = 'config.json'):
        """Initialize the LLM parser with Azure OpenAI configuration."""
        self.client = None
        self.deployment_name = None
        self.max_messages_per_request = 10
        self.max_tokens = 1000
        self.rate_limit_delay = 2.0
        self.max_retries = 3
        self.retry_delay = 5.0
        self.last_request_time = 0
        
        # Load configuration
        self._load_config(config_path)
        self._initialize_client()
    
    def _load_config(self, config_path: str):
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Get LLM configuration (add to config.json if not present)
            llm_config = config.get('llm', {})
            self.deployment_name = llm_config.get('deployment_name', 'gpt-4')
            self.max_messages_per_request = llm_config.get('max_messages_per_request', 10)
            self.max_tokens = llm_config.get('max_tokens', 1000)
            self.rate_limit_delay = llm_config.get('rate_limit_delay', 2.0)
            self.max_retries = llm_config.get('max_retries', 3)
            self.retry_delay = llm_config.get('retry_delay', 5.0)
            
            logger.info(f"LLM configuration loaded: deployment={self.deployment_name}, "
                       f"max_messages={self.max_messages_per_request}, max_tokens={self.max_tokens}, "
                       f"rate_limit_delay={self.rate_limit_delay}s")
                       
        except Exception as e:
            logger.warning(f"Could not load config from {config_path}: {e}. Using defaults.")
    
    def _initialize_client(self):
        """Initialize Azure OpenAI client."""
        try:
            # Get credentials from environment variables (loaded from .env file)
            api_key = os.getenv('AZURE_OPENAI_API_KEY')
            endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
            deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4.1')
            api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2025-01-01-preview')
            
            if not api_key or not endpoint:
                logger.warning("Azure OpenAI credentials not found in environment variables. "
                             "LLM parsing will be disabled. Set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT.")
                return
            
            self.client = AzureOpenAI(
                api_key=api_key,
                api_version=api_version,
                azure_endpoint=endpoint
            )
            
            # Update deployment name from environment if available
            if deployment:
                self.deployment_name = deployment
            
            logger.info(f"Azure OpenAI client initialized successfully with deployment: {self.deployment_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Azure OpenAI client: {e}")
            self.client = None
    
    def is_available(self) -> bool:
        """Check if LLM parsing is available."""
        return self.client is not None
    
    def analyze_birthday_cluster(self, cluster: WishCluster, messages: List[Message]) -> Dict[str, Any]:
        """
        Analyze a birthday cluster using LLM to extract structured information.
        
        Args:
            cluster: The birthday cluster to analyze
            messages: List of messages in the cluster
            
        Returns:
            Dictionary with extracted information including:
            - date: Birthday date (MM-DD format)
            - person: Name of birthday person
            - phone_number: Phone number if found
            - confidence: Confidence score (0-100)
            - year: Birth year if mentioned
            - analysis: LLM's reasoning
        """
        if not self.is_available():
            logger.warning("LLM parser not available, returning fallback analysis")
            return self._fallback_analysis(cluster, messages)
        
        try:
            # Prepare messages for LLM analysis
            selected_messages = self._select_messages_for_analysis(messages)
            
            if not selected_messages:
                logger.warning(f"No messages to analyze for cluster {cluster.date}")
                return self._fallback_analysis(cluster, messages)
            
            # Create prompt
            prompt = self._create_analysis_prompt(cluster, selected_messages)
            
            # Call LLM
            response = self._call_llm(prompt)
            
            # Parse response
            result = self._parse_llm_response(response, cluster, messages)
            
            logger.info(f"LLM analysis completed for cluster {cluster.date}: "
                       f"person={result.get('person')}, confidence={result.get('confidence')}%")
            
            return result
            
        except Exception as e:
            logger.error(f"LLM analysis failed for cluster {cluster.date}: {e}")
            return self._fallback_analysis(cluster, messages)
    
    def _select_messages_for_analysis(self, messages: List[Message]) -> List[Message]:
        """Select the most relevant messages for LLM analysis."""
        if len(messages) <= self.max_messages_per_request:
            return messages
        
        # Prioritize messages that:
        # 1. Contain birthday wishes keywords
        # 2. Mention names or phone numbers
        # 3. Are longer (more context)
        
        birthday_keywords = ['happy birthday', 'hbd', 'birthday', 'bday', 'born', 'birth', 'wish', 'celebrate']
        
        scored_messages = []
        for msg in messages:
            score = 0
            content_lower = msg.text.lower() if msg.text else ""
            
            # Birthday keywords boost
            for keyword in birthday_keywords:
                if keyword in content_lower:
                    score += 10
            
            # Name mentions (capital letters indicating names)
            capital_words = [word for word in (msg.text or "").split() if word and len(word) > 2 and word[0].isupper()]
            score += len(capital_words) * 2
            
            # Phone mentions
            if any(char.isdigit() for char in (msg.text or "")):
                score += 5
            
            # Message length (more context)
            score += min(len(msg.text or "") // 10, 5)
            
            scored_messages.append((score, msg))
        
        # Sort by score and take top messages
        scored_messages.sort(key=lambda x: x[0], reverse=True)
        return [msg for score, msg in scored_messages[:self.max_messages_per_request]]
    
    def _create_analysis_prompt(self, cluster: WishCluster, messages: List[Message]) -> str:
        """Create prompt for LLM analysis."""
        
        # Format messages for prompt
        formatted_messages = []
        for msg in messages:
            timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M")
            formatted_messages.append(f"[{timestamp}] {msg.sender}: {msg.text}")
        
        messages_text = "\n".join(formatted_messages)
        
        prompt = f"""You are analyzing WhatsApp messages to extract birthday information. 

MESSAGES TO ANALYZE:
{messages_text}

CONTEXT:
- These messages were clustered around the date: {cluster.date}
- They appear to contain birthday wishes
- Extract information about whose birthday it is

TASK:
Analyze these messages and return a JSON object with the following structure:
{{
    "date": "MM-DD",
    "person": "Name of birthday person",
    "phone_number": "Phone number if mentioned (null if not found)",
    "confidence": 85,
    "year": "Birth year if mentioned (null if not found)",
    "analysis": "Brief explanation of your reasoning"
}}

GUIDELINES:
1. Look for birthday wishes directed at someone specific
2. Identify the birthday person from names mentioned, "your", thanks responses, etc.
3. Extract phone numbers if explicitly mentioned in messages
4. Set confidence 80-100% for clear cases, 50-79% for somewhat unclear, 30-49% for uncertain
5. Use MM-DD format for date (e.g., "08-01" for August 1st)
6. Return only valid JSON, no additional text

JSON Response:"""

        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """Call Azure OpenAI with the given prompt, respecting rate limits."""
        try:
            # Rate limiting: ensure minimum delay between requests
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - time_since_last
                logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
            
            # Update last request time
            self.last_request_time = time.time()
            
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert at analyzing WhatsApp messages to extract birthday information. Always respond with valid JSON only."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=0.1  # Low temperature for consistent structured output
            )
            
            content = response.choices[0].message.content.strip()
            logger.debug(f"LLM response: {content}")
            return content
            
        except Exception as e:
            logger.error(f"Azure OpenAI API call failed: {e}")
            raise
    
    def _parse_llm_response(self, response: str, cluster: WishCluster, messages: List[Message]) -> Dict[str, Any]:
        """Parse LLM response and validate the extracted information."""
        try:
            # Try to extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")
            
            json_str = response[json_start:json_end]
            result = json.loads(json_str)
            
            # Validate and clean the response
            validated_result = {
                'date': self._validate_date(result.get('date'), cluster.date),
                'person': self._validate_person(result.get('person')),
                'phone_number': self._validate_phone(result.get('phone_number')),
                'confidence': self._validate_confidence(result.get('confidence')),
                'year': self._validate_year(result.get('year')),
                'analysis': result.get('analysis', 'LLM analysis completed'),
                'source': 'llm',
                'message_count': len(messages),
                'timestamp': datetime.now().isoformat()
            }
            
            return validated_result
            
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}. Response: {response}")
            return self._fallback_analysis(cluster, messages)
    
    def _validate_date(self, date: str, cluster_date: str) -> str:
        """Validate and format date."""
        if not date:
            return cluster_date
        
        # Ensure MM-DD format
        try:
            if len(date) == 5 and date[2] == '-':
                return date
            # Try to parse other formats
            dt = datetime.strptime(date, '%m-%d')
            return dt.strftime('%m-%d')
        except:
            return cluster_date
    
    def _validate_person(self, person: str) -> Optional[str]:
        """Validate person name."""
        if not person or person.lower() in ['null', 'none', 'unknown']:
            return None
        return person.strip()
    
    def _validate_phone(self, phone: str) -> Optional[str]:
        """Validate phone number."""
        if not phone or phone.lower() in ['null', 'none']:
            return None
        # Basic phone validation - contains digits
        if any(char.isdigit() for char in phone):
            return phone.strip()
        return None
    
    def _validate_confidence(self, confidence: Any) -> int:
        """Validate confidence score."""
        try:
            conf = int(confidence) if confidence else 50
            return max(0, min(100, conf))  # Clamp to 0-100
        except:
            return 50
    
    def _validate_year(self, year: Any) -> Optional[int]:
        """Validate birth year."""
        if not year or str(year).lower() in ['null', 'none']:
            return None
        try:
            y = int(year)
            if 1900 <= y <= 2024:  # Reasonable year range
                return y
        except:
            pass
        return None
    
    def _fallback_analysis(self, cluster: WishCluster, messages: List[Message]) -> Dict[str, Any]:
        """Provide fallback analysis when LLM is not available."""
        
        # Try to extract basic information from messages
        person = None
        phone_number = None
        
        # Look for names in messages (simple heuristic)
        for msg in messages:
            words = (msg.text or "").split()
            for word in words:
                if word and len(word) > 2 and word[0].isupper() and word.isalpha():
                    if not person:
                        person = word
                    break
        
        # Look for phone numbers
        for msg in messages:
            words = (msg.text or "").split()
            for word in words:
                if any(char.isdigit() for char in word) and len(word) >= 10:
                    phone_number = word
                    break
        
        return {
            'date': cluster.date,
            'person': person,
            'phone_number': phone_number,
            'confidence': 40,  # Lower confidence for fallback
            'year': None,
            'analysis': 'Fallback analysis (LLM not available)',
            'source': 'fallback',
            'message_count': len(messages),
            'timestamp': datetime.now().isoformat()
        }


# Global instance
llm_parser = LLMParser()