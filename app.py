"""
Main Flask application for WhatsApp Birthday Detection.
Provides web interface for uploading files and viewing results.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename

from logging_config import setup_logging, get_logger, LoggedOperation
from models import DatabaseManager
from parser import WhatsAppParser
from analyzer import BirthdayAnalyzer
from identity import IdentityResolver
from confidence import ConfidenceScorer

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
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_files():
    """Handle file upload and processing."""
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
            
            # Process each file
            processed_files = []
            all_clusters = []
            all_participants = []
            all_messages = []  # Collect all messages for later use
            
            for file in files:
                if file and file.filename and allowed_file(file.filename):
                    try:
                        # Save uploaded file
                        filename = secure_filename(file.filename)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"{timestamp}_{filename}"
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(file_path)
                        
                        # Process the file
                        chat, messages, participants = parser.parse_file(file_path)
                        
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
                            all_messages.extend(messages)  # Collect messages for later use
                            
                            logger.info(f"Processed {filename}: {len(valid_clusters)} valid clusters")
                        
                        processed_files.append({
                            'filename': file.filename,
                            'status': 'success',
                            'clusters': len([c for c in all_clusters if c.chat_id == chat_id]),
                            'participants': len(participants)
                        })
                        
                    except Exception as e:
                        logger.error(f"Error processing file {file.filename}: {str(e)}", exc_info=True)
                        processed_files.append({
                            'filename': file.filename,
                            'status': 'error',
                            'error': str(e)
                        })
                else:
                    flash(f'Invalid file type: {file.filename}. Only .txt files are allowed.', 'error')
            
            if not all_clusters:
                flash('No birthday wishes found in the uploaded files.', 'warning')
                return redirect(url_for('index'))
            
            # Create simple birthday summaries from clusters - skip complex identity resolution
            birthday_summaries = []
            for cluster in all_clusters:
                # Extract mentioned names and phone numbers from the cluster
                mentioned_names = []
                phone_mentions = []
                
                for wish in cluster.wish_messages:
                    for mention in wish.mentioned_names:
                        if mention.startswith('@') and mention[1:].isdigit():
                            phone_mentions.append(mention)
                        elif mention and len(mention) > 1 and mention.lower() not in ['recognise', 'wish', 'happy', 'birthday']:
                            mentioned_names.append(mention)
                
                # Get unique mentions
                unique_names = list(set(mentioned_names))
                unique_phones = list(set(phone_mentions))
                
                # Try to get target name if available
                target_name = "Someone's Birthday"
                target_info = "Unknown"
                
                # Try different strategies to find the target name
                if cluster.target_participant_id:
                    target_participant = next((p for p in all_participants if p.id == cluster.target_participant_id), None)
                    if target_participant:
                        target_name = target_participant.display_name or f"Contact {target_participant.phone}"
                        target_info = target_name
                
                # If no target found, try to infer from mentions
                if target_name == "Someone's Birthday" and unique_names:
                    target_name = unique_names[0]  # Use first mentioned name
                    target_info = f"{unique_names[0]}"
                
                # Fall back to phone if available
                if target_name == "Someone's Birthday" and unique_phones:
                    target_name = f"Contact {unique_phones[0]}"
                    target_info = unique_phones[0]

                # Create simple summary that matches template expectations
                summary = {
                    'canonical_name': target_name,
                    'name': target_name,  # Backup field
                    'target': target_info,  # For display in template
                    'birthday_date': cluster.date.strftime("%m-%d"),
                    'birthday_month': cluster.date.month,
                    'birthday_day': cluster.date.day,
                    'birthday_year': cluster.date.year,
                    'full_date': cluster.date.strftime("%B %d, %Y"),
                    'year': cluster.date.year,
                    'years_observed': 1,
                    'total_wishers': cluster.unique_wishers or 0,
                    'wisher_count': cluster.unique_wishers or 0,  # Template expects this field
                    'wishers': cluster.unique_wishers or 0,  # Additional field for compatibility
                    'total_wishes': len(cluster.wish_messages),
                    'mentioned_names': unique_names[:3],  # Top 3 mentioned names
                    'phone_mentions': unique_phones[:2],  # Top 2 phone mentions
                    'messages': [{'sender': msg.sender, 'content': msg.text[:50], 'timestamp': msg.timestamp.strftime("%H:%M")} 
                               for wish in cluster.wish_messages[:5]  # Show first 5 messages only
                               for msg in all_messages if msg.id == wish.message_id][:5],  # Limit to 5 messages max
                    'confidence': 0.7 if cluster.target_participant_id else 0.4  # As decimal for template
                }
                birthday_summaries.append(summary)
            
            # Sort by date (most recent first)
            birthday_summaries.sort(key=lambda x: (x['year'], x['birthday_month'], x['birthday_day']), reverse=True)
            
            # Store for results page using session (simpler than database)
            session['birthday_results'] = birthday_summaries
            session['processing_summary'] = {
                'total_files': len(processed_files),
                'successful_files': len([f for f in processed_files if f['status'] == 'success']),
                'total_clusters': len(all_clusters),
                'total_predictions': len(birthday_summaries),
                'processing_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            flash(f'Successfully processed {len(processed_files)} files. Found {len(birthday_summaries)} birthday predictions.', 'success')
            return redirect(url_for('results'))
            
        except Exception as e:
            logger.error(f"Unexpected error in upload_files: {str(e)}", exc_info=True)
            flash('An unexpected error occurred while processing your files.', 'error')
            return redirect(url_for('index'))


@app.route('/results')
def results():
    """Display results page."""
    try:
        # Get results from session instead of database
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