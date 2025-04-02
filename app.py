from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.sessions import SessionMiddleware
from datetime import datetime, timedelta, date, time
import uuid
import json

from pony.orm import db_session
from utils.repair import ensure_employee_plan_periods
# Importiere Datenbankmodule
from models import entities
from config.database import create_test_data
from utils.db_helpers import (
    get_plan_periods, get_time_of_day_options, get_selected_times,
    get_user_notes, save_note, toggle_availability, validate_login
)

# Lifespan-Kontext-Manager für Anwendungsstart und -ende
@asynccontextmanager
async def lifespan(app):
    """Wird beim Start und Herunterfahren der Anwendung ausgeführt"""
    # Beim Start: Erstelle Testdaten, wenn die Datenbank leer ist
    create_test_data()
    yield
    # Beim Herunterfahren (optional): Aufräumarbeiten
    print("Anwendung wird heruntergefahren...")

# FastAPI-App mit Lifespan-Kontext initialisieren
app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key="supersecretkey")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Globale Kontext-Variablen für Templates
templates.env.globals["datetime"] = datetime

# Globale Konstanten
# Monatsnamen für die Anzeige
month_names = {
    1: 'Januar',
    2: 'Februar',
    3: 'März',
    4: 'April',
    5: 'Mai',
    6: 'Juni',
    7: 'Juli',
    8: 'August',
    9: 'September',
    10: 'Oktober',
    11: 'November',
    12: 'Dezember'
}
# Farben für Planungsperioden
colors_for_periods = ['bg-blue-800/40', 'bg-emerald-800/40', 'bg-violet-800/40']
# Farben für die Notifikation:
notification_colors = {
    'background': {
        'checked': 'green-100', 
        'unchecked': 'red-100'
        },  
    'border': {
        'checked': 'green-400', 
        'unchecked': 'red-400'
        }, 
    'text': {
        'checked': 'green-700',
        'unchecked': 'red-700'
        }
}

# Session-Hilfe-Funktionen
def get_current_user(request: Request):
    """Holt den aktuellen Benutzer aus der Session"""
    user = request.session.get("user")
    return user

@app.get("/", name="index", response_class=HTMLResponse)
async def index(request: Request):
    """Zeigt die Hauptseite mit Login-Modal an"""
    # Prüfe, ob der Benutzer bereits eingeloggt ist
    user = get_current_user(request)
    if user:
        # Wenn der Benutzer eingeloggt ist, zeige den Kalender
        return await get_calendar_data(request)
    
    # Andernfalls zeige das Login-Modal
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )

