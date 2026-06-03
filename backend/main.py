from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import json
import re
import uuid
import time
import io

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"
LOG_FILE = DATA_DIR / "emergency_logs.json"
DATA_DIR.mkdir(exist_ok=True)
if not LOG_FILE.exists():
    LOG_FILE.write_text("[]", encoding="utf-8")
TTS_DIR = DATA_DIR / "tts_audio"
TTS_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="AI-Powered Rural Emergency Medical Assistant",
    description="Advanced rural emergency medical assistance prototype with symptom triage, first-aid, medicine suggestions, voice-friendly responses, and location based hospital routing.",
    version="2.0.0",
)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

class SymptomRequest(BaseModel):
    name: Optional[str] = "User"
    age: Optional[int] = Field(default=None, ge=0, le=120)
    gender: Optional[str] = "not specified"
    user_type: Optional[str] = "Patient"
    village: Optional[str] = ""
    phone: Optional[str] = ""
    emergency_contact: Optional[str] = ""
    blood_group: Optional[str] = ""
    existing_diseases: Optional[str] = ""
    current_medicines: Optional[str] = ""
    symptoms: str
    duration: Optional[str] = "not specified"
    temperature: Optional[float] = None
    spo2: Optional[int] = None
    pulse: Optional[int] = None
    bp_systolic: Optional[int] = None
    bp_diastolic: Optional[int] = None
    diabetes: Optional[bool] = False
    pregnancy: Optional[bool] = False
    child_patient: Optional[bool] = False
    allergy_type: Optional[str] = "No"
    allergy: Optional[str] = ""
    language: Optional[str] = "en"
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class TTSRequest(BaseModel):
    text: str
    language: Optional[str] = "en"

EMERGENCY_KEYWORDS = {
    "chest pain": 35, "heart pain": 35, "breathing difficulty": 35, "shortness of breath": 35,
    "unconscious": 45, "faint": 25, "stroke": 45, "seizure": 45, "fits": 45,
    "severe bleeding": 45, "bleeding": 25, "accident": 30, "fracture": 25,
    "burn": 20, "poison": 45, "snake bite": 45, "electric shock": 45,
    "blue lips": 45, "confusion": 25, "severe headache": 25, "one side weakness": 45,
    "vomiting blood": 45, "blood in stool": 25, "high fever": 25, "fever": 10,
    "cough": 5, "cold": 4, "headache": 8, "stomach pain": 10, "diarrhea": 10,
    "vomiting": 10, "dizziness": 10, "dehydration": 20, "asthma": 30,
    # Kannada symptom words
    "ಛಾತಿ ನೋವು": 35, "ಎದೆ ನೋವು": 35, "ಉಸಿರಾಟ ತೊಂದರೆ": 35, "ಉಸಿರಾಟ": 25,
    "ಜ್ವರ": 10, "ಹೆಚ್ಚಿನ ಜ್ವರ": 25, "ತಲೆ ನೋವು": 8, "ಕೆಮ್ಮು": 5, "ನೆಗಡಿ": 4,
    "ರಕ್ತಸ್ರಾವ": 25, "ಅಪಘಾತ": 30, "ಸುಟ್ಟ ಗಾಯ": 20, "ಪಾಮು ಕಚ್ಚು": 45, "ಪಾವು ಕಚ್ಚು": 45,
    "ಪ್ರಜ್ಞೆ ಇಲ್ಲ": 45, "ಬಿದ್ದುಹೋಗು": 25, "ವಾಂತಿ": 10, "ಅತಿಸಾರ": 10, "ಹೊಟ್ಟೆ ನೋವು": 10,
    # Telugu symptom words
    "ఛాతి నొప్పి": 35, "శ్వాస ఇబ్బంది": 35, "శ్వాస": 25,
    "జ్వరం": 10, "అధిక జ్వరం": 25, "తలనొప్పి": 8, "దగ్గు": 5, "జలుబు": 4,
    "రక్తస్రావం": 25, "ప్రమాదం": 30, "కాలిన గాయం": 20, "పాము కాటు": 45,
    "స్పృహ లేదు": 45, "మూర్ఛ": 45, "వాంతి": 10, "విరేచనాలు": 10, "కడుపు నొప్పి": 10,
}

FIRST_AID = {
    "chest pain": ["Call emergency help immediately.", "Make the patient sit or lie in a comfortable position.", "Loosen tight clothing and keep the patient calm.", "Do not give food or water if the patient is very weak or unconscious."],
    "breathing": ["Call emergency help immediately if breathing is severe.", "Make the patient sit upright.", "Move the person to fresh air.", "Avoid crowding around the patient."],
    "bleeding": ["Apply firm pressure using clean cloth.", "Raise the injured part if possible.", "Do not remove deep objects stuck in the wound.", "Go to hospital if bleeding does not stop."],
    "burn": ["Cool the burn under clean running water for 20 minutes.", "Do not apply toothpaste, oil, or ice directly.", "Cover with clean cloth.", "Go to hospital for large, deep, face, hand, or electric burns."],
    "fever": ["Drink enough fluids.", "Rest in a cool room.", "Use light clothing.", "Visit doctor if fever is very high, continuous, or with breathing difficulty/confusion."],
    "stroke": ["Remember FAST: Face drooping, Arm weakness, Speech problem, Time to call emergency.", "Do not give food or water.", "Keep the patient safe and calm.", "Reach hospital immediately."],
    "snake": ["Keep the person still and calm.", "Do not cut, suck, or tie tightly near bite.", "Remove rings or tight items.", "Reach hospital immediately for anti-venom evaluation."],
    "general": ["Stay calm and keep the patient safe.", "Call 108 or local emergency number for serious symptoms.", "Keep the patient in a comfortable position.", "Reach the nearest hospital if symptoms are severe or worsening."],
}

MEDICINE_RULES = [
    {
        "match": ["fever", "body pain", "headache"],
        "medicines": [
            "Paracetamol/Acetaminophen for fever or mild pain, only as per age/weight label or doctor's advice.",
            "ORS solution or fluids if fever is associated with weakness or dehydration."
        ],
        "avoid": "Avoid self-medicating with antibiotics. Avoid ibuprofen/NSAIDs in pregnancy, kidney disease, stomach ulcer, dengue suspicion, or severe dehydration unless a doctor advises."
    },
    {
        "match": ["cold", "cough", "sore throat", "runny nose"],
        "medicines": [
            "Steam inhalation and warm fluids may help cold symptoms.",
            "Saline nasal drops/spray may help blocked nose.",
            "Cough syrup should be chosen with pharmacist/doctor guidance, especially for children."
        ],
        "avoid": "Do not use antibiotics for common cold unless prescribed. Avoid giving adult cold medicines to small children."
    },
    {
        "match": ["diarrhea", "loose motion", "vomiting"],
        "medicines": [
            "ORS solution after every loose stool/vomiting to prevent dehydration.",
            "Zinc may be advised for children with diarrhea by healthcare workers."
        ],
        "avoid": "Avoid anti-diarrhea tablets in children or bloody diarrhea unless a doctor advises. Seek care for severe dehydration, blood in stool, or repeated vomiting."
    },
    {
        "match": ["acidity", "heartburn", "gas"],
        "medicines": [
            "Antacid gel/tablet may help mild acidity as per label instructions.",
            "Drink water and avoid spicy/oily food temporarily."
        ],
        "avoid": "Chest pain should not be treated as acidity without checking emergency signs. Seek urgent help for chest pain, sweating, or breathlessness."
    },
    {
        "match": ["wound", "cut", "minor bleeding"],
        "medicines": [
            "Clean wound with clean water.",
            "Use antiseptic solution/cream only for minor external wounds as per label.",
            "Tetanus injection may be needed for dirty/deep wounds; visit a healthcare center."
        ],
        "avoid": "Do not put unknown powders, soil, oil, or turmeric into deep wounds."
    },
]

