from uuid import UUID
from datetime import datetime, date, time # Add date and time here
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# --- Auth ---
class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    department: str
    name: str

# --- User ---
class UserCreate(BaseModel):
    name: str
    username: str
    password: str
    role: str
    department: str
    shift: Optional[str] = None
    phone: Optional[str] = None

class UserOut(BaseModel):
    id: UUID           # Changed from str to UUID
    name: str
    username: str
    role: str
    department: str
    shift: Optional[str] = None
    class Config:
        from_attributes = True

# --- Boiler Log Entry ---
class BoilerLogCreate(BaseModel):
    shift: str
    log_date: str
    log_time: str
    operator_name: Optional[str] = None
    steam_pressure: Optional[float] = None
    steam_flow_sep: Optional[float] = None
    steam_flow_refl: Optional[float] = None
    drum_water_level: Optional[float] = None
    bed1_top_temp: Optional[float] = None
    bed1_bottom_temp: Optional[float] = None
    bed2_top_temp: Optional[float] = None
    bed2_bottom_temp: Optional[float] = None
    flue_gas_temp: Optional[float] = None
    coal_feed_bed1_hz: Optional[float] = None
    coal_feed_bed2_hz: Optional[float] = None
    cbd_ibd_report: Optional[str] = None
    id_fan_damper: Optional[float] = None
    fd_fan1_damper: Optional[float] = None
    fd_fan2_damper: Optional[float] = None
    booster_fan1: Optional[float] = None
    booster_fan2: Optional[float] = None
    gag_filter_temp: Optional[float] = None
    breakdown_problem: Optional[str] = None
    feed_water_temp: Optional[float] = None
    fd_pressure: Optional[float] = None
    remarks: Optional[str] = None
    coal_opening_stock: Optional[float] = None
coal_received: Optional[float] = None
coal_consumed_sep: Optional[float] = None
coal_consumed_refinery: Optional[float] = None
coal_thermic: Optional[float] = None
steam_sep_opening: Optional[float] = None
steam_sep_closing: Optional[float] = None
steam_refl_opening: Optional[float] = None
steam_refl_closing: Optional[float] = None
coal_bunker_pct: Optional[float] = None
steam_pressure_ok: Optional[bool] = None

class BoilerLogOut(BoilerLogCreate):
    id: int
    user_id: UUID      # Changed from int to UUID
    log_date: date     # Changed from str to date
    log_time: time     # Changed from str to time
    status: str
    created_at: datetime
    class Config:
        from_attributes = True

# --- Daily Coal & Steam ---
class DailyCoalSteamCreate(BaseModel):
    report_date: str
    opening_coal_stock: float
    coal_arrival_indian: float = 0
    coal_arrival_imported: float = 0
    coal_consumed_sep: float
    coal_consumed_refinery: float
    coal_thermic: float = 0
    steam_sep_opening: float
    steam_sep_closing: float
    steam_refl_opening: float
    steam_refl_closing: float
    feed_water_temp: Optional[float] = None
    coal_bunker_pct: Optional[float] = None
    steam_pressure_ok: bool = True
    coal_rate_per_mt: Optional[float] = None
    coal_gcv: Optional[float] = None

class DailyCoalSteamOut(DailyCoalSteamCreate):
    id: int
    report_date: str  # change this line to:
    report_date: date  # ← use date type instead of str
    total_coal_consumed: Optional[float]
    closing_stock: Optional[float]
    steam_sep_consumed: Optional[float]
    steam_refl_consumed: Optional[float]
    total_steam: Optional[float]
    cs_ratio: Optional[float]
    status: str
    class Config:
        from_attributes = True

# --- Power Consumption ---
class PowerConsumptionCreate(BaseModel):
    reading_date: str
    sep_units: float = 0
    prep_units: float = 0
    solar_units: float = 0
    silo_units: float = 0
    doc_units: float = 0
    dsilo_units: float = 0
    acm_units: float = 0
    boiler_units: float = 0
    chp_units: float = 0
    dm_units: float = 0
    ug_tank_units: float = 0
    refinery_units: float = 0
    etp_units: float = 0
    packing_units: float = 0
    admin_units: float = 0
    dg_units: float = 0
    msedcl_units: float = 0
    power_kvah: float = 0
    power_factor: float = 0
    diesel_opening_stock: float = 0
    diesel_received: float = 0
    diesel_consumed: float = 0
    dg_generated_units: float = 0
    dg_reason: Optional[str] = None
    voltage_r_morning: Optional[float] = None
    voltage_y_morning: Optional[float] = None
    voltage_b_morning: Optional[float] = None
    voltage_r_evening: Optional[float] = None
    voltage_y_evening: Optional[float] = None
    voltage_b_evening: Optional[float] = None