@app.get("/api/calendar-data", response_class=HTMLResponse)
async def get_calendar_data(request: Request):
    """Gibt die Daten für den Kalender zurück"""
    # Prüfe, ob der Benutzer eingeloggt ist
    user = get_current_user(request)
    if not user:
        # Wenn der Benutzer nicht eingeloggt ist, umleiten zur Startseite
        return templates.TemplateResponse(
            "index.html",
            {"request": request}
        )
    
    # Lese compact_mode aus Query-Parametern
    compact_mode = request.query_params.get("compact", "0")

    # Definiere Höhen für normale und kompakte Ansicht
    base_row_height = 9  # normale Höhe
    compact_row_height = 5  # kompakte Höhe
    current_row_height = compact_row_height if compact_mode == "1" else base_row_height

    # Lade Daten aus der Datenbank
    plan_periods = get_plan_periods()
    time_of_day_options = get_time_of_day_options(user["id"])
    
    # DEBUG: Zeige Farbinformationen
    print("DEBUG: TimeOfDay Farben:")
    for tod in time_of_day_options:
        print(f"  - {tod['name']}: {tod['color']}")
    
    # Stelle sicher, dass EmployeePlanPeriods existieren
    ensure_employee_plan_periods(user["id"])
    
    selected_times = get_selected_times(user["id"])
    print(f"DEBUG APP: selected_times nach get_selected_times: {selected_times}")
    
    # Debug: Überprüfe was in selected_times ist
    if selected_times:
        print(f"DEBUG APP: selected_times enthält {len(selected_times)} Einträge")
        for key, values in selected_times.items():
            print(f"DEBUG APP: Datum {key} (Typ: {type(key)}) hat {len(values)} Zeitslots: {values}")
            
    user_notes = get_user_notes(user["id"])

    # Tage aller Planperioden, gruppieren nach Monat und plan_periods
    period_colors = {}
    grouped_dates = {} 
    period_deadlines = {}
    period_messages = {}  # Dictionary für die Mitteilungen
    period_first_month = {}  # Speichert den ersten Monat jeder Periode
    sorted_periods = []
    
    for period in plan_periods:
        text_plan_periods = f'{period["start"].strftime("%d.%m.%y")} - {period["end"].strftime("%d.%m.%y")}'
        period_deadlines[text_plan_periods] = period["deadline"]
        period_messages[text_plan_periods] = period["message"]
        
        # Ersten Monat für jede Periode speichern
        period_first_month[text_plan_periods] = period["start"].month
        
        for day in range((period['end'] - period['start']).days + 1):
            day_date = period['start'] + timedelta(days=day)
            if day_date.month not in grouped_dates:
                grouped_dates[day_date.month] = {
                    'year': day_date.year,
                    'periods': {}
                }
            if text_plan_periods not in grouped_dates[day_date.month]['periods']:
                grouped_dates[day_date.month]['periods'][text_plan_periods] = []
            grouped_dates[day_date.month]['periods'][text_plan_periods].append(day_date)

    # Sortierte Perioden basierend auf der Startdatum
    sorted_periods = sorted(list({period for periods in grouped_dates.values() 
                                for period in periods['periods'].keys()}), 
                                key=lambda x: (x.split(' - ')[0].split('.')[2], 
                                                x.split(' - ')[0].split('.')[1], 
                                                x.split(' - ')[0].split('.')[0]))

    # Generiere Farben für die Planungsperioden
    for month, month_periods in grouped_dates.items():
        for period in month_periods['periods'].keys():
            if period not in period_colors:
                period_colors.update({period: colors_for_periods[len(period_colors) % len(colors_for_periods)]})

    return templates.TemplateResponse("calendar.html", {
        "request": request,
        "grouped_dates": grouped_dates,
        "period_deadlines": period_deadlines,
        "period_messages": period_messages,
        "period_first_month": period_first_month,
        "selected_times": selected_times,
        "user_notes": user_notes,
        "sorted_periods": sorted_periods,
        "time_of_day_options": time_of_day_options,
        "compact_mode": compact_mode,
        "base_row_height": current_row_height,
        "month_names": month_names,
        "period_colors": period_colors,
        "user": user
    })

