from sqlalchemy import text
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
        "https://shalimar-ops-slxa.vercel.app",  # ADD THIS
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

from fastapi import HTTPException

@app.post("/power-consumption")
def submit_power(
    data: schemas.PowerConsumptionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("hod", "operator", "assistant"))
):
    try:
        from sqlalchemy import text
        date_str = str(data.reading_date)

        # 👇 Notice how EVERYTHING down to the returns is indented inside the try block
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
                CAST(:d AS DATE), CAST(:uid AS UUID),
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

    except Exception as e:
        # ✅ The except block matches the indentation of the try block!
        raise HTTPException(status_code=500, detail=str(e))

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
def export_daily_boiler_excel(date: str, db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)):
    try:
        from sqlalchemy import text
        import json

        # Try daily_entries first (new system), fallback to daily_coal_steam
        entry_result = db.execute(text(
            "SELECT * FROM daily_entries WHERE entry_date::text = :date LIMIT 1"
        ), {"date": date}).mappings().fetchone()
        
        report = None
        if entry_result:
            row = dict(entry_result)
            # Parse JSON arrays
            for field in ['feed_water_temps', 'fd_fan1_dampers', 'fd_fan2_dampers']:
                if row.get(field):
                    try: row[field] = json.loads(row[field])
                    except: row[field] = []
            report = row
            # Map daily_entries fields to what the Excel generator expects
            report['opening_coal_stock'] = row.get('opening_coal_stock')
            report['coal_arrival_indian'] = row.get('coal_arrival_indian')
            report['coal_thermic'] = row.get('coal_thermic')
            report['coal_bunker_pct'] = row.get('coal_bunker_pct')
            report['steam_pressure_ok'] = row.get('steam_pressure_ok', True)
            
            # Steam values
            sep_open = row.get('steam_sep_opening') or 0
            sep_close = row.get('steam_sep_closing') or 0
            refl_open = row.get('steam_refl_opening') or 0
            refl_close = row.get('steam_refl_closing') or 0
            
            # Feed water average
            fw = row.get('feed_water_temps', [])
            fw_vals = [x for x in fw if x is not None and x != '']
            avg_fw = round(sum(fw_vals)/len(fw_vals), 1) if fw_vals else None
            
            # FD fan averages  
            fd1 = row.get('fd_fan1_dampers', [])
            fd2 = row.get('fd_fan2_dampers', [])
            fd1_vals = [x for x in fd1 if x is not None and x != '']
            fd2_vals = [x for x in fd2 if x is not None and x != '']
            avg_fd1 = round(sum(fd1_vals)/len(fd1_vals), 2) if fd1_vals else None
            avg_fd2 = round(sum(fd2_vals)/len(fd2_vals), 2) if fd2_vals else None
            avg_feeding = avg_fd1  # use FD Fan 1 average as feeding HZ
        else:
            # Fallback to old table
            coal_result = db.execute(text(
                "SELECT * FROM daily_coal_steam WHERE report_date::text = :date LIMIT 1"
            ), {"date": date}).mappings().fetchone()
            report = dict(coal_result) if coal_result else {}
            sep_open = report.get('steam_sep_opening') or 0
            sep_close = report.get('steam_sep_closing') or 0
            refl_open = report.get('steam_refl_opening') or 0
            refl_close = report.get('steam_refl_closing') or 0
            avg_fw = report.get('avg_feed_water') or report.get('feed_water_temp')
            avg_feeding = None

        def safe_float(val, default=None):
            if val is None: return default
            try: return float(val)
            except: return default

        # Now build Excel with actual values (not formulas that reference empty cells)
        opening_stock = safe_float(report.get('opening_coal_stock')) if report else None
        arrival_ind = safe_float(report.get('coal_arrival_indian')) if report else None
        arrival_imp = safe_float(report.get('coal_arrival_imported', 0)) if report else 0
        coal_thermic = safe_float(report.get('coal_thermic', 0)) if report else 0
        coal_bunker = safe_float(report.get('coal_bunker_pct')) if report else None
        steam_pressure_ok = report.get('steam_pressure_ok', True) if report else True
        
        sep_consumed = (safe_float(sep_close) or 0) - (safe_float(sep_open) or 0)
        refl_consumed = (safe_float(refl_close) or 0) - (safe_float(refl_open) or 0)
        total_steam = sep_consumed + refl_consumed
        
        # Build the workbook (same structure as before but with real values)
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from io import BytesIO
        from fastapi.responses import StreamingResponse
        from datetime import datetime as dt

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"

        bold = Font(bold=True)
        center = Alignment(horizontal="center", vertical="center", wrap_text=True)
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

        try:
            d = dt.strptime(date, "%Y-%m-%d")
            date_display = d.strftime("%d/%m/%Y")
            month_year = d.strftime("%b. - %Y").upper()
        except:
            date_display = date
            month_year = date

        # Row 1-3 titles
        ws.merge_cells("B1:J1")
        cell(1, 2, f"DAILY STATUS REPORT- {month_year}", Font(bold=True, size=12), align=center)
        ws.merge_cells("B2:J2")
        cell(2, 2, f"DATE : {date_display}", Font(bold=True, size=11), align=center)
        ws.merge_cells("B3:J3")
        cell(3, 2, "COAL COSUMPTION AND STOCK SHEET", Font(bold=True), blue_fill, center, border)

        # Row 4 headers
        headers_coal = ["OPENING STOCK OF COAL IN MT","ARRIVAL COAL IN MT (IND)","ARRIVAL COAL IN MT (IMP)",
            "COAL CONSUMPTION IN MT (SEP)","COAL CONSUMPTION IN MT (REFINERY)","COAL ISSUE TO THERMIC BLR IN MT",
            "TOTAL COAL CONSUMPTION IN MT","CLOSING STOCK IN MT","REMARKS"]
        for i, h in enumerate(headers_coal, 2):
            cell(4, i, h, bold, blue_fill, center, border)

        # Coal data rows — use REAL calculated values
        coal_consumed_sep = row.get('coal_consumed_sep') if entry_result and row.get('coal_consumed_sep') else None
        coal_consumed_refl = row.get('coal_consumed_refinery') if entry_result and row.get('coal_consumed_refinery') else None
        total_coal = (coal_consumed_sep or 0) + (coal_consumed_refl or 0) + (coal_thermic or 0)
        closing_stock = (opening_stock or 0) + (arrival_ind or 0) + (arrival_imp or 0) - total_coal if opening_stock else None
        cs_ratio = round(total_steam / (total_coal * 1000), 3) if total_coal and total_coal > 0 and total_steam > 0 else None

        cell(5, 2, opening_stock, align=center, b=border)
        cell(5, 3, arrival_ind, align=center, b=border)
        cell(5, 4, arrival_imp or 0, align=center, b=border)
        cell(5, 5, coal_consumed_sep, align=center, b=border)
        cell(5, 6, coal_consumed_refl, align=center, b=border)
        cell(5, 7, coal_thermic or 0, align=center, b=border)
        c = ws.cell(5, 8, total_coal if total_coal > 0 else None)
        c.font = bold; c.alignment = center; c.border = border
        cell(5, 9, closing_stock, align=center, b=border)
        cell(5, 10, '', align=center, b=border)

        # Row 7-9 Coal bunker
        cell(7, 2, "PERTICULAR", bold, blue_fill, None, border)
        cell(7, 3, None, b=border)
        cell(7, 4, "COAL IN BUNKER (%)", bold, blue_fill, center, border)
        cell(7, 5, "REMARKS", bold, blue_fill, center, border)
        cell(7, 9, "COAL FOR STEAM (KG)", bold, align=center, b=border)

        cell(8, 2, "COAL BUNKER STATUS", bold, b=border)
        cell(8, 3, None, b=border)
        cell(8, 4, coal_bunker, align=center, b=border)
        coal_for_steam = round(avg_feeding * 60 * 24) if avg_feeding else None
        cell(8, 9, coal_for_steam, Font(bold=True), align=center, b=border)

        cell(9, 2, "STEAM PRESSURE PROBLEM", bold, b=border)
        cell(9, 3, None, b=border)
        sp_val = "NO" if steam_pressure_ok else "YES"
        sp_fill = green_fill if steam_pressure_ok else PatternFill("solid", fgColor="FADBD8")
        cell(9, 4, sp_val, Font(bold=True), sp_fill, center, border)

        # Row 11-13 SEP Steam
        ws.merge_cells("B11:J11")
        cell(11, 2, "STEAM FLOW METER READING (SEP)", Font(bold=True), blue_fill, center, border)
        steam_headers = ["OPENING READING IN KG","CLOSING READING IN KG","","STEAM CONSUMPTION IN KG",
            "","FEED WATER TEMP. (°C)","","AVERAGE FEEDING (HZ)",""]
        for i, h in enumerate(steam_headers, 2):
            cell(12, i, h if h else "", bold if h else None, blue_fill, center, border)

        cell(13, 2, safe_float(sep_open) or None, align=center, b=border)
        cell(13, 3, safe_float(sep_close) or None, align=center, b=border)
        cell(13, 4, None, b=border)
        c = ws.cell(13, 5, sep_consumed if sep_consumed else None)
        c.font = bold; c.fill = yellow_fill; c.alignment = center; c.border = border
        cell(13, 6, None, b=border)
        cell(13, 7, avg_fw, align=center, b=border)
        cell(13, 8, None, b=border)
        cell(13, 9, avg_feeding, align=center, b=border)

        # Row 15-17 REFL Steam
        ws.merge_cells("B15:J15")
        cell(15, 2, "STEAM FLOW METER READING (REFINERY)", Font(bold=True), blue_fill, center, border)
        refl_headers = ["OPENING READING IN KG","CLOSING READING IN KG","","STEAM COSUMPTION IN KG",
            "","TOTAL STEAM (KG)","","STEAM TO COAL RATIO",""]
        for i, h in enumerate(refl_headers, 2):
            cell(16, i, h if h else "", bold if h else None, blue_fill, center, border)

        cell(17, 2, safe_float(refl_open) or None, align=center, b=border)
        cell(17, 3, safe_float(refl_close) or None, align=center, b=border)
        cell(17, 4, None, b=border)
        c = ws.cell(17, 5, refl_consumed if refl_consumed else None)
        c.font = bold; c.fill = yellow_fill; c.alignment = center; c.border = border
        cell(17, 6, None, b=border)
        c = ws.cell(17, 7, total_steam if total_steam else None)
        c.font = bold; c.fill = yellow_fill; c.alignment = center; c.border = border
        cell(17, 8, None, b=border)
        c = ws.cell(17, 9, cs_ratio)
        c.font = bold; c.fill = green_fill; c.alignment = center; c.border = border
        if cs_ratio: c.number_format = '0.00'

        # Column widths
        for col, width in {'A':4,'B':22,'C':16,'D':16,'E':18,'F':16,'G':14,'H':14,'I':16,'J':12}.items():
            ws.column_dimensions[col].width = width
        for r in [4, 12, 16]:
            ws.row_dimensions[r].height = 40

        cell(21, 2, f"Generated: {date}  |  HOD: {current_user.name}  |  Shalimar Plant Ops System",
             Font(italic=True, color="888888", size=9))

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return StreamingResponse(buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=Boiler_{date}.xlsx"})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Excel generation failed: {str(e)}")

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
def export_monthly_coal_excel(year: int, month: int, db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)):
    try:
        from sqlalchemy import text
        from datetime import datetime

        prefix = f"{year}-{str(month).zfill(2)}%"
        results = db.execute(text(
            "SELECT * FROM daily_coal_steam WHERE report_date::text LIKE :prefix ORDER BY report_date ASC"
        ), {"prefix": prefix}).mappings().all()
        records = [dict(r) for r in results]

        def sf(val, default=None):
            if val is None: return default
            try: return float(val)
            except: return default

        def fmt_date(val):
            if val is None: return ''
            if hasattr(val, 'strftime'): return val.strftime("%d/%m/%Y")
            try: return datetime.strptime(str(val)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
            except: return str(val)

        month_name = datetime(year, month, 1).strftime("%b").upper()
        NUM_COLS = 14

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"

        bold = Font(bold=True, name='Calibri')
        center = Alignment(horizontal='center', vertical='center', wrap_text=True)
        thin = Side(style='thin')
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        blue_fill = PatternFill('solid', fgColor='BDD7EE')
        yellow_fill = PatternFill('solid', fgColor='FFFF00')
        last_col = openpyxl.utils.get_column_letter(NUM_COLS)

        # Row 1: Company name
        ws.merge_cells(f'A1:{last_col}1')
        ws['A1'] = 'SHALIMAR NUTRIENTS PRIVATE LIMITED'
        ws['A1'].font = Font(bold=True, size=14, name='Calibri')
        ws['A1'].alignment = center

        # Row 2: Section
        ws.merge_cells(f'A2:{last_col}2')
        ws['A2'] = 'BOILER SECTION'
        ws['A2'].font = Font(bold=True, size=12, name='Calibri')
        ws['A2'].alignment = center

        # Row 3: empty

        # Row 4: Title
        ws.merge_cells(f'A4:{last_col}4')
        ws['A4'] = f'COAL COSUMPTION AND STOCK SHEET {month_name}. -{year}'
        ws['A4'].font = Font(bold=True, size=11, name='Calibri')
        ws['A4'].alignment = center

        # Row 5: empty

        # Row 6: Column headers  (A=1 … O=15)
        headers = [
            'DATE',
            'OPENING STOCK OF COAL IN MT',
            'ARRIVAL COAL IN MT',
            'COAL CONSUMPTION IN  MT (SEP)',
            'COAL CONSUMPTION IN MT (REF.)',
            'TOTAL COAL FOR STEAM PRODUCTION',
            'COAL CONSUMPTION IN THERMIC BOILER IN MT',
            'COAL CONSUMPTION IN MT (TOTAL)',
            'CLOSING STOCK IN MT',
            'AVERAGE ASH OUTCOME IN MT',
            'STEAM PRODUCTION IN KG (SEP)',
            'STEAM PRODUCTION IN KG (REF.)',
            'TOTAL STEAM PRODUCTION IN KG',
            'C/S RATIO',
        ]
        for col_idx, h in enumerate(headers, 1):
            c = ws.cell(6, col_idx, h)
            c.font = bold
            c.fill = blue_fill
            c.border = border
            c.alignment = center
        ws.row_dimensions[6].height = 50

        DATA_START = 7
        
        # Python will track the bottom totals natively to bypass Excel's formula block
        col_totals = {3:0, 4:0, 5:0, 6:0, 7:0, 8:0, 10:0, 11:0, 12:0, 13:0}

        for i, rec in enumerate(records):
            r = DATA_START + i

            # 👇 1. SMART AUTO-CALCULATION FOR EACH DAY 👇
            current_date = str(rec.get('report_date'))[:10]
            
            # Quickly fetch the hourly logs for THIS specific day
            logs = db.execute(text(
                "SELECT * FROM boiler_log_entries WHERE log_date::text = :date"
            ), {"date": current_date}).mappings().all()
            
            sep_flows = [sf(l.get('steam_flow_sep')) for l in logs if sf(l.get('steam_flow_sep')) is not None]
            refl_flows = [sf(l.get('steam_flow_refl')) for l in logs if sf(l.get('steam_flow_refl')) is not None]
            bed1_hz = [sf(l.get('coal_feed_bed1_hz')) for l in logs if sf(l.get('coal_feed_bed1_hz')) is not None]
            bed2_hz = [sf(l.get('coal_feed_bed2_hz')) for l in logs if sf(l.get('coal_feed_bed2_hz')) is not None]

            # Calculate Steam Consumed
            steam_sep = (max(sep_flows) - min(sep_flows)) if sep_flows else None
            steam_ref = (max(refl_flows) - min(refl_flows)) if refl_flows else None
            total_steam = (steam_sep + steam_ref) if (steam_sep is not None and steam_ref is not None) else None

            # Calculate Coal for Steam & CS Ratio
            all_hz = bed1_hz + bed2_hz
            avg_feeding = round(sum(all_hz) / len(all_hz), 2) if all_hz else None
            coal_for_steam = round(avg_feeding * 60 * 24) if avg_feeding else None

            if total_steam is not None and coal_for_steam is not None and coal_for_steam > 0:
                actual_cs_ratio = round(total_steam / coal_for_steam, 2)
            else:
                actual_cs_ratio = 0

            # Calculate Coal SEP
            if steam_sep is not None and actual_cs_ratio > 0:
                sep = round(steam_sep / (actual_cs_ratio * 1000), 3)
            else:
                sep = sf(rec.get('coal_consumed_sep'))

            # Calculate Coal REF
            coal_for_steam_mt = round(coal_for_steam / 1000, 3) if coal_for_steam is not None else None
            if coal_for_steam_mt is not None and sep is not None:
                ref_ = round(coal_for_steam_mt - sep, 3)
            else:
                ref_ = sf(rec.get('coal_consumed_refinery'))

            # 2. Get the standard manual values
            arrival = (sf(rec.get('coal_arrival_indian'), 0) + sf(rec.get('coal_arrival_imported'), 0))
            thermic = sf(rec.get('coal_thermic'))
            opening = sf(rec.get('opening_coal_stock'))

            # 👇 PYTHON MATH (Replaces Excel string formulas) 👇
            f_val = round((sep or 0) + (ref_ or 0), 3)
            h_val = round(f_val + (thermic or 0), 3)
            i_val = round(opening + (arrival or 0) - h_val, 3) if opening is not None else None
            j_val = round(f_val * 0.32, 3)
            m_val = (steam_sep or 0) + (steam_ref or 0)
            n_val = round(m_val / (f_val * 1000), 2) if f_val > 0 and m_val > 0 else None

            # Add to Totals
            col_totals[3] += (arrival or 0)
            col_totals[4] += (sep or 0)
            col_totals[5] += (ref_ or 0)
            col_totals[6] += f_val
            col_totals[7] += (thermic or 0)
            col_totals[8] += h_val
            col_totals[10] += j_val
            col_totals[11] += (steam_sep or 0)
            col_totals[12] += (steam_ref or 0)
            col_totals[13] += m_val

            # 2. Get the standard manual values
            arrival = (sf(rec.get('coal_arrival_indian'), 0) + sf(rec.get('coal_arrival_imported'), 0))
            thermic = sf(rec.get('coal_thermic'))
            opening = sf(rec.get('opening_coal_stock'))

            def wc(col, val):
                c = ws.cell(r, col, val)
                c.border = border
                c.alignment = center
                return c

            wc(1, fmt_date(rec.get('report_date')))                      # A DATE
            wc(2, opening)                                               # B OPENING STOCK
            wc(3, arrival if arrival and arrival > 0 else None)          # C ARRIVAL
            wc(4, sep if sep and sep > 0 else None)                      # D SEP
            wc(5, ref_ if ref_ and ref_ > 0 else None)                   # E REF

            # 👇 LIVE EXCEL FORMULAS START HERE 👇

            # F: TOTAL COAL FOR STEAM = D + E
            c = ws.cell(r, 6, f'=IF(D{r}+E{r}>0,D{r}+E{r},0)')
            c.border = border; c.alignment = center; c.font = bold

            wc(7, thermic if thermic and thermic > 0 else None)          # G THERMIC

            # H: TOTAL COAL CONSUMPTION = F + G
            c = ws.cell(r, 8, f'=F{r}+IF(G{r}="",0,G{r})')
            c.border = border; c.alignment = center; c.font = bold

            # I: CLOSING STOCK = B + C - H
            c = ws.cell(r, 9, f'=B{r}+IF(C{r}="",0,C{r})-H{r}')
            c.border = border; c.alignment = center

            # J: AVERAGE ASH = F * 0.32
            c = ws.cell(r, 10, f'=F{r}*0.32')
            c.border = border; c.alignment = center

            wc(11, steam_sep if steam_sep and steam_sep > 0 else None)   # K STEAM SEP
            wc(12, steam_ref if steam_ref and steam_ref > 0 else None)   # L STEAM REF

            # M: TOTAL STEAM = K + L
            c = ws.cell(r, 13, f'=IF(K{r}+L{r}>0,K{r}+L{r},0)')
            c.border = border; c.alignment = center; c.font = bold

            # N: C/S RATIO = M / (F * 1000)
            c = ws.cell(r, 14, f'=IF(F{r}>0,M{r}/(F{r}*1000),"")')
            c.border = border; c.alignment = center
            c.number_format = '0.00'

        # 👇 LIVE FORMULAS FOR THE TOTALS ROW 👇
        if records:
            total_r = DATA_START + len(records)
            c = ws.cell(total_r, 1, 'TOTAL')
            c.font = bold; c.border = border; c.alignment = center; c.fill = yellow_fill

            last_data = DATA_START + len(records) - 1
            sum_cols = [3, 4, 5, 6, 7, 8, 10, 11, 12, 13]
            for col in sum_cols:
                cl = openpyxl.utils.get_column_letter(col)
                c = ws.cell(total_r, col, f'=SUM({cl}{DATA_START}:{cl}{last_data})')
                c.font = bold; c.border = border; c.alignment = center; c.fill = yellow_fill

            # C/S ratio total
            c = ws.cell(total_r, 14, f'=IF(F{total_r}>0,M{total_r}/(F{total_r}*1000),"")')
            c.font = bold; c.border = border; c.alignment = center
            c.fill = yellow_fill; c.number_format = '0.00'

            for col in [1, 2, 9]:
                ws.cell(total_r, col).border = border
                ws.cell(total_r, col).fill = yellow_fill

        # Column widths (Exactly 14 to match the removed Feed Water column)
        widths = [12, 15, 14, 16, 16, 18, 22, 18, 14, 16, 18, 18, 18, 10]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Monthly Excel failed: {str(e)}")

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

@app.get("/history/daily-entry")
def history_daily_entry(year: int, month: int, db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)):
    from sqlalchemy import text
    import json
    prefix = f"{year}-{str(month).zfill(2)}%"
    results = db.execute(text(
        "SELECT * FROM daily_entries WHERE entry_date::text LIKE :p ORDER BY entry_date ASC"
    ), {"p": prefix}).mappings().all()
    rows = []
    for r in results:
        row = dict(r)
        for field in ['feed_water_temps', 'fd_fan1_dampers', 'fd_fan2_dampers']:
            if row.get(field):
                try: row[field] = json.loads(row[field])
                except: row[field] = []
        rows.append(row)
    return rows

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

