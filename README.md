# 🏭 Shalimar Plant Ops

> **Industrial Operations Management System**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-shalimar--ops--slxa.vercel.app-blue?style=for-the-badge&logo=vercel)](https://shalimar-ops-slxa.vercel.app)
[![Backend](https://img.shields.io/badge/API-shalimar--ops.onrender.com-green?style=for-the-badge&logo=fastapi)](https://shalimar-ops.onrender.com/docs)
[![React](https://img.shields.io/badge/React-TypeScript-61DAFB?style=for-the-badge&logo=react)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Python-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=for-the-badge&logo=supabase)](https://supabase.com/)

---

## 📌 Overview

A full-stack web application built to **digitize and automate** the daily operations of a manufacturing plant's boiler section and power department. Previously, operators filled physical log books by hand and engineers manually compiled monthly Excel reports — this system replaces all of that.

The app allows shift operators to submit readings from their phones, and the HOD (Head of Department) to review, download daily/monthly Excel reports, and monitor the plant in real time.

---

## ✨ Features

### 🔥 Boiler Log Entry
- **Shift-based time slots** — Shift A (7AM–3PM), Shift B (3PM–11PM), Shift C (11PM–7AM)
- Records 20+ parameters per entry: Steam Pressure, Steam Flow SEP/REFL, Drum Water Level, Bed Temperatures, Flue Gas Temp, Fan Dampers, Coal Feed Hz, CBD/IBD reports
- **Duplicate prevention** — blocks re-entry for same shift/time; shows "Update Entry" option for corrections
- **Safe range alerts** — warns operator if readings are outside safe thresholds (e.g. steam pressure < 6 or > 12 KG/CM)

### 🪨 Daily Coal & Steam Summary
- Embedded inside Boiler Log Entry (fills once per day, any shift)
- **Auto-fills SEP/REFL steam opening/closing** from the day's first/last boiler log entries
- **Auto-fetches previous day's closing coal stock** as today's opening stock
- **Locks after first submission** — shows green banner + Modify button to prevent accidental overwrite

### ⚡ Power Consumption Report
- Section-wise KWH entry: SEP, PREP, Solar, Silo, DOC, D-Silo, ACM, Boiler, CHP, DM Plant, UG Tank, Refinery, ETP, Packing, Admin, DG Set
- **Auto-calculates Power Factor** from MSEDCL KWH ÷ kVAh
- Live summary: Total KWH, Solar KWH, MSEDCL KWH, DG KWH, Solar Savings %
- DG Set & Diesel tracking: opening stock, received, consumed, units generated

### 📊 HOD Dashboard
- **Today's entries only** — Boiler and Power tabs
- Click any entry to **expand all parameters** inline
- One-click **Today's Boiler Excel** download (all shifts compiled into one daily report)
- **Monthly Power Excel** download button
- Auto-logout on expired token (401 handling)

### 📁 Previous Data
- Calendar date picker per month/year
- Click any date → view all entries for that day
- **Daily Boiler Excel** download per selected date
- **Monthly Boiler Excel** and **Monthly Power Excel** download buttons per month
- Both Boiler Log and Power Log sections

### 📥 Excel Export Engine
- **Daily Boiler Report** — matches the exact format used by the plant (rows: Coal Stock Sheet, Bunker Status, Steam Pressure, SEP Steam Flow, REFL Steam Flow)
  - Auto-calculates: Steam Consumption, Feed Water Temp (avg), Average Feeding Hz, Coal For Steam, C/S Ratio, Total Steam, all coal values
- **Monthly Boiler Coal Report** — 14-column monthly format matching company standard (Shalimar Nutrients Pvt. Ltd. header, all coal/steam KPIs, TOTAL row with formulas)
- **Monthly Power Report** — horizontal cumulative format (sections as rows, each date as column, subtotals per group, TOTAL column, DG section at bottom)

### 🔐 Role-Based Access Control
- Roles: `operator`, `assistant`, `hod`
- HOD can create users, view all data, download reports
- Operators can submit entries for their shift

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18, TypeScript, CSS-in-JS (inline styles) |
| **Backend** | FastAPI (Python 3.11), SQLAlchemy ORM |
| **Database** | Supabase (PostgreSQL) |
| **Authentication** | JWT (python-jose), bcrypt password hashing |
| **Excel Generation** | openpyxl |
| **Frontend Deploy** | Vercel |
| **Backend Deploy** | Render (free tier) |

---

## 🏗 Architecture

```
User (Phone / Browser)
        ↓
  Vercel — React Frontend (TypeScript)
        ↓  REST API calls (JWT Bearer)
  Render — FastAPI Backend (Python)
        ↓  SQLAlchemy ORM
  Supabase — PostgreSQL Database
```

---

## 📁 Project Structure

```
shalimar-ops/
├── app/
│   ├── __init__.py
│   ├── auth.py          # JWT auth, password hashing, role guards
│   ├── database.py      # SQLAlchemy engine + session
│   ├── main.py          # All API routes + Excel export logic
│   ├── models.py        # ORM models (User, BoilerLogEntry, DailyCoalSteam, PowerConsumption, DailyEntry)
│   └── schemas.py       # Pydantic request/response schemas
├── frontend/
│   └── src/
│       ├── App.tsx               # Root component, login, page routing
│       ├── BoilerLogForm.tsx     # Boiler log entry form
│       ├── PowerConsumptionForm.tsx  # Power consumption form
│       ├── HODDashboard.tsx      # HOD review + Excel download
│       ├── HistoryPage.tsx       # Previous data browser
│       └── DailyCoalSteamForm.tsx    # (legacy, merged into boiler form)
├── create_hod.py        # Script to seed HOD admin user
├── requirements.txt
└── .env                 # DATABASE_URL, SECRET_KEY
```

---

## 🗄 Database Tables

| Table | Purpose |
|-------|---------|
| `users` | User accounts with roles |
| `boiler_log_entries` | Shift-wise boiler readings (20+ fields) |
| `daily_entries` | Daily coal/steam summary with JSON arrays for hourly readings |
| `daily_coal_steam` | Legacy daily coal/steam reports |
| `power_consumption` | Daily power section-wise KWH data |

---

## 🚀 Local Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Supabase account (free tier works)

### Backend

```bash
# Clone the repo
git clone https://github.com/athrvaraut/shalimar-ops.git
cd shalimar-ops

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "DATABASE_URL=postgresql://user:password@host:5432/postgres" > .env
echo "SECRET_KEY=your-secret-key-here" >> .env

# Run backend
uvicorn app.main:app --reload
# API docs at http://localhost:8000/docs
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Create .env
echo "REACT_APP_API_URL=http://localhost:8000" > .env

# Start dev server
npm start
# App at http://localhost:3000
```

### Create HOD Admin User

```bash
# After backend is running
python create_hod.py
# Default: username=hod_admin, password=Shalimar2024
```

---

## 🔌 Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Login, returns JWT token |
| POST | `/boiler-log` | Submit boiler shift entry |
| PUT | `/boiler-log/{id}/update` | Update existing entry |
| GET | `/boiler-log/today` | Today's boiler entries |
| POST | `/power-consumption` | Submit power report |
| GET | `/history/boiler?year=&month=` | Monthly boiler history |
| GET | `/history/power?year=&month=` | Monthly power history |
| GET | `/export/daily-boiler/{date}` | Download daily boiler Excel |
| GET | `/export/monthly-coal/{year}/{month}` | Download monthly boiler Excel |
| GET | `/export/power-monthly/{year}/{month}` | Download monthly power Excel |

Full interactive docs: [shalimar-ops.onrender.com/docs](https://shalimar-ops.onrender.com/docs)

---

## 📊 Excel Report Formats

### Daily Boiler Report
Matches the plant's physical log format exactly:
- Coal Consumption & Stock Sheet (Opening → Arrival → SEP → REFL → Thermic → Total → Closing)
- Coal Bunker Status, Steam Pressure Problem flag
- SEP Steam Flow (Opening/Closing/Consumption/Feed Water Avg/Average Feeding Hz)
- REFL Steam Flow (Opening/Closing/Consumption/Total Steam/C/S Ratio)
- All values auto-calculated from boiler log entries

### Monthly Boiler Coal Report
14-column monthly summary with TOTAL row:
`DATE | Opening Stock | Arrival | Coal SEP | Coal REF | Total for Steam | Thermic | Total Consumption | Closing Stock | Avg Ash | Steam SEP | Steam REF | Total Steam | C/S Ratio`

### Monthly Power Report
Horizontal format — sections as rows, each date as a column:
- Group subtotals (SEP group, ACM group, Refinery group, Admin group)
- Summary rows: Total With Solar, Total Without Solar, MSEDCL Units, kVAh, Power Factor
- DG/Diesel section at bottom with daily tracking

---

## 🏢 About This Project

This system was built for **Shalimar Nutrients Pvt. Ltd.**, a soya processing and refining company in Sonkhamb, Katol, Nagpur. The plant runs 3 shifts daily, 365 days/year.

Before this app, operators filled handwritten log books and the HOD manually compiled monthly Excel reports — sometimes hours of work per month. Now, operators submit from their phones in minutes, and monthly reports are generated instantly.

> Built as a real-world production tool, not just a demo — it's live and used daily.


*Made with by [AR](https://github.com/athrvaraut)*