@app.get("/api/calendar-content", response_class=HTMLResponse)
async def get_calendar_content(request: Request):
    """Gibt die Daten für den Kalenderinhalt zurück"""
    # Prüfe, ob der Benutzer eingeloggt ist
    user = get_current_user(request)
    if not user:
        # Wenn der Benutzer nicht eingeloggt ist, zeige eine Fehlermeldung
        return templates.TemplateResponse(
            "notification_error.html",
            {
                "request": request,
                "message": "Bitte melden Sie sich an"
            }
        )
    
    # Lese compact_mode aus Query-Parametern
    compact_mode = request.query_params.get("compact", "0")

    # Wenn der Request vom Button kommt (HX-Target enthält view-mode-button)
    if "view-mode-button" in request.headers.get("HX-Target", ""):
        return templates.TemplateResponse(
            "calendar_view_mode_button.html",
            {
                "request": request,
                "compact_mode": compact_mode
            }
        ).body.decode()

    # Definiere Höhen für normale und kompakte Ansicht
    base_row_height = 9  # normale Höhe
    compact_row_height = 5  # kompakte Höhe
    current_row_height = compact_row_height if compact_mode == "1" else base_row_height

    # Lade Daten aus der Datenbank
    plan_periods = get_plan_periods()
    time_of_day_options = get_time_of_day_options(user["id"])
    
    # Stelle sicher, dass EmployeePlanPeriods existieren
    ensure_employee_plan_periods(user["id"])
    
    selected_times = get_selected_times(user["id"])

    # Tage aller Planperioden, gruppieren nach Monat und plan_periods
    period_colors = {}
    grouped_dates = {} 
    period_deadlines = {}
    period_messages = {}  # Dictionary für die Mitteilungen
    period_first_month = {}  # Speichert den ersten Monat jeder Periode
    sorted_periods = []
    
    for period in plan_periods:
        text_plan_periods = f'{period["start"].strftime("%d.%m.%y")} - {period["end"].strftime("%d.%m.%y")}'
        period_deadlines[text_plan_periods] = period["deadline"]
        period_messages[text_plan_periods] = period["message"]
        
        # Ersten Monat für jede Periode speichern
        period_first_month[text_plan_periods] = period["start"].month
        
        for day in range((period['end'] - period['start']).days + 1):
            day_date = period['start'] + timedelta(days=day)
            if day_date.month not in grouped_dates:
                grouped_dates[day_date.month] = {
                    'year': day_date.year,
                    'periods': {}
                }
            if text_plan_periods not in grouped_dates[day_date.month]['periods']:
                grouped_dates[day_date.month]['periods'][text_plan_periods] = []
            grouped_dates[day_date.month]['periods'][text_plan_periods].append(day_date)

    # Sortierte Perioden basierend auf der Startdatum
    sorted_periods = sorted(list({period for periods in grouped_dates.values() 
                                for period in periods['periods'].keys()}), 
                                key=lambda x: (x.split(' - ')[0].split('.')[2], 
                                                x.split(' - ')[0].split('.')[1], 
                                                x.split(' - ')[0].split('.')[0]))

    # Generiere Farben für die Planungsperioden
    for month, month_periods in grouped_dates.items():
        for period in month_periods['periods'].keys():
            if period not in period_colors:
                period_colors.update({period: colors_for_periods[len(period_colors) % len(colors_for_periods)]})

    return templates.TemplateResponse(
        "calendar_container.html",
        {
            "request": request,
            "grouped_dates": grouped_dates,
            "period_first_month": period_first_month,
            "period_deadlines": period_deadlines,
            "sorted_periods": sorted_periods,
            "time_of_day_options": time_of_day_options,
            "selected_times": selected_times,
            "compact_mode": compact_mode,
            "base_row_height": current_row_height,
            "month_names": month_names,
            "period_colors": period_colors,
            "user": user
        }
    )

@app.post("/api/login", name="login")
async def login(request: Request):
    """Authentifiziert den Benutzer"""
    form = await request.form()
    username = form.get("username")
    password = form.get("password")
    
    # Überprüfe die Anmeldedaten gegen die Datenbank
    user = validate_login(username, password)
    
    if user:
        # Bei erfolgreicher Anmeldung den Benutzer in der Session speichern
        request.session["user"] = user
        
        # Kalender zurückgeben
        return await get_calendar_data(request)
    else:
        # Bei fehlgeschlagener Anmeldung einen JSON-Fehler zurückgeben
        return JSONResponse(
            content={
                "error": True,
                "error_message": "Anmeldedaten sind nicht korrekt"
            },
            status_code=401
        )

@app.get("/logout", name="logout")
async def logout(request: Request):
    """Meldet den Benutzer ab"""
    # Session löschen
    request.session.clear()
    
    # Zur Startseite umleiten
    return RedirectResponse(url="/", status_code=303)

@app.get("/reset-password", name="reset_password")
async def reset_password(request: Request):
    """Zeigt die Passwort-Reset-Seite an"""
    return templates.TemplateResponse(
        "reset_password.html",
        {"request": request}
    )

