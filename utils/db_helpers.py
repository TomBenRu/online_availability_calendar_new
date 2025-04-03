from pony.orm import db_session, flush

from models import schemas
from models.entities import PlanPeriod, EmployeePlanPeriod, Person, TimeOfDay, Availability
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
import uuid

@db_session
def get_plan_periods() -> List[Dict[str, Any]]:
    """Holt alle Planungsperioden aus der Datenbank und formatiert sie"""
    periods = PlanPeriod.select(lambda p: p.prep_delete is None).order_by(PlanPeriod.start)
    result = []
    
    for period in periods:
        result.append({
            'id': str(period.id),
            'start': period.start,
            'end': period.end,
            'deadline': period.deadline,
            'message': period.notes or f'Planungsperiode {period.start.strftime("%d.%m.%y")} - {period.end.strftime("%d.%m.%y")}'
        })
    
    return result


@db_session
def get_time_of_day(tod_id: str) -> schemas.TimeOfDayResponse:
    """Holt eine Tageszeit aus der Datenbank und formatiert sie"""
    tod = TimeOfDay.get(id=uuid.UUID(tod_id))
    return schemas.TimeOfDayResponse.model_validate(tod)


@db_session
def get_time_of_day_options(user_id=None) -> List[Dict[str, Any]]:
    """Holt alle Tageszeiten aus der Datenbank und formatiert sie"""
    if user_id:
        times = TimeOfDay.select(lambda t: t.prep_delete is None and t.person.id == uuid.UUID(user_id))
    else:
        times = TimeOfDay.select(lambda t: t.prep_delete is None)
    
    result = []
    for tod in times:
        # Stelle sicher, dass start ein datetime.time-Objekt ist
        start_time = tod.start
        if isinstance(start_time, str):
            # Wenn es ein String ist, konvertiere es zu einem time-Objekt
            # Versuche verschiedene Zeitformate
            try:
                # Versuche zuerst mit HH:MM:SS Format
                start_time = datetime.strptime(start_time, "%H:%M:%S").time()
            except ValueError:
                try:
                    # Falls das nicht klappt, versuche HH:MM Format
                    start_time = datetime.strptime(start_time, "%H:%M").time()
                except ValueError as e:
                    # Im Fehlerfall, gib ein Standardzeit-Objekt zurück und protokolliere den Fehler
                    print(f"Fehler beim Konvertieren der Zeit: {start_time} - {e}")
                    start_time = datetime.strptime("00:00", "%H:%M").time()
        
        # Hol die Farbinformation und setze eine Standardfarbe, wenn keine vorhanden ist
        # Präferierte Farben: yellow-400, amber-500, red-500, blue-500, green-500, purple-500
        default_color = "gray-500"
        color = getattr(tod, 'color', default_color)

        
        result.append({
            'id': str(tod.id),
            'name': tod.name,
            'start': start_time,
            'delta': tod.delta,
            'created_at': tod.created_at,
            'latest_change': tod.latest_change,
            'color': color
        })
    
    return result
    
    return result

@db_session
def get_selected_times(user_id, period_id=None) -> Dict[str, List[str]]:
    """Holt die ausgewählten Zeiten eines Benutzers für alle oder eine bestimmte Periode"""
    
    result = {}
    
    try:
        
        # Überprüfe, ob der angegebene Benutzer existiert
        user_uuid = uuid.UUID(user_id)

        
        if period_id:
            period_uuid = uuid.UUID(period_id)
            emp_periods = EmployeePlanPeriod.select(
                lambda epp: epp.person.id == user_uuid and 
                            epp.plan_period.id == period_uuid and
                            epp.prep_delete is None
            )
        else:
            emp_periods = EmployeePlanPeriod.select(
                lambda epp: epp.person.id == user_uuid and
                             epp.prep_delete is None
            )
        
        all_emp_periods = list(emp_periods)  # Konvertieren zu Liste für Zählung

        for i, emp_period in enumerate(all_emp_periods):
            
            # Verfügbarkeiten für diese Periode abrufen
            availabilities = Availability.select(
                lambda a: a.employee_plan_period == emp_period and
                          a.prep_delete is None
            )
            
            all_availabilities = list(availabilities)  # Konvertieren zu Liste für Zählung
            
            # Verarbeite alle Verfügbarkeiten
            for j, avail in enumerate(all_availabilities):
                try:
                    tod_id = str(avail.time_of_day.id)
                    
                    # Verwende direkt das Datum aus dem Verfügbarkeitseintrag
                    if hasattr(avail, 'date') and avail.date is not None:
                        date_str = avail.date.strftime("%Y-%m-%d")
                        
                        # Füge die Verfügbarkeit zum Ergebnis hinzu
                        if date_str not in result:
                            result[date_str] = []
                        if tod_id not in result[date_str]:
                            result[date_str].append(tod_id)
                    else:
                        print(f"    - Verfügbarkeit {j+1}/{len(all_availabilities)}: ID={avail.id} hat kein Datum")
                        
                except Exception as e:
                    print(f"    - Fehler bei Verarbeitung von Verfügbarkeit {avail.id}: {str(e)}")
                
        # Stelle sicher, dass alle Schlüssel Strings sind (nicht datetime.date)
        string_result = {}
        for key, value in result.items():
            if not isinstance(key, str):
                string_key = key.strftime('%Y-%m-%d') if hasattr(key, 'strftime') else str(key)
                string_result[string_key] = value
            else:
                string_result[key] = value
        
        return string_result
    except Exception as e:
        return {}
    finally:
        print("--- END get_selected_times ---\n")

