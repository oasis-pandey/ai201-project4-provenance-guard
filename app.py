import os
import json
import uuid
import datetime
import sqlite3
import re
import math
from flask import Flask, request, jsonify
# pyrefly: ignore [missing-import]
from flask_limiter import Limiter
# pyrefly: ignore [missing-import]
from flask_limiter.util import get_remote_address
# pyrefly: ignore [missing-import]
from groq import Groq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Setup Flask-Limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

# Initialize Groq client
# This expects GROQ_API_KEY to be set in the environment or .env file
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Database setup for Audit Log
DB_FILE = "audit_log.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                content_id TEXT PRIMARY KEY,
                creator_id TEXT,
                timestamp TEXT,
                attribution TEXT,
                confidence REAL,
                llm_score REAL,
                burstiness_score REAL,
                status TEXT,
                appeal_reasoning TEXT
            )
        ''')
        conn.commit()

init_db()


# ==========================================
# Signal 1: Perplexity Score (LLM-based)
# ==========================================
def get_perplexity_score(text: str) -> float:
    """
    Measures how surprised a language model is by the choice of words in the text.
    Higher score (closer to 1.0) -> More surprised/unpredictable -> More human.
    Lower score (closer to 0.0) -> More predictable -> AI-generated.
    """
    prompt = f"""
    Analyze the following text and evaluate its 'perplexity' (predictability of word choices and structure).
    Provide a score between 0.0 and 1.0, where:
    - 0.0 means the text is highly predictable, uniform, and typical of AI-generated content.
    - 1.0 means the text is highly surprising, creative, unpredictable, and typical of human writing.
    
    Respond ONLY with a valid JSON object in this exact format, with no additional text or markdown:
    {{"score": 0.85}}
    
    Text to analyze:
    {text}
    """
    
    try:
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a text analysis engine that outputs only JSON."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        
        result_str = response.choices[0].message.content
        result_json = json.loads(result_str)
        return float(result_json.get("score", 0.5))
        
    except Exception as e:
        print(f"Error calling Groq API: {e}")
        # Fallback score if API fails
        return 0.5


# ==========================================
# Signal 2: Burstiness Score
# ==========================================
def get_burstiness_score(text: str) -> float:
    """
    Measures the variation in sentence length and structure.
    Returns the standard deviation of sentence lengths in words.
    """
    sentences = re.split(r'[.!?]+', text)
    lengths = [len(s.split()) for s in sentences if s.strip()]
    
    if not lengths or len(lengths) == 1:
        return 0.0
        
    mean = sum(lengths) / len(lengths)
    variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
    return math.sqrt(variance)

def calculate_confidence(perplexity: float, burstiness: float) -> tuple[float, str, str]:
    """
    Combines perplexity and burstiness into a single confidence score.
    Returns (confidence_score, attribution, label)
    """
    # Normalize Burstiness: min 5.0, max 10.0 (based on test calibration)
    b_norm = max(0.0, min(1.0, (burstiness - 5.0) / 5.0))
    
    # Perplexity is already 0.0 to 1.0
    p_norm = perplexity
    
    # Calculate score (1.0 = AI, 0.0 = Human)
    score = 1.0 - (0.6 * p_norm + 0.4 * b_norm)
    
    if score <= 0.4:
        attribution = "human"
        label = "Verified Human-Written: The structural variation and word choices in this text strongly align with human writing patterns."
    elif score <= 0.7:
        attribution = "uncertain"
        label = "Uncertain/Mixed: This text exhibits a combination of predictable patterns and style variations. It may be human work that is highly structured, or AI-generated text that has been edited."
    else:
        attribution = "ai"
        label = "Likely AI-Generated: This text contains highly predictable word choices and uniform sentence structures characteristic of AI generation."
        
    return score, attribution, label


# ==========================================
# API Endpoints
# ==========================================

@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    """
    Submission endpoint that accepts a piece of text and returns the classification output.
    """
    data = request.get_json()
    if not data or "text" not in data or "creator_id" not in data:
        return jsonify({"error": "Missing 'text' or 'creator_id' in request body"}), 400
        
    text = data["text"]
    creator_id = data["creator_id"]
    content_id = str(uuid.uuid4())
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # Run Signal 1
    llm_score = get_perplexity_score(text)
    
    # Run Signal 2 and Combination Logic
    burstiness_score = get_burstiness_score(text)
    confidence, attribution, label = calculate_confidence(llm_score, burstiness_score)
    
    status = "classified"
    
    # Write to audit log
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO audit_log 
            (content_id, creator_id, timestamp, attribution, confidence, llm_score, burstiness_score, status, appeal_reasoning)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (content_id, creator_id, timestamp, attribution, confidence, llm_score, burstiness_score, status, None))
        conn.commit()
        
    response = {
        "content_id": content_id,
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "burstiness_score": burstiness_score,
        "label": label
    }
    
    return jsonify(response), 200


@app.route("/appeal", methods=["POST"])
def appeal():
    """
    Appeal endpoint that accepts a content_id and reasoning to flag a classification for review.
    """
    data = request.get_json()
    if not data or "content_id" not in data or "creator_reasoning" not in data:
        return jsonify({"error": "Missing 'content_id' or 'creator_reasoning' in request body"}), 400
        
    content_id = data["content_id"]
    creator_reasoning = data["creator_reasoning"]
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE audit_log 
            SET status = ?, appeal_reasoning = ?
            WHERE content_id = ?
        ''', ("under_review", creator_reasoning, content_id))
        
        if cursor.rowcount == 0:
            return jsonify({"error": "Content ID not found"}), 404
            
        conn.commit()
        
    return jsonify({
        "message": "Appeal received",
        "content_id": content_id,
        "status": "under_review"
    }), 200


@app.route("/log", methods=["GET"])
def get_log():
    """
    Returns the most recent audit log entries.
    """
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 10")
        rows = cursor.fetchall()
        
        entries = [dict(row) for row in rows]
        
    return jsonify({"entries": entries}), 200

if __name__ == "__main__":
    app.run(debug=True, port=5001)