@app.post("/api/reset-password-request", name="reset_password_request")
async def reset_password_request(request: Request):
    """Verarbeitet die Anfrage zum Zurücksetzen des Passworts"""
    form = await request.form()
    email = form.get("email")
    
    # Hier später die E-Mail-Logik implementieren
    # Erfolgstemplate zurückgeben, das das Formular ersetzt
    return templates.TemplateResponse(
        "reset_password_success.html",
        {
            "request": request,
            "email": email
        }
    )

@app.post("/api/load-period-notes", name="load_period_notes")
async def load_period_notes(request: Request):
    """Lädt die Notizen für eine bestimmte Planungsperiode"""
    # Prüfe, ob der Benutzer eingeloggt ist
    user = get_current_user(request)
    if not user:
        return templates.TemplateResponse(
            "notification_error.html",
            {
                "request": request,
                "message": "Bitte melden Sie sich an"
            }
        )
    
    form = await request.form()
    period = form.get("period")
    color = form.get("color")
    
    if not period:
        return templates.TemplateResponse(
            "notification_error.html",
            {
                "request": request,
                "message": "Keine Periode angegeben"
            }
        )
        
    # Lade Daten aus der Datenbank
    plan_periods = get_plan_periods()
    user_notes = get_user_notes(user["id"])
    
    # Finde die entsprechende Periode
    period_data = None
    for p in plan_periods:
        text_plan_periods = f'{p["start"].strftime("%d.%m.%y")} - {p["end"].strftime("%d.%m.%y")}'
        if text_plan_periods == period:
            period_data = p
            break
    
    if not period_data:
        return templates.TemplateResponse(
            "notification_error.html",
            {
                "request": request,
                "message": "Periode nicht gefunden"
            }
        )
    
    return templates.TemplateResponse(
        "period_notes.html",
        {
            "request": request,
            "period": period,
            "deadline": period_data["deadline"],
            "message": period_data["message"],
            "notes": user_notes.get(period, ""),
            "color": color
        }
    )

@app.post("/api/save-notes", name="save_notes")
async def save_notes_handler(request: Request):
    """Speichert die Notizen für eine bestimmte Planungsperiode"""
    # Prüfe, ob der Benutzer eingeloggt ist
    user = get_current_user(request)
    if not user:
        return templates.TemplateResponse(
            "notification_error.html",
            {
                "request": request,
                "message": "Bitte melden Sie sich an"
            }
        )
    
    try:
        form = await request.form()
        period = form.get("period")
        notes = form.get("notes")
        
        # Validiere die Eingaben
        if not period:
            return templates.TemplateResponse(
                "notification_error.html",
                {
                    "request": request,
                    "message": "Ungültige Eingabe"
                }
            )
            
        # Speichere die Notiz in der Datenbank
        success = save_note(user["id"], period, notes)
        
        return templates.TemplateResponse("notification_notes.html", {
            "request": request,
            "period": period,
            "success": success
        })
    except Exception as e:
        return templates.TemplateResponse(
            "notification_error.html",
            {
                "request": request,
                "message": f"Fehler beim Speichern: {str(e)}"
            }
        )

