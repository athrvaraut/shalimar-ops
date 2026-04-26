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
        "http://localhost:3001",
        "https://shalimar-ops-slxa.vercel.app",  # ← ADD THIS
        "https://*.vercel.app",                   # ← ADD THIS
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
        status="approved"
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
        
        # 👇 PASTE THE NEW VOLTAGE FIELDS HERE 👇
        voltage_r_morning=data.voltage_r_morning,
        voltage_y_morning=data.voltage_y_morning,
        voltage_b_morning=data.voltage_b_morning,
        voltage_r_evening=data.voltage_r_evening,
        voltage_y_evening=data.voltage_y_evening,
        voltage_b_evening=data.voltage_b_evening,
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
        "SELECT * FROM power_consumption "
        "WHERE EXTRACT(YEAR FROM reading_date) = :year "
        "AND EXTRACT(MONTH FROM reading_date) = :month "
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
        if hasattr(date_val, 'strftime'):
            date_str = date_val.strftime("%d/%m/%Y")
        else:
            date_str = str(date_val)[:10]
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
    for i in range(len(records) + 1):
        c = ws.cell(3, i + 3, "UNIT (KWH)")
        c.font = bold; c.fill = blue_fill; c.border = border; c.alignment = center
    ws.row_dimensions[3].height = 25

    # Section definitions
    sections = [
        ("1", "SEP", "sep_units"),
        ("2", "PREP", "prep_units"),
        ("", "SOLAR", "solar_units"),
        ("3", "SILO", "silo_units"),
        ("4", "DOC", "doc_units"),
        ("5", "D-SILO", "dsilo_units"),
        ("", "", None),  # subtotal row
        ("6", "ACM/ SOYA CHUNKS", "acm_units"),
        ("7", "BOILER", "boiler_units"),
        ("8", "CHP", "chp_units"),
        ("9", "DM", "dm_units"),
        ("", "UG TANK", "ug_tank_units"),
        ("", "", None),  # subtotal row
        ("10", "REFINERY", "refinery_units"),
        ("11", "ETP/ACID/MVR", "etp_units"),
        ("12", "PACKING", "packing_units"),
        ("", "", None),  # subtotal row
        ("13", "ADMIN", "admin_units"),
        ("15", "MISCELLENIOUS", None),
        ("", "", None),  # subtotal row
        ("16", "DG SET UNIT", "dg_units"),
    ]

    data_rows_start = 4
    section_row_map = {}  # field -> row number for formula building

    current_row = data_rows_start
    for sr, name, field in sections:
        if field is None and name == "":
            # Subtotal row - skip for now
            current_row += 1
            continue
        ws.cell(current_row, 1, sr).border = border; ws.cell(current_row, 1).alignment = center
        ws.cell(current_row, 2, name).font = bold if sr else Font(); ws.cell(current_row, 2).border = border
        
        row_total = 0
        for i, rec in enumerate(records):
            val = rec.get(field, 0) or 0 if field else 0
            c = ws.cell(current_row, i + 3, val)
            c.border = border; c.alignment = center
            row_total += val
        
        # Total column
        if len(records) > 0:
            first_data_col = openpyxl.utils.get_column_letter(3)
            last_data_col = openpyxl.utils.get_column_letter(2 + len(records))
            ws.cell(current_row, total_col, f"=SUM({first_data_col}{current_row}:{last_data_col}{current_row})")
        ws.cell(current_row, total_col).border = border
        ws.cell(current_row, total_col).alignment = center
        
        if field:
            section_row_map[field] = current_row
        current_row += 1

    # Summary rows
    summary_items = [
        ("TOTAL UNIT WITH SOLAR GEN. UNIT", True),
        ("TOTAL SECTION UNIT WITHOUT SOLAR UNIT", True),
        ("MSDCL UNIT (KWH)", False),
        ("POWER (KVAH)", False),
        ("POWER FACTOR", False),
    ]

    for label, is_calc in summary_items:
        c = ws.cell(current_row, 2, label)
        c.font = bold
        for i, rec in enumerate(records):
            col = i + 3
            if label == "MSDCL UNIT (KWH)":
                val = rec.get('msedcl_units', 0) or 0
            elif label == "POWER (KVAH)":
                val = rec.get('power_kvah', 0) or 0
            elif label == "POWER FACTOR":
                kwh = rec.get('msedcl_units', 0) or 0
                kvah = rec.get('power_kvah', 0) or 0
                val = round(kwh / kvah, 4) if kvah and kvah > 0 else 0
            elif label == "TOTAL UNIT WITH SOLAR GEN. UNIT":
                val = sum((rec.get(f[2], 0) or 0) for f in sections if f[2] and f[2] != 'None')
            elif label == "TOTAL SECTION UNIT WITHOUT SOLAR UNIT":
                val = sum((rec.get(f[2], 0) or 0) for f in sections if f[2] and f[2] != 'solar_units')
            else:
                val = 0
            c2 = ws.cell(current_row, col, val)
            c2.fill = yellow_fill; c2.font = Font(bold=True); c2.border = border; c2.alignment = center
        # Total col
        if label not in ("POWER FACTOR",):
            fc = openpyxl.utils.get_column_letter(3)
            lc = openpyxl.utils.get_column_letter(2 + len(records))
            ws.cell(current_row, total_col, f"=SUM({fc}{current_row}:{lc}{current_row})")
        ws.cell(current_row, total_col).fill = yellow_fill
        ws.cell(current_row, total_col).border = border
        current_row += 1

    # DG/Diesel section
    current_row += 1
    dg_headers = ["DATE", "O/P STOCK (Ltr)", "DIESEL RECEIVED", "D.G. CONSUMPTION", "DETAILS", "D.G. UNITS", "C/L STOCK (Ltr)"]
    for i, h in enumerate(dg_headers, 1):
        c = ws.cell(current_row, i, h)
        c.font = bold; c.fill = blue_fill; c.border = border; c.alignment = center
    current_row += 1

    prev_closing = None
    for rec in records:
        date_val = rec.get('reading_date')
        date_str = date_val.strftime("%d/%m/%Y") if hasattr(date_val, 'strftime') else str(date_val)[:10]
        opening = rec.get('diesel_opening_stock', 0) or 0
        received = rec.get('diesel_received', 0) or 0
        consumed = rec.get('diesel_consumed', 0) or 0
        dg_units = rec.get('dg_generated_units', 0) or 0
        closing = opening + received - consumed
        reason = rec.get('dg_reason', '') or ''
        
        row_data = [date_str, opening, received, consumed, reason, dg_units, closing]
        for i, val in enumerate(row_data, 1):
            c = ws.cell(current_row, i, val)
            c.border = border; c.alignment = center
        current_row += 1

    # Column widths
    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 26
    for i in range(3, len(records) + 4):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = 12

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"Power_Consumption_{month_name}_{year}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/export/monthly-coal/{year}/{month}")
def export_monthly_coal_excel(
    year: int, month: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    import calendar
    from datetime import date, datetime

    month_name = datetime(year, month, 1).strftime("%b").upper()
    reports = db.query(models.DailyCoalSteam).filter(
        models.DailyCoalSteam.report_date >= f"{year}-{month:02d}-01",
        models.DailyCoalSteam.report_date <= f"{year}-{month:02d}-{calendar.monthrange(year,month)[1]}"
    ).order_by(models.DailyCoalSteam.report_date).all()

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
        date_val = r.report_date
        total_coal = r.total_coal_consumed or 0
        total_steam = r.total_steam or 0
        total_coal_sum += total_coal; total_steam_sum += total_steam

        row_data = [
            date_val, r.opening_coal_stock,
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
def history_boiler(
    year: int, month: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    from sqlalchemy import text, extract
    results = db.execute(text(
        "SELECT * FROM boiler_log_entries "
        "WHERE EXTRACT(YEAR FROM log_date) = :year "
        "AND EXTRACT(MONTH FROM log_date) = :month "
        "ORDER BY log_date ASC, log_time ASC"
    ), {"year": year, "month": month}).mappings().all()
    return [dict(r) for r in results]

@app.get("/history/coal")
def history_coal(
    year: int, month: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    from sqlalchemy import text
    results = db.execute(text(
        "SELECT * FROM daily_coal_steam "
        "WHERE EXTRACT(YEAR FROM report_date) = :year "
        "AND EXTRACT(MONTH FROM report_date) = :month "
        "ORDER BY report_date ASC"
    ), {"year": year, "month": month}).mappings().all()
    return [dict(r) for r in results]

@app.get("/history/power")
def history_power(
    year: int, month: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    from sqlalchemy import text
    results = db.execute(text(
        "SELECT * FROM power_consumption "
        "WHERE EXTRACT(YEAR FROM reading_date) = :year "
        "AND EXTRACT(MONTH FROM reading_date) = :month "
        "ORDER BY reading_date ASC"
    ), {"year": year, "month": month}).mappings().all()
    return [dict(r) for r in results]

# ─── HEALTH CHECK ─────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "Shalimar Plant Ops API is running", "version": "1.0.0"}