TRANSLATIONS = {
    "en": {
        "critical": "Critical Emergency", "high": "High Risk", "medium": "Medium Risk", "low": "Low Risk",
        "go_now": "This may be serious. Please call 108 or go to the nearest hospital immediately.",
        "doctor": "Please consult a qualified doctor or pharmacist before taking medicines, especially for children, pregnancy, allergies, or chronic disease.",
    },
    "kn": {
        "critical": "ಗಂಭೀರ ತುರ್ತು ಪರಿಸ್ಥಿತಿ", "high": "ಹೆಚ್ಚಿನ ಅಪಾಯ", "medium": "ಮಧ್ಯಮ ಅಪಾಯ", "low": "ಕಡಿಮೆ ಅಪಾಯ",
        "go_now": "ಇದು ಗಂಭೀರವಾಗಿರಬಹುದು. ದಯವಿಟ್ಟು 108 ಗೆ ಕರೆ ಮಾಡಿ ಅಥವಾ ಸಮೀಪದ ಆಸ್ಪತ್ರೆಗೆ ತಕ್ಷಣ ಹೋಗಿ.",
        "doctor": "ಮಕ್ಕಳು, ಗರ್ಭಾವಸ್ಥೆ, ಅಲರ್ಜಿ ಅಥವಾ ದೀರ್ಘಕಾಲಿನ ಕಾಯಿಲೆಗಳಿದ್ದರೆ ಔಷಧಿ ತೆಗೆದುಕೊಳ್ಳುವ ಮೊದಲು ಅರ್ಹ ವೈದ್ಯರು ಅಥವಾ ಫಾರ್ಮಸಿಸ್ಟ್ ಸಲಹೆ ಪಡೆಯಿರಿ.",
    },
    "te": {
        "critical": "తీవ్ర అత్యవసర పరిస్థితి", "high": "అధిక ప్రమాదం", "medium": "మధ్యస్థ ప్రమాదం", "low": "తక్కువ ప్రమాదం",
        "go_now": "ఇది తీవ్రమై ఉండవచ్చు. దయచేసి 108 కు కాల్ చేయండి లేదా సమీప ఆసుపత్రికి వెంటనే వెళ్లండి.",
        "doctor": "పిల్లలు, గర్భధారణ, అలెర్జీలు లేదా దీర్ఘకాలిక వ్యాధులు ఉంటే మందులు తీసుకునే ముందు అర్హత కలిగిన డాక్టర్ లేదా ఫార్మసిస్ట్‌ను సంప్రదించండి.",
    },
}


