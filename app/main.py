from fastapi.responses import StreamingResponse
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from io import BytesIO
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import engine, get_db, Base
from app import models, schemas, auth

# Create all tables
# Tables already created in Supabase directly
# Base.metadata.create_all(bind=engine)

# Replace with this safe formatter:
from datetime import date, datetime

def safe_date_str(val):
    if val is None:
        return ''
    if isinstance(val, (date, datetime)):
        return val.strftime("%d/%m/%Y")
    # Handle Excel serial number
    if isinstance(val, (int, float)):
        from datetime import timedelta
        base = datetime(1899, 12, 30)
        return (base + timedelta(days=int(val))).strftime("%d/%m/%Y")
    # String
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        return str(val)

app = FastAPI(title="Shalimar Plant Ops", version="1.0.0")

# CORS — allow React frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://shalimar-ops-slxa.vercel.app",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── AUTH ────────────────────────────────────────────────

@app.post("/auth/login", response_model=schemas.Token)
def login(request: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == request.username).first()
    if not user or not auth.verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong username or password")
    token = auth.create_access_token({"sub": user.username})
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "department": user.department,
        "name": user.name
    }

@app.post("/auth/create-user", response_model=schemas.UserOut)
def create_user(
    user_data: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("hod"))
):
    existing = db.query(models.User).filter(models.User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    user = models.User(
        name=user_data.name,
        username=user_data.username,
        password_hash=auth.hash_password(user_data.password),
        role=user_data.role,
        department=user_data.department,
        shift=user_data.shift,
        phone=user_data.phone
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.get("/auth/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

# ─── BOILER LOG ──────────────────────────────────────────

@app.post("/boiler-log", response_model=schemas.BoilerLogOut)
def submit_boiler_log(
    entry: schemas.BoilerLogCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("operator", "assistant", "hod"))
):
    # Check duplicate
    existing = db.query(models.BoilerLogEntry).filter(
        models.BoilerLogEntry.shift == entry.shift,
        models.BoilerLogEntry.log_date == str(entry.log_date),
        models.BoilerLogEntry.log_time == str(entry.log_time)
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail={"message": f"Entry already exists for Shift {entry.shift} at {entry.log_time}", "existing_id": existing.id}
        )
        
    # FIX 1: Indented properly
    warnings = []
    if entry.steam_pressure and not (6 <= entry.steam_pressure <= 12):
        warnings.append(f"Steam pressure {entry.steam_pressure} outside safe range 6-12 KG/CM")
    if entry.drum_water_level and not (60 <= entry.drum_water_level <= 90):
        warnings.append(f"Drum water level {entry.drum_water_level}% outside safe range 60-90%")
    if entry.flue_gas_temp and entry.flue_gas_temp > 200:
        warnings.append(f"Flue gas temp {entry.flue_gas_temp}°C too high (max 200°C)")

    log = models.BoilerLogEntry(
        user_id=current_user.id,
        shift=entry.shift,
        log_date=entry.log_date,
        log_time=entry.log_time,
        operator_name=entry.operator_name,
        steam_pressure=entry.steam_pressure,
        steam_flow_sep=entry.steam_flow_sep,
        steam_flow_refl=entry.steam_flow_refl,
        drum_water_level=entry.drum_water_level,
        bed1_top_temp=entry.bed1_top_temp,
        bed1_bottom_temp=entry.bed1_bottom_temp,
        bed2_top_temp=entry.bed2_top_temp,
        bed2_bottom_temp=entry.bed2_bottom_temp,
        flue_gas_temp=entry.flue_gas_temp,
        coal_feed_bed1_hz=entry.coal_feed_bed1_hz,
        coal_feed_bed2_hz=entry.coal_feed_bed2_hz,
        cbd_ibd_report=entry.cbd_ibd_report,
        id_fan_damper=entry.id_fan_damper,
        fd_fan1_damper=entry.fd_fan1_damper,
        fd_fan2_damper=entry.fd_fan2_damper,
        booster_fan1=entry.booster_fan1,
        booster_fan2=entry.booster_fan2,
        gag_filter_temp=entry.gag_filter_temp,
        breakdown_problem=entry.breakdown_problem,
        feed_water_temp=entry.feed_water_temp,
        fd_pressure=entry.fd_pressure,
        remarks=entry.remarks,
        status="approved"
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    # FIX 2: Indented properly and handles both Create AND Update
    if hasattr(entry, 'coal_consumed_sep') and entry.coal_consumed_sep:
        from sqlalchemy import text
        coal_date = str(entry.log_date)
        
        # Calculate all the math once
        total_coal = (entry.coal_consumed_sep or 0) + (entry.coal_consumed_refinery or 0) + getattr(entry, 'coal_thermic', 0)
        opening = getattr(entry, 'coal_opening_stock', 0) or 0
        arrival = getattr(entry, 'coal_received', 0) or 0
        closing = opening + arrival - total_coal
        
        steam_sep = (entry.steam_sep_closing or 0) - (entry.steam_sep_opening or 0)
        steam_refl = (entry.steam_refl_closing or 0) - (entry.steam_refl_opening or 0)
        total_steam = steam_sep + steam_refl
        cs = round(total_steam / total_coal, 3) if total_coal > 0 else 0

        existing_coal = db.query(models.DailyCoalSteam).filter(
            models.DailyCoalSteam.report_date == coal_date
        ).first()

        if not existing_coal:
            # CREATE a new daily report
            coal_rec = models.DailyCoalSteam(
                report_date=coal_date,
                opening_coal_stock=opening,
                coal_arrival_indian=arrival, 
                coal_arrival_imported=0,
                coal_consumed_sep=entry.coal_consumed_sep,
                coal_consumed_refinery=entry.coal_consumed_refinery,
                coal_thermic=getattr(entry, 'coal_thermic', 0),
                total_coal_consumed=round(total_coal, 3),
                closing_stock=round(closing, 3),
                steam_sep_opening=entry.steam_sep_opening,
                steam_sep_closing=entry.steam_sep_closing,
                steam_sep_consumed=steam_sep,
                steam_refl_opening=entry.steam_refl_opening,
                steam_refl_closing=entry.steam_refl_closing,
                steam_refl_consumed=steam_refl,
                total_steam=total_steam,
                cs_ratio=cs,
                feed_water_temp=entry.feed_water_temp,
                coal_bunker_pct=getattr(entry, 'coal_bunker_pct', 0),
                steam_pressure_ok=getattr(entry, 'steam_pressure_ok', True),
            )
            db.add(coal_rec)
        else:
            # UPDATE the existing report with the newest numbers
            existing_coal.total_coal_consumed = round(total_coal, 3)
            existing_coal.closing_stock = round(closing, 3)
            existing_coal.steam_sep_consumed = steam_sep
            existing_coal.steam_refl_consumed = steam_refl
            existing_coal.total_steam = total_steam
            existing_coal.cs_ratio = cs
            
            existing_coal.steam_sep_opening = entry.steam_sep_opening
            existing_coal.steam_sep_closing = entry.steam_sep_closing
            existing_coal.steam_refl_opening = entry.steam_refl_opening
            existing_coal.steam_refl_closing = entry.steam_refl_closing
            existing_coal.coal_consumed_sep = entry.coal_consumed_sep
            existing_coal.coal_consumed_refinery = entry.coal_consumed_refinery
            
        db.commit()

    return log

@app.put("/boiler-log/{log_id}/update")
def update_boiler_log(
    log_id: int,
    entry: schemas.BoilerLogCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("operator", "assistant", "hod"))
):
    log = db.query(models.BoilerLogEntry).filter(models.BoilerLogEntry.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Entry not found")
    for field, value in entry.dict().items():
        setattr(log, field, value)
    db.commit()
    db.refresh(log)
    return log

@app.get("/boiler-log/today")
def get_todays_logs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    today = datetime.now().strftime("%Y-%m-%d")
    logs = db.query(models.BoilerLogEntry).filter(
        models.BoilerLogEntry.log_date == today
    ).order_by(models.BoilerLogEntry.id.desc()).limit(20).all()
    return logs

@app.get("/boiler-log/pending")
def get_pending_logs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("hod"))
):
    logs = db.query(models.BoilerLogEntry).filter(
        models.BoilerLogEntry.status == "pending"
    ).all()
    return logs

@app.put("/boiler-log/{log_id}/approve")
def approve_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("hod"))
):
    log = db.query(models.BoilerLogEntry).filter(models.BoilerLogEntry.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log entry not found")
    log.status = "approved"
    log.approved_by = current_user.id
    log.approved_at = datetime.utcnow()
    db.commit()
    return {"message": "Approved", "id": log_id}

@app.put("/boiler-log/{log_id}/reject")
def reject_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("hod"))
):
    log = db.query(models.BoilerLogEntry).filter(models.BoilerLogEntry.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log entry not found")
    log.status = "rejected"
    db.commit()
    return {"message": "Rejected", "id": log_id}

# ─── DAILY COAL & STEAM ──────────────────────────────────

@app.post("/daily-report", response_model=schemas.DailyCoalSteamOut)
def submit_daily_report(
    data: schemas.DailyCoalSteamCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("hod", "operator"))
):
    # Auto-calculate all derived fields
    total_coal = data.coal_consumed_sep + data.coal_consumed_refinery + data.coal_thermic
    closing = data.opening_coal_stock + data.coal_arrival_indian + data.coal_arrival_imported - total_coal
    steam_sep = data.steam_sep_closing - data.steam_sep_opening
    steam_refl = data.steam_refl_closing - data.steam_refl_opening
    total_steam = steam_sep + steam_refl
    cs_ratio = round(total_steam / total_coal, 3) if total_coal > 0 else 0

    # Check if report for this date already exists — update it
    existing = db.query(models.DailyCoalSteam).filter(
        models.DailyCoalSteam.report_date == data.report_date
    ).first()

    if existing:
        existing.opening_coal_stock = data.opening_coal_stock
        existing.coal_arrival_indian = data.coal_arrival_indian
        existing.coal_arrival_imported = data.coal_arrival_imported
        existing.coal_consumed_sep = data.coal_consumed_sep
        existing.coal_consumed_refinery = data.coal_consumed_refinery
        existing.coal_thermic = data.coal_thermic
        existing.total_coal_consumed = round(total_coal, 3)
        existing.closing_stock = round(closing, 3)
        existing.steam_sep_opening = data.steam_sep_opening
        existing.steam_sep_closing = data.steam_sep_closing
        existing.steam_sep_consumed = steam_sep
        existing.steam_refl_opening = data.steam_refl_opening
        existing.steam_refl_closing = data.steam_refl_closing
        existing.steam_refl_consumed = steam_refl
        existing.total_steam = total_steam
        existing.cs_ratio = cs_ratio
        existing.feed_water_temp = data.feed_water_temp
        existing.coal_bunker_pct = data.coal_bunker_pct
        existing.steam_pressure_ok = data.steam_pressure_ok
        existing.coal_rate_per_mt = data.coal_rate_per_mt
        existing.coal_gcv = data.coal_gcv
        db.commit()
        db.refresh(existing)
        return existing

    report = models.DailyCoalSteam(
        report_date=data.report_date,
        opening_coal_stock=data.opening_coal_stock,
        coal_arrival_indian=data.coal_arrival_indian,
        coal_arrival_imported=data.coal_arrival_imported,
        coal_consumed_sep=data.coal_consumed_sep,
        coal_consumed_refinery=data.coal_consumed_refinery,
        coal_thermic=data.coal_thermic,
        total_coal_consumed=round(total_coal, 3),
        closing_stock=round(closing, 3),
        steam_sep_opening=data.steam_sep_opening,
        steam_sep_closing=data.steam_sep_closing,
        steam_sep_consumed=steam_sep,
        steam_refl_opening=data.steam_refl_opening,
        steam_refl_closing=data.steam_refl_closing,
        steam_refl_consumed=steam_refl,
        total_steam=total_steam,
        cs_ratio=cs_ratio,
        feed_water_temp=data.feed_water_temp,
        coal_bunker_pct=data.coal_bunker_pct,
        steam_pressure_ok=data.steam_pressure_ok,
        coal_rate_per_mt=data.coal_rate_per_mt,
        coal_gcv=data.coal_gcv
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report

@app.get("/daily-report/{date}")
def get_daily_report(
    date: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    report = db.query(models.DailyCoalSteam).filter(
        models.DailyCoalSteam.report_date == date
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="No report found for this date")
    return report

@app.post("/power-consumption")
def submit_power(
    data: schemas.PowerConsumptionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("hod", "operator", "assistant"))
):
    from sqlalchemy import text
    date_str = str(data.reading_date)

    existing = db.execute(text(
        "SELECT id FROM power_consumption WHERE reading_date::text = :d LIMIT 1"
    ), {"d": date_str}).mappings().fetchone()

    params = {
        "d": date_str, "uid": str(current_user.id),
        "sep": data.sep_units or 0, "prep": data.prep_units or 0,
        "solar": data.solar_units or 0, "silo": data.silo_units or 0,
        "doc": data.doc_units or 0, "dsilo": data.dsilo_units or 0,
        "acm": data.acm_units or 0, "boiler": data.boiler_units or 0,
        "chp": data.chp_units or 0, "dm": data.dm_units or 0,
        "ug": data.ug_tank_units or 0, "ref": data.refinery_units or 0,
        "etp": data.etp_units or 0, "pack": data.packing_units or 0,
        "admin": data.admin_units or 0, "dg": data.dg_units or 0,
        "msedcl": data.msedcl_units or 0,
        "kvah": data.power_kvah or 0, "pf": data.power_factor or 0,
        "d_open": data.diesel_opening_stock or 0,
        "d_recv": data.diesel_received or 0,
        "d_cons": data.diesel_consumed or 0,
        "dg_gen": data.dg_generated_units or 0,
        "dg_r": data.dg_reason or '',
    }

    if existing:
        db.execute(text("""
            UPDATE power_consumption SET
            sep_units=:sep, prep_units=:prep, solar_units=:solar,
            silo_units=:silo, doc_units=:doc, dsilo_units=:dsilo,
            acm_units=:acm, boiler_units=:boiler, chp_units=:chp,
            dm_units=:dm, ug_tank_units=:ug, refinery_units=:ref,
            etp_units=:etp, packing_units=:pack, admin_units=:admin,
            dg_units=:dg, msedcl_units=:msedcl, power_kvah=:kvah,
            power_factor=:pf, diesel_opening_stock=:d_open,
            diesel_received=:d_recv, diesel_consumed=:d_cons,
            dg_generated_units=:dg_gen, dg_reason=:dg_r
            WHERE reading_date::text = :d
        """), params)
        db.commit()
        return {"message": "Power report updated", "id": existing['id']}

    result = db.execute(text("""
        INSERT INTO power_consumption (
            reading_date, entered_by,
            sep_units, prep_units, solar_units, silo_units, doc_units,
            dsilo_units, acm_units, boiler_units, chp_units, dm_units,
            ug_tank_units, refinery_units, etp_units, packing_units,
            admin_units, dg_units, msedcl_units, power_kvah, power_factor,
            diesel_opening_stock, diesel_received, diesel_consumed,
            dg_generated_units, dg_reason
        ) VALUES (
            :d::date, :uid::uuid,
            :sep, :prep, :solar, :silo, :doc,
            :dsilo, :acm, :boiler, :chp, :dm,
            :ug, :ref, :etp, :pack,
            :admin, :dg, :msedcl, :kvah, :pf,
            :d_open, :d_recv, :d_cons, :dg_gen, :dg_r
        ) RETURNING id
    """), params)
    db.commit()
    new_id = result.fetchone()[0]
    return {"message": "Power report submitted", "id": new_id}

@app.get("/power-consumption/today")
def get_todays_power(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    from sqlalchemy import text
    from datetime import date
    today = date.today().isoformat()
    results = db.execute(text(
        "SELECT * FROM power_consumption WHERE reading_date::text = :today ORDER BY id ASC"
    ), {"today": today}).mappings().all()
    return [dict(r) for r in results]

@app.get("/export/daily-boiler/{date}")
def export_daily_boiler_excel(
    date: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    from sqlalchemy import text
    
    # Pull coal/steam from BOTH tables — boiler_log_entries first, fallback to daily_coal_steam
    coal_result = db.execute(text(
        "SELECT * FROM daily_coal_steam WHERE report_date::text = :date LIMIT 1"
    ), {"date": date}).mappings().fetchone()
    report = dict(coal_result) if coal_result else None
    
    # If not in boiler_log_entries, check daily_coal_steam
    if not coal_result:
        coal_result = db.execute(text(
            "SELECT * FROM daily_coal_steam WHERE report_date::text = :date LIMIT 1"
        ), {"date": date}).mappings().fetchone()
    
    report = dict(coal_result) if coal_result else None
    
    logs = db.execute(text(
        "SELECT * FROM boiler_log_entries WHERE log_date::text = :date "
        "ORDER BY log_time ASC"
    ), {"date": date}).mappings().all()
    logs = [dict(r) for r in logs]

    # ── AUTO-CALCULATE from boiler entries ──────────────────
    sep_flows = [l['steam_flow_sep'] for l in logs if l.get('steam_flow_sep')]
    refl_flows = [l['steam_flow_refl'] for l in logs if l.get('steam_flow_refl')]
    feed_temps = [l['feed_water_temp'] for l in logs if l.get('feed_water_temp')]
    bed1_hz = [l['coal_feed_bed1_hz'] for l in logs if l.get('coal_feed_bed1_hz')]
    bed2_hz = [l['coal_feed_bed2_hz'] for l in logs if l.get('coal_feed_bed2_hz')]

    sep_opening = sep_flows[0] if sep_flows else None
    sep_closing = sep_flows[-1] if sep_flows else None
    refl_opening = refl_flows[0] if refl_flows else None
    refl_closing = refl_flows[-1] if refl_flows else None

    sep_consumed = (sep_closing - sep_opening) if (sep_closing and sep_opening) else None
    refl_consumed = (refl_closing - refl_opening) if (refl_closing and refl_opening) else None
    total_steam = (sep_consumed + refl_consumed) if (sep_consumed and refl_consumed) else None

    avg_feed_water = round(sum(feed_temps) / len(feed_temps), 1) if feed_temps else None

    all_hz = bed1_hz + bed2_hz
    avg_feeding = round(sum(all_hz) / len(all_hz), 2) if all_hz else None

    # Coal for Steam = avg_feeding * 60 * 24 (in KG, stays as KG for display)
    coal_for_steam = round(avg_feeding * 60 * 24) if avg_feeding else None

    # Get manual coal data from report (or from boiler entries)
    opening_stock = report.get('opening_coal_stock') if report else None
    arrival_ind = report.get('coal_arrival_indian') if report else None
    arrival_imp = report.get('coal_arrival_imported', 0) if report else 0
    coal_thermic = report.get('coal_thermic', 0) if report else 0
    coal_bunker = report.get('coal_bunker_pct') if report else None
    steam_pressure_ok = report.get('steam_pressure_ok', True) if report else True

    # Calculate coal SEP and REFL
    # E8: Coal SEP = steam_sep_consumed (KG) / coal_for_steam * coal_total... 
    # Actually from father's formula: Coal consumed SEP is calculated differently
    # Using the C/S ratio approach: coal_sep_mt = sep_consumed / (cs_ratio * 1000)
    cs_ratio = report.get('cs_ratio') if report else None
    
    # If we have report data, use it. Otherwise calculate from entries
    coal_consumed_sep = report.get('coal_consumed_sep') if report else None
    coal_consumed_refinery = report.get('coal_consumed_refinery') if report else None
    total_coal = report.get('total_coal_consumed') if report else None
    closing_stock = report.get('closing_stock') if report else None

    # If no cs_ratio in report but we have total_steam and coal data
    if not cs_ratio and total_steam and total_coal and total_coal > 0:
        cs_ratio = round(total_steam / (total_coal * 1000), 3)  # steam KG / coal MT*1000

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    # Styles matching father's file exactly
    bold = Font(bold=True)
    bold_blue = Font(bold=True, color="1F3864")
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    thin = Side(style="thin")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    yellow_fill = PatternFill("solid", fgColor="FFFF00")
    blue_fill = PatternFill("solid", fgColor="BDD7EE")
    green_fill = PatternFill("solid", fgColor="E2EFDA")

    def cell(row, col, value, font=None, fill=None, align=None, b=None):
        c = ws.cell(row=row, column=col, value=value)
        if font: c.font = font
        if fill: c.fill = fill
        if align: c.alignment = align
        if b: c.border = b
        return c

    # Parse date for display
    from datetime import datetime

    date_display = safe_date_str(date)

    try:
        d = datetime.strptime(date, "%Y-%m-%d")
        date_display = d.strftime("%d/%m/%Y")
        month_year = d.strftime("%b. - %Y").upper()
    except:
        date_display = date
        month_year = date

    # ROW 1 - Title
    ws.merge_cells("B1:J1")
    cell(1, 2, f"DAILY STATUS REPORT- {month_year}", Font(bold=True, size=12), align=center)

    # ROW 2 - Date
    ws.merge_cells("B2:J2")
    cell(2, 2, f"DATE : {date_display}", Font(bold=True, size=11), align=center)

    # ROW 3 - Section title
    ws.merge_cells("B3:J3")
    cell(3, 2, "COAL COSUMPTION AND STOCK SHEET", Font(bold=True), blue_fill, center, border)

    # ROW 4 - Coal headers (matching father's exact column names)
    headers_coal = [
        "OPENING STOCK OF COAL IN MT",
        "ARRIVAL COAL IN MT (IND)",
        "ARRIVAL COAL IN MT (IMP)",
        "COAL CONSUMPTION IN MT (SEP)",
        "COAL CONSUMPTION IN MT (REFINERY)",
        "COAL ISSUE TO THERMIC BLR IN MT",
        "TOTAL COAL CONSUMPTION IN MT",
        "CLOSING STOCK IN MT",
        "REMARKS"
    ]
    for i, h in enumerate(headers_coal, 2):
        cell(4, i, h, bold, blue_fill, center, border)

    # ROW 5 - Coal values
    if report:
        coal_vals = [
            report.get('opening_coal_stock'), report.get('coal_arrival_indian'),
        report.get('coal_arrival_imported'), report.get('coal_consumed_sep'),
        report.get('coal_consumed_refinery'), report.get('coal_thermic'),
        report.get('total_coal_consumed'), report.get('closing_stock'), ""
    ]
        for i, v in enumerate(coal_vals, 2):
            cell(5, i, v, align=center, b=border)

    ws.append([])  # row 6 empty

# ROW 7 - Coal bunker (Fixed with all borders)
    cell(7, 2, "PERTICULAR", bold, blue_fill, left, border)
    cell(7, 3, None, b=border) # Border for empty C
    cell(7, 4, "COAL IN BUNKER (%)", bold, blue_fill, center, border)
    cell(7, 5, "REMARKS", bold, blue_fill, center, border)
    cell(7, 6, None, b=border) # Border for empty F
    cell(7, 7, None, b=border) # Border for empty G
    cell(7, 8, None, b=border) # Border for empty H
    cell(7, 9, "COAL FOR STEAM", bold, align=center, b=border)
    cell(7, 10, None, b=border) # Border for empty J

    # ROW 8 - Data
    cell(8, 2, "COAL BUNKER STATUS", bold, align=left, b=border)
    cell(8, 3, None, b=border)
    cell(8, 4, coal_bunker, align=center, b=border)
    cell(8, 5, None, b=border)
    cell(8, 6, None, b=border)
    cell(8, 7, None, b=border)
    cell(8, 8, None, b=border)
    cell(8, 9, coal_for_steam, Font(bold=True), align=center, b=border)

    # ROW 9 - Pressure
    cell(9, 2, "STEAM PRESSURE PROBLEM", bold, align=left, b=border)
    cell(9, 3, None, b=border)
    sp_val = "NO" if steam_pressure_ok else "YES ⚠️"
    sp_fill = green_fill if steam_pressure_ok else PatternFill("solid", fgColor="FADBD8")
    cell(9, 4, sp_val, Font(bold=True), sp_fill, center, border)
    cell(9, 5, None, b=border)

    ws.append([])  # row 10 empty

    # ROW 11 - Steam SEP header
    ws.merge_cells("B11:J11")
    cell(11, 2, "STEAM FLOW METER READING (SEP)", Font(bold=True), blue_fill, center, border)

    steam_headers = [
        "OPENING READING IN KG", "CLOSING READING IN KG", "",
        "STEAM COSUMPTION IN KG", "", "FEED WATER TEMP. (°C)", "",
        "AVERAGE FEEDING", ""
    ]
    for i, h in enumerate(steam_headers, 2):
        if h:
            cell(12, i, h, bold, blue_fill, center, border)
        else:
            cell(12, i, "", None, blue_fill, None, border)

    # FIXED ROW 13 - Shifts data to Col 7 (G)
    if report:
        cell(13, 2, sep_opening, align=center, b=border)
        cell(13, 3, sep_closing, align=center, b=border)
        cell(13, 4, None, align=center, b=border)
        cell(13, 5, sep_consumed, Font(bold=True), yellow_fill, center, border)
        cell(13, 6, None, align=center, b=border)
        cell(13, 7, avg_feed_water, align=center, b=border)
        cell(13, 8, None, align=center, b=border)
        cell(13, 9, avg_feeding, align=center, b=border)

    ws.append([])  # row 14

    # ROW 15 - Steam REFL header 
    ws.merge_cells("B15:J15")
    cell(15, 2, "STEAM FLOW METER READING (REFINERY)", Font(bold=True), blue_fill, center, border)

    refl_headers = [
        "OPENING READING IN KG", "CLOSING READING IN KG", "",
        "STEAM COSUMPTION IN KG", "", "TOTAL STEAM", "",
        "STEAM TO COAL RATIO", ""
    ]
    for i, h in enumerate(refl_headers, 2):
        if h:
            cell(16, i, h, bold, blue_fill, center, border)
        else:
            cell(16, i, "", None, blue_fill, None, border)

    # FIXED ROW 17 - Shifts Total Steam to 7 (G) and CS Ratio to 9 (I)
    if report:
        cell(17, 2, refl_opening, align=center, b=border)
        cell(17, 3, refl_closing, align=center, b=border)
        cell(17, 4, None, align=center, b=border)
        cell(17, 5, refl_consumed, Font(bold=True), yellow_fill, center, border)
        cell(17, 6, None, align=center, b=border)
        cell(17, 7, total_steam, Font(bold=True), yellow_fill, center, border)
        cell(17, 8, None, align=center, b=border)
        cs_val = cs_ratio or 0
        cs_fill = green_fill if (cs_val and 5.0 <= float(cs_val) <= 5.6) else PatternFill("solid", fgColor="FADBD8")
        cell(17, 9, cs_val, Font(bold=True), cs_fill, center, border)

    # Column widths matching father's layout
    col_widths = {
        'A': 4, 'B': 22, 'C': 16, 'D': 16,
        'E': 18, 'F': 16, 'G': 14, 'H': 14, 'I': 16, 'J': 12
    }
    for col, width in col_widths.items():
        ws.column_dimensions[col].width = width

    # Row heights
    for r in [4, 12, 16]:
        ws.row_dimensions[r].height = 40

    # Footer
    ws.append([])
    ws.append([])
    for _ in range(4):
        ws.append([])
    footer_row = ws.max_row
    ws.cell(footer_row, 2).value = f"Generated: {date}  |  HOD: {current_user.name}  |  Shalimar Plant Ops System"
    ws.cell(footer_row, 2).font = Font(italic=True, color="888888", size=9)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Daily_Boiler_Report_{date}.xlsx"}
    )

@app.get("/daily-report/recent")
def get_recent_coal_reports(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    from sqlalchemy import text
    results = db.execute(
        text("SELECT * FROM daily_coal_steam ORDER BY id DESC LIMIT 31")
    ).mappings().all()
    return [dict(r) for r in results]

@app.get("/power-consumption/recent")
def get_recent_power_reports(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    try:
        from sqlalchemy import text
        results = db.execute(
            text("SELECT * FROM power_consumption ORDER BY id DESC LIMIT 31")
        ).mappings().all()
        return [dict(r) for r in results]
    except Exception as e:
        return []

@app.get("/export/power-monthly/{year}/{month}")
def export_power_monthly_excel(
    year: int, month: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    import calendar
    from datetime import datetime, date
    
    # Get all power records for this month
    from sqlalchemy import text
    results = db.execute(text(
        "SELECT reading_date, "
        "SUM(sep_units) as sep_units, SUM(prep_units) as prep_units, "
        "SUM(solar_units) as solar_units, SUM(silo_units) as silo_units, "
        "SUM(doc_units) as doc_units, SUM(dsilo_units) as dsilo_units, "
        "SUM(acm_units) as acm_units, SUM(boiler_units) as boiler_units, "
        "SUM(chp_units) as chp_units, SUM(dm_units) as dm_units, "
        "SUM(ug_tank_units) as ug_tank_units, SUM(refinery_units) as refinery_units, "
        "SUM(etp_units) as etp_units, SUM(packing_units) as packing_units, "
        "SUM(admin_units) as admin_units, SUM(dg_units) as dg_units, "
        "SUM(msedcl_units) as msedcl_units, "
        "MAX(power_kvah) as power_kvah, "
        "SUM(diesel_opening_stock) as diesel_opening_stock, "
        "SUM(diesel_received) as diesel_received, "
        "SUM(diesel_consumed) as diesel_consumed, "
        "SUM(dg_generated_units) as dg_generated_units, "
        "STRING_AGG(dg_reason, '; ') as dg_reason "
        "FROM power_consumption "
        "WHERE EXTRACT(YEAR FROM reading_date) = :year "
        "AND EXTRACT(MONTH FROM reading_date) = :month "
        "GROUP BY reading_date "
        "ORDER BY reading_date ASC"
    ), {"year": year, "month": month}).mappings().all()
    records = [dict(r) for r in results]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    bold = Font(bold=True)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Side(style="thin")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    blue_fill = PatternFill("solid", fgColor="BDD7EE")
    yellow_fill = PatternFill("solid", fgColor="FFFF00")
    light_blue = PatternFill("solid", fgColor="DEEAF1")

    month_name = datetime(year, month, 1).strftime("%b").upper()
    num_days = calendar.monthrange(year, month)[1]

    # ROW 1: Title
    days_in_month = len(records) if records else num_days
    total_cols = days_in_month + 3  # SR + Name + days + TOTAL
    last_col_letter = openpyxl.utils.get_column_letter(total_cols)
    ws.merge_cells(f"A1:{last_col_letter}1")
    ws["A1"] = f"POWER CONSUMPTION DAILY REPORT - {month_name}. -{year}"
    ws["A1"].font = Font(bold=True, size=12)
    ws["A1"].alignment = center

    # ROW 2: DATE header row
    ws.cell(2, 1, "DATE").font = bold
    ws.cell(2, 1).fill = blue_fill
    ws.cell(2, 1).border = border
    ws.cell(2, 1).alignment = center
    ws.cell(2, 2).fill = blue_fill
    ws.cell(2, 2).border = border

    for i, rec in enumerate(records):
        col = i + 3
        date_val = rec.get('reading_date')
        date_str = safe_date_str(rec.get('reading_date'))
        c = ws.cell(2, col, date_str)
        c.font = bold; c.fill = blue_fill; c.border = border; c.alignment = center

    # TOTAL column
    total_col = len(records) + 3
    ws.cell(2, total_col, "TOTAL").font = bold
    ws.cell(2, total_col).fill = yellow_fill
    ws.cell(2, total_col).border = border
    ws.cell(2, total_col).alignment = center

    # ROW 3: SR.NO. / SECTION NAME / UNIT (KWH) headers
    ws.cell(3, 1, "SR.NO.").font = bold; ws.cell(3, 1).fill = blue_fill; ws.cell(3, 1).border = border; ws.cell(3, 1).alignment = center
    ws.cell(3, 2, "SECTION NAME").font = bold; ws.cell(3, 2).fill = blue_fill; ws.cell(3, 2).border = border; ws.cell(3, 2).alignment = center
    
    for i in range(len(records)):
        col = i + 3
        ws.cell(3, col, "UNIT (KWH)").font = bold
        ws.cell(3, col).fill = blue_fill
        ws.cell(3, col).border = border
        ws.cell(3, col).alignment = center

    ws.cell(3, total_col, "TOTAL").font = bold
    ws.cell(3, total_col).fill = yellow_fill
    ws.cell(3, total_col).border = border
    ws.cell(3, total_col).alignment = center

    # Data rows start
    data_rows_start = 4

    # Section groups with subtotals
    # Define sections with group markers
    SECTION_GROUPS = [
        # (SR, Name, Field, is_subtotal)
        ("1", "SEP", "sep_units", False),
        ("2", "PREP", "prep_units", False),
        ("", "SOLAR", "solar_units", False),
        ("3", "SILO", "silo_units", False),
        ("4", "DOC", "doc_units", False),
        ("5", "D-SILO", "dsilo_units", False),
        ("", "SUBTOTAL (1-5)", None, True),   # Subtotal 1
        ("6", "ACM/ SOYA CHUNKS", "acm_units", False),
        ("7", "BOILER", "boiler_units", False),
        ("8", "CHP", "chp_units", False),
        ("9", "DM PLANT", "dm_units", False), 
        ("", "UG TANK", "ug_tank_units", False),
        ("", "SUBTOTAL (6-9)", None, True),   # Subtotal 2
        ("10", "REFINERY", "refinery_units", False),
        ("11", "ETP/ACID/MVR", "etp_units", False),
        ("12", "PACKING", "packing_units", False),
        ("", "SUBTOTAL (10-12)", None, True), # Subtotal 3
        ("13", "ADMIN", "admin_units", False),
        ("15", "MISCELLENIOUS", None, False),
        ("", "SUBTOTAL (13-15)", None, True), # Subtotal 4
        ("16", "DG SET UNIT", "dg_units", False),
    ]

    # Track group subtotal rows for formula ranges
    group_data_rows = []  # (start_row, end_row) for each group
    current_group_start = data_rows_start
    current_row = data_rows_start

    for sr, name, field, is_subtotal in SECTION_GROUPS:
        # ALWAYS set border for Col 1 and 2 first
        ws.cell(current_row, 1).border = border
        ws.cell(current_row, 2).border = border
        
        if is_subtotal:
            # STYLE THE SUBTOTAL ROW
            ws.cell(current_row, 2, name).font = Font(bold=True)
            ws.cell(current_row, 2).fill = light_blue
            
            for i, rec in enumerate(records):
                col = i + 3
                col_letter = openpyxl.utils.get_column_letter(col)
                # Formula: Sum from current_group_start to row right above this one
                ws.cell(current_row, col, f"=SUM({openpyxl.utils.get_column_letter(col)}{current_group_start}:{openpyxl.utils.get_column_letter(col)}{current_row-1})")
                ws.cell(current_row, col).fill = light_blue
                ws.cell(current_row, col).font = Font(bold=True)
                ws.cell(current_row, col).border = border
                ws.cell(current_row, col).alignment = center
            
            # Total column for the subtotal row
            row_start_letter = openpyxl.utils.get_column_letter(3)
            row_end_letter = openpyxl.utils.get_column_letter(2 + len(records))
            ws.cell(current_row, total_col, f"=SUM({row_start_letter}{current_row}:{row_end_letter}{current_row})")
            ws.cell(current_row, total_col).fill = light_blue
            ws.cell(current_row, total_col).font = Font(bold=True)
            ws.cell(current_row, total_col).border = border
            
            current_group_start = current_row + 1 # Next group starts after subtotal
            current_row += 1
            continue

        # --- NORMAL SECTION ROW ---
        ws.cell(current_row, 1, sr).alignment = center
        ws.cell(current_row, 2, name).font = Font(bold=True) if sr else Font()

        for i, rec in enumerate(records):
            val = rec.get(field, 0) or 0 if field else 0
            c = ws.cell(current_row, i + 3, val)
            c.border = border
            c.alignment = center
            
        # Total column for normal row
        fc = openpyxl.utils.get_column_letter(3)
        lc = openpyxl.utils.get_column_letter(2 + len(records))
        ws.cell(current_row, total_col, f"=SUM({fc}{current_row}:{lc}{current_row})")
        ws.cell(current_row, total_col).border = border
        ws.cell(current_row, total_col).alignment = center
        current_row += 1

    # Summary rows — with borders and yellow fill
    summary_rows = [
        ("TOTAL UNIT WITH SOLAR GEN. UNIT", "total_with_solar"),
        ("TOTAL SECTION UNIT WITHOUT SOLAR UNIT", "total_without_solar"),
        ("MSEDCL UNIT (KWH)", "msedcl"),
        ("POWER (KVAH)", "kvah"),
        ("POWER FACTOR", "pf"),
    ]

    for label, key in summary_rows:
        ws.cell(current_row, 1).border = border  # Fix border for Col A
        c2 = ws.cell(current_row, 2, label)
        c2.font = Font(bold=True)
        c2.border = border
        
        for i, rec in enumerate(records):
            col = i + 3
            if key == "total_with_solar":
                # Only sum real data fields (not subtotal markers)
                val = sum((rec.get(f[2], 0) or 0) for f in SECTION_GROUPS if f[2] and not f[3])
            elif key == "total_without_solar":
                val = sum((rec.get(f[2], 0) or 0) for f in SECTION_GROUPS if f[2] and not f[3] and f[2] != 'solar_units')
            elif key == "msedcl":
                val = rec.get('msedcl_units', 0) or 0
            elif key == "kvah":
                val = rec.get('power_kvah', 0) or 0
            elif key == "pf":
                kwh = rec.get('msedcl_units', 0) or 0
                kvah = rec.get('power_kvah', 0) or 0
                val = round(kwh/kvah, 4) if kvah and kvah > 0 else 0
            else:
                val = 0
                
            c3 = ws.cell(current_row, col, val)
            c3.fill = yellow_fill
            c3.font = Font(bold=True)
            c3.border = border
            c3.alignment = center
        
        # Summary Total Column
        if key != "pf":
            fc = openpyxl.utils.get_column_letter(3)
            lc = openpyxl.utils.get_column_letter(2 + len(records))
            ws.cell(current_row, total_col, f"=SUM({fc}{current_row}:{lc}{current_row})")
            
        ws.cell(current_row, total_col).fill = yellow_fill
        ws.cell(current_row, total_col).font = Font(bold=True)
        ws.cell(current_row, total_col).border = border
        current_row += 1

    # Column widths
    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 25
    for i in range(len(records)):
        col_letter = openpyxl.utils.get_column_letter(i + 3)
        ws.column_dimensions[col_letter].width = 14
    ws.column_dimensions[openpyxl.utils.get_column_letter(total_col)].width = 14

    # Row heights
    ws.row_dimensions[1].height = 25
    ws.row_dimensions[2].height = 20
    ws.row_dimensions[3].height = 30

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Power_Monthly_Report_{year}_{month}.xlsx"}
    )


@app.get("/export/monthly-coal/{year}/{month}")
def export_monthly_coal_excel(
    year: int, month: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    import calendar
    from datetime import date, datetime
    from sqlalchemy import text          # 👈 FIX 1: Clears the "text is not defined" error
    from types import SimpleNamespace    # 👈 Fixes object dot-notation (r.report_date)

    month_name = datetime(year, month, 1).strftime("%b").upper()
     # Try daily_coal_steam first
    prefix = f"{year}-{str(month).zfill(2)}%"
    results = db.execute(text(
        "SELECT * FROM daily_coal_steam "
        "WHERE report_date LIKE :prefix "
        "ORDER BY report_date ASC"
        ), {"prefix": prefix}).mappings().all()
    reports = [SimpleNamespace(**dict(r)) for r in results]
    
    # Also check boiler_log_entries for coal data merged there
    if not reports:
        results2 = db.execute(text(
            "SELECT DISTINCT ON (log_date) log_date as report_date, "
            "coal_opening_stock as opening_coal_stock, "
            "coal_arrival_indian, coal_arrival_imported, "
            "coal_consumed_sep, coal_consumed_refinery, coal_thermic, "
            "total_coal_consumed, closing_stock, "
            "steam_sep_opening, steam_sep_closing, steam_sep_consumed, "
            "steam_refl_opening, steam_refl_closing, steam_refl_consumed, "
            "total_steam, cs_ratio, feed_water_temp, coal_bunker_pct "
            "FROM boiler_log_entries "
            "WHERE log_date LIKE :prefix "
            "AND coal_opening_stock IS NOT NULL "
            "ORDER BY log_date ASC"
        ), {"prefix": prefix}).mappings().all()
        
        reports = [SimpleNamespace(**dict(r)) for r in results2]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    bold = Font(bold=True)
    center = Alignment(horizontal="center", vertical="center")
    thin = Side(style="thin")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    blue_fill = PatternFill("solid", fgColor="BDD7EE")
    yellow_fill = PatternFill("solid", fgColor="FFFF00")

    # Header rows exactly matching father's file
    ws["A1"] = "SHALIMAR NUTRIENTS PRIVATE LIMITED"
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = "BOILER SECTION"
    ws["A2"].font = bold
    ws["A3"] = f"COAL COSUMPTION AND STOCK SHEET {month_name}. -{year}"
    ws["A3"].font = Font(bold=True, size=11)
    ws.merge_cells("A3:O3")
    ws["A3"].alignment = center

    # Column headers exactly matching father's file
    col_headers = [
        "DATE", "OPENING STOCK OF COAL IN MT", "ARRIVAL COAL IN MT",
        "COAL CONSUMPTION IN MT (SEP)", "CLOSING STOCK",
        "COAL CONSUMPTION IN MT (REF.)", "TOTAL COAL FOR STEAM PRODUCTION",
        "COAL CONSUMPTION IN THERMIC BOILER IN MT",
        "COAL CONSUMPTION IN MT (TOTAL)", "CLOSING STOCK IN MT",
        "STEAM PRODUCTION IN KG (SEP)", "STEAM PRODUCTION IN KG (REF.)",
        "TOTAL STEAM PRODUCTION IN KG", "C/S RATIO", "FEED WATER TEMP (°C)"
    ]

    for i, h in enumerate(col_headers, 1):
        c = ws.cell(4, i, h)
        c.font = bold; c.fill = blue_fill
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = border
    ws.row_dimensions[4].height = 50

    # Data rows
    total_coal_sum = 0; total_steam_sum = 0
    for r in reports:
        row_num = ws.max_row + 1
        date_str = safe_date_str(getattr(r, 'report_date', getattr(r, 'log_date', None)))
        total_coal = r.total_coal_consumed or 0
        total_steam = r.total_steam or 0
        total_coal_sum += total_coal; total_steam_sum += total_steam

        row_data = [
            date_str, r.opening_coal_stock,
            (r.coal_arrival_indian or 0) + (r.coal_arrival_imported or 0),
            r.coal_consumed_sep, r.closing_stock,
            r.coal_consumed_refinery,
            (r.coal_consumed_sep or 0) + (r.coal_consumed_refinery or 0),
            r.coal_thermic, total_coal, r.closing_stock,
            r.steam_sep_consumed, r.steam_refl_consumed,
            total_steam, r.cs_ratio, r.feed_water_temp
        ]
        for i, val in enumerate(row_data, 1):
            c = ws.cell(row_num, i, val)
            c.border = border; c.alignment = center
            # Highlight C/S ratio
            if i == 14 and val:
                if 5.0 <= float(val) <= 5.6:
                    c.fill = PatternFill("solid", fgColor="E2EFDA")
                else:
                    c.fill = PatternFill("solid", fgColor="FADBD8")

    # Totals row
    total_row = ws.max_row + 1
    ws.cell(total_row, 1, "TOTAL").font = Font(bold=True)
    ws.cell(total_row, 9, round(total_coal_sum, 3)).font = Font(bold=True)
    ws.cell(total_row, 9).fill = yellow_fill
    ws.cell(total_row, 13, total_steam_sum).font = Font(bold=True)
    ws.cell(total_row, 13).fill = yellow_fill
    avg_cs = round(total_steam_sum / total_coal_sum, 3) if total_coal_sum > 0 else 0
    ws.cell(total_row, 14, avg_cs).font = Font(bold=True)
    ws.cell(total_row, 14).fill = yellow_fill

    # Column widths
    widths = [12, 18, 14, 18, 14, 18, 18, 18, 16, 14, 16, 16, 16, 12, 14]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    buffer = BytesIO()
    wb.save(buffer); buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Coal_Steam_{month_name}_{year}.xlsx"}
    )

@app.get("/history/boiler")
def history_boiler(year: int, month: int, db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)):
    from sqlalchemy import text
    prefix = f"{year}-{str(month).zfill(2)}%"
    results = db.execute(text(
        "SELECT * FROM boiler_log_entries WHERE log_date::text LIKE :p "
        "ORDER BY log_date ASC, log_time ASC"
    ), {"p": prefix}).mappings().all()
    return [dict(r) for r in results]

@app.get("/history/coal")
def history_coal(year: int, month: int, db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)):
    from sqlalchemy import text
    prefix = f"{year}-{str(month).zfill(2)}%"
    results = db.execute(text(
        "SELECT * FROM daily_coal_steam WHERE report_date::text LIKE :p "
        "ORDER BY report_date ASC"
    ), {"p": prefix}).mappings().all()
    return [dict(r) for r in results]

@app.get("/history/power")
def history_power(year: int, month: int, db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)):
    from sqlalchemy import text
    prefix = f"{year}-{str(month).zfill(2)}%"
    results = db.execute(text(
        "SELECT * FROM power_consumption WHERE reading_date::text LIKE :p "
        "ORDER BY reading_date ASC"
    ), {"p": prefix}).mappings().all()
    return [dict(r) for r in results]

@app.get("/daily-report/closing/{date}")
def get_prev_closing(date: str, db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)):
    from sqlalchemy import text
    from datetime import datetime, timedelta
    try:
        prev_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    except:
        return {"closing_stock": None}
    result = db.execute(text(
        "SELECT closing_stock FROM daily_coal_steam WHERE report_date::text = :d LIMIT 1"
    ), {"d": prev_date}).mappings().fetchone()
    return {"closing_stock": result['closing_stock'] if result else None, "date": prev_date}

# ─── HEALTH CHECK ─────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "Shalimar Plant Ops API is running", "version": "1.0.0"}
