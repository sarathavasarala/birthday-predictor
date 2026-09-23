# 🎂 WhatsApp Birthday Predictor

> **Never miss a friend or family member's birthday again.**  
> Automatically turn years of chaotic WhatsApp chats into an organized, accurate birthday calendar in seconds.

![Python](https://img.shields.io/badge/python-v3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-v2.3+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

---

## 💡 Why This Exists (The Problem)

Every year, birthdays are celebrated across your WhatsApp chats—family groups, college alumni, sports clubs, close friends, and colleague threads:
* Messages like *"Happy birthday Sarah! 🎂"*, *"Belated HBD bro!"*, or *"Thanks everyone! 🙏"* are buried across thousands of texts.
* Half the time, the birthday person isn't even saved in your address book—they just appear as a raw phone number (`+1 555...`).
* Some people wish in advance, others wish belatedly, making dates tricky to pin down manually.
* Scrolling through years of chat history to manually populate your calendar takes hours.

**WhatsApp Birthday Predictor fixes this instantly.** Just drop in your chat export, and the app reconstructs who was celebrated, adjusts for belated/early wishes, and creates a ready-to-import calendar file with automatic yearly reminders.

---

## ✨ What You Get

* ⚡ **Zero-Effort Birthday Discovery**: Turn years of group banter into an organized, verified list of birthdays in seconds.
* 📱 **Works With Phone Numbers & Names**: Accurately identifies recipients even if you haven't saved their contact name. If someone was tagged as `@1234567890` or replied *"thanks all!"* from an unsaved number, the app detects it.
* 📅 **One-Click Calendar Sync (.ics)**: Download an `.ics` file with one click and import all birthdays directly into **Apple Calendar, Google Calendar, or Outlook** with automatic yearly recurring alerts.
* 🎯 **Smart Belated & Early Adjustment**: Automatically recognizes when someone says *"Belated happy birthday!"* and shifts the calendar event back to their actual special day.
* 🛡️ **Confidence Scoring**: Every predicted birthday comes with a clear reliability score so you can verify uncertain dates before syncing.
* 🔒 **Private & Secure**: Runs locally on your machine—your personal messages and exports are never uploaded to third-party public databases.

---

## 🎬 How It Works in 3 Simple Steps

```
┌─────────────────────┐      ┌─────────────────────────┐      ┌───────────────────────┐
│ 1. Export Chat      │ ───► │ 2. Upload & Analyze     │ ───► │ 3. Sync Calendar (.ics)│
│ From WhatsApp app   │      │ AI identifies birthdays │      │ Apple / Google / Outlook
└─────────────────────┘      └─────────────────────────┘      └───────────────────────┘
```

1. **Export Chat from WhatsApp**:
   - **iPhone**: Tap Contact/Group name → **Export Chat** → choose **"Without Media"** → Save to Files.
   - **Android**: Tap **⋮** (menu) → **More** → **Export chat** → choose **"Without media"** → Save `.txt`.
2. **Upload & Relax**:
   - Drag & drop your `.txt` file into the web interface.
   - Watch real-time progress as conversations are analyzed.
3. **Review & Export**:
   - Select the birthdays you want to keep.
   - Click **Export Calendar** to download your ready-to-use `.ics` calendar file!

---

## 📊 Example Output

| Name / Contact | Birthday | Wishers | Target Info | Confidence |
| :--- | :--- | :--- | :--- | :--- |
| **Sarah Johnson** | Aug 1 (Aug 1) | 8 wishers | Identified via 8 wishes & thank-you response | 🟢 **96% (High)** |
| **+1 (555) 987-6543** | Mar 14 (Mar 14) | 5 wishers | Identified via `@15559876543` mentions | 🟢 **92% (High)** |
| **Dave** | Oct 22 (Oct 22) | 3 wishers | Adjusted from belated wish on Oct 23 | 🟡 **78% (Good)** |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- An optional AI API key for enhanced intelligence:
  - **TypeSafe AI (Jev)** (Recommended for speed & low cost) from [console.typesafe.ai](https://console.typesafe.ai/home)
  - *OR* **Azure OpenAI** (GPT-4)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/sarathavasarala/birthday-predictor.git
   cd birthday-predictor
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment (Optional but Recommended)**:
   ```bash
   cp .env.example .env
   ```
   Add your preferred API key to `.env`:
   ```env
   # TypeSafe AI Jev (Fast & lightweight)
   TYPESAFE_API_KEY=your_typesafe_key_here

   # OR Azure OpenAI (GPT-4)
   AZURE_OPENAI_API_KEY=your_azure_key_here
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_DEPLOYMENT=gpt-4.1
   ```
   *(Note: The app will still work with basic pattern matching if no AI keys are provided).*

4. **Run the application**:
   ```bash
   python app.py
   ```

5. **Open your browser**:
   Navigate to `http://127.0.0.1:5001` and upload your chat!

---

## 🧠 Under the Hood (For Developers & Curious Minds)

For developers looking at the architecture, the detection pipeline employs a multi-tiered approach:

1. **Chat Parser ([`parser.py`](file:///Users/sarathavasarala/Desktop/Projects/HBD%20App/parser.py))**:
   - Universal regex engine supporting iOS, Android (12-hour AM/PM and 24-hour), and ISO timestamp standards.
   - Extracts participants, maps display names to raw phone numbers, and filters out system noise.

2. **Temporal Clustering ([`analyzer.py`](file:///Users/sarathavasarala/Desktop/Projects/HBD%20App/analyzer.py))**:
   - Scans message streams for wish triggers, multilingual patterns, and thanks replies.
   - Groups related wishes within a 16–36 hour window into discrete `WishCluster` events.

3. **Dual-Engine AI Disambiguation ([`jev_parser.py`](file:///Users/sarathavasarala/Desktop/Projects/HBD%20App/jev_parser.py) & [`llm_parser.py`](file:///Users/sarathavasarala/Desktop/Projects/HBD%20App/llm_parser.py))**:
   - **TypeSafe AI (Jev System One)**: Uses typed probabilistic primitives (`Choice` and `Score`) to match recipients against candidate names and phone numbers in **~150ms** with complete probability distributions.
   - **Azure OpenAI (GPT-4)**: Autoregressive fallback for full contextual inference.

4. **Identity Resolution & Confidence Engine ([`identity.py`](file:///Users/sarathavasarala/Desktop/Projects/HBD%20App/identity.py), [`confidence.py`](file:///Users/sarathavasarala/Desktop/Projects/HBD%20App/confidence.py))**:
   - Consolidates observations across multiple years and different group chats into unified identities.
   - Calibrates confidence based on wish volume, explicit mentions, and thank-you confirmations.

---

## 📁 Project Structure

```
├── app.py              # Flask server, routes, and SSE progress stream
├── parser.py           # WhatsApp export parser (iOS/Android/ISO)
├── analyzer.py         # Wish detection, date clustering & heuristics
├── jev_parser.py       # TypeSafe AI Jev System One integration
├── llm_parser.py       # Dual-engine AI dispatcher & Azure OpenAI fallback
├── identity.py         # Cross-chat and multi-year identity resolution
├── confidence.py       # Prediction confidence scoring algorithms
├── models.py           # SQLite database models & schemas
├── config.json         # Detection thresholds, window hours, & patterns
├── templates/          # Modern Bootstrap web interface
└── tests/              # Verification suites (test_jev.py, test_improvements.py, etc.)
```

---

## 🛠 Running Tests

```bash
# Verify Jev & dual-engine detection
python test_jev.py

# Verify clustering improvements
python test_improvements.py

# Verify calendar (.ics) generation
python test_ics_export.py
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**⭐ Star this repo if it helped you stay on top of birthdays!**