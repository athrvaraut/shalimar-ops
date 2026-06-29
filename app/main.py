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
        from datetime import datetime as dt, timedelta

        # Fetch data
        entry_result = db.execute(text(
            "SELECT * FROM daily_entries WHERE entry_date::text = :date LIMIT 1"
        ), {"date": date}).mappings().fetchone()

        row = None
        if entry_result:
            row = dict(entry_result)
            for field in ['feed_water_temps', 'fd_fan1_dampers', 'fd_fan2_dampers']:
                if row.get(field):
                    try: row[field] = json.loads(row[field])
                    except: row[field] = []
            sep_open  = row.get('steam_sep_opening') or 0
            sep_close = row.get('steam_sep_closing') or 0
            refl_open  = row.get('steam_refl_opening') or 0
            refl_close = row.get('steam_refl_closing') or 0
            fw_vals = [x for x in row.get('feed_water_temps', []) if x is not None and x != '']
            avg_fw = round(sum(fw_vals)/len(fw_vals), 1) if fw_vals else None
            fd1_vals = [x for x in row.get('fd_fan1_dampers', []) if x is not None and x != '']
            avg_feeding = round(sum(fd1_vals)/len(fd1_vals), 2) if fd1_vals else None
        else:
            coal_r = db.execute(text(
                "SELECT * FROM daily_coal_steam WHERE report_date::text = :date LIMIT 1"
            ), {"date": date}).mappings().fetchone()
            row = dict(coal_r) if coal_r else {}
            sep_open  = row.get('steam_sep_opening') or 0
            sep_close = row.get('steam_sep_closing') or 0
            refl_open  = row.get('steam_refl_opening') or 0
            refl_close = row.get('steam_refl_closing') or 0
            avg_fw = row.get('avg_feed_water') or row.get('feed_water_temp')
            avg_feeding = None

        def sf(val):
            if val is None: return None
            try: return float(val)
            except: return None

        # Auto-fill opening from yesterday's closing
        opening_stock = sf(row.get('opening_coal_stock'))
        try:
            prev_date = (dt.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
            prev = db.execute(text(
                "SELECT closing_stock FROM daily_entries WHERE entry_date::text = :d LIMIT 1"
            ), {"d": prev_date}).mappings().fetchone()
            if prev and prev['closing_stock']:
                opening_stock = float(prev['closing_stock'])
        except: pass

        arrival_ind      = sf(row.get('coal_arrival_indian'))
        arrival_imp      = sf(row.get('coal_arrival_imported')) or 0
        coal_thermic     = sf(row.get('coal_thermic')) or 0
        coal_bunker      = sf(row.get('coal_bunker_pct'))
        steam_pressure_ok = row.get('steam_pressure_ok', True)
        remarks_text     = row.get('remarks', '') if row else ''

        # Build workbook — NO FILLS, just borders + bold
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"

        bold   = Font(bold=True)
        center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left   = Alignment(horizontal="left",   vertical="center", wrap_text=True)
        thin   = Side(style="thin")
        bdr    = Border(left=thin, right=thin, top=thin, bottom=thin)

        def C(r, c, val=None, fnt=None, aln=None, b=None):
            cell = ws.cell(row=r, column=c, value=val)
            cell.font      = fnt if fnt else Font()
            cell.alignment = aln if aln else center
            cell.border    = b   if b   else Border()
            return cell

        try:
            d_obj = dt.strptime(date, "%Y-%m-%d")
            date_display = d_obj.strftime("%d/%m/%Y")
            month_year   = d_obj.strftime("%b. - %Y").upper()
        except:
            date_display = date
            month_year   = date

        # ── ROW 3: Title ──────────────────────────────────────────────────
        ws.merge_cells("B3:J3")
        C(3, 2, f"DAILY STATUS REPORT- {month_year}", bold, center, bdr)
        for col in range(3, 11): ws.cell(3, col).border = bdr

        # ── ROW 4: Date ───────────────────────────────────────────────────
        ws.merge_cells("B4:J4")
        C(4, 2, f"DATE : {date_display}", bold, center, bdr)
        for col in range(3, 11): ws.cell(4, col).border = bdr

        # Row 5: empty

        # ── ROW 6: Section header ─────────────────────────────────────────
        ws.merge_cells("B6:J6")
        C(6, 2, "COAL COSUMPTION AND STOCK SHEET", bold, center, bdr)
        for col in range(3, 11): ws.cell(6, col).border = bdr

        # ── ROW 7: Coal table headers ─────────────────────────────────────
        coal_hdrs = [
            "OPENING STOCK OF COAL IN MT",
            "ARRIVAL COAL IN MT (IND)",
            "ARRIVAL COAL IN MT (IMP)",
            "COAL CONSUMPTION IN MT (SEP)",
            "COAL CONSUMPTION IN MT (REFINERY)",
            "COAL ISSUE TO THERMIC BLR IN MT",
            "TOTAL COAL CONSUMPTION IN MT",
            "CLOSING STOCK IN MT",
            "REMARKS",
        ]
        for i, h in enumerate(coal_hdrs, 2):
            C(7, i, h, bold, center, bdr)
        ws.row_dimensions[7].height = 42

        # ── ROW 8: Coal data ──────────────────────────────────────────────
        # B8 Opening (raw)
        C(8, 2, opening_stock, b=bdr)
        # C8 Arrival Indian (raw)
        C(8, 3, arrival_ind, b=bdr)
        # D8 Arrival Imported (raw)
        C(8, 4, arrival_imp or 0, b=bdr)
        # E8 Coal SEP = E16(SEP consumed) / (I19(C/S ratio) * 1000)
        c = ws.cell(8, 5, '=IF(AND(I19>0,E16>0),E16/(I19*1000),"")')
        c.alignment = center; c.border = bdr
        # F8 Coal REFL = I12(Coal For Steam KG)/1000 - E8
        c = ws.cell(8, 6, '=IF(AND(I12>0,E8<>""),I12/1000-E8,"")')
        c.alignment = center; c.border = bdr
        # G8 Thermic (raw)
        C(8, 7, coal_thermic or 0, b=bdr)
        # H8 Total Coal = E8+F8+G8
        c = ws.cell(8, 8, '=E8+IF(F8="",0,F8)+IF(G8="",0,G8)')
        c.font = bold; c.alignment = center; c.border = bdr
        # I8 Closing = B8+C8+D8-H8
        c = ws.cell(8, 9, '=B8+C8+D8-H8')
        c.alignment = center; c.border = bdr
        # J8 Remarks
        C(8, 10, remarks_text, b=bdr)

        # Row 9: empty

        # ── ROW 10: PERTICULAR section ────────────────────────────────────
        C(10, 2, "PERTICULAR",        bold, left,   bdr)
        C(10, 3, None,                None, center, bdr)
        C(10, 4, "COAL IN BUNKER (%)",bold, center, bdr)
        # E10:H10 merged = REMARKS
        ws.merge_cells("E10:H10")
        C(10, 5, "REMARKS", bold, center, bdr)
        for col in [6, 7, 8]: ws.cell(10, col).border = bdr
        # I10 = COAL FOR STEAM header
        C(10, 9, "COAL FOR STEAM (KG)", bold, center, bdr)

        # ── ROW 11: COAL BUNKER STATUS ────────────────────────────────────
        C(11, 2, "COAL BUNKER STATUS", bold, left,   bdr)
        C(11, 3, None,                 None, center, bdr)
        C(11, 4, coal_bunker,          None, center, bdr)
        ws.merge_cells("E11:H11")
        C(11, 5, None, b=bdr)
        for col in [6, 7, 8]: ws.cell(11, col).border = bdr
        C(11, 9, None, b=bdr)

        # ── ROW 12: STEAM PRESSURE PROBLEM + COAL FOR STEAM value ─────────
        C(12, 2, "STEAM PRESSURE PROBLEM", bold, left, bdr)
        C(12, 3, None, b=bdr)
        sp_val  = "NO" if steam_pressure_ok else "YES"
        C(12, 4, sp_val, bold, center, bdr)
        ws.merge_cells("E12:H12")
        C(12, 5, None, b=bdr)
        for col in [6, 7, 8]: ws.cell(12, col).border = bdr
        # I12: Coal For Steam = I16(avg_feeding) * 60 * 24
        c = ws.cell(12, 9, '=IF(I16<>"",I16*60*24,"")')
        c.font = bold; c.alignment = center; c.border = bdr

        # Row 13: empty

        # ── ROW 14: STEAM FLOW SEP title ──────────────────────────────────
        ws.merge_cells("B14:I14")
        C(14, 2, "STEAM FLOW METER READING (SEP)", bold, center, bdr)
        for col in range(3, 10): ws.cell(14, col).border = bdr

        # ── ROW 15: SEP headers ───────────────────────────────────────────
        sep_h = {2:"OPENING READING IN KG", 3:"CLOSING READING IN KG", 4:"",
                 5:"STEAM COSUMPTION IN KG", 6:"", 7:"FEED WATER TEMP. (°C)",
                 8:"", 9:"AVERAGE FEEDING"}
        for col, h in sep_h.items():
            C(15, col, h if h else None, bold if h else None, center, bdr)
        ws.row_dimensions[15].height = 38

        # ── ROW 16: SEP data ──────────────────────────────────────────────
        C(16, 2, sf(sep_open),  b=bdr)
        C(16, 3, sf(sep_close), b=bdr)
        C(16, 4, None, b=bdr)
        # E16: SEP consumed = C16-B16
        c = ws.cell(16, 5, '=C16-B16')
        c.font = bold; c.alignment = center; c.border = bdr
        C(16, 6, None, b=bdr)
        C(16, 7, avg_fw, b=bdr)       # Feed water avg
        C(16, 8, None, b=bdr)
        C(16, 9, avg_feeding, b=bdr)  # Average feeding HZ

        # Row 17: empty

        # ── ROW 18: REFL headers (NO separate title row — matches real excel) ──
        refl_h = {2:"OPENING READING IN KG", 3:"CLOSING READING IN KG", 4:"",
                  5:"STEAM COSUMPTION IN KG", 6:"", 7:"TOTAL STEAM (KG)",
                  8:"", 9:"STEAM TO COAL  RATIO"}
        for col, h in refl_h.items():
            C(18, col, h if h else None, bold if h else None, center, bdr)
        ws.row_dimensions[18].height = 38

        # ── ROW 19: REFL data ─────────────────────────────────────────────
        C(19, 2, sf(refl_open),  b=bdr)
        C(19, 3, sf(refl_close), b=bdr)
        C(19, 4, None, b=bdr)
        # E19: REFL consumed = C19-B19
        c = ws.cell(19, 5, '=C19-B19')
        c.font = bold; c.alignment = center; c.border = bdr
        C(19, 6, None, b=bdr)
        # G19: Total Steam = E16+E19
        c = ws.cell(19, 7, '=E16+E19')
        c.font = bold; c.alignment = center; c.border = bdr
        C(19, 8, None, b=bdr)
        # I19: C/S Ratio = G19/I12
        c = ws.cell(19, 9, '=IF(I12>0,G19/I12,"")')
        c.font = bold; c.alignment = center; c.border = bdr
        c.number_format = '0.000'

        # Column widths — match real excel proportions
        widths = {'A':3,'B':24,'C':18,'D':18,'E':20,'F':20,'G':20,'H':14,'I':18,'J':14}
        for col, w in widths.items():
            ws.column_dimensions[col].width = w

        # Footer
        ws.cell(22, 2).value = f"Generated: {date}  |  HOD: {current_user.name}  |  Shalimar Plant Ops"
        ws.cell(22, 2).font = Font(italic=True, color="888888", size=9)

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
    
@app.get("/power-consumption/date/{date}")
def get_power_by_date(date: str, db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)):
    from sqlalchemy import text
    result = db.execute(text(
        "SELECT * FROM power_consumption WHERE reading_date::text = :d ORDER BY id DESC LIMIT 1"
    ), {"d": date}).mappings().fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="No power entry for this date")
    return dict(result)

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
    solar_fill = PatternFill("solid", fgColor="92D050")

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
    ws.cell(2, 1).border = border
    ws.cell(2, 1).alignment = center
    ws.cell(2, 2).border = border

    for i, rec in enumerate(records):
        col = i + 3
        date_str = safe_date_str(rec.get('reading_date'))
        c = ws.cell(2, col, date_str)
        c.font = bold; c.border = border; c.alignment = center

    # TOTAL column
    total_col = len(records) + 3
    ws.cell(2, total_col, "TOTAL").font = bold
    ws.cell(2, total_col).border = border
    ws.cell(2, total_col).alignment = center

    # ROW 3: SR.NO. / SECTION NAME / UNIT (KWH) headers
    ws.cell(3, 1, "SR.NO.").font = bold; ws.cell(3, 1).border = border; ws.cell(3, 1).alignment = center
    ws.cell(3, 2, "SECTION NAME").font = bold; ws.cell(3, 2).border = border; ws.cell(3, 2).alignment = center
    
    for i in range(len(records)):
        col = i + 3
        ws.cell(3, col, "UNIT (KWH)").font = bold
        ws.cell(3, col).border = border
        ws.cell(3, col).alignment = center

    ws.cell(3, total_col, "TOTAL").font = bold
    ws.cell(3, total_col).border = border
    ws.cell(3, total_col).alignment = center

    # Data rows start
    data_rows_start = 4

    # Section groups with subtotals
    # Define sections with group markers
    # (SR, Name, Field, is_subtotal, exclude_from_subtotal)
    SECTION_GROUPS = [
        ("1",  "SEP",              "sep_units",      False, False),
        ("2",  "PREP",             "prep_units",     False, False),
        ("",   "SOLAR",            "solar_units",    False, True),   # excluded from subtotal 1
        ("3",  "SILO",             "silo_units",     False, False),
        ("4",  "DOC",              "doc_units",      False, False),
        ("5",  "D-SILO",           "dsilo_units",    False, False),
        ("",   "",                 None,             True,  False),  # Subtotal 1
        ("6",  "ACM/ SOYA CHUNKS", "acm_units",      False, True),   # excluded from subtotal 2
        ("7",  "BOILER",           "boiler_units",   False, False),
        ("8",  "CHP",              "chp_units",      False, False),
        ("9",  "DM PLANT",         "dm_units",       False, False),
        ("",   "UG TANK",          "ug_tank_units",  False, False),
        ("",   "",                 None,             True,  False),  # Subtotal 2
        ("10", "REFINERY",         "refinery_units", False, False),
        ("11", "ETP/ACID/MVR",     "etp_units",      False, False),
        ("12", "PACKING",          "packing_units",  False, False),
        ("",   "",                 None,             True,  False),  # Subtotal 3
        ("13", "ADMIN",            "admin_units",    False, False),
        ("15", "MISCELLENIOUS",    None,             False, False),
        ("",   "",                 None,             True,  False),  # Subtotal 4
        ("16", "DG SET UNIT",      "dg_units",       False, False),
    ]

    def build_subtotal_formula(col_letter, rows):
        if not rows: return "0"
        if len(rows) == 1: return f"={col_letter}{rows[0]}"
        is_consec = all(rows[j+1] == rows[j]+1 for j in range(len(rows)-1))
        if is_consec:
            return f"=SUM({col_letter}{rows[0]}:{col_letter}{rows[-1]})"
        return "=" + "+".join(f"{col_letter}{r}" for r in rows)

    current_group_included_rows = []
    current_row = data_rows_start
    subtotal_row_nums = []
    solar_row_num = None
    dg_set_row = None

    for sr, name, field, is_subtotal, exclude_from_subtotal in SECTION_GROUPS:
        ws.cell(current_row, 1).border = border
        ws.cell(current_row, 2).border = border

        if is_subtotal:
            # Yellow subtotal row — ONLY values get colored now (Labels stay white)
            for i, rec in enumerate(records):
                col = i + 3
                col_l = openpyxl.utils.get_column_letter(col)
                formula = build_subtotal_formula(col_l, current_group_included_rows)
                c = ws.cell(current_row, col, formula)
                c.fill = yellow_fill
                c.font = Font(bold=True)
                c.border = border
                c.alignment = center

            rs = openpyxl.utils.get_column_letter(3)
            re = openpyxl.utils.get_column_letter(2 + len(records))
            ws.cell(current_row, total_col, f"=SUM({rs}{current_row}:{re}{current_row})")
            ws.cell(current_row, total_col).fill = yellow_fill
            ws.cell(current_row, total_col).font = Font(bold=True)
            ws.cell(current_row, total_col).border = border

            subtotal_row_nums.append(current_row)
            current_group_included_rows = []
            current_row += 1
            continue

        # --- NORMAL SECTION ROW ---
        ws.cell(current_row, 1, sr).alignment = center
        ws.cell(current_row, 2, name).font = Font(bold=True) if sr else Font()

        # Track for subtotal (exclude flagged rows like SOLAR, ACM)
        if not exclude_from_subtotal:
            current_group_included_rows.append(current_row)

        # SOLAR gets green fill; others get no fill
        is_solar = (name == 'SOLAR')
        row_fill = solar_fill if is_solar else None

        for i, rec in enumerate(records):
            val = rec.get(field, 0) or 0 if field else 0
            c = ws.cell(current_row, i + 3, val)
            c.border = border
            c.alignment = center
            if row_fill:
                c.fill = row_fill
                c.font = Font(bold=True)

        fc = openpyxl.utils.get_column_letter(3)
        lc = openpyxl.utils.get_column_letter(2 + len(records))
        ws.cell(current_row, total_col, f"=SUM({fc}{current_row}:{lc}{current_row})")
        ws.cell(current_row, total_col).border = border
        ws.cell(current_row, total_col).alignment = center
        if row_fill:
            ws.cell(current_row, total_col).fill = row_fill

        if name == 'SOLAR':
            solar_row_num = current_row
        if name == 'DG SET UNIT':
            dg_set_row = current_row

        current_row += 1

    # Summary rows — per-row color matching real excel
    orange_fill     = PatternFill("solid", fgColor="FFBF00")  # Rich Yellow-Orange
    soft_blue_fill  = PatternFill("solid", fgColor="8EA9DB")  # Softer, lighter Excel blue
    pf_fill         = PatternFill("solid", fgColor="BDD7EE")  # Power factor pale blue

    # 👇 Reduced 45 to 38 for a slightly tighter, perfect fit
    summary_rows = [
        ("TOTAL UNIT WITH SOLAR GEN. UNIT",       "total_with_solar",    orange_fill,    "000000", 38),
        ("TOTAL SECTION UNIT WITHOUT SOLAR UNIT", "total_without_solar", soft_blue_fill, "000000", 38),
        ("MSEDCL UNIT (KWH)",                     "msedcl",              None,           "000000", 30),
        ("POWER (KVAH)",                           "kvah",                None,           "000000", 30),
        ("POWER FACTOR",                           "pf",                  pf_fill,        "000000", 30),
    ]

    for label, key, row_fill, txt_color, r_height in summary_rows:
        ws.cell(current_row, 1).border = border
        
        # Apply the newly tuned row height
        ws.row_dimensions[current_row].height = r_height 

        c2 = ws.cell(current_row, 2, label)
        c2.font = Font(bold=True, color="000000") 
        c2.border = border
        c2.alignment = center 

        for i, rec in enumerate(records):
            col = i + 3
            if key == "total_with_solar":
                col_l = openpyxl.utils.get_column_letter(col)
                parts = '+'.join([f'{col_l}{r}' for r in subtotal_row_nums]) if subtotal_row_nums else '0'
                dg_row = dg_set_row if dg_set_row else (current_row - 1)
                val = f'=({parts})+{col_l}{dg_row}'
            elif key == "total_without_solar":
                col_l = openpyxl.utils.get_column_letter(col)
                parts = '+'.join([f'{col_l}{r}' for r in subtotal_row_nums]) if subtotal_row_nums else '0'
                dg_row = dg_set_row if dg_set_row else (current_row - 1)
                solar_ref = f'{col_l}{solar_row_num}' if solar_row_num else '0'
                val = f'=({parts}+{col_l}{dg_row})-{solar_ref}'
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
            if row_fill: c3.fill = row_fill 
            c3.font = Font(bold=True, color=txt_color) 
            c3.border = border
            c3.alignment = center

        if key != "pf":
            fc = openpyxl.utils.get_column_letter(3)
            lc = openpyxl.utils.get_column_letter(2 + len(records))
            ws.cell(current_row, total_col, f"=SUM({fc}{current_row}:{lc}{current_row})")
            
        if row_fill: ws.cell(current_row, total_col).fill = row_fill
        ws.cell(current_row, total_col).font = Font(bold=True, color=txt_color)
        ws.cell(current_row, total_col).border = border
        
        # 👇 ADDED THIS LINE: Forces the Total calculation to sit dead-center in the box
        ws.cell(current_row, total_col).alignment = center 
        
        current_row += 1

    # Column widths
    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 28  # Tuned so the text wraps identically to the original
    for i in range(len(records)):
        col_letter = openpyxl.utils.get_column_letter(i + 3)
        ws.column_dimensions[col_letter].width = 14
    ws.column_dimensions[openpyxl.utils.get_column_letter(total_col)].width = 14

    # Row heights for the top headers
    ws.row_dimensions[1].height = 25
    ws.row_dimensions[2].height = 20
    ws.row_dimensions[3].height = 30

    # 👇 ── DIESEL / DG SECTION ── 👇
    diesel_start = ws.max_row + 2  # leave one blank row

    # Header row
    diesel_headers = ['DATE', 'O/P STOCK (Ltr)', 'DIESEL RECEIVED', 
                      'D.G. CONSUMPTION', 'OTHER CONSUMPTION', 
                      'DETAILS', 'D.G. UNITS', 'C/L STOCK (Ltr)']
    for col_idx, h in enumerate(diesel_headers, 1):
        c = ws.cell(diesel_start, col_idx, h)
        c.font = Font(bold=True)
        # Exact pale peach/pink from the original Excel sheet
        c.fill = PatternFill('solid', fgColor='FCE4D6') 
        c.border = border
        c.alignment = center
    ws.row_dimensions[diesel_start].height = 30

    # Data rows — one per day
    prev_closing = None
    for idx, rec in enumerate(records):
        dr = diesel_start + 1 + idx
        d_open = rec.get('diesel_opening_stock') or prev_closing or 0
        d_recv = rec.get('diesel_received') or 0
        d_cons = rec.get('diesel_consumed') or 0
        d_other = 0  # other_consumption not stored yet
        d_gen = rec.get('dg_generated_units') or 0
        d_reason = rec.get('dg_reason') or ''
        d_close = d_open + d_recv - d_cons - d_other
        
        # Safely format the date string
        current_date = rec.get('reading_date')
        if current_date and hasattr(current_date, 'strftime'):
            date_str = current_date.strftime("%d/%m/%Y")
        else:
            date_str = str(current_date)[:10] if current_date else ''

        row_vals = [
            date_str,
            d_open, d_recv, d_cons, d_other, d_reason, d_gen, d_close
        ]
        for col_idx, val in enumerate(row_vals, 1):
            c = ws.cell(dr, col_idx, val)
            c.border = border
            c.alignment = center

        c = ws.cell(dr, 8, f'=(B{dr}+IF(C{dr}="",0,C{dr}))-(IF(D{dr}="",0,D{dr})+IF(E{dr}="",0,E{dr}))')
        c.border = border
        c.alignment = center
        c.font = Font(bold=True)
        
        prev_closing = d_close

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

        # Read from daily_entries (new system) first, fallback to daily_coal_steam
        import json
        entry_results = db.execute(text(
            "SELECT * FROM daily_entries WHERE entry_date::text LIKE :prefix ORDER BY entry_date ASC"
        ), {"prefix": prefix}).mappings().all()
        entry_records = [dict(r) for r in entry_results]

        # Also get old records
        old_results = db.execute(text(
            "SELECT * FROM daily_coal_steam WHERE report_date::text LIKE :prefix ORDER BY report_date ASC"
        ), {"prefix": prefix}).mappings().all()
        old_records = {str(dict(r)['report_date'])[:10]: dict(r) for r in old_results}

        # Merge — daily_entries takes priority
        records = []
        for er in entry_records:
            row = dict(er)
            date_key = str(row.get('entry_date'))[:10]
            row['report_date'] = row.get('entry_date')
            
            # Parse JSON arrays for avg values
            for field in ['feed_water_temps', 'fd_fan1_dampers', 'fd_fan2_dampers']:
                if row.get(field):
                    try: row[field] = json.loads(row[field])
                    except: row[field] = []
            
            # Use stored avg_fd1 as avg_feeding if no log entries
            if not row.get('avg_fd1'):
                fd1 = row.get('fd_fan1_dampers', [])
                fd1_vals = [x for x in fd1 if x is not None]
                row['avg_fd1'] = round(sum(fd1_vals)/len(fd1_vals), 2) if fd1_vals else None
            
            records.append(row)

        # If no daily_entries, fall back to old records
        if not records:
            records = [dict(r) for r in old_results]
            for r in records:
                r['report_date'] = r.get('report_date')

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

            # 👇 1. SMART DATA FETCH (Using pre-calculated daily entries) 👇
            current_date = str(rec.get('report_date') or rec.get('entry_date'))[:10]
            
            # 👇 DEFINITIONS MOVED HERE 👇
            arrival = (sf(rec.get('coal_arrival_indian'), 0) + sf(rec.get('coal_arrival_imported'), 0))
            thermic = sf(rec.get('coal_thermic'))
            opening = sf(rec.get('opening_coal_stock'))
            # 👆 ---------------------- 👆
            
            # Use stored steam values from daily_entries if available
            steam_sep_consumed = sf(rec.get('steam_sep_consumed'))
            steam_refl_consumed = sf(rec.get('steam_refl_consumed'))
            avg_fd1 = sf(rec.get('avg_fd1'))
            cs_ratio_stored = sf(rec.get('cs_ratio'))
            
            # Calculate from stored values
            steam_sep = steam_sep_consumed
            steam_ref = steam_refl_consumed
            total_steam = (steam_sep + steam_ref) if (steam_sep is not None and steam_ref is not None) else None
            avg_feeding = avg_fd1
            coal_for_steam = round(avg_feeding * 60 * 24) if avg_feeding else None
            actual_cs_ratio = cs_ratio_stored or 0
            
            # If cs_ratio not stored, calculate it
            if not actual_cs_ratio and total_steam and coal_for_steam and coal_for_steam > 0:
                actual_cs_ratio = round(total_steam / coal_for_steam, 3)
            
            # Coal SEP and REFL from formula
            if steam_sep and actual_cs_ratio > 0:
                sep = round(steam_sep / (actual_cs_ratio * 1000), 3)
            else:
                sep = sf(rec.get('coal_consumed_sep'))
            
            coal_for_steam_mt = round(coal_for_steam / 1000, 3) if coal_for_steam else None
            if coal_for_steam_mt and sep:
                ref_ = round(coal_for_steam_mt - sep, 3)
            else:
                ref_ = sf(rec.get('coal_consumed_refinery'))

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
    
    entry_date = data.get('entry_date')
    opening = 0  # Always auto-fetch — field is hidden from form
    
    # 👇 AUTO-FETCH YESTERDAY'S CLOSING 👇
    if entry_date:  # Always try to get yesterday's closing
        from datetime import datetime, timedelta
        from sqlalchemy import text
        try:
            prev_date = (datetime.strptime(entry_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
            prev = db.execute(text(
                "SELECT closing_stock FROM daily_entries WHERE entry_date::text = :d LIMIT 1"
            ), {"d": prev_date}).mappings().fetchone()
            if prev and prev['closing_stock']:
                opening = float(prev['closing_stock'])
        except Exception as e:
            pass
    # 👆 -------------------------------- 👆

    # Now calculate totals using the (potentially updated) opening value
    total_coal = sep + refl + thermic
    closing = opening + arrival_in + arrival_im - total_coal

    # Auto-calculate steam

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


@app.get("/daily-entry/date/{date}")
def get_daily_entry_by_date(date: str, db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)):
    import json
    result = db.execute(text(
        "SELECT * FROM daily_entries WHERE entry_date::text = :d LIMIT 1"
    ), {"d": date}).mappings().fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="No entry for this date")
    row = dict(result)
    for field in ['feed_water_temps', 'fd_fan1_dampers', 'fd_fan2_dampers']:
        if row.get(field):
            try: row[field] = json.loads(row[field])
            except: row[field] = []
    return row


# ─── HEALTH CHECK ─────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "Shalimar Plant Ops API is running", "version": "1.0.0"}
