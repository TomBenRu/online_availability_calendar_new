from pony.orm import db_session, select
from datetime import datetime
import uuid

from models.entities import (
    Person, Team, Project, PlanPeriod, TimeOfDay,
    Availability, EmployeePlanPeriod
)

@db_session
def ensure_employee_plan_periods(user_id):
    """Stellt sicher, dass für den Benutzer Employee Plan Periods existieren"""
    print(f"\n--- START ensure_employee_plan_periods ---")
    print(f"Argumente: user_id={user_id}")
    
    try:
        # Benutzer suchen
        user_uuid = uuid.UUID(user_id)
        user = Person.get(id=user_uuid)
        if not user:
            print(f"Benutzer mit ID {user_id} nicht gefunden!")
            return False
            
        print(f"Benutzer gefunden: id={user.id}, username={user.username}")
        
        # Vorhandene EmployeePlanPeriods zählen
        existing_epps = list(EmployeePlanPeriod.select(lambda epp: epp.person.id == user_uuid and epp.prep_delete is None))
        print(f"Vorhandene EmployeePlanPeriods: {len(existing_epps)}")
        
        if len(existing_epps) > 0:
            print("Es existieren bereits EmployeePlanPeriods für diesen Benutzer.")
            return True
            
        # Alle Planperioden laden
        plan_periods = list(PlanPeriod.select(lambda pp: pp.prep_delete is None))
        print(f"Verfügbare PlanPeriods: {len(plan_periods)}")
        
        if len(plan_periods) == 0:
            print("Keine Planperioden in der Datenbank gefunden!")
            return False
            
        # Für jede Planperiode ein EmployeePlanPeriod erstellen
        now = datetime.now()
        created_count = 0
        
        for pp in plan_periods:
            try:
                new_epp = EmployeePlanPeriod(
                    id=uuid.uuid4(),
                    created_at=now,
                    latest_change=now,
                    plan_period=pp,
                    person=user
                )
                print(f"Neue EmployeePlanPeriod erstellt: id={new_epp.id}, plan_period={pp.id}")
                created_count += 1
            except Exception as e:
                print(f"Fehler beim Erstellen einer EmployeePlanPeriod: {str(e)}")
        
        print(f"Insgesamt {created_count} neue EmployeePlanPeriods erstellt.")
        return created_count > 0
    except Exception as e:
        print(f"Fehler in ensure_employee_plan_periods: {str(e)}")
        return False
    finally:
        print("--- END ensure_employee_plan_periods ---\n")