CONTENT = {
    "en": {
        "monitor": "Monitor the symptoms. If symptoms worsen, visit a healthcare center.",
        "no_major": "No major emergency keyword found.",
        "matched": "Symptom matched",
        "danger_chest": "Danger combination: chest pain with sweating/breathing/arm/jaw symptoms",
        "danger_fever": "Danger combination: fever with serious warning symptom",
        "dehydration": "Possible dehydration warning signs",
        "spo2_low": "SpO₂ is low",
        "spo2_very_low": "SpO₂ is very low",
        "high_fever": "High fever",
        "very_high_fever": "Very high fever",
        "abnormal_pulse": "Abnormal pulse",
        "fast_pulse": "Fast pulse",
        "bp_danger": "Danger blood pressure systolic",
        "age_caution": "Age group needs extra caution",
        "preg_caution": "Pregnancy needs extra caution",
        "diabetes_caution": "Diabetes/comorbidity needs extra caution",
        "next_steps": ["Press Call 108 for emergency help if the case is serious.", "Use Live Location to find nearby hospitals.", "Share the risk result and symptoms with a doctor/ambulance staff."],
        "voice": "{name}, your risk level is {risk} with score {score} out of 100. {msg}",
        "first_aid": {
            "chest pain": ["Call 108 immediately.", "Make the patient sit or lie in a comfortable position.", "Loosen tight clothing and keep the patient calm.", "Do not give food or water if the patient is very weak or unconscious."],
            "breathing": ["Call 108 immediately if breathing difficulty is severe.", "Make the patient sit upright.", "Move the person to fresh air.", "Avoid crowding around the patient."],
            "bleeding": ["Apply firm pressure using clean cloth.", "Raise the injured part if possible.", "Do not remove deep objects stuck in the wound.", "Go to hospital if bleeding does not stop."],
            "burn": ["Cool the burn under clean running water for 20 minutes.", "Do not apply toothpaste, oil, or ice directly.", "Cover with clean cloth.", "Go to hospital for large, deep, face, hand, or electric burns."],
            "fever": ["Drink enough fluids.", "Rest in a cool room.", "Use light clothing.", "Visit doctor if fever is very high, continuous, or with breathing difficulty/confusion."],
            "stroke": ["Check FAST: Face drooping, Arm weakness, Speech problem, Time to call 108.", "Do not give food or water.", "Keep the patient safe and calm.", "Reach hospital immediately."],
            "snake": ["Keep the person still and calm.", "Do not cut, suck, or tie tightly near bite.", "Remove rings or tight items.", "Reach hospital immediately for anti-venom evaluation."],
            "general": ["Stay calm and keep the patient safe.", "Call 108 or local emergency number for serious symptoms.", "Keep the patient in a comfortable position.", "Reach the nearest hospital if symptoms are severe or worsening."]
        },
        "meds": {
            "none": ["No specific medicine suggestion. Use first-aid guidance and consult a healthcare professional."],
            "urgent": "Do not delay for medicines. First call 108 or reach the nearest hospital.",
            "fever": ["Paracetamol/Acetaminophen for fever or mild pain, only as per age/weight label or doctor's advice.", "ORS solution or fluids if fever is associated with weakness or dehydration."],
            "cold": ["Steam inhalation and warm fluids may help cold symptoms.", "Saline nasal drops/spray may help blocked nose.", "Cough syrup should be chosen with pharmacist/doctor guidance, especially for children."],
            "diarrhea": ["ORS solution after every loose stool/vomiting to prevent dehydration.", "Zinc may be advised for children with diarrhea by healthcare workers."],
            "acidity": ["Antacid gel/tablet may help mild acidity as per label instructions.", "Drink water and avoid spicy/oily food temporarily."],
            "wound": ["Clean wound with clean water.", "Use antiseptic solution/cream only for minor external wounds as per label.", "Tetanus injection may be needed for dirty/deep wounds; visit a healthcare center."],
            "warn_common": "Avoid self-medicating with antibiotics. Avoid ibuprofen/NSAIDs in pregnancy, kidney disease, stomach ulcer, dengue suspicion, or severe dehydration unless a doctor advises.",
            "warn_cold": "Do not use antibiotics for common cold unless prescribed. Avoid giving adult cold medicines to small children.",
            "warn_diarrhea": "Avoid anti-diarrhea tablets in children or bloody diarrhea unless a doctor advises. Seek care for severe dehydration, blood in stool, or repeated vomiting.",
            "warn_acidity": "Chest pain should not be treated as acidity without checking emergency signs. Seek urgent help for chest pain, sweating, or breathlessness.",
            "warn_wound": "Do not put unknown powders, soil, oil, or turmeric into deep wounds.",
            "preg_warn": "Pregnancy: do not take any medicine without doctor advice.",
            "allergy_warn": "Allergy noted: {allergy}. Avoid medicines that may trigger allergy and consult a doctor/pharmacist."
        }
    },
    "kn": {
        "monitor": "ಲಕ್ಷಣಗಳನ್ನು ಗಮನಿಸಿ. ಲಕ್ಷಣಗಳು ಹೆಚ್ಚಾದರೆ ಆರೋಗ್ಯ ಕೇಂದ್ರಕ್ಕೆ ಹೋಗಿ.",
        "no_major": "ದೊಡ್ಡ ತುರ್ತು ಸೂಚನೆ ಕಂಡುಬಂದಿಲ್ಲ.", "matched": "ಹೊಂದಿದ ಲಕ್ಷಣ", "danger_chest": "ಅಪಾಯ ಸಂಯೋಜನೆ: ಛಾತಿ ನೋವು ಜೊತೆಗೆ ಬೆವರು/ಉಸಿರಾಟ ತೊಂದರೆ/ಕೈ ಅಥವಾ ದವಡೆ ನೋವು", "danger_fever": "ಅಪಾಯ ಸಂಯೋಜನೆ: ಜ್ವರ ಜೊತೆಗೆ ಗಂಭೀರ ಎಚ್ಚರಿಕೆಯ ಲಕ್ಷಣ", "dehydration": "ದೇಹದ ನೀರಿನ ಕೊರತೆ ಸೂಚನೆಗಳು ಇರಬಹುದು", "spo2_low": "SpO₂ ಕಡಿಮೆ ಇದೆ", "spo2_very_low": "SpO₂ ತುಂಬಾ ಕಡಿಮೆ ಇದೆ", "high_fever": "ಹೆಚ್ಚಿನ ಜ್ವರ", "very_high_fever": "ತುಂಬಾ ಹೆಚ್ಚಿನ ಜ್ವರ", "abnormal_pulse": "ನಾಡಿ ಅಸಾಮಾನ್ಯವಾಗಿದೆ", "fast_pulse": "ನಾಡಿ ವೇಗವಾಗಿದೆ", "bp_danger": "ರಕ್ತದ ಒತ್ತಡ ಅಪಾಯಕಾರಿ ಮಟ್ಟದಲ್ಲಿದೆ", "age_caution": "ಈ ವಯಸ್ಸಿನವರಿಗೆ ಹೆಚ್ಚಿನ ಜಾಗ್ರತೆ ಅಗತ್ಯ", "preg_caution": "ಗರ್ಭಧಾರಣೆಯಲ್ಲಿ ಹೆಚ್ಚಿನ ಜಾಗ್ರತೆ ಅಗತ್ಯ", "diabetes_caution": "ಮಧುಮೇಹ/ಇತರೆ ಕಾಯಿಲೆ ಇದ್ದರೆ ಹೆಚ್ಚಿನ ಜಾಗ್ರತೆ ಅಗತ್ಯ",
        "next_steps": ["ಗಂಭೀರ ಸ್ಥಿತಿಯಲ್ಲಿ 108 ಗೆ ಕರೆ ಮಾಡಿ.", "ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆ ಹುಡುಕಲು ಲೈವ್ ಸ್ಥಳ ಬಳಸಿ.", "ಅಪಾಯ ಫಲಿತಾಂಶ ಮತ್ತು ಲಕ್ಷಣಗಳನ್ನು ವೈದ್ಯರು/ಆಂಬುಲೆನ್ಸ್ ಸಿಬ್ಬಂದಿಗೆ ತೋರಿಸಿ."],
        "voice": "{name}, ನಿಮ್ಮ ಅಪಾಯ ಮಟ್ಟ {risk}. ಅಂಕ {score} / 100. {msg}",
        "first_aid": {
            "chest pain": ["ತಕ್ಷಣ 108 ಗೆ ಕರೆ ಮಾಡಿ.", "ರೋಗಿಯನ್ನು ಆರಾಮದಾಯಕ ಸ್ಥಿತಿಯಲ್ಲಿ ಕುಳ್ಳಿರಿಸಿ ಅಥವಾ ಮಲಗಿಸಿ.", "ಬಿಗಿಯಾದ ಬಟ್ಟೆ ಸಡಿಲಿಸಿ ಮತ್ತು ರೋಗಿಯನ್ನು ಶಾಂತವಾಗಿರಿಸಿ.", "ರೋಗಿ ತುಂಬಾ ದುರ್ಬಲ ಅಥವಾ ಪ್ರಜ್ಞೆ ಇಲ್ಲದಿದ್ದರೆ ಆಹಾರ ಅಥವಾ ನೀರು ಕೊಡಬೇಡಿ."],
            "breathing": ["ಉಸಿರಾಟ ತೊಂದರೆ ಗಂಭೀರವಾಗಿದ್ದರೆ ತಕ್ಷಣ 108 ಗೆ ಕರೆ ಮಾಡಿ.", "ರೋಗಿಯನ್ನು ನೇರವಾಗಿ ಕುಳ್ಳಿರಿಸಿ.", "ತಾಜಾ ಗಾಳಿಯ ಸ್ಥಳಕ್ಕೆ ಕರೆದೊಯ್ಯಿರಿ.", "ರೋಗಿಯ ಸುತ್ತ ಜನರು ಗುಂಪಾಗಬಾರದು."],
            "bleeding": ["ಸ್ವಚ್ಛ ಬಟ್ಟೆಯಿಂದ ಬಲವಾಗಿ ಒತ್ತಿರಿ.", "ಸಾಧ್ಯವಿದ್ದರೆ ಗಾಯವಾದ ಭಾಗವನ್ನು ಮೇಲಕ್ಕೆ ಎತ್ತಿರಿ.", "ಗಾಯದಲ್ಲಿ ಸಿಕ್ಕಿಕೊಂಡ ವಸ್ತುಗಳನ್ನು ತೆಗೆದುಕೊಳ್ಳಬೇಡಿ.", "ರಕ್ತಸ್ರಾವ ನಿಲ್ಲದಿದ್ದರೆ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ."],
            "burn": ["ಸುಟ್ಟ ಭಾಗವನ್ನು ಸ್ವಚ್ಛ ಹರಿಯುವ ನೀರಿನಲ್ಲಿ 20 ನಿಮಿಷ ತಂಪಾಗಿಸಿ.", "ಟೂತ್‌ಪೇಸ್ಟ್, ಎಣ್ಣೆ ಅಥವಾ ಐಸ್ ನೇರವಾಗಿ ಹಾಕಬೇಡಿ.", "ಸ್ವಚ್ಛ ಬಟ್ಟೆಯಿಂದ ಮುಚ್ಚಿ.", "ದೊಡ್ಡ/ಆಳವಾದ/ಮುಖ/ಕೈ/ವಿದ್ಯುತ್ ಸುಟ್ಟ ಗಾಯಕ್ಕೆ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ."],
            "fever": ["ಸಾಕಷ್ಟು ದ್ರವ ಪದಾರ್ಥ ಕುಡಿಯಿರಿ.", "ತಂಪಾದ ಕೊಠಡಿಯಲ್ಲಿ ವಿಶ್ರಾಂತಿ ಮಾಡಿ.", "ಹಗುರವಾದ ಬಟ್ಟೆ ಧರಿಸಿ.", "ಜ್ವರ ತುಂಬಾ ಹೆಚ್ಚು, ನಿರಂತರ, ಉಸಿರಾಟ ತೊಂದರೆ ಅಥವಾ ಗೊಂದಲ ಇದ್ದರೆ ವೈದ್ಯರನ್ನು ಭೇಟಿ ಮಾಡಿ."],
            "stroke": ["FAST ಪರಿಶೀಲಿಸಿ: ಮುಖ ಬಾಗುವುದು, ಕೈ ದುರ್ಬಲತೆ, ಮಾತಿನ ತೊಂದರೆ, ತಕ್ಷಣ 108 ಕರೆ.", "ಆಹಾರ ಅಥವಾ ನೀರು ಕೊಡಬೇಡಿ.", "ರೋಗಿಯನ್ನು ಸುರಕ್ಷಿತವಾಗಿ ಮತ್ತು ಶಾಂತವಾಗಿರಿಸಿ.", "ತಕ್ಷಣ ಆಸ್ಪತ್ರೆಗೆ ಕರೆದೊಯ್ಯಿರಿ."],
            "snake": ["ವ್ಯಕ್ತಿಯನ್ನು ಚಲಿಸದಂತೆ ಶಾಂತವಾಗಿರಿಸಿ.", "ಕಚ್ಚಿದ ಜಾಗವನ್ನು ಕತ್ತರಿಸಬೇಡಿ, ಹೀರಬೇಡಿ ಅಥವಾ ಬಿಗಿಯಾಗಿ ಕಟ್ಟುಬೇಡಿ.", "ಉಂಗುರ ಅಥವಾ ಬಿಗಿಯಾದ ವಸ್ತುಗಳನ್ನು ತೆಗೆದುಹಾಕಿ.", "ಆಂಟಿ-ವೆನಮ್ ಪರಿಶೀಲನೆಗಾಗಿ ತಕ್ಷಣ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ."],
            "general": ["ಶಾಂತವಾಗಿರಿ ಮತ್ತು ರೋಗಿಯನ್ನು ಸುರಕ್ಷಿತವಾಗಿರಿಸಿ.", "ಗಂಭೀರ ಲಕ್ಷಣಗಳಿಗೆ 108 ಅಥವಾ ಸ್ಥಳೀಯ ತುರ್ತು ಸಂಖ್ಯೆಗೆ ಕರೆ ಮಾಡಿ.", "ರೋಗಿಯನ್ನು ಆರಾಮದಾಯಕ ಸ್ಥಿತಿಯಲ್ಲಿ ಇರಿಸಿ.", "ಲಕ್ಷಣಗಳು ಗಂಭೀರವಾಗಿದ್ದರೆ ಅಥವಾ ಹೆಚ್ಚಾದರೆ ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ."]
        },
        "meds": {
            "none": ["ನಿರ್ದಿಷ್ಟ ಔಷಧಿ ಸಲಹೆ ಇಲ್ಲ. ಪ್ರಥಮ ಚಿಕಿತ್ಸೆಯನ್ನು ಅನುಸರಿಸಿ ಮತ್ತು ಆರೋಗ್ಯ ಸಿಬ್ಬಂದಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ."], "urgent": "ಔಷಧಿಗಾಗಿ ತಡಮಾಡಬೇಡಿ. ಮೊದಲು 108 ಗೆ ಕರೆ ಮಾಡಿ ಅಥವಾ ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ.",
            "fever": ["ಜ್ವರ ಅಥವಾ ಸಣ್ಣ ನೋವಿಗೆ ಪ್ಯಾರಾಸಿಟಮಾಲ್/ಅಸೆಟಾಮಿನೋಫೆನ್ ಅನ್ನು ವಯಸ್ಸು/ತೂಕದ ಲೇಬಲ್ ಅಥವಾ ವೈದ್ಯರ ಸಲಹೆಯಂತೆ ಮಾತ್ರ ಬಳಸಿ.", "ದುರ್ಬಲತೆ ಅಥವಾ ನೀರಿನ ಕೊರತೆ ಇದ್ದರೆ ORS ಅಥವಾ ದ್ರವ ಪದಾರ್ಥ ಕುಡಿಯಿರಿ."],
            "cold": ["ಆವಿನ ಉಸಿರಾಟ ಮತ್ತು ಬಿಸಿ ದ್ರವ ಪದಾರ್ಥಗಳು ಜಲದುಷ್ಠಿ ಲಕ್ಷಣಗಳಿಗೆ ಸಹಾಯ ಮಾಡಬಹುದು.", "ಮೂಗು ಮುಚ್ಚಿಕೊಂಡಿದ್ದರೆ ಸ್ಯಾಲೈನ್ ಮೂಗು ಡ್ರಾಪ್ಸ್/ಸ್ಪ್ರೇ ಸಹಾಯ ಮಾಡಬಹುದು.", "ವಿಶೇಷವಾಗಿ ಮಕ್ಕಳಿಗೆ ಕೆಮ್ಮಿನ ಸಿರಪ್ ಅನ್ನು ಫಾರ್ಮಸಿಸ್ಟ್/ವೈದ್ಯರ ಸಲಹೆಯಿಂದ ಮಾತ್ರ ಬಳಸಿ."],
            "diarrhea": ["ಪ್ರತಿ ಸಡಿಲ ಮಲ/ವಾಂತಿಯ ನಂತರ ORS ಕುಡಿಯಿರಿ.", "ಮಕ್ಕಳ ಅತಿಸಾರಕ್ಕೆ ಆರೋಗ್ಯ ಸಿಬ್ಬಂದಿ ಜಿಂಕ್ ಸಲಹೆ ನೀಡಬಹುದು."],
            "acidity": ["ಸ್ವಲ್ಪ ಆಸಿಡಿಟಿಗೆ ಲೇಬಲ್ ಸೂಚನೆಯಂತೆ ಆಂಟಾಸಿಡ್ ಜೆಲ್/ಟ್ಯಾಬ್ಲೆಟ್ ಸಹಾಯ ಮಾಡಬಹುದು.", "ನೀರು ಕುಡಿಯಿರಿ ಮತ್ತು ತಾತ್ಕಾಲಿಕವಾಗಿ ಖಾರ/ಎಣ್ಣೆಯ ಆಹಾರ ತಪ್ಪಿಸಿ."],
            "wound": ["ಗಾಯವನ್ನು ಸ್ವಚ್ಛ ನೀರಿನಿಂದ ತೊಳೆಯಿರಿ.", "ಸಣ್ಣ ಹೊರಗಿನ ಗಾಯಗಳಿಗೆ ಮಾತ್ರ ಲೇಬಲ್ ಸೂಚನೆಯಂತೆ ಆಂಟಿಸೆಪ್ಟಿಕ್ ಬಳಸಿ.", "ಕೊಳಕು/ಆಳವಾದ ಗಾಯಗಳಿಗೆ ಟೆಟನಸ್ ಇಂಜೆಕ್ಷನ್ ಬೇಕಾಗಬಹುದು; ಆರೋಗ್ಯ ಕೇಂದ್ರಕ್ಕೆ ಹೋಗಿ."],
            "warn_common": "ಆಂಟಿಬಯಾಟಿಕ್‌ಗಳನ್ನು ಸ್ವಯಂವಾಗಿ ತೆಗೆದುಕೊಳ್ಳಬೇಡಿ. ಗರ್ಭಾವಸ್ಥೆ, ಕಿಡ್ನಿ ಕಾಯಿಲೆ, ಹೊಟ್ಟೆ ಅಲ್ಸರ್, ಡೆಂಗ್ಯೂ ಅನುಮಾನ ಅಥವಾ ಗಂಭೀರ ನೀರಿನ ಕೊರತೆ ಇದ್ದರೆ ವೈದ್ಯರ ಸಲಹೆ ಇಲ್ಲದೆ ಐಬುಪ್ರೊಫೆನ್/NSAID ತಪ್ಪಿಸಿ.",
            "warn_cold": "ವೈದ್ಯರು ಹೇಳದಿದ್ದರೆ ಸಾಮಾನ್ಯ ಜಲದುಷ್ಠಿಗೆ ಆಂಟಿಬಯಾಟಿಕ್ ಬಳಸಬೇಡಿ. ಸಣ್ಣ ಮಕ್ಕಳಿಗೆ ವಯಸ್ಕರ ಜಲದುಷ್ಠಿ ಔಷಧಿ ಕೊಡಬೇಡಿ.",
            "warn_diarrhea": "ಮಕ್ಕಳು ಅಥವಾ ರಕ್ತ ಮಿಶ್ರಿತ ಅತಿಸಾರದಲ್ಲಿ ವೈದ್ಯರ ಸಲಹೆ ಇಲ್ಲದೆ ಅತಿಸಾರ ನಿಲ್ಲಿಸುವ ಟ್ಯಾಬ್ಲೆಟ್ ಕೊಡಬೇಡಿ.",
            "warn_acidity": "ಛಾತಿ ನೋವನ್ನು ತುರ್ತು ಲಕ್ಷಣ ಪರೀಕ್ಷೆ ಇಲ್ಲದೆ ಆಸಿಡಿಟಿ ಎಂದು ಚಿಕಿತ್ಸೆ ಮಾಡಬೇಡಿ. ಬೆವರು/ಉಸಿರಾಟ ತೊಂದರೆ ಇದ್ದರೆ ತಕ್ಷಣ ಸಹಾಯ ಪಡೆಯಿರಿ.",
            "warn_wound": "ಆಳವಾದ ಗಾಯಗಳಿಗೆ ಅಪರಿಚಿತ ಪುಡಿ, ಮಣ್ಣು, ಎಣ್ಣೆ ಅಥವಾ ಅರಿಶಿಣ ಹಾಕಬೇಡಿ.",
            "preg_warn": "ಗರ್ಭಧಾರಣೆ: ವೈದ್ಯರ ಸಲಹೆ ಇಲ್ಲದೆ ಯಾವುದೇ ಔಷಧಿ ತೆಗೆದುಕೊಳ್ಳಬೇಡಿ.",
            "allergy_warn": "ಅಲರ್ಜಿ ದಾಖಲಿಸಲಾಗಿದೆ: {allergy}. ಅಲರ್ಜಿ ಉಂಟುಮಾಡಬಹುದಾದ ಔಷಧಿಗಳನ್ನು ತಪ್ಪಿಸಿ ಮತ್ತು ವೈದ್ಯರು/ಫಾರ್ಮಸಿಸ್ಟ್ ಸಲಹೆ ಪಡೆಯಿರಿ."
        }
    },
    "te": {
        "monitor": "లక్షణాలను గమనించండి. లక్షణాలు పెరిగితే ఆరోగ్య కేంద్రానికి వెళ్లండి.",
        "no_major": "పెద్ద అత్యవసర సూచన కనిపించలేదు.", "matched": "సరిపోలిన లక్షణం", "danger_chest": "ప్రమాద కలయిక: ఛాతి నొప్పితో చెమట/శ్వాస ఇబ్బంది/చేతి లేదా దవడ నొప్పి", "danger_fever": "ప్రమాద కలయిక: తీవ్రమైన హెచ్చరిక లక్షణంతో జ్వరం", "dehydration": "నీటి లోపం హెచ్చరిక లక్షణాలు ఉండవచ్చు", "spo2_low": "SpO₂ తక్కువగా ఉంది", "spo2_very_low": "SpO₂ చాలా తక్కువగా ఉంది", "high_fever": "అధిక జ్వరం", "very_high_fever": "చాలా అధిక జ్వరం", "abnormal_pulse": "పల్స్ అసాధారణంగా ఉంది", "fast_pulse": "పల్స్ వేగంగా ఉంది", "bp_danger": "రక్తపోటు ప్రమాద స్థాయిలో ఉంది", "age_caution": "ఈ వయస్సు వారికి అదనపు జాగ్రత్త అవసరం", "preg_caution": "గర్భధారణలో అదనపు జాగ్రత్త అవసరం", "diabetes_caution": "మధుమేహం/ఇతర వ్యాధి ఉంటే అదనపు జాగ్రత్త అవసరం",
        "next_steps": ["స్థితి తీవ్రమైతే 108 కు కాల్ చేయండి.", "సమీప ఆసుపత్రులు కనుగొనడానికి లైవ్ లొకేషన్ వాడండి.", "రిస్క్ ఫలితం మరియు లక్షణాలను డాక్టర్/అంబులెన్స్ సిబ్బందికి చూపండి."],
        "voice": "{name}, మీ ప్రమాద స్థాయి {risk}. స్కోర్ {score} / 100. {msg}",
        "first_aid": {
            "chest pain": ["వెంటనే 108 కు కాల్ చేయండి.", "రోగిని సౌకర్యమైన స్థితిలో కూర్చోబెట్టండి లేదా పడుకోబెట్టండి.", "బిగువైన బట్టలు సడలించి రోగిని ప్రశాంతంగా ఉంచండి.", "రోగి చాలా బలహీనంగా లేదా స్పృహ లేకుండా ఉంటే ఆహారం లేదా నీరు ఇవ్వవద్దు."],
            "breathing": ["శ్వాస ఇబ్బంది తీవ్రమైతే వెంటనే 108 కు కాల్ చేయండి.", "రోగిని నిటారుగా కూర్చోబెట్టండి.", "తాజా గాలి ఉన్న చోటుకు తీసుకెళ్లండి.", "రోగి చుట్టూ జనాలు గుంపుకాకుండా చూడండి."],
            "bleeding": ["శుభ్రమైన బట్టతో గట్టిగా ఒత్తండి.", "సాధ్యమైతే గాయమైన భాగాన్ని పైకి ఎత్తండి.", "గాయంలో చిక్కుకున్న లోతైన వస్తువులను తీసేయవద్దు.", "రక్తస్రావం ఆగకపోతే ఆసుపత్రికి వెళ్లండి."],
            "burn": ["కాలిన భాగాన్ని శుభ్రమైన ప్రవహించే నీటిలో 20 నిమిషాలు చల్లబరచండి.", "టూత్‌పేస్ట్, నూనె లేదా ఐస్ నేరుగా పెట్టవద్దు.", "శుభ్రమైన బట్టతో కప్పండి.", "పెద్ద/లోతైన/ముఖం/చేతి/విద్యుత్ కాలిన గాయాలకు ఆసుపత్రికి వెళ్లండి."],
            "fever": ["తగినంత ద్రవాలు తాగండి.", "చల్లటి గదిలో విశ్రాంతి తీసుకోండి.", "తేలికపాటి బట్టలు ధరించండి.", "జ్వరం చాలా ఎక్కువగా, నిరంతరం, శ్వాస ఇబ్బంది లేదా గందరగోళంతో ఉంటే డాక్టర్‌ను సంప్రదించండి."],
            "stroke": ["FAST చూడండి: ముఖం వంగడం, చేతి బలహీనత, మాటల సమస్య, వెంటనే 108 కాల్.", "ఆహారం లేదా నీరు ఇవ్వవద్దు.", "రోగిని సురక్షితంగా మరియు ప్రశాంతంగా ఉంచండి.", "వెంటనే ఆసుపత్రికి తీసుకెళ్లండి."],
            "snake": ["వ్యక్తిని కదలకుండా ప్రశాంతంగా ఉంచండి.", "కాటు దగ్గర కోయవద్దు, పీల్చవద్దు, బిగిగా కట్టవద్దు.", "ఉంగరాలు లేదా బిగువైన వస్తువులు తీసేయండి.", "యాంటీ-వెనమ్ పరీక్ష కోసం వెంటనే ఆసుపత్రికి వెళ్లండి."],
            "general": ["ప్రశాంతంగా ఉండండి మరియు రోగిని సురక్షితంగా ఉంచండి.", "తీవ్రమైన లక్షణాలకు 108 లేదా స్థానిక అత్యవసర నంబర్‌కు కాల్ చేయండి.", "రోగిని సౌకర్యమైన స్థితిలో ఉంచండి.", "లక్షణాలు తీవ్రమైతే లేదా పెరిగితే సమీప ఆసుపత్రికి వెళ్లండి."]
        },
        "meds": {
            "none": ["నిర్దిష్ట మందుల సూచన లేదు. ఫస్ట్ ఎయిడ్ పాటించి ఆరోగ్య సిబ్బందిని సంప్రదించండి."], "urgent": "మందుల కోసం ఆలస్యం చేయవద్దు. ముందుగా 108 కు కాల్ చేయండి లేదా సమీప ఆసుపత్రికి వెళ్లండి.",
            "fever": ["జ్వరం లేదా స్వల్ప నొప్పికి ప్యారాసిటమాల్/అసెటామినోఫెన్‌ను వయస్సు/బరువు లేబల్ లేదా డాక్టర్ సలహా ప్రకారం మాత్రమే వాడండి.", "బలహీనత లేదా నీటి లోపం ఉంటే ORS లేదా ద్రవాలు తాగండి."],
            "cold": ["ఆవిరి పీల్చడం మరియు వెచ్చని ద్రవాలు జలుబు లక్షణాలకు సహాయపడవచ్చు.", "ముక్కు మూసుకుపోతే సాలైన్ నాసల్ డ్రాప్స్/స్ప్రే సహాయపడవచ్చు.", "ప్రత్యేకంగా పిల్లలకు దగ్గు సిరప్‌ను ఫార్మసిస్ట్/డాక్టర్ సలహాతో మాత్రమే వాడండి."],
            "diarrhea": ["ప్రతి విరేచనం/వాంతి తర్వాత ORS తాగండి.", "పిల్లల విరేచనాలకు ఆరోగ్య సిబ్బంది జింక్ సలహా ఇవ్వవచ్చు."],
            "acidity": ["స్వల్ప అసిడిటీకి లేబల్ ప్రకారం యాంటాసిడ్ జెల్/టాబ్లెట్ సహాయపడవచ్చు.", "నీరు తాగండి మరియు తాత్కాలికంగా కారం/నూనె ఆహారం నివారించండి."],
            "wound": ["గాయాన్ని శుభ్రమైన నీటితో శుభ్రం చేయండి.", "స్వల్ప బయట గాయాలకు మాత్రమే లేబల్ ప్రకారం యాంటిసెప్టిక్ వాడండి.", "మురికి/లోతైన గాయాలకు టెటనస్ ఇంజెక్షన్ అవసరం కావచ్చు; ఆరోగ్య కేంద్రానికి వెళ్లండి."],
            "warn_common": "ఆంటీబయాటిక్స్‌ను స్వయంగా వాడవద్దు. గర్భధారణ, కిడ్నీ వ్యాధి, కడుపు అల్సర్, డెంగ్యూ అనుమానం లేదా తీవ్రమైన నీటి లోపం ఉంటే డాక్టర్ సలహా లేకుండా ఐబుప్రోఫెన్/NSAIDs నివారించండి.",
            "warn_cold": "డాక్టర్ చెప్పకపోతే సాధారణ జలుబుకు ఆంటీబయాటిక్ వాడవద్దు. చిన్న పిల్లలకు పెద్దల జలుబు మందులు ఇవ్వవద్దు.",
            "warn_diarrhea": "పిల్లలు లేదా రక్తంతో కూడిన విరేచనాల్లో డాక్టర్ సలహా లేకుండా విరేచనాలు ఆపే టాబ్లెట్లు ఇవ్వవద్దు.",
            "warn_acidity": "ఛాతి నొప్పిని అత్యవసర లక్షణాలు చూడకుండా అసిడిటీగా చికిత్స చేయవద్దు. చెమట/శ్వాస ఇబ్బంది ఉంటే అత్యవసర సహాయం పొందండి.",
            "warn_wound": "లోతైన గాయాల్లో తెలియని పొడి, మట్టి, నూనె లేదా పసుపు వేయవద్దు.",
            "preg_warn": "గర్భధారణ: డాక్టర్ సలహా లేకుండా ఏ మందు తీసుకోవద్దు.",
            "allergy_warn": "అలెర్జీ నమోదు చేయబడింది: {allergy}. అలెర్జీ కలిగించే మందులను నివారించండి మరియు డాక్టర్/ఫార్మసిస్ట్‌ను సంప్రదించండి."
        }
    }
}

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())

