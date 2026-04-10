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

app = FastAPI(title="Shalimar Plant Ops", version="1.0.0")

# CORS — allow React frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001"  # Add this line!
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
    # Validation — flag if out of safe range
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
        status="pending"
    )
    db.add(log)
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
    ).all()
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
    report = models.PowerConsumption(
        reading_date=data.reading_date,
        entered_by=current_user.id,
        sep_units=data.sep_units,
        prep_units=data.prep_units,
        solar_units=data.solar_units,
        silo_units=data.silo_units,
        doc_units=data.doc_units,
        dsilo_units=data.dsilo_units,
        acm_units=data.acm_units,
        boiler_units=data.boiler_units,
        chp_units=data.chp_units,
        dm_units=data.dm_units,
        ug_tank_units=data.ug_tank_units,
        refinery_units=data.refinery_units,
        etp_units=data.etp_units,
        packing_units=data.packing_units,
        admin_units=data.admin_units,
        dg_units=data.dg_units,
        msedcl_units=data.msedcl_units,
        power_kvah=data.power_kvah,
        power_factor=data.power_factor,
        diesel_opening_stock=data.diesel_opening_stock,
        diesel_received=data.diesel_received,
        diesel_consumed=data.diesel_consumed,
        dg_generated_units=data.dg_generated_units,
        dg_reason=data.dg_reason,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"message": "Power report submitted", "id": report.id}

@app.get("/export/daily-boiler/{date}")
def export_daily_boiler_excel(
    date: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    report = db.query(models.DailyCoalSteam).filter(
        models.DailyCoalSteam.report_date == date
    ).first()

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
            report.opening_coal_stock, report.coal_arrival_indian,
            report.coal_arrival_imported, report.coal_consumed_sep,
            report.coal_consumed_refinery, report.coal_thermic,
            report.total_coal_consumed, report.closing_stock, ""
        ]
        for i, v in enumerate(coal_vals, 2):
            cell(5, i, v, align=center, b=border)

    ws.append([])  # row 6 empty

    # ROW 7 - Coal bunker
    cell(7, 2, "PERTICULAR", bold, align=left, b=border)
    cell(7, 4, "COAL IN BUNKER (%)", bold, blue_fill, center, border)
    cell(7, 5, "REMARKS", bold, blue_fill, center, border)
    cell(7, 9, "COAL FOR STEAM", bold, align=center, b=border)

    cell(8, 2, "COAL BUNKER STATUS", bold, align=left, b=border)
    cell(8, 4, report.coal_bunker_pct if report else None, align=center, b=border)
    cell(8, 9, date_display, align=center, b=border)

    cell(9, 2, "STEAM PRESSURE PROBLEM", bold, align=left, b=border)
    sp_val = "NO" if (report and report.steam_pressure_ok) else "YES ⚠️"
    sp_fill = green_fill if (report and report.steam_pressure_ok) else PatternFill("solid", fgColor="FADBD8")
    cell(9, 4, sp_val, Font(bold=True), sp_fill, center, border)

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
        cell(12, i, h, bold, blue_fill, center, border)

    if report:
        cell(13, 2, report.steam_sep_opening, align=center, b=border)
        cell(13, 3, report.steam_sep_closing, align=center, b=border)
        cell(13, 5, report.steam_sep_consumed, Font(bold=True), yellow_fill, center, border)
        cell(13, 6, report.feed_water_temp, align=center, b=border)

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
        cell(16, i, h, bold, blue_fill, center, border)

    if report:
        cell(17, 2, report.steam_refl_opening, align=center, b=border)
        cell(17, 3, report.steam_refl_closing, align=center, b=border)
        cell(17, 5, report.steam_refl_consumed, Font(bold=True), yellow_fill, center, border)
        cell(17, 6, report.total_steam, Font(bold=True), yellow_fill, center, border)
        cs_fill = green_fill if (report.cs_ratio and 5.0 <= report.cs_ratio <= 5.6) else PatternFill("solid", fgColor="FADBD8")
        cell(17, 8, report.cs_ratio, Font(bold=True), cs_fill, center, border)

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

# ─── HEALTH CHECK ─────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "Shalimar Plant Ops API is running", "version": "1.0.0"}