@app.get("/boiler-log/date/{date}")
def get_logs_by_date(date: str, db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)):
    from sqlalchemy import text
    results = db.execute(text(
        "SELECT * FROM boiler_log_entries WHERE log_date::text = :d "
        "ORDER BY log_time ASC"
    ), {"d": date}).mappings().all()
    return [dict(r) for r in results]

@app.put("/daily-report/{date}/opening")
def set_opening_stock(
    date: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("hod"))
):
    from sqlalchemy import text
    opening = float(payload.get("opening_stock", 0))
    
    existing = db.execute(text(
        "SELECT id FROM daily_coal_steam WHERE report_date::text = :d LIMIT 1"
    ), {"d": date}).mappings().fetchone()
    
    if existing:
        db.execute(text(
            "UPDATE daily_coal_steam SET opening_coal_stock = :o WHERE report_date::text = :d"
        ), {"o": opening, "d": date})
    else:
        db.execute(text("""
            INSERT INTO daily_coal_steam (report_date, opening_coal_stock,
              coal_arrival_indian, coal_arrival_imported, coal_consumed_sep,
              coal_consumed_refinery, coal_thermic, total_coal_consumed,
              closing_stock, steam_sep_opening, steam_sep_closing, steam_sep_consumed,
              steam_refl_opening, steam_refl_closing, steam_refl_consumed,
              total_steam, cs_ratio)
            VALUES (:d::date, :o, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)
        """), {"d": date, "o": opening})
    db.commit()
    return {"message": "Opening stock set", "opening_stock": opening, "date": date}

    # ─── DAILY ENTRY (SIMPLIFIED) ────────────────────────────

