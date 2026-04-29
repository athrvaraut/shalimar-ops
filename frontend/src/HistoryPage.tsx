import React, { useState, useEffect } from 'react';

interface Props { token: string; onBack: () => void; }

type Section = 'boiler' | 'power';

export default function HistoryPage({ token, onBack }: Props) {
  const [section, setSection] = useState<Section>('boiler');
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const API = 'https://shalimar-ops.onrender.com';
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const daysInMonth = new Date(year, month, 0).getDate();

  useEffect(() => {
    fetchData();
  }, [section, year, month]);

  const fetchData = async () => {
    setLoading(true);
    setSelectedDate(null);
    try {
      const endpoint = section === 'boiler'
        ? `/history/boiler?year=${year}&month=${month}`
        : `/history/power?year=${year}&month=${month}`;

      const res = await fetch(`${API}${endpoint}`, {
        headers: { 'Authorization': `Bearer ${token || localStorage.getItem('token') || ''}` }
      });
      const d = await res.json();
      // ADD THIS LINE:
      console.log("Backend Response:", d);
      setData(Array.isArray(d) ? d : []);
    } catch {
      setData([]);
    } finally {
      setLoading(false);
    }
  };

  const downloadMonthlyBoilerExcel = async () => {
    const res = await fetch(
      `https://shalimar-ops.onrender.com/export/monthly-coal/${year}/${month}`,
      { 
    headers: { 
      'Authorization': `Bearer ${localStorage.getItem('token') || ''}`,
      'Content-Type': 'application/json' 
    } 
  }
);
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = window.URL.createObjectURL(blob);
    a.download = `Boiler_Monthly_${year}_${month}.xlsx`; a.click();
  };

  const downloadMonthlyPowerExcel = async () => {
    const res = await fetch(
      `https://shalimar-ops.onrender.com/export/power-monthly/${year}/${month}`,
     { 
    headers: { 
      'Authorization': `Bearer ${localStorage.getItem('token') || ''}`,
      'Content-Type': 'application/json' 
    } 
  }
);
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = window.URL.createObjectURL(blob);
    a.download = `Power_Monthly_${year}_${month}.xlsx`; a.click();
  };

  // Group data by date
  const byDate: Record<string, any[]> = {};
  data.forEach(item => {
    const date = String(item.log_date || item.report_date || item.reading_date || '').slice(0, 10);
    if (!byDate[date]) byDate[date] = [];
    byDate[date].push(item);
  });

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={s.header}>
        <button onClick={onBack} style={s.backBtn}>← Back</button>
        <div>
          <div style={s.headerTitle}>Previous Data</div>
          <div style={s.headerSub}>Historical logs — filter by year, month, date</div>
        </div>
      </div>

      {/* Section tabs */}
      <div style={s.sectionTabs}>
        <button style={section === 'boiler' ? s.sTabActive : s.sTab} onClick={() => setSection('boiler')}>
          🔥 Boiler Log
        </button>
        <button style={section === 'power' ? s.sTabActive : s.sTab} onClick={() => setSection('power')}>
          ⚡ Power Log
        </button>
      </div>

      {/* Year + Month Navigation Bar */}
      <div style={s.filterBar}>
        <button style={s.arrowBtn} onClick={() => setYear(y => y - 1)}>◀</button>
        <span style={s.yearLabel}>{year}</span>
        <button style={s.arrowBtn} onClick={() => setYear(y => y + 1)}>▶</button>

        <div style={s.monthRow}>
          {['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'].map((m, i) => (
            <button key={m}
              style={month === i + 1 ? s.monthActive : s.monthBtn}
              onClick={() => setMonth(i + 1)}>
              {m}
            </button>
          ))}
        </div>
      </div>

      {/* Monthly Download Banner — clean full-width card */}
      <div style={s.downloadBanner}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 20 }}>{section === 'boiler' ? '🔥' : '⚡'}</span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#0f3460' }}>
              {section === 'boiler' ? 'Boiler Monthly Report' : 'Power Monthly Report'}
            </div>
            <div style={{ fontSize: 11, color: '#888', marginTop: 1 }}>
              {['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][month - 1]} {year} — all entries compiled
            </div>
          </div>
        </div>
        <button
          onClick={section === 'boiler' ? downloadMonthlyBoilerExcel : downloadMonthlyPowerExcel}
          style={s.downloadBtn}>
          📥 Download Monthly Excel
        </button>
      </div>

      {/* Calendar day grid */}
      <div style={s.calGrid}>
        {Array.from({ length: daysInMonth }, (_, i) => {
          const d = `${year}-${String(month).padStart(2, '0')}-${String(i + 1).padStart(2, '0')}`;
          const hasData = !!byDate[d];
          const isSelected = selectedDate === d;
          return (
            <button
              key={d}
              style={{
                ...s.dayBtn,
                background: isSelected ? '#0f3460'
                  : hasData ? '#dbeafe' : '#f8f9fa',
                color: isSelected ? '#fff'
                  : hasData ? '#1d4ed8' : '#aaa',
                border: hasData ? '1px solid #93c5fd' : '1px solid #e0e0e0',
                fontWeight: hasData ? 700 : 400,
              }}
              onClick={() => hasData && setSelectedDate(d)}
            >
              <div style={{ fontSize: 14 }}>{i + 1}</div>
              {hasData && (
                <div style={{ fontSize: 9, marginTop: 2 }}>
                  {byDate[d].length} {section === 'boiler' ? 'entries' : 'record'}
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* Selected day detail */}
      {selectedDate && byDate[selectedDate] && (
        <div style={s.detailPanel}>
          <div style={s.detailHeader}>
            📋 {selectedDate} — {byDate[selectedDate].length} entries
          </div>
          {selectedDate && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 10 }}>
              <button
                onClick={() => {
                  const url = section === 'boiler'
                    ? `https://shalimar-ops.onrender.com/export/daily-boiler/${selectedDate}`
                    : `https://shalimar-ops.onrender.com/export/power-monthly/${selectedDate.split('-')[0]}/${parseInt(selectedDate.split('-')[1])}`;
                  fetch(url, { headers: { 'Authorization': `Bearer ${token || localStorage.getItem('token') || ''}` } })
                    .then(r => r.blob()).then(blob => {
                      const a = document.createElement('a');
                      a.href = window.URL.createObjectURL(blob);
                      a.download = `${section}_${selectedDate}.xlsx`; a.click();
                    });
                }}
                style={{ background: '#10b981', color: '#fff', border: 'none', borderRadius: 8, padding: '8px 16px', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}
              >
                📥 Download Excel
              </button>
            </div>
          )}
          {section === 'boiler' && (
            <BoilerDetail entries={byDate[selectedDate]} />
          )}
          {section === 'power' && (
            <PowerDetail entries={byDate[selectedDate]} />
          )}
        </div>
      )}

      {!selectedDate && !loading && (
        <div style={s.hint}>
          {Object.keys(byDate).length > 0
            ? '👆 Click a highlighted day to see entries'
            : '📭 No data for this month'}
        </div>
      )}
    </div>
  );
}

function BoilerDetail({ entries }: { entries: any[] }) {
  const shifts = ['A', 'B', 'C'];
  return (
    <div>
      {shifts.map(shift => {
        const shiftEntries = entries.filter(e => e.shift === shift);
        if (shiftEntries.length === 0) return null;
        return (
          <div key={shift} style={d.shiftBlock}>
            <div style={d.shiftTitle}>Shift {shift}</div>
            {shiftEntries.map((e, i) => (
              <div key={i} style={d.entryRow}>
                <div style={d.timeLabel}>{String(e.log_time).slice(0, 5)}</div>
                <div style={d.paramGrid}>
                  <Param label="Steam Pr" value={e.steam_pressure} unit="KG/CM" />
                  <Param label="Drum Lvl" value={e.drum_water_level} unit="%" />
                  <Param label="Bed1 Top" value={e.bed1_top_temp} unit="°C" />
                  <Param label="Flue Gas" value={e.flue_gas_temp} unit="°C" />
                  <Param label="Feed Wtr" value={e.feed_water_temp} unit="°C" />
                  <Param label="Status" value={e.status?.toUpperCase()} unit="" />
                </div>
                {e.breakdown_problem && (
                  <div style={d.breakdown}>🚨 {e.breakdown_problem}</div>
                )}
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

function CoalDetail({ entries }: { entries: any[] }) {
  const e = entries[0];
  if (!e) return null;
  return (
    <div style={d.coalBlock}>
      <div style={d.row2}>
        <Param label="Opening Stock" value={e.opening_coal_stock} unit="MT" />
        <Param label="Closing Stock" value={e.closing_stock} unit="MT" />
        <Param label="Coal SEP" value={e.coal_consumed_sep} unit="MT" />
        <Param label="Coal REFL" value={e.coal_consumed_refinery} unit="MT" />
        <Param label="Total Steam" value={e.total_steam} unit="KG" />
        <Param label="C/S Ratio" value={e.cs_ratio} unit="" highlight />
      </div>
    </div>
  );
}

function PowerDetail({ entries }: { entries: any[] }) {
  const shifts = ['A', 'B', 'C'];
  return (
    <div>
      {shifts.map(shift => {
        const e = entries.find(x => x.shift === shift);
        if (!e) return null;
        return (
          <div key={shift} style={d.shiftBlock}>
            <div style={d.shiftTitle}>Shift {shift}</div>
            <div style={d.paramGrid}>
              <Param label="SEP" value={e.sep_units} unit="KWH" />
              <Param label="PREP" value={e.prep_units} unit="KWH" />
              <Param label="Solar" value={e.solar_units} unit="KWH" />
              <Param label="Boiler" value={e.boiler_units} unit="KWH" />
              <Param label="MSEDCL" value={e.msedcl_units} unit="KWH" />
              <Param label="PF" value={e.power_factor} unit="" />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Param({ label, value, unit, highlight }: any) {
  return (
    <div style={{ ...d.param, ...(highlight ? d.paramHL : {}) }}>
      <div style={d.pLabel}>{label}</div>
      <div style={{ ...d.pValue, color: highlight ? '#059669' : '#111' }}>
        {value != null ? `${value} ${unit}` : '—'}
      </div>
    </div>
  );
}

// Styles
const s: Record<string, React.CSSProperties> = {
  page: { minHeight: '100vh', background: '#f0f2f5', fontFamily: '-apple-system, sans-serif' },
  header: { background: '#0f3460', color: '#fff', padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 16, position: 'sticky', top: 0, zIndex: 10 },
  headerTitle: { fontSize: 16, fontWeight: 700 },
  headerSub: { fontSize: 11, opacity: 0.75, marginTop: 2 },
  backBtn: { background: 'rgba(255,255,255,0.15)', color: '#fff', border: '1px solid rgba(255,255,255,0.3)', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: 13 },
  sectionTabs: { display: 'flex', background: '#fff', borderBottom: '1px solid #e5e7eb', overflowX: 'auto' as const },
  sTab: { padding: '12px 20px', border: 'none', background: 'none', cursor: 'pointer', fontSize: 13, color: '#666', whiteSpace: 'nowrap' as const, borderBottom: '2px solid transparent' },
  sTabActive: { padding: '12px 20px', border: 'none', background: 'none', cursor: 'pointer', fontSize: 13, color: '#0f3460', fontWeight: 700, whiteSpace: 'nowrap' as const, borderBottom: '2px solid #0f3460' },
  filterBar: { background: '#fff', padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' as const, borderBottom: '1px solid #e5e7eb' },
  downloadBanner: {background: '#fff',margin: '12px 16px 0',borderRadius: 12,padding: '14px 18px',display: 'flex',justifyContent: 'space-between',alignItems: 'center',boxShadow: '0 1px 4px rgba(0,0,0,0.08)',border: '1px solid #e5e7eb',maxWidth: 760,marginLeft: 'auto',marginRight: 'auto',},
  downloadBtn: {background: '#0f3460',color: '#fff',border: 'none',borderRadius: 8,padding: '9px 18px',cursor: 'pointer',fontSize: 13,fontWeight: 700,whiteSpace: 'nowrap' as const,boxShadow: '0 2px 6px rgba(15,52,96,0.3)',},
  arrowBtn: { background: '#f0f2f5', border: '1px solid #e0e0e0', borderRadius: 6, padding: '6px 10px', cursor: 'pointer', fontSize: 14 },
  yearLabel: { fontSize: 16, fontWeight: 700, minWidth: 50, textAlign: 'center' as const },
  monthRow: { display: 'flex', gap: 4, flexWrap: 'wrap' as const },
  monthBtn: { padding: '4px 8px', border: '1px solid #e0e0e0', borderRadius: 6, background: '#f8f9fa', cursor: 'pointer', fontSize: 12, color: '#555' },
  monthActive: { padding: '4px 8px', border: '1px solid #0f3460', borderRadius: 6, background: '#0f3460', cursor: 'pointer', fontSize: 12, color: '#fff', fontWeight: 700 },
  calGrid: { display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 6, padding: '14px 16px', maxWidth: 500, margin: '0 auto' },
  dayBtn: { border: 'none', borderRadius: 8, padding: '8px 4px', cursor: 'pointer', textAlign: 'center' as const, minHeight: 52 },
  detailPanel: { maxWidth: 720, margin: '0 auto', padding: '0 16px 40px' },
  detailHeader: { fontSize: 14, fontWeight: 700, color: '#0f3460', padding: '12px 0 8px', borderBottom: '2px solid #0f3460', marginBottom: 12 },
  hint: { textAlign: 'center' as const, color: '#888', fontSize: 14, padding: '30px 0' },
};

const d: Record<string, React.CSSProperties> = {
  shiftBlock: { background: '#fff', borderRadius: 10, padding: '12px 14px', marginBottom: 10, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' },
  shiftTitle: { fontSize: 12, fontWeight: 700, color: '#0f3460', marginBottom: 10, textTransform: 'uppercase' as const },
  entryRow: { borderBottom: '1px solid #f0f0f0', paddingBottom: 10, marginBottom: 10 },
  timeLabel: { fontSize: 11, color: '#888', marginBottom: 6 },
  paramGrid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 },
  row2: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 },
  coalBlock: { background: '#fff', borderRadius: 10, padding: '14px', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' },
  param: { background: '#f8f9fa', borderRadius: 6, padding: '7px 10px' },
  paramHL: { background: '#d1fae5' },
  pLabel: { fontSize: 10, color: '#888', textTransform: 'uppercase' as const, marginBottom: 3 },
  pValue: { fontSize: 12, fontWeight: 600 },
  breakdown: { background: '#fff0f0', color: '#dc2626', padding: '6px 10px', borderRadius: 6, fontSize: 12, marginTop: 6 },
};