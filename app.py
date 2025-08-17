"""
Main Flask application for WhatsApp Birthday Detection.
Provides web interface for uploading files and viewing results.

TODO: Add Google Calendar integration
- Create birthday events from detected birthdays
- Use Google Calendar API to schedule recurring events
- Add user authentication and calendar permission flow
- Allow users to select which birthdays to add to calendar
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, Response
from werkzeug.utils import secure_filename

# Load environment variables from .env file
load_dotenv()

from logging_config import setup_logging, get_logger, LoggedOperation
from models import DatabaseManager
from parser import WhatsAppParser
from analyzer import BirthdayAnalyzer
from identity import IdentityResolver
from confidence import ConfidenceScorer
from llm_parser import llm_parser
from progress_tracker import progress_tracker

# Initialize logging
setup_logging()
logger = get_logger('app')

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize components
db_manager = DatabaseManager()
parser = WhatsAppParser()
analyzer = BirthdayAnalyzer()
identity_resolver = IdentityResolver()
confidence_scorer = ConfidenceScorer()


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """Main upload page."""
    llm_status = {
        'available': llm_parser.is_available(),
        'deployment': llm_parser.deployment_name if llm_parser.is_available() else None
    }
    return render_template('index.html', llm_status=llm_status)


@app.route('/upload', methods=['POST'])
def upload_files():
    """Handle file upload and redirect to processing page."""
    import uuid
    session_id = str(uuid.uuid4())
    
    with LoggedOperation("Processing uploaded files", 'app'):
        try:
            # Check if files were uploaded
            if 'files' not in request.files:
                flash('No files selected', 'error')
                return redirect(url_for('index'))
            
            files = request.files.getlist('files')
            
            if not files or all(f.filename == '' for f in files):
                flash('No files selected', 'error')
                return redirect(url_for('index'))
            
            # Save uploaded files first
            uploaded_files = []
            for file in files:
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{timestamp}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    uploaded_files.append({
                        'original_name': file.filename,
                        'file_path': file_path
                    })
            
            if not uploaded_files:
                flash('No valid files uploaded. Only .txt files are allowed.', 'error')
                return redirect(url_for('index'))
            
            # Store upload info in session
            session['uploaded_files'] = uploaded_files
            session['progress_session_id'] = session_id
            
            # Start background processing
            import threading
            thread = threading.Thread(target=process_files_background, args=(session_id, uploaded_files))
            thread.daemon = True
            thread.start()
            
            # Redirect to processing page
            return redirect(url_for('process_page'))
            
        except Exception as e:
            logger.error(f"Unexpected error in upload_files: {str(e)}", exc_info=True)
            flash(f'Error processing upload: {str(e)}', 'error')
            return redirect(url_for('index'))


def process_files_background(session_id, uploaded_files):
    """Process files in background thread with progress updates."""
    try:
        # Initialize progress tracking
        total_files = len(uploaded_files)
        progress_tracker.start_session(session_id, total_files * 3, "Processing WhatsApp files")
        
        # Process each file
        processed_files = []
        all_clusters = []
        all_participants = []
        all_messages = []
        current_step = 0
        
        for file_index, file_info in enumerate(uploaded_files):
            try:
                current_step += 1
                progress_tracker.update_progress(
                    session_id, current_step, 
                    f"Parsing file: {file_info['original_name']}"
                )
                
                # Process the file
                chat, messages, participants = parser.parse_file(file_info['file_path'])
                
                current_step += 1
                progress_tracker.update_progress(
                    session_id, current_step, 
                    f"Analyzing messages from {file_info['original_name']}"
                )
                
                # Save to database
                chat_id = db_manager.save_chat(chat)
                
                # Update message and participant chat_ids
                for msg in messages:
                    msg.chat_id = chat_id
                for participant in participants:
                    participant.chat_id = chat_id
                
                # Save messages
                message_ids = db_manager.save_messages(messages)
                
                # Update message IDs
                for i, msg in enumerate(messages):
                    msg.id = message_ids[i]
                
                # Analyze messages for birthday wishes
                wish_messages = analyzer.analyze_messages(messages)
                
                if wish_messages:
                    # Cluster wishes by date
                    clusters = analyzer.cluster_wishes_by_date(messages, wish_messages, chat_id)
                    
                    # Infer targets for each cluster
                    for cluster in clusters:
                        target_id = analyzer.infer_birthday_target(
                            cluster, participants, messages, chat.chat_type.value
                        )
                        cluster.target_participant_id = target_id
                        
                        # Adjust birthday date if needed
                        cluster.date = analyzer.adjust_birthday_date(cluster, messages)
                    
                    # Filter clusters with identified targets
                    valid_clusters = clusters  # Show all clusters, not just those with identified targets
                    all_clusters.extend(valid_clusters)
                    all_participants.extend(participants)
                    all_messages.extend(messages)
                    
                    logger.info(f"Processed {file_info['original_name']}: {len(valid_clusters)} valid clusters")
                
                processed_files.append({
                    'filename': file_info['original_name'],
                    'status': 'success',
                    'clusters': len([c for c in all_clusters if c.chat_id == chat_id]),
                    'participants': len(participants)
                })
                
            except Exception as e:
                logger.error(f"Error processing file {file_info['original_name']}: {str(e)}", exc_info=True)
                processed_files.append({
                    'filename': file_info['original_name'],
                    'status': 'error',
                    'error': str(e)
                })
        
        if not all_clusters:
            progress_tracker.complete_session(session_id, success=False, error="No birthday wishes found in the uploaded files.")
            return
        
        # Update progress for LLM analysis phase
        progress_tracker.update_progress(
            session_id, current_step + 1,
            f"Starting AI analysis of {len(all_clusters)} birthday clusters"
        )
        
        # Create simple birthday summaries from clusters using LLM analysis
        birthday_summaries = []
        for cluster_index, cluster in enumerate(all_clusters):
            # Update progress for each cluster
            progress_tracker.update_progress(
                session_id, current_step + 2 + cluster_index,
                f"Analyzing birthday cluster {cluster.date.strftime('%m-%d')}...",
                f"Processing cluster {cluster_index + 1}/{len(all_clusters)}"
            )
            
            # Get cluster messages for LLM analysis
            cluster_messages = [msg for msg in all_messages if any(wish.message_id == msg.id for wish in cluster.wish_messages)]
            
            # Use LLM parser to analyze the cluster
            llm_result = llm_parser.analyze_birthday_cluster(cluster, cluster_messages)
            
            # Update progress with results
            person = llm_result.get('person', 'Unknown')
            confidence = llm_result.get('confidence', 40)
            progress_tracker.update_progress(
                session_id, current_step + 2 + cluster_index,
                f"✅ Identified: {person} ({confidence}% confidence)",
                f"Birthday: {cluster.date.strftime('%m-%d')}, Person: {person}"
            )
            
            # Create comprehensive summary
            summary = {
                'canonical_name': llm_result.get('person') or f"Birthday {cluster.date.strftime('%m-%d')}",
                'name': llm_result.get('person') or "Unknown",
                'target': llm_result.get('person') or "Unknown",
                'birthday_date': llm_result.get('date', cluster.date.strftime("%m-%d")),
                'birthday_month': cluster.date.month,
                'birthday_day': cluster.date.day,
                'birthday_year': llm_result.get('year') or cluster.date.year,
                'full_date': cluster.date.strftime("%B %d, %Y"),
                'year': llm_result.get('year') or cluster.date.year,
                'years_observed': 1,
                'total_wishers': cluster.unique_wishers or 0,
                'wisher_count': cluster.unique_wishers or 0,
                'wishers': cluster.unique_wishers or 0,
                'total_wishes': len(cluster.wish_messages),
                'phone_number': llm_result.get('phone_number'),
                'messages': [
                    {
                        'sender': msg.sender, 
                        'content': msg.text[:100],  # First 100 chars
                        'timestamp': msg.timestamp.strftime("%H:%M")
                    } 
                    for msg in cluster_messages[:5]  # First 5 messages
                ],
                'confidence': llm_result.get('confidence', 40) / 100,  # Convert percentage to decimal for template
                'confidence_percent': llm_result.get('confidence', 40),  # Keep percentage for display
                'llm_analysis': llm_result.get('analysis', 'No analysis available'),
                'llm_source': llm_result.get('source', 'unknown'),
                'message_count': len(cluster_messages)
            }
            birthday_summaries.append(summary)
        
        # Sort by confidence (highest confidence first)
        birthday_summaries.sort(key=lambda x: x['confidence_percent'], reverse=True)
        
        # Store results temporarily (in a simple in-memory cache)
        global processing_results
        if 'processing_results' not in globals():
            processing_results = {}
        
        processing_results[session_id] = {
            'birthday_results': birthday_summaries,
            'processing_summary': {
                'total_files': len(processed_files),
                'successful_files': len([f for f in processed_files if f['status'] == 'success']),
                'total_clusters': len(all_clusters),
                'total_predictions': len(birthday_summaries),
                'processing_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        
        # Complete progress tracking
        progress_tracker.complete_session(session_id, success=True)
        
    except Exception as e:
        logger.error(f"Background processing error: {str(e)}", exc_info=True)
        progress_tracker.complete_session(session_id, success=False, error=str(e))


@app.route('/process')
def process_page():
    """Show processing page with live progress."""
    session_id = session.get('progress_session_id')
    if not session_id:
        flash('No active processing session found.', 'error')
        return redirect(url_for('index'))
    
    return render_template('process.html', session_id=session_id)

@app.route('/progress/<session_id>')
def progress_stream(session_id):
    """Stream progress updates via Server-Sent Events."""
    def generate():
        # Set up SSE headers
        yield "data: " + json.dumps({"status": "connected", "message": "Connection established"}) + "\n\n"
        
        # Track last sent detail index to only send new updates
        last_detail_index = 0
        
        # Stream progress updates
        while True:
            progress = progress_tracker.get_progress(session_id)
            if not progress:
                yield f"data: {json.dumps({'error': 'Session not found'})}\n\n"
                break
            
            # Send basic progress data
            progress_data = {
                'progress': progress.get('percent', 0),
                'current_task': progress.get('current_task', ''),
                'status': progress.get('status', 'running'),
                'step': progress.get('current_step', 0),
                'total_steps': progress.get('total_steps', 1)
            }
            
            # Send new activity details
            details = progress.get('details', [])
            if len(details) > last_detail_index:
                new_details = details[last_detail_index:]
                for detail in new_details:
                    activity_data = progress_data.copy()
                    activity_data['activity'] = detail.get('task', '') + (f" - {detail.get('details', '')}" if detail.get('details') else "")
                    activity_data['activity_type'] = 'update'
                    yield f"data: {json.dumps(activity_data, default=str)}\n\n"
                last_detail_index = len(details)
            
            # Send current progress without activity
            yield f"data: {json.dumps(progress_data, default=str)}\n\n"
            
            # Stop streaming if completed or errored
            if progress['status'] in ['completed', 'error']:
                break
            
            # Wait before next update
            time.sleep(0.5)  # Update every 500ms
    
    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Cache-Control'
    })

@app.route('/results')
def results():
    """Display results page."""
    try:
        # Get results from session or global storage
        session_id = session.get('progress_session_id')
        
        # Try to get from global storage first
        birthday_results = []
        processing_summary = {}
        
        if session_id and 'processing_results' in globals() and session_id in processing_results:
            data = processing_results[session_id]
            birthday_results = data.get('birthday_results', [])
            processing_summary = data.get('processing_summary', {})
            
            # Also store in session for future use
            session['birthday_results'] = birthday_results
            session['processing_summary'] = processing_summary
        else:
            # Fallback to session storage
            birthday_results = session.get('birthday_results', [])
            processing_summary = session.get('processing_summary', {})
        
        if not birthday_results:
            flash('No results found. Please upload WhatsApp chat files first.', 'info')
            return redirect(url_for('index'))
        
        return render_template('results.html', 
                             identities=birthday_results,
                             summary=processing_summary)
        
    except Exception as e:
        logger.error(f"Error loading results: {str(e)}", exc_info=True)
        flash('Error loading results.', 'error')
        return redirect(url_for('index'))


@app.route('/api/identities')
def api_identities():
    """API endpoint to get identities as JSON."""
    try:
        identities = db_manager.get_all_identities()
        return jsonify([identity.to_dict() for identity in identities])
    except Exception as e:
        logger.error(f"Error in API endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve identities'}), 500


@app.route('/api/identity/<int:identity_id>')
def api_identity_detail(identity_id):
    """API endpoint to get detailed information about a specific identity."""
    try:
        identities = db_manager.get_all_identities()
        identity = next((i for i in identities if i.id == identity_id), None)
        
        if not identity:
            return jsonify({'error': 'Identity not found'}), 404
        
        # Get confidence explanation
        explanation = confidence_scorer.get_confidence_explanation(identity)
        
        result = identity.to_dict()
        result['confidence_explanation'] = explanation
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting identity detail: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve identity details'}), 500


@app.route('/clear', methods=['POST'])
def clear_data():
    """Clear all data from the database."""
    try:
        db_manager.clear_all_data()
        flash('All data cleared successfully.', 'success')
        logger.info("Database cleared by user request")
    except Exception as e:
        logger.error(f"Error clearing data: {str(e)}", exc_info=True)
        flash('Error clearing data.', 'error')
    
    return redirect(url_for('index'))


@app.route('/export')
def export_csv():
    """Export results as CSV."""
    from flask import Response
    import csv
    import io
    
    try:
        identities = db_manager.get_all_identities()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Name', 'Birthday', 'Phone', 'Confidence', 'Years Observed', 'Total Wishers'])
        
        # Write data
        for identity in identities:
            writer.writerow([
                identity.canonical_name or '',
                identity.birthday_date or '',
                identity.phone or '',
                f"{identity.confidence:.3f}",
                identity.years_observed,
                identity.total_wishers
            ])
        
        output.seek(0)
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=birthday_predictions.csv'}
        )
        
    except Exception as e:
        logger.error(f"Error exporting CSV: {str(e)}", exc_info=True)
        flash('Error exporting data.', 'error')
        return redirect(url_for('results'))


@app.errorhandler(413)
def file_too_large(error):
    """Handle file size too large error."""
    flash('File size too large. Maximum size is 16MB.', 'error')
    return redirect(url_for('index'))


@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors."""
    logger.error(f"Internal server error: {str(error)}", exc_info=True)
    flash('An internal error occurred. Please try again.', 'error')
    return redirect(url_for('index'))


if __name__ == '__main__':
    logger.info("Starting WhatsApp Birthday Detection App")
    app.run(debug=True, port=5001)