@app.post("/daily-entry")
def create_daily_entry(data: dict, db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)):
    import json
    from decimal import Decimal

    # Auto-calculate coal
    sep = data.get('coal_consumed_sep') or 0
    refl = data.get('coal_consumed_refinery') or 0
    thermic = data.get('coal_thermic') or 0
    arrival_in = data.get('coal_arrival_indian') or 0
    arrival_im = data.get('coal_arrival_imported') or 0
    opening = data.get('opening_coal_stock') or 0
    total_coal = sep + refl + thermic
    closing = opening + arrival_in + arrival_im - total_coal

    # Auto-calculate steam
    sep_open = data.get('steam_sep_opening') or 0
    sep_close = data.get('steam_sep_closing') or 0
    refl_open = data.get('steam_refl_opening') or 0
    refl_close = data.get('steam_refl_closing') or 0
    steam_sep = sep_close - sep_open
    steam_refl = refl_close - refl_open
    total_steam = steam_sep + steam_refl
    cs = round(total_steam / total_coal, 3) if total_coal > 0 else 0

    # Auto-calculate averages from arrays
    fw_temps = data.get('feed_water_temps', [])
    fd1 = data.get('fd_fan1_dampers', [])
    fd2 = data.get('fd_fan2_dampers', [])
    fw_vals = [x for x in fw_temps if x is not None and x != '']
    fd1_vals = [x for x in fd1 if x is not None and x != '']
    fd2_vals = [x for x in fd2 if x is not None and x != '']
    avg_fw = round(sum(fw_vals)/len(fw_vals), 2) if fw_vals else None
    avg_fd1 = round(sum(fd1_vals)/len(fd1_vals), 2) if fd1_vals else None
    avg_fd2 = round(sum(fd2_vals)/len(fd2_vals), 2) if fd2_vals else None

    row = db.execute(
        text("""
        INSERT INTO daily_entries (
            entry_date, operator_name,
            opening_coal_stock, coal_arrival_indian, coal_arrival_imported,
            coal_consumed_sep, coal_consumed_refinery, coal_thermic,
            total_coal_consumed, closing_stock, coal_bunker_pct, steam_pressure_ok, coal_rate_per_mt,
            steam_sep_opening, steam_sep_closing, steam_sep_consumed,
            steam_refl_opening, steam_refl_closing, steam_refl_consumed,
            total_steam, cs_ratio,
            feed_water_temps, avg_feed_water,
            fd_fan1_dampers, avg_fd_fan1,
            fd_fan2_dampers, avg_fd_fan2,
            remarks, submitted_by
        ) VALUES (
            :entry_date, :operator_name,
            :opening_coal_stock, :coal_arrival_indian, :coal_arrival_imported,
            :coal_consumed_sep, :coal_consumed_refinery, :coal_thermic,
            :total_coal_consumed, :closing_stock, :coal_bunker_pct, :steam_pressure_ok, :coal_rate_per_mt,
            :steam_sep_opening, :steam_sep_closing, :steam_sep_consumed,
            :steam_refl_opening, :steam_refl_closing, :steam_refl_consumed,
            :total_steam, :cs_ratio,
            :feed_water_temps, :avg_feed_water,
            :fd_fan1_dampers, :avg_fd_fan1,
            :fd_fan2_dampers, :avg_fd_fan2,
            :remarks, :submitted_by
        )
        ON CONFLICT (entry_date) DO UPDATE SET
            operator_name=EXCLUDED.operator_name,
            opening_coal_stock=EXCLUDED.opening_coal_stock,
            coal_arrival_indian=EXCLUDED.coal_arrival_indian,
            coal_arrival_imported=EXCLUDED.coal_arrival_imported,
            coal_consumed_sep=EXCLUDED.coal_consumed_sep,
            coal_consumed_refinery=EXCLUDED.coal_consumed_refinery,
            coal_thermic=EXCLUDED.coal_thermic,
            total_coal_consumed=EXCLUDED.total_coal_consumed,
            closing_stock=EXCLUDED.closing_stock,
            coal_bunker_pct=EXCLUDED.coal_bunker_pct,
            steam_pressure_ok=EXCLUDED.steam_pressure_ok,
            coal_rate_per_mt=EXCLUDED.coal_rate_per_mt,
            steam_sep_opening=EXCLUDED.steam_sep_opening,
            steam_sep_closing=EXCLUDED.steam_sep_closing,
            steam_sep_consumed=EXCLUDED.steam_sep_consumed,
            steam_refl_opening=EXCLUDED.steam_refl_opening,
            steam_refl_closing=EXCLUDED.steam_refl_closing,
            steam_refl_consumed=EXCLUDED.steam_refl_consumed,
            total_steam=EXCLUDED.total_steam,
            cs_ratio=EXCLUDED.cs_ratio,
            feed_water_temps=EXCLUDED.feed_water_temps,
            avg_feed_water=EXCLUDED.avg_feed_water,
            fd_fan1_dampers=EXCLUDED.fd_fan1_dampers,
            avg_fd_fan1=EXCLUDED.avg_fd_fan1,
            fd_fan2_dampers=EXCLUDED.fd_fan2_dampers,
            avg_fd_fan2=EXCLUDED.avg_fd_fan2,
            remarks=EXCLUDED.remarks,
            updated_at=now()
        RETURNING id
        """),
        {
            "entry_date": data.get('entry_date'),
            "operator_name": data.get('operator_name'),
            "opening_coal_stock": opening,
            "coal_arrival_indian": arrival_in,
            "coal_arrival_imported": arrival_im,
            "coal_consumed_sep": sep,
            "coal_consumed_refinery": refl,
            "coal_thermic": thermic,
            "total_coal_consumed": round(total_coal, 3),
            "closing_stock": round(closing, 3),
            "coal_bunker_pct": data.get('coal_bunker_pct'),
            "steam_pressure_ok": data.get('steam_pressure_ok', True),
            "coal_rate_per_mt": data.get('coal_rate_per_mt'),
            "steam_sep_opening": sep_open,
            "steam_sep_closing": sep_close,
            "steam_sep_consumed": round(steam_sep, 3),
            "steam_refl_opening": refl_open,
            "steam_refl_closing": refl_close,
            "steam_refl_consumed": round(steam_refl, 3),
            "total_steam": round(total_steam, 3),
            "cs_ratio": cs,
            "feed_water_temps": json.dumps(fw_temps),
            "avg_feed_water": avg_fw,
            "fd_fan1_dampers": json.dumps(fd1),
            "avg_fd_fan1": avg_fd1,
            "fd_fan2_dampers": json.dumps(fd2),
            "avg_fd_fan2": avg_fd2,
            "remarks": data.get('remarks'),
            "submitted_by": str(current_user.id),
        }
    )
    db.commit()
    return {"message": "Saved", "id": row.fetchone()[0],
            "total_coal": round(total_coal,3), "closing_stock": round(closing,3),
            "total_steam": round(total_steam,3), "cs_ratio": cs,
            "avg_feed_water": avg_fw, "avg_fd_fan1": avg_fd1, "avg_fd_fan2": avg_fd2}

