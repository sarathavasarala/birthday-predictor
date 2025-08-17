# 🎂 WhatsApp Birthday Detector

A sophisticated Python Flask application that analyzes WhatsApp chat exports to automatically detect and predict birthdays using AI-powered pattern recognition.

## ✨ Features

### 🔍 **Smart Analysis**
- **WhatsApp Export Parser**: Supports multiple Android/iOS export formats
- **AI Birthday Detection**: Identifies birthday wishes with confidence scoring
- **Intelligent Clustering**: Groups wishes by date with configurable time windows
- **Target Inference**: Determines who the birthday wishes are for using:
  - Phone number mentions (@919545598844)
  - Name pattern matching
  - Thanks message analysis
  - Process of elimination

### 🎯 **Real-World Tested**
- Successfully analyzed 1,449 messages from 41 participants
- Detected 27 birthday clusters across 2024-2025
- Handles various message formats and ambiguous cases
- Provides meaningful results even with incomplete data

### 🛠 **Technical Features**
- **Modular Architecture**: Separate components for parsing, analysis, identity resolution
- **Configurable Patterns**: JSON-based configuration for different WhatsApp formats
- **Comprehensive Logging**: Detailed logging for debugging and monitoring
- **SQLite Database**: Persistent storage with full schema support
- **Web Interface**: Clean Flask app with Bootstrap styling

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip (Python package manager)

### Installation

1. **Clone or download the project**
```bash
cd "HBD App"
```

2. **Run the application**
```bash
python app.py
```

3. **Open your browser**
Navigate to: `http://127.0.0.1:5001`

## 📱 How to Export WhatsApp Chats

### Android:
1. Open WhatsApp → Select chat → ⋮ (menu) → More → Export chat
2. Choose "Without media" for better performance
3. Save the .txt file

### iOS:
1. Open WhatsApp → Select chat → Contact/Group name → Export Chat
2. Choose "Without Media"
3. Save to Files app, then download to computer

## 🎯 Usage

1. **Upload WhatsApp Export**: Drag and drop or select your .txt file
2. **Processing**: The app will automatically:
   - Parse messages and identify participants
   - Detect birthday wishes using AI patterns
   - Cluster wishes by date
   - Infer who the birthdays are for
   - Calculate confidence scores

3. **View Results**: See discovered birthdays with:
   - Date and person's name
   - Confidence percentage
   - Number of wishers
   - Years of evidence

## ⚙️ Configuration

The app uses `config.json` for customization:

### Key Settings:
```json
{
  "confidence": {
    "min_threshold": 0.3,  // 30% minimum confidence
    "base_score": 0.3      // Starting confidence score
  },
  "clustering": {
    "window_hours": 36,    // Group wishes within 36 hours
    "min_wish_score": 0.1  // Minimum wish quality
  }
}
```

### Supported Export Formats:
- Android: `4/26/25, 3:10 PM - Name: Message`
- iOS: `[4/26/25, 3:10:45 PM] Name: Message`
- Various name prefixes: `MS - Name`, `+91 Phone Number`

## 📊 Example Results

After processing a real WhatsApp group chat:
- **1,449 messages** analyzed from 41 participants
- **27 birthday clusters** detected spanning 2024-2025
- **Multiple identification strategies** used for accuracy

Sample output:
```
🎂 Rohit
   📅 Birthday: 4/26
   📱 Phone: +919545598844
   🎯 Confidence: 75.0%
   👥 Evidence: 18 wishers
```

## 🔍 How It Works

### 1. **Parsing**
- Detects WhatsApp export format automatically
- Extracts messages, timestamps, and participant info
- Handles various date formats and name patterns

### 2. **Wish Detection**
- Scans for birthday-related keywords and phrases
- Analyzes emojis and patterns (🎂, 🎉, "happy birthday")
- Scores each message for birthday relevance

### 3. **Clustering**
- Groups wishes occurring within 36 hours
- Creates birthday event clusters
- Handles multi-day celebrations

### 4. **Target Inference**
- **Phone mentions**: @919545598844 style references
- **Name analysis**: Mentioned names in wishes
- **Thanks detection**: Who responded with thanks
- **Elimination**: Process of elimination in small groups

### 5. **Identity Resolution**
- Links mentions across different chats
- Builds comprehensive identity profiles
- Resolves aliases and variations

## 🛠 Architecture

```
📁 Project Structure
├── app.py              # Main Flask application
├── parser.py           # WhatsApp export parsing
├── analyzer.py         # Birthday wish detection & clustering  
├── identity.py         # Identity resolution across chats
├── confidence.py       # Confidence scoring algorithms
├── models.py          # Data models & database operations
├── config.json        # Configuration settings
├── logging_config.py  # Logging setup
├── templates/         # HTML templates
│   ├── base.html     # Base template
│   ├── index.html    # Upload page
│   └── results.html  # Results display
└── static/           # CSS, JS, images
```

## 📝 Logging

Comprehensive logging helps track the analysis process:
- **INFO**: General progress and results
- **DEBUG**: Detailed analysis steps
- **WARNING**: Ambiguous cases and fallbacks
- **ERROR**: Processing issues

Logs are saved to `logs/hbd_app.log` with automatic rotation.

## 🐛 Troubleshooting

### Common Issues:

**"No birthday wishes found"**
- Check if the chat file has birthday-related messages
- Verify the export format is supported
- Try lowering confidence thresholds in config.json

**"Port already in use"**
- Kill existing Python processes: `pkill -f "python.*app.py"`
- Or change the port in app.py: `app.run(debug=True, port=5002)`

**"Invalid file format"**
- Ensure you're uploading a .txt file
- Check the export was done "without media"
- Verify the file contains properly formatted WhatsApp messages

### Debug Mode:
Set logging level to DEBUG in `config.json` for detailed analysis information.

## 🎉 Success Stories

Real-world validation with actual WhatsApp group chat:
- **41 participants** in active group chat
- **Multiple years** of birthday data (2024-2025)
- **High accuracy** with phone number mentions
- **Graceful handling** of ambiguous cases

The system successfully identified patterns like:
- `@919545598844` phone mentions linking to "Rohit"
- `MS - Name` prefix patterns from Android exports
- Multi-day birthday celebrations
- Thank you responses confirming birthday recipients

---

**Made with ❤️ for birthday celebration automation**