@app.post("/api/get-time-of-day-options", name="get_time_of_day_options")
async def get_time_of_day_options_handler(request: Request):
    """Gibt die verfügbaren Tageszeiten für einen bestimmten Tag zurück"""
    # Prüfe, ob der Benutzer eingeloggt ist
    user = get_current_user(request)
    if not user:
        return templates.TemplateResponse(
            "notification_error.html",
            {
                "request": request,
                "message": "Bitte melden Sie sich an"
            }
        )
    
    try:
        form = await request.form()
        date_str = form.get("date")
        plan_period = form.get("plan_period")
        
        if not date_str:
            return templates.TemplateResponse(
                "notification_error.html",
                {
                    "request": request,
                    "message": "Datum fehlt"
                }
            )
            
        # Stelle sicher, dass das Datum immer ein date-Objekt ist, nicht ein String
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError) as e:
            return templates.TemplateResponse(
                "notification_error.html",
                {
                    "request": request,
                    "message": f"Fehler beim Konvertieren des Datums: {str(e)}"
                }
            )
        
        # Hole Daten aus der Datenbank
        time_options = get_time_of_day_options(user["id"])
        
        # Stelle sicher, dass EmployeePlanPeriods existieren
        ensure_employee_plan_periods(user["id"])
        
        selected_times = get_selected_times(user["id"])
        
        # Hole ausgewählte Zeiten für dieses Datum
        selected_tod_ids = selected_times.get(date_str, [])
        print(f"Lade Tageszeit-Modal für {date_str}, ausgewählte IDs: {selected_tod_ids}")
        
        for tod in time_options:
            if tod['id'] in selected_tod_ids:
                print(f"  - Vorausgewählt: {tod['name']} ({tod['id']})")
        
        return templates.TemplateResponse("time_of_day_selector.html", {
            "request": request,
            "date": date_obj,
            "date_str": date_str,
            "plan_period": plan_period,
            "time_of_day_options": time_options,
            "selected_tod_ids": selected_tod_ids
        })
    except Exception as e:
        print(f"Fehler in get_time_of_day_options_handler: {e}")
        return templates.TemplateResponse(
            "notification_error.html",
            {
                "request": request,
                "message": f"Fehler beim Laden der Tageszeiten: {str(e)}"
            }
        )

@app.post("/api/select-time-of-day", name="select_time_of_day")
async def select_time_of_day(request: Request):
    """Wählt eine bestimmte Tageszeit für ein Datum aus oder entfernt sie"""
    # Prüfe, ob der Benutzer eingeloggt ist
    user = get_current_user(request)
    if not user:
        return templates.TemplateResponse(
            "notification_error.html",
            {
                "request": request,
                "message": "Bitte melden Sie sich an"
            }
        )
    
    try:
        form = await request.form()
        date_str = form.get("date")
        tod_id = form.get("tod_id")
        
        if not date_str or not tod_id:
            return templates.TemplateResponse(
                "notification_error.html",
                {
                    "request": request,
                    "message": "Datum oder Tageszeit fehlt"
                }
            )
        
        # Verfügbarkeit in der Datenbank umschalten
        try:
            # Verwende jetzt immer die normale toggle_availability Funktion
            print(f"Verwende normales toggle für {date_str}")
            is_checked, success = toggle_availability(user["id"], date_str, tod_id)
            
            if not success:
                return templates.TemplateResponse(
                    "notification_error.html",
                    {
                        "request": request,
                        "message": f"Fehler beim Umschalten der Verfügbarkeit: Datum oder Tageszeit konnte nicht verarbeitet werden."
                    }
                )
        except Exception as e:
            # Detaillierte Fehlermeldung an den Client zurückgeben
            error_message = str(e)
            print(f"Detaillierter Fehler in select_time_of_day: {error_message}")
            return templates.TemplateResponse(
                "notification_error.html",
                {
                    "request": request,
                    "message": f"Fehler beim Umschalten der Verfügbarkeit: {error_message}"
                }
            )
        
        # Hole Tageszeit-Daten
        time_options = get_time_of_day_options(user["id"])
        
        # Finden der TOD nach ID
        matching_tods = [tod for tod in time_options if tod['id'] == tod_id]
        
        if not matching_tods:
            return templates.TemplateResponse(
                "notification_error.html",
                {
                    "request": request,
                    "message": "Ungültige Tageszeit-ID: Keine passende Zeit gefunden"
                }
            )
            
        tod = matching_tods[0]
        print(f"Tageszeit {tod['name']} ({tod['id']}) ist nun {is_checked and 'aktiviert' or 'deaktiviert'}")
            
        curr_notification_colors = {
            'background': notification_colors['background']['checked' if is_checked else 'unchecked'],
            'border': notification_colors['border']['checked' if is_checked else 'unchecked'],
            'text': notification_colors['text']['checked' if is_checked else 'unchecked']
        }
        
        # Lade auch die aktuellen ausgewählten Zeiten neu, um die Anzeige zu aktualisieren
        selected_times = get_selected_times(user["id"])
        selected_tod_ids = selected_times.get(date_str, [])
        print(f"Aktualisierte Selected TOD IDs für {date_str}: {selected_tod_ids}")
        
        return templates.TemplateResponse(
            "time_of_day_selection_response.html",
            {
                "request": request,
                "date_str": date_str,
                "tod": tod,
                "is_checked": is_checked,
                "curr_notification_colors": curr_notification_colors,
            }
        )
    except Exception as e:
        print(f"Allgemeiner Fehler in select_time_of_day: {e}")
        return templates.TemplateResponse(
            "notification_error.html",
            {
                "request": request,
                "message": f"Fehler bei der Auswahl der Tageszeit: {str(e)}"
            }
        )

