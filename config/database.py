from pony.orm import db_session, Database, commit
import os
from pathlib import Path

# Projektbasis-Pfad
BASE_DIR = Path(__file__).resolve().parent.parent

# SQLite Datenbankpfad
DB_PATH = os.path.join(BASE_DIR, "database.sqlite")

def init_db(db):
    """Initialisiert die Datenbankverbindung"""
    db.bind(provider='sqlite', filename=DB_PATH, create_db=True)
    db.generate_mapping(create_tables=True)
    
    # Debug-Informationen
    print(f"Database initialized at: {DB_PATH}")
    return db

def get_db():
    """Gibt die Datenbankinstanz zurück"""
    from models.entities import db
    return db

# Funktion zum Erstellen von Beispieldaten, wenn die Datenbank leer ist
@db_session
def create_test_data():
    """Erstellt Beispieldaten in der Datenbank, wenn keine vorhanden sind"""
    from models.entities import Person, Team, Project, PlanPeriod, TimeOfDay, Availability, EmployeePlanPeriod
    import datetime
    import uuid
    
    # Überprüfen, ob bereits Daten vorhanden sind
    if Person.select().count() > 0:
        print("Datenbank enthält bereits Daten. Keine Testdaten erstellt.")
        return
    
    print("Erstelle Testdaten...")
    
    # Aktuelles Datum und Zeit
    now = datetime.datetime.now()
    
    try:
        # Erstelle zunächst den Admin-Benutzer
        admin = Person(
            f_name="Admin",
            l_name="User",
            email="admin@example.com",
            username="admin",
            password="p",  # In einer realen Anwendung sollte das Passwort gehasht werden
            created_at=now,
            latest_change=now
        )
        
        # Dann erstelle das Projekt
        project = Project(
            name="Demo-Projekt",
            active=True,
            created_at=now,
            latest_change=now,
            admin=admin
        )
        
        # Weise dem Admin das Projekt zu
        admin.project_of_admin = project
        
        # Team erstellen
        team = Team(
            name="Demo-Team",
            created_at=now,
            latest_change=now,
            dispatcher=admin,
            project=project
        )

        # Wir führen ein explizites Commit durch, um sicherzustellen, dass
        # alle bisherigen Objekte in der Datenbank gespeichert werden
        commit()
        
        # Admin dem Team zuordnen
        admin.team = team
        
        # Testmitarbeiter erstellen
        test_user = Person(
            f_name="Test",
            l_name="User",
            email="test@example.com",
            username="test",
            password="test",  # In einer realen Anwendung sollte das Passwort gehasht werden
            created_at=now,
            latest_change=now,
            team=team
        )
        
        # Tageszeiten erstellen
        time_of_day_options = [
            {
                'name': 'Früher Morgen',
                'start': datetime.time(6, 0),
                'delta': datetime.timedelta(hours=3),
                'color': 'yellow-400'
            },
            {
                'name': 'Vormittag',
                'start': datetime.time(9, 0),
                'delta': datetime.timedelta(hours=3),
                'color': 'amber-500'
            },
            {
                'name': 'Mittag',
                'start': datetime.time(12, 0),
                'delta': datetime.timedelta(hours=2),
                'color': 'orange-500'
            },
            {
                'name': 'Nachmittag',
                'start': datetime.time(14, 0),
                'delta': datetime.timedelta(hours=3),
                'color': 'orange-600'
            },
            {
                'name': 'Abend',
                'start': datetime.time(17, 0),
                'delta': datetime.timedelta(hours=3),
                'color': 'red-500'
            },
            {
                'name': 'Spätabend',
                'start': datetime.time(20, 0),
                'delta': datetime.timedelta(hours=3),
                'color': 'purple-500'
            }
        ]
        
        # Tageszeiten für Admin erstellen
        admin_times = []
        for i, tod_data in enumerate(time_of_day_options):
            tod = TimeOfDay(
                name=f"{tod_data['name']} (Admin)",
                start=tod_data['start'],
                delta=tod_data['delta'],
                color=tod_data['color'],
                created_at=now,
                latest_change=now,
                person=admin
            )
            admin_times.append(tod)
        
        # Tageszeiten für Testuser erstellen
        test_user_times = []
        for i, tod_data in enumerate(time_of_day_options):
            tod = TimeOfDay(
                name=f"{tod_data['name']} (Test)",
                start=tod_data['start'],
                delta=tod_data['delta'],
                color=tod_data['color'],
                created_at=now,
                latest_change=now,
                person=test_user
            )
            test_user_times.append(tod)
        
        # Wir führen ein weiteres explizites Commit durch
        commit()
        
        # Planungsperioden erstellen
        plan_periods = []
        for i in range(15):
            if i == 0:
                period_start = datetime.date(2024, 11, 1)
                period_end = datetime.date(2024, 11, 11)
                deadline = datetime.date(2024, 11, 10)
                notes = "Planungsperiode 1\nErledige deine Einträge bitte bis zur Deadline."
            elif i == 1:
                period_start = datetime.date(2024, 11, 12)
                period_end = datetime.date(2024, 11, 24)
                deadline = datetime.date(2024, 11, 23)
                notes = "Planungsperiode 2"
            elif i == 2:
                period_start = datetime.date(2024, 11, 25)
                period_end = datetime.date(2024, 12, 10)
                deadline = datetime.date(2024, 12, 9)
                notes = "Planungsperiode 3"
            elif i == 3:
                period_start = datetime.date(2024, 12, 11)
                period_end = datetime.date(2025, 1, 10)
                deadline = datetime.date(2025, 1, 9)
                notes = "Planungsperiode 4"
            elif i == 4:
                period_start = datetime.date(2025, 1, 11)
                period_end = datetime.date(2025, 1, 20)
                deadline = datetime.date(2025, 1, 19)
                notes = "Planungsperiode 5"
            else:
                # Für die übrigen Perioden einfach 20 Tage hinzufügen
                period_start = period_end + datetime.timedelta(days=1)
                period_end = period_start + datetime.timedelta(days=19)
                deadline = period_end - datetime.timedelta(days=1)
                notes = f"Planungsperiode {i+1}"
            
            period = PlanPeriod(
                start=period_start,
                end=period_end,
                deadline=deadline,
                notes=notes,
                created_at=now,
                latest_change=now,
                team=team
            )
            plan_periods.append(period)
        
        # Noch ein Commit
        commit()
        
        # EmployeePlanPeriod für Testuser erstellen
        emp_plan_periods = []
        for period in plan_periods:
            emp_plan_period = EmployeePlanPeriod(
                created_at=now,
                latest_change=now,
                plan_period=period,
                person=test_user
            )
            emp_plan_periods.append(emp_plan_period)
        
        # Erneut ein Commit
        commit()
        
        # Beispiel-Verfügbarkeiten für den Testbenutzer erstellen
        for i, period in enumerate(plan_periods):
            if i > 2:  # Nur für die ersten 3 Perioden
                continue
                
            emp_plan_period = emp_plan_periods[i]
            
            # Für die ersten 3 Tage der Periode einige Verfügbarkeiten setzen
            for day_offset in range(3):
                # Aktuelles Datum berechnen
                current_date = period.start + datetime.timedelta(days=day_offset)
                
                # An jedem Tag 2 der 6 Tageszeiten auswählen (alternierend)
                for j in range(2):
                    tod_index = (day_offset * 2 + j) % len(test_user_times)
                    tod = test_user_times[tod_index]
                    
                    Availability(
                        created_at=now,
                        latest_change=now,
                        time_of_day=tod,
                        employee_plan_period=emp_plan_period,
                        date=current_date  # Neues Datumsfeld verwenden
                    )
        
        # Notizen für einige EmployeePlanPeriods eintragen
        for i, epp in enumerate(emp_plan_periods):
            if i % 3 == 0:  # Nur für jede dritte Periode
                epp.notes = f"Meine Notizen für Planungsperiode {i+1}"
        
        print("Testdaten wurden erfolgreich erstellt.")
        
    except Exception as e:
        print(f"Fehler beim Erstellen der Testdaten: {e}")
        raise e
