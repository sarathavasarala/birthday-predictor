# 🎂 WhatsApp Birthday Predictor

A Python Flask application that analyzes WhatsApp chat exports to automatically detect and predict birthdays using some rules + LLMs.

![Python](https://img.shields.io/badge/python-v3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-v2.3+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## ✨ Key Features

### 🤖 **AI-Powered Analysis**
- **Azure OpenAI Integration**: Uses GPT.4-1 (or any other model) for intelligent message analysis
- **Pattern Recognition**: Detects birthday wishes with sophisticated scoring
- **Smart Clustering**: Groups related messages across time windows
- **Confidence Scoring**: Provides reliability metrics for each prediction

### 🔍 **Multi-Strategy Detection**
- **Phone Number Mentions**: `@911234567889` style references
- **Name Pattern Matching**: Direct name mentions in wishes
- **Thank You Analysis**: Identifies recipients through responses
- **Process of Elimination**: Smart inference for group chats

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Azure OpenAI API access (for AI analysis)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/sarathavasarala/birthday-predictor.git
cd birthday-predictor
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your Azure OpenAI credentials
```

4. **Run the application**
```bash
python app.py
```

5. **Open your browser**
Navigate to: `http://127.0.0.1:5001`

## ⚙️ Environment Setup

Create a `.env` file with your Azure OpenAI credentials:

```env
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4
AZURE_OPENAI_API_VERSION=2025-01-01-preview
```

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

1. **Upload WhatsApp Export**: Drag and drop your .txt file
2. **Watch Real-Time Processing**: See AI analysis progress live
3. **Review Results**: Explore predictions with detailed explanations
4. **Export Birthdays**: Use results to update your calendar

## 🏗 Architecture

```
📁 Project Structure
├── app.py              # Main Flask application & API endpoints
├── parser.py           # WhatsApp export parsing engine
├── analyzer.py         # Birthday detection & clustering logic
├── llm_parser.py       # Azure OpenAI integration & AI analysis
├── identity.py         # Cross-chat identity resolution
├── confidence.py       # Confidence scoring algorithms
├── progress_tracker.py # Real-time progress tracking
├── models.py          # Database models & operations
├── config.json        # Configuration & patterns
├── templates/         # HTML templates
└── static/           # CSS, JS, images
```

## 🤖 AI Analysis Features

### Intelligent Message Analysis
- **Context Understanding**: AI comprehends birthday wish patterns
- **Person Identification**: Smart extraction of recipient names
- **Confidence Assessment**: Reliability scoring for each prediction
- **Explanation Generation**: Clear reasoning for each decision

### Real-Time Feedback
- **Progress Tracking**: Live updates during processing
- **Activity Logging**: See "✅ Identified: Sarah (95% confidence)"
- **Transparent AI**: Understand why AI made each prediction

## 🔧 Configuration

Customize behavior in `config.json`:

```json
{
  "confidence": {
    "min_threshold": 0.3  // 30% minimum confidence
  },
  "clustering": {
    "window_hours": 36,   // Group wishes within 36 hours
    "min_wishers": 1      // Minimum wishers per cluster
  },
  "llm": {
    "deployment_name": "gpt-4",
    "rate_limit_delay": 2.0  // Rate limiting for API calls
  }
}
```

## 📊 Example Output

```
🎂 Sarah Johnson
   📅 Birthday: January 24th
   🎯 Confidence: 95%
   📱 Phone: +1234567890
   👥 Wishers: 8 people
   🤖 AI Analysis: "Multiple messages directly mention 'Happy Birthday Sarah' 
      with high certainty. Phone number @1234567890 consistently referenced."
```

## 🛠 Development

### Running Tests
```bash
python test_parser.py
python test_llm.py
```

### Debug Mode
Set `DEBUG = True` in app.py for detailed logging.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with Flask and Bootstrap for clean UI
- Powered by Azure OpenAI for intelligent analysis
- Inspired by the need to never miss a birthday again!

---

**⭐ Star this repo if it helped you catch up on birthdays!**