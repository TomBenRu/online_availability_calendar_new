
import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator


class EntityBase(BaseModel):
    """Basisklasse für alle Entities mit gemeinsamen Feldern"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime.datetime
    latest_change: datetime.datetime
    prep_delete: Optional[datetime.datetime] = None


# Availability Schemas
class AvailabilityBase(EntityBase):
    notes: Optional[str] = None
    date: datetime.date

class AvailabilityCreate(BaseModel):
    notes: Optional[str] = None
    time_of_day_id: UUID
    employee_plan_period_id: UUID
    date: datetime.date

class AvailabilityResponse(AvailabilityBase):
    time_of_day: "TimeOfDayBase"
    employee_plan_period: "EmployeePlanPeriodBase"


# TimeOfDay Schemas
class TimeOfDayBase(EntityBase):
    name: str = Field(..., max_length=40)
    start: datetime.time
    delta: datetime.timedelta
    color: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = None

class TimeOfDayCreate(BaseModel):
    name: str = Field(..., max_length=40)
    start: datetime.time
    delta: datetime.timedelta
    color: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = None
    person_id: UUID

class TimeOfDayResponse(TimeOfDayBase):
    person: "PersonBase"
    availabilities: List[AvailabilityBase]

    @field_validator("availabilities")
    def set_to_list(cls, v):
        return [v for v in v]


# Person Schemas
class PersonBase(EntityBase):
    f_name: str = Field(..., max_length=50)
    l_name: Optional[str] = Field(None, max_length=50)
    artist_name: Optional[str] = Field(None, max_length=50)
    email: EmailStr = Field(..., max_length=50)
    username: str = Field(..., max_length=50)

class PersonCreate(BaseModel):
    f_name: str = Field(..., max_length=50)
    l_name: Optional[str] = Field(None, max_length=50)
    artist_name: Optional[str] = Field(None, max_length=50)
    email: EmailStr = Field(..., max_length=50)
    username: str = Field(..., max_length=50)
    password: str

class PersonResponse(PersonBase):
    team: Optional["TeamBase"] = None
    time_of_days: List[TimeOfDayBase]
    teams_of_dispatcher: List["TeamBase"]
    project_of_admin: Optional["ProjectBase"] = None

    @field_validator("time_of_days", "teams_of_dispatcher")
    def set_to_list(cls, v):
        return [v for v in v]


# Project Schemas
class ProjectBase(EntityBase):
    name: str = Field(..., max_length=50)
    active: bool = True

class ProjectCreate(BaseModel):
    name: str = Field(..., max_length=50)
    active: bool = True
    admin_id: UUID

class ProjectResponse(ProjectBase):
    admin: PersonBase
    teams: List["TeamBase"]

    @field_validator("teams")
    def set_to_list(cls, v):
        return [v for v in v]


# Team Schemas
class TeamBase(EntityBase):
    name: str = Field(..., max_length=50)

class TeamCreate(BaseModel):
    name: str = Field(..., max_length=50)
    dispatcher_id: UUID
    project_id: UUID

class TeamResponse(TeamBase):
    persons: List[PersonBase]
    plan_periods: List["PlanPeriodBase"]
    dispatcher: PersonBase
    project: ProjectBase

    @field_validator("persons", "plan_periods")
    def set_to_list(cls, v):
        return [v for v in v]


# PlanPeriod Schemas
class PlanPeriodBase(EntityBase):
    notes: Optional[str] = None
    start: datetime.date
    end: datetime.date
    deadline: datetime.date

class PlanPeriodCreate(BaseModel):
    notes: Optional[str] = None
    start: datetime.date
    end: datetime.date
    deadline: datetime.date
    team_id: UUID

class PlanPeriodResponse(PlanPeriodBase):
    team: TeamBase
    employee_plan_periods: List["EmployeePlanPeriodBase"]
    apscheduler_job: Optional["APSchedulerJobBase"] = None

    @field_validator("employee_plan_periods")
    def set_to_list(cls, v):
        return [v for v in v]


# EmployeePlanPeriod Schemas
class EmployeePlanPeriodBase(EntityBase):
    notes: Optional[str] = None

class EmployeePlanPeriodCreate(BaseModel):
    notes: Optional[str] = None
    plan_period_id: UUID
    person_id: UUID

class EmployeePlanPeriodResponse(EmployeePlanPeriodBase):
    plan_period: PlanPeriodBase
    person: PersonBase
    availabilities: List[AvailabilityBase]

    @field_validator("availabilities")
    def set_to_list(cls, v):
        return [v for v in v]


# APSchedulerJob Schemas
class APSchedulerJobBase(EntityBase):
    job_id: str = Field(..., max_length=50)
    name: str = "APScheduler Job"
    func_name: str
    args: Optional[str] = None
    kwargs: Optional[str] = None
    trigger_type: str
    trigger_args: str
    next_runt_ime: Optional[datetime.datetime] = None
    active: bool = True

class APSchedulerJobCreate(BaseModel):
    job_id: str = Field(..., max_length=50)
    name: str = "APScheduler Job"
    func_name: str
    args: Optional[str] = None
    kwargs: Optional[str] = None
    trigger_type: str
    trigger_args: str
    plan_period_id: UUID

class APSchedulerJobResponse(APSchedulerJobBase):
    plan_period: PlanPeriodBase