def contains_any(text: str, words: List[str]) -> bool:
    return any(w in text for w in words)

def calculate_risk(req: SymptomRequest) -> Dict[str, Any]:
    text = normalize(req.symptoms)
    lang = req.language if req.language in CONTENT else "en"
    c = CONTENT[lang]
    score = 0
    factors = []
    matched = []

    for keyword, points in EMERGENCY_KEYWORDS.items():
        if keyword in text:
            score += points
            factors.append(f"{c['matched']}: {keyword} (+{points})")
            matched.append(keyword)

    # combinations
    if contains_any(text, ["chest pain", "heart pain"]) and contains_any(text, ["sweating", "breathing", "shortness of breath", "left arm", "jaw pain"]):
        score += 35
        factors.append(c["danger_chest"] + " (+35)")
    if contains_any(text, ["fever"]) and contains_any(text, ["stiff neck", "confusion", "rash", "breathing difficulty", "seizure"]):
        score += 30
        factors.append(c["danger_fever"] + " (+30)")
    if contains_any(text, ["vomiting", "diarrhea"]) and contains_any(text, ["dizziness", "dry mouth", "no urine", "weakness", "dehydration"]):
        score += 20
        factors.append(c["dehydration"] + " (+20)")

    # vitals
    if req.spo2 is not None:
        if req.spo2 < 90:
            score += 45; factors.append(f"{c['spo2_very_low']}: {req.spo2}% (+45)")
        elif req.spo2 < 94:
            score += 25; factors.append(f"{c['spo2_low']}: {req.spo2}% (+25)")
    if req.temperature is not None:
        if req.temperature >= 40:
            score += 30; factors.append(f"{c['very_high_fever']}: {req.temperature}°C (+30)")
        elif req.temperature >= 38.5:
            score += 15; factors.append(f"{c['high_fever']}: {req.temperature}°C (+15)")
    if req.pulse is not None:
        if req.pulse > 130 or req.pulse < 45:
            score += 25; factors.append(f"{c['abnormal_pulse']}: {req.pulse} bpm (+25)")
        elif req.pulse > 110:
            score += 12; factors.append(f"{c['fast_pulse']}: {req.pulse} bpm (+12)")
    if req.bp_systolic is not None:
        if req.bp_systolic >= 180 or req.bp_systolic < 90:
            score += 25; factors.append(f"{c['bp_danger']}: {req.bp_systolic} (+25)")
    duration_text = normalize(req.duration or "")
    if "more than 2 days" in duration_text or "more than 1 week" in duration_text or "3 days" in duration_text or "week" in duration_text:
        score += 8; factors.append("Long symptom duration needs extra caution (+8)")
    if req.age is not None:
        if req.age < 5 or req.age > 65:
            score += 10; factors.append(c["age_caution"] + " (+10)")
    if req.child_patient or (req.age is not None and req.age < 12):
        score += 8; factors.append("Child patient needs medicine safety caution (+8)")
    if req.allergy_type and req.allergy_type.lower() != "no":
        score += 5; factors.append("Medicine allergy warning (+5)")
    if req.pregnancy:
        score += 10; factors.append(c["preg_caution"] + " (+10)")
    if req.diabetes:
        score += 8; factors.append(c["diabetes_caution"] + " (+8)")

    score = min(score, 100)
    lang = req.language if req.language in TRANSLATIONS else "en"
    tr = TRANSLATIONS[lang]
    if score >= 75:
        level_key = "critical"
    elif score >= 50:
        level_key = "high"
    elif score >= 25:
        level_key = "medium"
    else:
        level_key = "low"

    return {"score": score, "level_key": level_key, "risk_level": tr[level_key], "factors": factors or [c["no_major"]], "matched": matched}

