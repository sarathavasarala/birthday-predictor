"""
Progress tracking module for real-time UI updates.
Uses Server-Sent Events to show processing progress.
"""

import json
import threading
from typing import Dict, Any, Optional
from datetime import datetime
from flask import Response
from logging_config import get_logger

logger = get_logger('progress')


class ProgressTracker:
    """Thread-safe progress tracker for UI updates."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: Dict[str, Dict[str, Any]] = {}
    
    def start_session(self, session_id: str, total_steps: int, description: str = "Processing") -> None:
        """Start a new progress session."""
        with self._lock:
            self._sessions[session_id] = {
                'total_steps': total_steps,
                'current_step': 0,
                'description': description,
                'status': 'running',
                'current_task': 'Starting...',
                'start_time': datetime.now(),
                'details': [],
                'error': None
            }
        logger.info(f"Progress session started: {session_id} - {description} ({total_steps} steps)")
    
    def update_progress(self, session_id: str, step: int, task: str, details: Optional[str] = None) -> None:
        """Update progress for a session."""
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                session['current_step'] = step
                session['current_task'] = task
                session['last_update'] = datetime.now()
                
                if details:
                    session['details'].append({
                        'timestamp': datetime.now().isoformat(),
                        'step': step,
                        'task': task,
                        'details': details
                    })
                
                # Calculate percentage
                percent = min(100, (step / session['total_steps']) * 100) if session['total_steps'] > 0 else 0
                session['percent'] = percent
                
                logger.info(f"Progress update {session_id}: Step {step}/{session['total_steps']} - {task}")
    
    def complete_session(self, session_id: str, success: bool = True, error: Optional[str] = None) -> None:
        """Complete a progress session."""
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                session['status'] = 'completed' if success else 'error'
                session['percent'] = 100 if success else session.get('percent', 0)
                session['end_time'] = datetime.now()
                session['error'] = error
                
                status_text = "completed successfully" if success else f"failed: {error}"
                logger.info(f"Progress session {session_id} {status_text}")
    
    def get_progress(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current progress for a session."""
        with self._lock:
            return self._sessions.get(session_id, None)
    
    def cleanup_session(self, session_id: str) -> None:
        """Clean up a completed session."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.debug(f"Progress session cleaned up: {session_id}")
    
    def stream_progress(self, session_id: str):
        """Generate Server-Sent Events stream for progress updates."""
        def generate():
            while True:
                progress = self.get_progress(session_id)
                if not progress:
                    yield f"data: {json.dumps({'error': 'Session not found'})}\n\n"
                    break
                
                # Send progress update
                yield f"data: {json.dumps(progress, default=str)}\n\n"
                
                # Stop streaming if completed or errored
                if progress['status'] in ['completed', 'error']:
                    break
                
                # Wait before next update
                import time
                time.sleep(0.5)  # Update every 500ms
        
        return Response(generate(), mimetype='text/event-stream')


# Global progress tracker instance
progress_tracker = ProgressTracker()