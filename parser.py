"""
WhatsApp chat export parser.
Handles different export formats and extracts structured data from chat files.
"""

import re
import json
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
from models import Message, Chat, Participant, ChatType, MessageType
from logging_config import get_logger, log_function_call, LoggedOperation

logger = get_logger('parser')


class WhatsAppParser:
    """Parses WhatsApp chat export files and extracts structured data."""
    
    def __init__(self, config_path: str = "config.json"):
        self.logger = get_logger('parser')
        self.config = self._load_config(config_path)
        
        # Load export formats from config
        self.export_formats = self.config.get('export_formats', {})
        self.datetime_patterns = []
        
        # Build datetime patterns from config
        for format_name, format_config in self.export_formats.items():
            pattern_info = {
                'name': format_name,
                'pattern': format_config['pattern'],
                'date_format': format_config['date_format'],
                'time_format': format_config['time_format'],
                'groups': format_config['groups']
            }
            self.datetime_patterns.append(pattern_info)
            self.logger.debug(f"Loaded format: {format_name}")
        
        # Fallback patterns if config is missing
        if not self.datetime_patterns:
            self._load_fallback_patterns()
        
        # System message patterns
        self.system_patterns = [
            r'.*added\s+([+\d\s\-\(\)]+)',  # X added +1 234 567 890
            r'.*changed.*phone.*number.*to\s+([+\d\s\-\(\)]+)',  # X changed phone number to +...
            r'.*left',  # X left
            r'Messages.*secured.*end-to-end.*encryption',
            r'.*created.*group',
            r'.*changed.*group.*subject',
            r'.*image.*omitted',
            r'.*video.*omitted',
            r'.*audio.*omitted',
            r'.*document.*omitted',
            r'.*sticker.*omitted',
            r'.*GIF.*omitted',
            r'.*contact.*omitted',
            r'.*location.*omitted',
            r'<Media omitted>',  # Android format
            r'<This message was edited>',  # Edited message marker
        ]
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            self.logger.info(f"Loaded configuration from {config_path}")
            return config
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.warning(f"Could not load config from {config_path}: {e}")
            return {}
    
    def _load_fallback_patterns(self):
        """Load fallback patterns if config is missing or incomplete."""
        self.datetime_patterns = [
            {
                'name': 'fallback_us',
                'pattern': r'(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2})\s*(AM|PM)?\s*-\s*([^:]+?):\s*(.*)',
                'date_format': '%m/%d/%y',
                'time_format': '%I:%M %p',
                'groups': ['date', 'time', 'ampm', 'sender', 'message']
            },
            {
                'name': 'fallback_24h',
                'pattern': r'(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2})\s*-\s*([^:]+?):\s*(.*)',
                'date_format': '%d/%m/%y',
                'time_format': '%H:%M',
                'groups': ['date', 'time', 'sender', 'message']
            }
        ]
        self.logger.warning("Using fallback datetime patterns")
    
    @log_function_call
    def parse_file(self, file_path: str) -> Tuple[Chat, List[Message], List[Participant]]:
        """
        Parse a WhatsApp export file and return structured data.
        
        Args:
            file_path: Path to the WhatsApp export file
            
        Returns:
            Tuple of (Chat, Messages, Participants)
        """
        with LoggedOperation(f"Parsing WhatsApp file: {file_path}", 'parser'):
            try:
                # Read file content
                file_content = self._read_file(file_path)
                self.logger.info(f"Read {len(file_content)} lines from {file_path}")
                
                # Detect format and extract basic info
                chat_info = self._extract_chat_info(file_path, file_content)
                self.logger.info(f"Detected chat: {chat_info['name']}, type: {chat_info['type']}")
                
                # Parse messages
                messages = self._parse_messages(file_content)
                self.logger.info(f"Parsed {len(messages)} messages")
                
                # Extract participants
                participants = self._extract_participants(messages, chat_info)
                self.logger.info(f"Identified {len(participants)} participants")
                
                # Create chat object
                chat = Chat(
                    name=chat_info['name'],
                    chat_type=chat_info['type'],
                    file_path=file_path,
                    participants=participants,
                    message_count=len(messages),
                    date_range=self._get_date_range(messages)
                )
                
                return chat, messages, participants
                
            except Exception as e:
                self.logger.error(f"Failed to parse file {file_path}: {str(e)}", exc_info=True)
                raise
    
    def _read_file(self, file_path: str) -> List[str]:
        """Read file content with proper encoding detection."""
        encodings = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.readlines()
                self.logger.debug(f"Successfully read file with {encoding} encoding")
                return [line.strip() for line in content if line.strip()]
            except UnicodeDecodeError:
                self.logger.debug(f"Failed to read with {encoding} encoding")
                continue
        
        raise ValueError(f"Could not read file {file_path} with any supported encoding")
    
    @log_function_call
    def _extract_chat_info(self, file_path: str, content: List[str]) -> Dict[str, Any]:
        """Extract basic chat information from file path and content."""
        file_name = Path(file_path).stem
        
        # Try to determine chat type and name from filename or content
        chat_name = file_name
        chat_type = ChatType.UNKNOWN
        
        # Look for group indicators in filename
        if any(keyword in file_name.lower() for keyword in ['group', 'grupo', 'groupe']):
            chat_type = ChatType.GROUP
        
        # Analyze first few messages for patterns
        if content:
            # Look for group-specific patterns in early messages
            early_messages = content[:50]  # Check first 50 lines
            
            system_message_count = 0
            unique_senders = set()
            
            for line in early_messages:
                parsed = self._parse_single_message(line)
                if parsed:
                    if parsed['message_type'] == MessageType.SYSTEM:
                        system_message_count += 1
                        # Check for group creation messages
                        if any(keyword in line.lower() for keyword in ['created group', 'group subject']):
                            chat_type = ChatType.GROUP
                    else:
                        unique_senders.add(parsed['sender'])
            
            # If we see many unique senders, it's likely a group
            if len(unique_senders) > 2:
                chat_type = ChatType.GROUP
            elif len(unique_senders) == 2:
                chat_type = ChatType.DIRECT
        
        self.logger.debug(f"Chat info: name='{chat_name}', type={chat_type}")
        
        return {
            'name': chat_name,
            'type': chat_type,
            'file_path': file_path
        }
    
    @log_function_call
    def _parse_messages(self, content: List[str]) -> List[Message]:
        """Parse all messages from file content."""
        messages = []
        current_message = None
        
        for line_num, line in enumerate(content, 1):
            try:
                parsed = self._parse_single_message(line)
                
                if parsed:
                    # If we have a pending multiline message, save it first
                    if current_message:
                        messages.append(current_message)
                    
                    # Create new message
                    current_message = Message(
                        timestamp=parsed['timestamp'],
                        sender=parsed['sender'],
                        text=parsed['text'],
                        message_type=parsed['message_type'],
                        original_line=line
                    )
                else:
                    # This line is a continuation of the previous message
                    if current_message:
                        current_message.text += '\n' + line
                        current_message.original_line += '\n' + line
                    else:
                        # Orphan line - log and skip
                        self.logger.warning(f"Orphan line {line_num}: {line[:50]}...")
                
            except Exception as e:
                self.logger.error(f"Error parsing line {line_num}: {str(e)}", exc_info=True)
                continue
        
        # Don't forget the last message
        if current_message:
            messages.append(current_message)
        
        self.logger.info(f"Successfully parsed {len(messages)} messages")
        return messages
    
    def _parse_single_message(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single message line and return structured data."""
        line = line.strip()
        if not line:
            return None
        
        # Try each datetime pattern from config
        for pattern_info in self.datetime_patterns:
            try:
                pattern = pattern_info['pattern']
                match = re.match(pattern, line)
                if match:
                    groups = match.groups()
                    group_names = pattern_info['groups']
                    
                    # Extract components based on group names
                    components = dict(zip(group_names, groups))
                    
                    # Handle different time formats
                    if 'ampm' in components and components['ampm']:
                        time_str = f"{components['time']} {components['ampm']}"
                        time_format = pattern_info['time_format']
                    else:
                        time_str = components['time']
                        time_format = pattern_info['time_format']
                    
                    # Parse datetime
                    timestamp = self._parse_datetime_flexible(
                        components['date'], 
                        time_str,
                        pattern_info['date_format'],
                        time_format
                    )
                    
                    if timestamp:
                        # Clean sender name (remove prefixes like "MS - ")
                        sender = self._clean_sender_name(components['sender'])
                        message_text = components['message'].strip()
                        
                        # Determine message type
                        message_type = self._classify_message_type(message_text, sender)
                        
                        self.logger.debug(f"Parsed with format {pattern_info['name']}: {sender}")
                        
                        return {
                            'timestamp': timestamp,
                            'sender': sender,
                            'text': message_text,
                            'message_type': message_type,
                            'raw_sender': components['sender'],  # Keep original for analysis
                            'format_used': pattern_info['name']
                        }
                        
            except Exception as e:
                self.logger.debug(f"Failed to parse with format {pattern_info['name']}: {e}")
                continue
        
        # If no pattern matches, log for debugging
        self.logger.debug(f"No pattern matched for line: {line[:100]}...")
        return None
    
    def _parse_datetime_flexible(self, date_str: str, time_str: str, 
                               date_format: str, time_format: str) -> Optional[datetime]:
        """Parse date and time with flexible format handling."""
        try:
            # Handle 2-digit years
            if 'YY' not in date_format.upper() and len(date_str.split('/')[-1]) == 2:
                # Convert YY format to YYYY
                year_part = date_str.split('/')[-1]
                if int(year_part) <= 30:  # Assume 00-30 = 2000-2030
                    date_str = date_str.replace(f'/{year_part}', f'/20{year_part}')
                else:  # 31-99 = 1931-1999
                    date_str = date_str.replace(f'/{year_part}', f'/19{year_part}')
                date_format = date_format.replace('%y', '%Y')
            
            datetime_str = f"{date_str} {time_str}"
            combined_format = f"{date_format} {time_format}"
            
            return datetime.strptime(datetime_str, combined_format)
            
        except ValueError as e:
            self.logger.debug(f"DateTime parsing failed: {datetime_str} with format {combined_format}: {e}")
            
            # Try alternative formats
            fallback_formats = [
                f"{date_format} %H:%M",  # 24-hour fallback
                f"{date_format} %I:%M",  # 12-hour without AM/PM
                "%m/%d/%Y %I:%M %p",    # Common US format
                "%d/%m/%Y %H:%M",       # Common EU format
            ]
            
            for fmt in fallback_formats:
                try:
                    return datetime.strptime(datetime_str, fmt)
                except ValueError:
                    continue
            
            return None
    
    def _clean_sender_name(self, raw_sender: str) -> str:
        """Clean sender name by removing common prefixes."""
        sender = raw_sender.strip()
        
        # Remove common prefixes from config
        name_config = self.config.get('patterns', {}).get('name_extraction', {})
        prefixes = name_config.get('name_prefixes', ['MS - ', 'Mr. ', 'Mrs. ', 'Dr. '])
        
        for prefix in prefixes:
            if sender.startswith(prefix):
                sender = sender[len(prefix):].strip()
                break
        
        return sender
        """Parse date and time strings into datetime object."""
        # Common datetime format patterns
        datetime_formats = [
            "%m/%d/%y %I:%M %p",      # 12/31/20 9:08 PM
            "%m/%d/%Y %I:%M %p",      # 12/31/2020 9:08 PM
            "%d/%m/%y %H:%M",         # 31/12/20 21:08
            "%d/%m/%Y %H:%M",         # 31/12/2020 21:08
            "%Y-%m-%d %H:%M",         # 2020-12-31 21:08
            "%m/%d/%y %H:%M",         # 12/31/20 21:08
            "%m/%d/%Y %H:%M",         # 12/31/2020 21:08
        ]
        
        datetime_str = f"{date_str} {time_str}"
        
        for fmt in datetime_formats:
            try:
                return datetime.strptime(datetime_str, fmt)
            except ValueError:
                continue
        
        # If all else fails, try a more flexible approach
        raise ValueError(f"Could not parse datetime: {datetime_str}")
    
    def _classify_message_type(self, text: str, sender: str) -> MessageType:
        """Classify the type of message."""
        text_lower = text.lower()
        
        # Check for media omitted messages (multiple formats)
        media_patterns = [
            'omitted',
            '<media omitted>',
            'image omitted',
            'video omitted',
            'audio omitted',
            'document omitted'
        ]
        
        for pattern in media_patterns:
            if pattern in text_lower:
                return MessageType.MEDIA_OMITTED
        
        # Check for edited messages
        if 'this message was edited' in text_lower:
            return MessageType.MEDIA_OMITTED  # Treat as non-content for analysis
        
        # Check for system messages
        for pattern in self.system_patterns:
            if re.search(pattern, text_lower):
                return MessageType.SYSTEM
        
        return MessageType.NORMAL
    
    @log_function_call
    def _extract_participants(self, messages: List[Message], chat_info: Dict[str, Any]) -> List[Participant]:
        """Extract participant information from messages."""
        participants_dict = {}
        phone_mappings = {}
        
        # Get phone patterns from config
        name_config = self.config.get('patterns', {}).get('name_extraction', {})
        phone_patterns = name_config.get('phone_patterns', [r'[+]?[\d\s\-\(\)]{10,}'])
        
        for message in messages:
            if not message.sender:
                continue
            
            sender = message.sender.strip()
            
            # Check if sender is a phone number
            is_phone = any(re.match(pattern, sender) for pattern in phone_patterns)
            
            if is_phone:
                # Sender is a phone number
                clean_phone = self._clean_phone_number(sender)
                if clean_phone not in participants_dict:
                    participants_dict[clean_phone] = Participant(
                        display_name=sender,
                        phone=clean_phone,
                        canonical_name=clean_phone
                    )
            else:
                # Sender is a display name
                if sender not in participants_dict:
                    participants_dict[sender] = Participant(
                        display_name=sender,
                        canonical_name=sender
                    )
            
            # Extract phone numbers from system messages
            if message.message_type == MessageType.SYSTEM:
                phone_numbers = self._extract_phone_from_system_message(message.text)
                for phone in phone_numbers:
                    clean_phone = self._clean_phone_number(phone)
                    phone_mappings[sender] = clean_phone
            
            # Extract phone mentions from message text (like @1234567890)
            if message.text:
                mentioned_phones = self._extract_phone_mentions(message.text)
                for phone in mentioned_phones:
                    clean_phone = self._clean_phone_number(phone)
                    # Try to associate this phone with known participants
                    if clean_phone not in participants_dict:
                        participants_dict[clean_phone] = Participant(
                            display_name=clean_phone,
                            phone=clean_phone,
                            canonical_name=clean_phone
                        )
        
        # Apply phone mappings to participants
        for participant in participants_dict.values():
            if participant.display_name in phone_mappings:
                participant.phone = phone_mappings[participant.display_name]
        
        participants = list(participants_dict.values())
        self.logger.info(f"Extracted {len(participants)} unique participants")
        
        return participants
    
    def _extract_phone_mentions(self, text: str) -> List[str]:
        """Extract phone number mentions from message text (like @1234567890)."""
        phone_mentions = []
        
        # Patterns for phone mentions
        mention_patterns = [
            r'@(\d{10,15})',  # @1234567890
            r'@([+]\d{1,3}\d{10,12})',  # @+1234567890
            r'([+]\d{1,3}\s?\d{5}\s?\d{5})',  # +91 12345.*67890
        ]
        
        for pattern in mention_patterns:
            matches = re.findall(pattern, text)
            phone_mentions.extend(matches)
        
        return phone_mentions
    
    def _clean_phone_number(self, phone_str: str) -> str:
        """Clean and normalize phone number."""
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', phone_str)
        
        # Ensure it starts with + if it looks international
        if len(cleaned) > 10 and not cleaned.startswith('+'):
            cleaned = '+' + cleaned
        
        return cleaned
    
    def _extract_phone_from_system_message(self, text: str) -> List[str]:
        """Extract phone numbers from system messages."""
        phone_pattern = r'[+]?[\d\s\-\(\)]{10,}'
        phones = re.findall(phone_pattern, text)
        return [self._clean_phone_number(phone) for phone in phones]
    
    def _get_date_range(self, messages: List[Message]) -> Optional[Tuple[datetime, datetime]]:
        """Get the date range of messages."""
        if not messages:
            return None
        
        timestamps = [msg.timestamp for msg in messages if msg.timestamp]
        if not timestamps:
            return None
        
        return min(timestamps), max(timestamps)