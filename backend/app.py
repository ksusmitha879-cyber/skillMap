from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import sqlite3
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Database setup ──────────────────────────────
def init_db():
    conn = sqlite3.connect("skillMap.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_skills TEXT,
            job_role TEXT,
            match_score INTEGER,
            missing_skills TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ── Job data ─────────────────────────────────────
JOBS = {
    "AI/ML Engineer": ["Python","Machine Learning","Deep Learning",
        "TensorFlow","PyTorch","Scikit-learn","NumPy","Pandas",
        "SQL","Git","Statistics","Data Visualization"],
    "Full Stack Dev": ["JavaScript","React","Node.js","Python",
        "SQL","REST API","Git","HTML","CSS","MongoDB","Docker","TypeScript"],
    "Data Analyst": ["Python","SQL","Excel","Tableau","Power BI",
        "Pandas","NumPy","Data Visualization","Statistics","Matplotlib"],
    "UI/UX Designer": ["Figma","User Research","Wireframing",
        "Prototyping","Design Thinking","HTML","CSS","Adobe XD"],
}

# ── ML Matching using TF-IDF ──────────────────────
def compute_match(user_skills: List[str], job_role: str):
    required = JOBS.get(job_role, [])
    if not required or not user_skills:
        return 0, [], required

    # TF-IDF similarity
    user_text = " ".join(user_skills).lower()
    job_text = " ".join(required).lower()

    vectorizer = TfidfVectorizer()
    vectors = vectorizer.fit_transform([user_text, job_text])
    similarity = cosine_similarity(vectors[0], vectors[1])[0][0]

    # Also do exact matching for skill breakdown
    user_norm = [s.lower() for s in user_skills]
    matched = [r for r in required if any(
        u in r.lower() or r.lower() in u for u in user_norm
    )]
    missing = [r for r in required if r not in matched]

    score = round((len(matched) / len(required)) * 100)
    return score, matched, missing

# ── Models ────────────────────────────────────────
class AnalysisRequest(BaseModel):
    user_skills: List[str]
    job_role: str

# ── Routes ───────────────────────────────────────
@app.get("/")
def home():
    return {"message": "SkillMap API running"}

@app.get("/api/jobs")
def get_jobs():
    return {"jobs": list(JOBS.keys())}

@app.post("/api/analyze")
def analyze(req: AnalysisRequest):
    score, matched, missing = compute_match(
        req.user_skills, req.job_role
    )
    return {
        "job_role": req.job_role,
        "match_score": score,
        "matched_skills": matched,
        "missing_skills": missing,
        "total_required": len(JOBS.get(req.job_role, []))
    }

@app.post("/api/save")
def save_analysis(req: AnalysisRequest):
    score, _, missing = compute_match(
        req.user_skills, req.job_role
    )
    conn = sqlite3.connect("skillMap.db")
    conn.execute(
        "INSERT INTO analyses (user_skills, job_role, match_score, missing_skills) VALUES (?,?,?,?)",
        (json.dumps(req.user_skills), req.job_role,
         score, json.dumps(missing))
    )
    conn.commit()
    conn.close()
    return {"message": "Saved", "score": score}

@app.get("/api/history")
def get_history():
    conn = sqlite3.connect("skillMap.db")
    rows = conn.execute(
        "SELECT * FROM analyses ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return {"history": [
        {"id": r[0], "skills": json.loads(r[1]),
         "role": r[2], "score": r[3],
         "missing": json.loads(r[4]), "date": r[5]}
        for r in rows
    ]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)