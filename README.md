# AI-Powered Rural Emergency Medical Assistant - Final Mega Advanced Version

This version includes all requested advanced rural healthcare features:

- Emergency Profile Card with blood group, emergency contact, allergies, current medicines
- Allergy warning system
- Pregnancy and child safety check
- Symptom duration selection
- Offline visual symptom buttons
- Village Health Worker Mode
- Disease outbreak alert
- Multilingual health tips
- Nearby pharmacy search
- Emergency report QR code
- Saved patient history in browser
- Admin dashboard
- Mobile app style bottom navigation
- Existing features: symptom analysis, first-aid, medicine guidance, live/manual location, hospital cards, route, voice assistance, multilingual UI, report download, WhatsApp/share, doctor connect simulation

## Run Steps

Open this folder in VS Code, then run:

```powershell
pip install edge-tts gTTS qrcode[pil]
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## Notes

- Kannada/Telugu voice needs internet for online TTS.
- Live location and hospital/pharmacy search need internet and browser location permission.
- Medicine guidance is only for basic awareness. Always consult a doctor/pharmacist.
- This is an educational project prototype.


## Final added features
- Ambulance tracking simulation
- Emergency WhatsApp alert
- Automatic medicine reminders from analysis result
- First-aid video guide
- Emergency heatmap and risk trend chart
- Multi-patient register for village health workers
- Emergency Case ID generation and patient record lookup
- AI confidence score and explanation
- Removed repeated offline symptom text boxes; kept only visual symptom buttons


## Final Added Features
- Emergency Family Contact List with call and WhatsApp alert
- Hospital-style PDF Emergency Report using reportlab
- Voice Command Shortcuts: find hospital, call emergency, speak first aid, show medicine, open dashboard, demo mode
- Offline Emergency Numbers section

Extra install command:
```powershell
pip install edge-tts gTTS qrcode[pil] reportlab
```
