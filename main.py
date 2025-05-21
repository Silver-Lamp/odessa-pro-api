# File: main.py
# Odessa Pro API - FastAPI + Summarization Integration + Full Text + Async Ready

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uuid
import datetime
import os
from pathlib import Path
import pdfplumber
import asyncio

app = FastAPI()

# CORS (allow from frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data model for summary metadata
class SummaryMeta(BaseModel):
    id: str
    filename: str
    created_at: str
    tags: list[str]
    project: str

# In-memory store for MVP
summaries = {}
UPLOAD_DIR = Path("uploads")
SUMMARY_DIR = Path("summaries")
UPLOAD_DIR.mkdir(exist_ok=True)
SUMMARY_DIR.mkdir(exist_ok=True)

# Basic section splitter

def basic_section_split(text):
    sections = {"abstract": "", "introduction": "", "methods": "", "results": "", "conclusion": ""}
    current = None
    for line in text.splitlines():
        lower = line.strip().lower()
        if "abstract" in lower:
            current = "abstract"
        elif "introduction" in lower:
            current = "introduction"
        elif "methods" in lower:
            current = "methods"
        elif "results" in lower:
            current = "results"
        elif "conclusion" in lower or "discussion" in lower:
            current = "conclusion"
        elif current:
            sections[current] += line + "\n"
    return sections

# Summary generator

def generate_summary(sections, filename):
    summary = f"# Summary of {filename}\n\n"
    summary += f"## 🔍 Abstract\n{sections['abstract'].strip()}\n\n"
    summary += f"## 🎯 Key Points\n- {sections['results'].strip().replace('\n', '\n- ')}\n\n"
    summary += f"## ❓ Open Questions\n- TODO: Add with model."
    return summary

# PDF text extractor

def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

@app.get("/")
def root():
    return {"message": "Odessa Pro API is live"}

async def process_and_save(file_path: Path, filename: str, uid: str):
    raw_text = extract_text_from_pdf(file_path)
    sections = basic_section_split(raw_text)
    summary_text = generate_summary(sections, filename)
    summary_path = SUMMARY_DIR / f"{uid}.md"
    with open(summary_path, "w") as f:
        f.write(summary_text)
    return summary_text

@app.post("/summarize")
async def summarize_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    tags: str = Form(""),
    project: str = Form("Default")
):
    uid = str(uuid.uuid4())
    timestamp = datetime.datetime.utcnow().isoformat()
    filename = f"{uid}_{file.filename}"
    file_path = UPLOAD_DIR / filename

    with open(file_path, "wb") as f:
        f.write(await file.read())

    background_tasks.add_task(process_and_save, file_path, file.filename, uid)

    meta = SummaryMeta(
        id=uid,
        filename=file.filename,
        created_at=timestamp,
        tags=tags.split(",") if tags else [],
        project=project
    )
    summaries[uid] = meta.dict()

    return {"id": uid, "message": "Summary is being processed.", "meta": summaries[uid]}

@app.get("/summaries")
def list_summaries():
    return list(summaries.values())

@app.get("/summaries/{uid}")
def get_summary(uid: str):
    meta = summaries.get(uid)
    if not meta:
        return {"error": "Summary not found"}
    summary_path = SUMMARY_DIR / f"{uid}.md"
    if not summary_path.exists():
        return {"status": "Processing"}
    with open(summary_path, "r") as f:
        content = f.read()
    return {"meta": meta, "summary": content}

@app.get("/download/{uid}")
def download_summary(uid: str):
    summary_path = SUMMARY_DIR / f"{uid}.md"
    if not summary_path.exists():
        return {"error": "Summary not found"}
    return FileResponse(summary_path, media_type='text/markdown', filename=f"summary_{uid}.md")