def choose_first_aid(text: str, lang: str = "en") -> List[str]:
    t = normalize(text)
    content = CONTENT.get(lang, CONTENT["en"])["first_aid"]
    steps: List[str] = []
    mapping = [
        (["chest pain", "heart pain", "ಛಾತಿ", "ఛాతి"], "chest pain"),
        (["breathing", "asthma", "shortness of breath", "ಉಸಿರ", "శ్వాస"], "breathing"),
        (["bleeding", "wound", "cut", "ರಕ್ತ", "రక్త"], "bleeding"),
        (["burn", "ಸುಟ್ಟ", "కాలిన"], "burn"),
        (["fever", "ಜ್ವರ", "జ్వరం"], "fever"),
        (["stroke", "one side weakness", "speech", "ಸ್ಟ್ರೋಕ್", "స్ట్రోక్"], "stroke"),
        (["snake bite", "snake", "ಪಾಮು", "పాము"], "snake"),
    ]
    for words, key in mapping:
        if contains_any(t, words):
            steps.extend(content[key])
    if not steps:
        steps = content["general"]
    seen = set(); clean=[]
    for st in steps:
        if st not in seen:
            clean.append(st); seen.add(st)
    return clean[:8]

def suggest_medicines(req: SymptomRequest, risk_key: str) -> Dict[str, Any]:
    lang = req.language if req.language in CONTENT else "en"
    m = CONTENT[lang]["meds"]
    text = normalize(req.symptoms)
    meds, avoid = [], []
    if contains_any(text, ["fever", "body pain", "headache", "ಜ್ವರ", "ತಲೆ", "జ్వరం", "తలనొప్పి"]):
        meds.extend(m["fever"]); avoid.append(m["warn_common"])
    if contains_any(text, ["cold", "cough", "sore throat", "runny nose", "ಕೆಮ್ಮು", "ಜಲದುಷ್ಠಿ", "దగ్గు", "జలుబు"]):
        meds.extend(m["cold"]); avoid.append(m["warn_cold"])
    if contains_any(text, ["diarrhea", "loose motion", "vomiting", "ವಾಂತಿ", "ಅತಿಸಾರ", "వాంతి", "విరేచన"]):
        meds.extend(m["diarrhea"]); avoid.append(m["warn_diarrhea"])
    if contains_any(text, ["acidity", "heartburn", "gas", "ಆಸಿಡಿಟಿ", "ಗ್ಯಾಸ", "అసిడిటీ", "గ్యాస్"]):
        meds.extend(m["acidity"]); avoid.append(m["warn_acidity"])
    if contains_any(text, ["wound", "cut", "minor bleeding", "ಗಾಯ", "ಕಟ್", "గాయం", "కట్"]):
        meds.extend(m["wound"]); avoid.append(m["warn_wound"])
    if risk_key in ["critical", "high"]:
        meds.insert(0, m["urgent"])
    if req.pregnancy:
        avoid.append(m["preg_warn"])
    allergy_note = req.allergy or (req.allergy_type if req.allergy_type and req.allergy_type.lower() != "no" else "")
    if allergy_note:
        avoid.append(m["allergy_warn"].format(allergy=allergy_note))
    if req.child_patient or (req.age is not None and req.age < 12):
        avoid.append("Child medicine dose depends on age and weight. Do not give adult dosage without doctor advice.")
    if not meds:
        meds = m["none"]
    return {"suggestions": list(dict.fromkeys(meds)), "warnings": list(dict.fromkeys(avoid))}