@db_session
def get_user_notes(user_id=None) -> Dict[str, str]:
    """Holt die Notizen eines Benutzers für alle Perioden"""
    # Manuell die Abfrage durchführen
    result = {}
    
    if not user_id:
        return result
        
    # Employee Plan Periods mit Notizen finden
    user_uuid = uuid.UUID(user_id)
    employee_plan_periods = EmployeePlanPeriod.select(
        lambda epp: epp.person.id == user_uuid and 
                    epp.notes is not None and 
                    epp.prep_delete is None
    )
    
    # Für jede Periode die Notizen abrufen
    for epp in employee_plan_periods:
        plan_period = epp.plan_period
        period_key = f"{plan_period.start.strftime('%d.%m.%y')} - {plan_period.end.strftime('%d.%m.%y')}"
        result[period_key] = epp.notes
        
    return result

@db_session
def save_note(user_id, period_text, notes):
    """Speichert eine Notiz für eine Planungsperiode"""
    # Parse period_text to get start and end dates
    start_str, end_str = period_text.split(' - ')
    start_date = datetime.strptime(start_str, "%d.%m.%y").date()
    end_date = datetime.strptime(end_str, "%d.%m.%y").date()
    
    # Find the corresponding plan_period
    plan_periods = PlanPeriod.select(
        lambda p: p.start == start_date and 
                  p.end == end_date and 
                  p.prep_delete is None
    )
    plan_period = None
    for p in plan_periods:
        plan_period = p
        break
    
    if not plan_period:
        return False
    
    # Find or create employee_plan_period
    person = Person[uuid.UUID(user_id)]
    
    emp_plan_periods = EmployeePlanPeriod.select(
        lambda epp: epp.person.id == uuid.UUID(user_id) and 
                     epp.plan_period.id == plan_period.id and 
                     epp.prep_delete is None
    )
    
    emp_plan_period = None
    for epp in emp_plan_periods:
        emp_plan_period = epp
        break
    
    if not emp_plan_period:
        emp_plan_period = EmployeePlanPeriod(
            id=uuid.uuid4(),
            created_at=datetime.now(),
            latest_change=datetime.now(),
            plan_period=plan_period,
            person=person,
            notes=notes
        )
    else:
        emp_plan_period.notes = notes
        emp_plan_period.latest_change = datetime.now()
    
    return True


@db_session
def get_availability_user_date(user_id: str, date_str: str) -> List[schemas.AvailabilityResponse]:
    """Holt die Verfügbarkeit eines Benutzers für ein bestimmtes Datum"""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    user_uuid = uuid.UUID(user_id)
    availabilities_db = Availability.select(
        lambda a: a.employee_plan_period.person.id == user_uuid and
                  a.date == date_obj and
                  a.prep_delete is None
    )
    return [schemas.AvailabilityResponse.model_validate(a) for a in availabilities_db]


@db_session
def toggle_availability(user_id: str, date_str: str, tod_id: str) -> schemas.AvailabilityResponse:
    """
    Schaltet die Verfügbarkeit eines Benutzers für eine bestimmte Tageszeit an einem bestimmten Datum um.
    
    Wenn für die angegebene Kombination aus Benutzer, Datum und Tageszeit bereits eine aktive 
    Verfügbarkeit existiert, wird diese deaktiviert. Andernfalls wird eine neue Verfügbarkeit erstellt.

    Args:
        user_id (str): Die UUID des Benutzers als String
        date_str (str): Das Datum im Format "YYYY-MM-DD"
        tod_id (str): Die UUID der Tageszeit (TimeOfDay) als String

    Returns:
        schemas.AvailabilityResponse]
    """
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    plan_period_db = (PlanPeriod.select()
                      .filter(lambda p: p.prep_delete is None)
                      .filter(lambda p: p.start <= date_obj)
                      .filter(lambda p: p.end >= date_obj)
                      .filter(lambda p: p.prep_delete is None)
                      .first())

    employee_plan_period_db = (EmployeePlanPeriod.select()
                               .filter(lambda epp: epp.person.id == uuid.UUID(user_id))
                               .filter(lambda epp: epp.prep_delete is None)
                               .filter(lambda epp: epp.plan_period.id == plan_period_db.id)
                               .first())
    time_of_day_db = TimeOfDay.get(id=uuid.UUID(tod_id))
    availability_db = Availability.get(
        lambda a: a.employee_plan_period.id == employee_plan_period_db.id and
                  a.time_of_day == time_of_day_db and
                  a.date == date_obj and
                  a.prep_delete is None
    )
    if availability_db:
        availability_db.prep_delete = datetime.now()
    else:
        availability_db = Availability(
            created_at=datetime.now(),
            latest_change=datetime.now(),
            time_of_day=time_of_day_db,
            employee_plan_period=employee_plan_period_db,
            date=date_obj
        )
    return schemas.AvailabilityResponse.model_validate(availability_db)

        
@db_session
def validate_login(username, password):
    """Überprüft die Anmeldedaten des Benutzers"""
    
    try:
        # Umgehe den Generator-Ausdruck, der in Python 3.12 zu Problemen führt
        users = Person.select(lambda p: p.username == username and 
                              p.password == password and 
                              p.prep_delete is None)
        
        # Manuelles Abrufen des ersten Ergebnisses
        user = None
        for p in users:
            user = p
            break
        
        if user:
            return {
                'id': str(user.id),
                'username': user.username,
                'first_name': user.f_name,
                'last_name': user.l_name,
                'email': user.email,
                'is_admin': user.project_of_admin is not None
            }
        else:
            print(f"Kein Benutzer mit dem Benutzernamen '{username}' und dem angegebenen Passwort gefunden.")
        
        return None
    finally:
        print("--- END validate_login ---\n")