@app.get("/daily-entry/{date}")
def get_daily_entry(date: str, db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)):
    import json
    result = db.execute(text("SELECT * FROM daily_entries WHERE entry_date = :d"), {"d": date}).fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="No entry for this date")
    row = dict(result._mapping)
    for field in ['feed_water_temps','fd_fan1_dampers','fd_fan2_dampers']:
        if row.get(field):
            try: row[field] = json.loads(row[field])
            except: row[field] = []
    return row

@app.put("/daily-entry/{date}/opening")
def set_opening_stock_entry(
    date: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("hod"))
):
    from sqlalchemy import text
    opening = float(payload.get("opening_stock", 0))
    
    existing = db.execute(text(
        "SELECT id FROM daily_entries WHERE entry_date::text = :d LIMIT 1"
    ), {"d": date}).mappings().fetchone()
    
    if existing:
        db.execute(text(
            "UPDATE daily_entries SET opening_coal_stock = :o WHERE entry_date::text = :d"
        ), {"o": opening, "d": date})
    else:
        db.execute(text("""
            INSERT INTO daily_entries (entry_date, opening_coal_stock, coal_arrival_indian,
              coal_thermic, total_coal_consumed, closing_stock, steam_sep_opening,
              steam_sep_closing, steam_sep_consumed, steam_refl_opening, steam_refl_closing,
              steam_refl_consumed, total_steam, cs_ratio)
            VALUES (CAST(:d AS DATE), :o, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        """), {"d": date, "o": opening})
    db.commit()
    return {"message": "Opening stock set", "opening_stock": opening, "date": date}

@app.get("/daily-entry/closing/{date}")
def get_prev_closing_entry(date: str, db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)):
    from sqlalchemy import text
    from datetime import datetime, timedelta
    try:
        prev_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    except:
        return {"closing_stock": None}
    result = db.execute(text(
        "SELECT closing_stock FROM daily_entries WHERE entry_date::text = :d LIMIT 1"
    ), {"d": prev_date}).mappings().fetchone()
    return {"closing_stock": result['closing_stock'] if result else None, "date": prev_date}


# ─── HEALTH CHECK ─────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "Shalimar Plant Ops API is running", "version": "1.0.0"}