@app.get("/")
def home():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.post("/api/analyze")
def analyze(req: SymptomRequest):
    risk = calculate_risk(req)
    first_aid = choose_first_aid(req.symptoms, req.language or "en")
    medicines = suggest_medicines(req, risk["level_key"])
    lang = req.language if req.language in TRANSLATIONS else "en"
    tr = TRANSLATIONS[lang]
    c = CONTENT.get(lang, CONTENT["en"])
    emergency_message = tr["go_now"] if risk["level_key"] in ["critical", "high"] else c["monitor"]
    doctor_warning = tr["doctor"]
    # Official-looking emergency case ID for lookup and report tracking
    case_id = "EMR-" + datetime.now().strftime("%Y%m%d-") + uuid.uuid4().hex[:6].upper()
    confidence = max(55, min(96, 58 + len(risk.get("matched", []))*7 + len(risk.get("factors", []))*4 + (15 if risk["score"] >= 70 else 0)))
    explanation = risk.get("factors", [])[:6] or [c.get("no_major", "No major emergency signal detected")]
    response = {
        "case_id": case_id,
        "ai_confidence": confidence,
        "ai_explanation": explanation,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "patient": {"name": req.name, "age": req.age, "gender": req.gender, "user_type": req.user_type, "village": req.village, "phone": req.phone, "emergency_contact": req.emergency_contact, "blood_group": req.blood_group, "existing_diseases": req.existing_diseases, "current_medicines": req.current_medicines, "pregnancy": req.pregnancy, "child_patient": req.child_patient, "allergy_type": req.allergy_type, "allergy": req.allergy},
        "symptoms": req.symptoms,
        "risk": risk,
        "emergency_message": emergency_message,
        "first_aid": first_aid,
        "medicine_guidance": medicines,
        "doctor_warning": doctor_warning,
        "next_steps": c["next_steps"],
        "voice_reply": c["voice"].format(name=req.name or "User", risk=risk["risk_level"], score=risk["score"], msg=emergency_message),
    }
    try:
        logs = json.loads(LOG_FILE.read_text(encoding="utf-8"))
        logs.append(response)
        LOG_FILE.write_text(json.dumps(logs[-300:], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return JSONResponse(response)

@app.get("/api/first-aid")
def first_aid(symptom: str = "", lang: str = "en"):
    # Returns offline-friendly first-aid + medicine guidance for a typed symptom.
    req = SymptomRequest(symptoms=symptom or "general", language=lang)
    risk = calculate_risk(req)
    medicines = suggest_medicines(req, risk["level_key"])
    return JSONResponse({
        "symptom": symptom,
        "risk": risk,
        "first_aid": choose_first_aid(symptom, lang),
        "medicine_guidance": medicines,
        "doctor_warning": TRANSLATIONS.get(lang, TRANSLATIONS["en"])["doctor"],
    })

@app.get("/api/dashboard")
def dashboard(lang: str = "en"):
    # Simple analytics dashboard summary used by the frontend.
    try:
        logs_data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        logs_data = []
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    recent = logs_data[-10:][::-1]
    for item in logs_data:
        key = item.get("risk", {}).get("level_key", "low")
        if key in counts:
            counts[key] += 1
    return JSONResponse({
        "total_cases": len(logs_data),
        "risk_counts": counts,
        "recent_logs": recent,
    })

@app.get("/service-worker.js")
def service_worker():
    return FileResponse(FRONTEND_DIR / "sw.js", media_type="application/javascript")

@app.get("/manifest.json")
def manifest():
    return FileResponse(FRONTEND_DIR / "manifest.json", media_type="application/manifest+json")


@app.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    """Generate Kannada/Telugu/English MP3 voice.
    Priority: Microsoft Edge Neural TTS, then Google gTTS fallback.
    This is needed because most Windows/Chrome installs do not include Kannada/Telugu local voices.
    Internet is required for Kannada/Telugu speech.
    """
    clean_text = (req.text or "").strip()
    if not clean_text:
        return JSONResponse({"error": "No text provided"}, status_code=400)
    clean_text = clean_text[:900]
    lang = (req.language or "en").lower()
    voice_map = {"kn": "kn-IN-SapnaNeural", "te": "te-IN-ShrutiNeural", "en": "en-IN-NeerjaNeural"}
    gtts_lang_map = {"kn": "kn", "te": "te", "en": "en"}

    now = time.time()
    for old in TTS_DIR.glob("*.mp3"):
        try:
            if now - old.stat().st_mtime > 3600:
                old.unlink()
        except Exception:
            pass

    errors = []

    # Method 1: Edge neural voice
    try:
        import edge_tts
        out_file = TTS_DIR / f"edge_voice_{uuid.uuid4().hex}.mp3"
        communicate = edge_tts.Communicate(clean_text, voice=voice_map.get(lang, voice_map["en"]), rate="-5%")
        await communicate.save(str(out_file))
        if out_file.exists() and out_file.stat().st_size > 500:
            return FileResponse(str(out_file), media_type="audio/mpeg", filename="assistant_voice.mp3")
        errors.append("Edge TTS created empty audio")
    except Exception as exc:
        errors.append("Edge TTS: " + str(exc))

    # Method 2: Google Translate TTS fallback
    try:
        from gtts import gTTS
        out_file = TTS_DIR / f"gtts_voice_{uuid.uuid4().hex}.mp3"
        tts = gTTS(text=clean_text, lang=gtts_lang_map.get(lang, "en"), slow=False)
        tts.save(str(out_file))
        if out_file.exists() and out_file.stat().st_size > 500:
            return FileResponse(str(out_file), media_type="audio/mpeg", filename="assistant_voice.mp3")
        errors.append("gTTS created empty audio")
    except Exception as exc:
        errors.append("gTTS: " + str(exc))

    return JSONResponse({
        "error": "Kannada/Telugu online voice generation failed",
        "details": " | ".join(errors),
        "help": "Run: pip install edge-tts gTTS ; keep internet ON ; restart uvicorn. If your college network blocks TTS, use mobile hotspot."
    }, status_code=500)

@app.get("/api/tts/check")
def tts_check():
    return JSONResponse({
        "message": "TTS API is available",
        "languages": {"en": "English", "kn": "Kannada", "te": "Telugu"},
        "note": "Kannada/Telugu speech needs internet or installed OS voice pack."
    })

@app.get("/api/logs")
def logs():
    return JSONResponse(json.loads(LOG_FILE.read_text(encoding="utf-8")))

@app.delete("/api/logs")
def clear_logs():
    LOG_FILE.write_text("[]", encoding="utf-8")
    return {"status": "cleared"}

@app.get("/api/admin-summary")
def admin_summary():
    try:
        logs_data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        logs_data = []
    villages = {}
    symptoms = {}
    patients = set()
    for l in logs_data:
        p = l.get("patient", {})
        if p.get("name") or p.get("phone"):
            patients.add((p.get("name",""), p.get("phone","")))
        v = p.get("village") or "Unknown"
        villages[v] = villages.get(v, 0) + 1
        for m in l.get("risk", {}).get("matched", []) or []:
            symptoms[m] = symptoms.get(m, 0) + 1
    top_symptom = max(symptoms.items(), key=lambda x: x[1])[0] if symptoms else "-"
    outbreak = "Normal"
    for v, count in villages.items():
        if v != "Unknown" and count >= 3:
            outbreak = f"Possible outbreak alert in {v}: {count} cases"
            break
    return JSONResponse({
        "total_patients": len(patients) or len(logs_data),
        "total_emergencies": len(logs_data),
        "critical_cases": sum(1 for x in logs_data if x.get("risk", {}).get("level_key") == "critical"),
        "villages_covered": len([v for v in villages if v != "Unknown"]),
        "common_symptom": top_symptom,
        "outbreak_status": outbreak,
    })

@app.get("/api/qr")
def qr_code(text: str = "Emergency Report"):
    try:
        import qrcode
        img = qrcode.make(text[:1200])
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png")
    except Exception as exc:
        return JSONResponse({"error": "QR generation failed", "details": str(exc), "help": "Run: pip install qrcode[pil]"}, status_code=500)

@app.get("/api/record/{case_id}")
def record_lookup(case_id: str):
    try:
        logs_data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        logs_data = []
    wanted = case_id.strip().upper()
    for item in reversed(logs_data):
        if str(item.get("case_id", "")).upper() == wanted:
            return JSONResponse(item)
    return JSONResponse({"error": "Record not found", "case_id": case_id}, status_code=404)


@app.post("/api/pdf-report")
async def pdf_report(request: Request):
    """Generate a hospital-style PDF emergency report from frontend report data."""
    try:
        data = await request.json()
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfbase.pdfmetrics import stringWidth
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=14*mm, bottomMargin=14*mm)
        styles = getSampleStyleSheet()
        title = ParagraphStyle('TitleBlue', parent=styles['Title'], textColor=colors.HexColor('#0f766e'), fontSize=18, leading=22)
        h2 = ParagraphStyle('Head', parent=styles['Heading2'], textColor=colors.HexColor('#0f172a'), fontSize=12, leading=15, spaceBefore=8)
        normal = ParagraphStyle('NormalSmall', parent=styles['BodyText'], fontSize=9, leading=12)
        warning = ParagraphStyle('Warn', parent=styles['BodyText'], fontSize=8, leading=10, textColor=colors.HexColor('#991b1b'))
        story = []
        story.append(Paragraph('AI-Powered Rural Emergency Medical Assistant', title))
        story.append(Paragraph('Hospital-style Emergency PDF Report', styles['Heading3']))
        story.append(Spacer(1, 6))
        patient = data.get('patient') or {}
        risk = data.get('risk') or {}
        rows = [
            ['Emergency ID', data.get('case_id','-'), 'Date/Time', data.get('timestamp','-')],
            ['Patient Name', patient.get('name','-'), 'Age / Gender', f"{patient.get('age','-')} / {patient.get('gender','-')}"],
            ['Village', patient.get('village','-'), 'Phone', patient.get('phone','-')],
            ['Emergency Contact', patient.get('emergency_contact','-'), 'Blood Group', patient.get('blood_group','-')],
            ['Risk Level', risk.get('risk_level','-'), 'Risk Score', str(risk.get('score','-')) + ' / 100'],
            ['AI Confidence', str(data.get('ai_confidence','-')) + '%', 'Symptoms', data.get('symptoms','-')],
        ]
        table = Table(rows, colWidths=[32*mm, 58*mm, 32*mm, 58*mm])
        table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#ccfbf1')),
            ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#cbd5e1')),
            ('FONTNAME',(0,0),(-1,-1),'Helvetica'),
            ('FONTSIZE',(0,0),(-1,-1),8),
            ('VALIGN',(0,0),(-1,-1),'TOP'),
            ('TEXTCOLOR',(0,0),(-1,-1),colors.HexColor('#0f172a')),
        ]))
        story.append(table)
        def para_list(title_text, values):
            story.append(Paragraph(title_text, h2))
            vals = values or []
            if isinstance(vals, str): vals = [vals]
            if not vals: vals = ['-']
            for i, x in enumerate(vals, 1):
                story.append(Paragraph(f'{i}. {str(x)}', normal))
        para_list('Why this risk / AI Explanation', data.get('ai_explanation') or (risk.get('factors') if isinstance(risk, dict) else []))
        para_list('First-Aid Steps', data.get('first_aid'))
        med = data.get('medicine_guidance') or {}
        para_list('Medicine Guidance', med.get('suggestions'))
        para_list('Warnings', [data.get('doctor_warning','')] + (med.get('warnings') or []))
        hosp = data.get('selected_hospital') or {}
        if hosp:
            story.append(Paragraph('Nearest Hospital / Route', h2))
            story.append(Paragraph(f"{hosp.get('name','-')} | Distance: {hosp.get('distance','-')} | Address: {hosp.get('address','-')}", normal))
        story.append(Spacer(1, 8))
        story.append(Paragraph('Important: This is an educational prototype. It is not a replacement for a doctor. For serious symptoms call 108 or visit the nearest hospital immediately. Do not take medicine without doctor advice, especially for children, pregnant women, elderly patients, allergies, or serious symptoms.', warning))
        doc.build(story)
        pdf = buf.getvalue()
        return Response(content=pdf, media_type='application/pdf', headers={'Content-Disposition': 'attachment; filename="emergency_medical_report.pdf"'})
    except Exception as exc:
        return JSONResponse({'error':'PDF generation failed','details':str(exc),'help':'Run: pip install reportlab'}, status_code=500)

@app.get("/health")
def health():
    return {"status": "ok", "project": "AI-Powered Rural Emergency Medical Assistant"}