@app.post("/api/update-day-indicators", name="update_day_indicators")
async def update_day_indicators(request: Request):
    """Aktualisiert die Indikatoren für einen bestimmten Tag nach Auswahl/Abwahl einer Tageszeit"""
    # Prüfe, ob der Benutzer eingeloggt ist
    user = get_current_user(request)
    if not user:
        return templates.TemplateResponse(
            "notification_error.html",
            {
                "request": request,
                "message": "Bitte melden Sie sich an"
            }
        )
    
    try:
        form = await request.form()
        date_str = form.get("date")
        
        if not date_str:
            return templates.TemplateResponse(
                "notification_error.html",
                {
                    "request": request,
                    "message": "Datum fehlt"
                }
            )
            
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        # Hole Daten aus der Datenbank
        time_options = get_time_of_day_options(user["id"])
        selected_times = get_selected_times(user["id"])
        
        # Hole ausgewählte Zeiten für dieses Datum
        selected_tod_ids = selected_times.get(date_str, [])
        print(f"Selected TOD IDs for {date_str}: {selected_tod_ids}")
        
        # Finde die ausgewählten Tageszeiten mit vollständigen Daten
        selected_tods = []
        for tod in time_options:
            if tod['id'] in selected_tod_ids:
                selected_tods.append(tod)
        
        print(f"Selected TODs for {date_str}: {len(selected_tods)}")
        for tod in selected_tods:
            print(f"  - {tod['name']} ({tod['id']})")
        
        return templates.TemplateResponse(
            "day_indicators.html",
            {
                "request": request,
                "date": date_obj,
                "date_str": date_str,
                "selected_tods": selected_tods
            }
        )
    except Exception as e:
        print(f"Fehler in update_day_indicators: {str(e)}")
        return templates.TemplateResponse(
            "notification_error.html",
            {
                "request": request,
                "message": f"Fehler beim Aktualisieren der Tagesanzeige: {str(e)}"
            }
        )

@app.get("/get-calendar-menus", response_class=HTMLResponse)
async def get_calendar_menus(request: Request):
    """Liefert die Menüs für den Kalender"""
    # Prüfe, ob der Benutzer eingeloggt ist
    user = get_current_user(request)
    
    # Lade Planungsperioden aus der Datenbank
    plan_periods = get_plan_periods()
    
    # Sortierte Perioden basierend auf dem Startdatum
    sorted_periods = [f'{period["start"].strftime("%d.%m.%y")} - {period["end"].strftime("%d.%m.%y")}' for period in plan_periods]
    
    return templates.TemplateResponse("menus_calendar.html", {
        "request": request,
        "sorted_periods": sorted_periods,
        "user": user
    })

@app.exception_handler(500)
async def internal_server_error(request: Request, exc: Exception):
    """Handler für interne Serverfehler"""
    print(f"Server Error: {exc}")  # Debug print
    if "hx-request" in request.headers:
        # HTMX Request - zeige Notification
        return templates.TemplateResponse(
            "notification_error.html",
            {
                "request": request,
                "message": f"Server Fehler: {str(exc)}"  # Zeige den tatsächlichen Fehler
            }
        )
    else:
        # Normaler Request - zeige Fehlerseite
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": f"Ein unerwarteter Fehler ist aufgetreten: {str(exc)}"
            },
            status_code=500
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
