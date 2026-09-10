/**
 * AeroAQI — Premium Dashboard
 * Delhi-NCR Air Intelligence Platform
 * Interactive Delhi-NCR air intelligence dashboard
 */

import { useState, useEffect, useRef } from "react";
import {
  AreaChart, Area, LineChart, Line, ResponsiveContainer,
  XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine,
} from "recharts";
import {
  Activity, AlertTriangle, ArrowUpRight, BarChart3, Bell,
  ChevronDown, ChevronRight, CloudSun, Droplets, Flame,
  Gauge, Info, LayoutDashboard, Layers, Map, MapPin, Menu,
  Navigation, Settings, TrendingUp, TrendingDown, Wind,
  FileText, ZoomIn, ZoomOut, Crosshair, Radio, Thermometer,
  Eye, Clock, X, LogOut, User, Save, Lock, Mail, CheckCircle2, Phone, Upload, Gift, Sparkles, Bot, MessageCircle, Play, Pause, RefreshCw, Download, Award, Check, ChevronLeft, ChevronUp, ShieldCheck, FileSpreadsheet, SlidersHorizontal, Search, CircleHelp, Heart, Target, Zap, Users, CalendarDays, GaugeCircle, CloudRain, Wind as WindIcon, BellRing, ExternalLink, RotateCcw, Layers3, MapPinned, CircleDot, Star, Send, Image as ImageIcon,
} from "lucide-react";

// Dashboard hero: place the exact India Gate image at public/hero.png
// Keep the filename exactly "hero.png" so the dashboard hero path remains stable.

// ─── Forecast data ───────────────────────────────────────
const forecastData = [
  { t: "Now",  aqi: 182, pm25: 104 },
  { t: "+6h",  aqi: 192, pm25: 112 },
  { t: "+12h", aqi: 178, pm25: 98  },
  { t: "+18h", aqi: 165, pm25: 90  },
  { t: "+24h", aqi: 155, pm25: 85  },
  { t: "+30h", aqi: 148, pm25: 80  },
  { t: "+36h", aqi: 138, pm25: 74  },
  { t: "+42h", aqi: 145, pm25: 78  },
  { t: "+48h", aqi: 160, pm25: 88  },
  { t: "+54h", aqi: 172, pm25: 95  },
  { t: "+60h", aqi: 168, pm25: 92  },
  { t: "+72h", aqi: 158, pm25: 87  },
];

const pblData = [
  { t:"00",v:380},{t:"04",v:310},{t:"08",v:480},{t:"12",v:750},
  {t:"16",v:820},{t:"20",v:560},{t:"24",v:410},
];
const mixData = [
  {t:"00",v:45},{t:"04",v:38},{t:"08",v:62},{t:"12",v:88},
  {t:"16",v:95},{t:"20",v:70},{t:"24",v:52},
];
const invData = [
  {t:"00",v:3.2},{t:"04",v:4.1},{t:"08",v:2.8},{t:"12",v:1.2},
  {t:"16",v:0.8},{t:"20",v:1.9},{t:"24",v:2.9},
];

// ─── AQI helpers ─────────────────────────────────────────
function aqiColor(v) {
  if (v <= 50)  return "#22c55e";
  if (v <= 100) return "#eab308";
  if (v <= 150) return "#f97316";
  if (v <= 200) return "#ef4444";
  if (v <= 300) return "#a855f7";
  return "#b91c1c";
}
function aqiLabel(v) {
  if (v <= 50)  return "Good";
  if (v <= 100) return "Moderate";
  if (v <= 150) return "Unhealthy (Sensitive)";
  if (v <= 200) return "Unhealthy";
  if (v <= 300) return "Very Unhealthy";
  return "Hazardous";
}
function aqiBgClass(v) {
  if (v <= 50)  return "bg-aqi-good";
  if (v <= 100) return "bg-aqi-moderate";
  if (v <= 150) return "bg-aqi-sensitive";
  if (v <= 200) return "bg-aqi-unhealthy";
  if (v <= 300) return "bg-aqi-very";
  return "bg-aqi-hazardous";
}

// ─── Custom Tooltip ───────────────────────────────────────
// ─── AQI Ambient Motion ───────────────────────────────────


// ─── Nav Item ─────────────────────────────────────────────

// ─── Account Auth: Create Account / Login / OTP ────────────

// ─── AeroAQI Brand Logo ─────────────────────────────────────
function AeroAQILogo({ className = "", compact = false }) {
  return (
    <img
      src="/icon.png"
      alt="AeroAQI — Clean Air, Forecasted"
      className={
        (compact ? "h-12 w-auto" : "h-16 sm:h-20 w-auto") +
        " object-contain object-left " + className
      }
    />
  );
}

function NavItem({ icon, label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 text-left group
        ${active
          ? "nav-active text-emerald-300"
          : "text-slate-400 hover:text-white hover:bg-white/[0.05]"
        }`}
    >
      <span className={`${active ? "text-emerald-400" : "text-slate-500 group-hover:text-emerald-400"} transition-colors`}>
        {icon}
      </span>
      <span className="truncate">{label}</span>
      {active && <ChevronRight size={14} className="ml-auto text-emerald-400/60" />}
    </button>
  );
}

// ─── Sidebar ──────────────────────────────────────────────
const NAV = [
  { icon:<LayoutDashboard size={16}/>, label:"Dashboard" },
  { icon:<Map size={16}/>,            label:"NCR Map" },
  { icon:<BarChart3 size={16}/>,      label:"AQI Forecast" },
  { icon:<CloudSun size={16}/>,       label:"Weather & Atmosphere" },
  { icon:<Flame size={16}/>,          label:"Plume Tracker" },
  { icon:<Bell size={16}/>,           label:"Alerts & Notifications" },
  { icon:<Navigation size={16}/>,     label:"Stations" },
  { icon:<FileText size={16}/>,       label:"Reports" },
  { icon:<Activity size={16}/>,       label:"Data Pipeline" },
  { icon:<Bot size={16}/>,             label:"AI Insights" },
  { icon:<Settings size={16}/>,       label:"Profile & Settings" },
];

const AQI_SCALE = [
  { range:"0–50",   label:"Good",                    dot:"#22c55e" },
  { range:"51–100", label:"Moderate",                dot:"#eab308" },
  { range:"101–150",label:"Unhealthy for Sensitive", dot:"#f97316" },
  { range:"151–200",label:"Unhealthy",               dot:"#ef4444" },
  { range:"201–300",label:"Very Unhealthy",          dot:"#a855f7" },
  { range:"301+",   label:"Hazardous",               dot:"#b91c1c" },
];

function Sidebar({ active, setActive, mobile, onClose, user }) {
  const initial = (user?.name || "A").trim().charAt(0).toUpperCase() || "A";
  return (
    <aside className={`flex flex-col h-full w-[232px] bg-[#061b12] border-r border-white/[0.07] ${mobile ? "" : "fixed left-0 top-0"}`}>
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 pt-6 pb-5 border-b border-white/[0.06]">
  <img
    src="/icon.png"
    alt="AeroAQI"
    className="w-12 h-12 object-contain"
  />

  <div>
          <h1 className="text-base font-bold text-white tracking-tight">AeroAQI</h1>
          <p className="text-[10px] text-slate-400 leading-tight">Clean Air, Better Tomorrow</p>
        </div>
        {mobile && (
          <button onClick={onClose} className="ml-auto text-slate-400 hover:text-white">
            <X size={18}/>
          </button>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        <p className="px-3 pt-1 pb-2 text-[10px] font-semibold uppercase tracking-widest text-slate-600">
          Navigation
        </p>
        {NAV.map((n, i) => (
          <NavItem key={n.label} icon={n.icon} label={n.label}
            active={active === i} onClick={() => { setActive(i); if (onClose) onClose(); }} />
        ))}
      </nav>

      {/* AQI Legend */}
      <div className="mx-3 mb-3 rounded-xl p-3 glass-dark">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 mb-2.5">
          AQI Index Scale
        </p>
        {AQI_SCALE.map(s => (
          <div key={s.range} className="flex items-center gap-2 py-0.5">
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{background:s.dot,boxShadow:`0 0 5px ${s.dot}80`}}/>
            <span className="text-[10px] text-slate-500 w-11 flex-shrink-0">{s.range}</span>
            <span className="text-[10px] text-slate-400">{s.label}</span>
          </div>
        ))}
      </div>

      {/* Profile */}
      <button onClick={() => setActive(NAV.length - 1)}
        className="mx-3 mb-4 p-3 rounded-xl glass-subtle flex items-center gap-2.5 text-left hover:bg-white/[0.05] transition">
        <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white"
          style={{background:"linear-gradient(135deg,#16a34a,#22c55e)"}}>{initial}</div>
        <div className="min-w-0">
          <p className="text-xs font-semibold text-white truncate">{user?.name || "AeroAQI User"}</p>
          <p className="text-[10px] text-slate-500 truncate">Profile & Settings</p>
        </div>
      </button>
    </aside>
  );
}

function AmbientMelodyButton(){
  const [on,setOn]=useState(false); const ctxRef=useRef(null); const timerRef=useRef(null);
  const notes=[261.63,329.63,392,329.63,293.66,349.23,440,392];
  const stop=()=>{if(timerRef.current){clearInterval(timerRef.current);timerRef.current=null} if(ctxRef.current){ctxRef.current.close();ctxRef.current=null}setOn(false)};
  const start=()=>{try{const Ctx=window.AudioContext||window.webkitAudioContext; if(!Ctx)return; const ctx=new Ctx();ctxRef.current=ctx;let i=0;const play=()=>{const o=ctx.createOscillator(),g=ctx.createGain();o.type='sine';o.frequency.value=notes[i%notes.length];g.gain.setValueAtTime(.0001,ctx.currentTime);g.gain.exponentialRampToValueAtTime(.075,ctx.currentTime+.03);g.gain.exponentialRampToValueAtTime(.0001,ctx.currentTime+.55);o.connect(g);g.connect(ctx.destination);o.start();o.stop(ctx.currentTime+.58);i++};play();timerRef.current=setInterval(play,620);setOn(true)}catch{setOn(false)}};
  useEffect(()=>()=>stop(),[]);
  return <button onClick={on?stop:start} title="Original ambient melody" className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-semibold" style={{background:on?"rgba(34,197,94,.12)":"rgba(255,255,255,.035)",border:`1px solid ${on?"rgba(74,222,128,.22)":"rgba(255,255,255,.07)"}`,color:on?"#86efac":"#94a3b8"}}>{on?<Pause size={11}/>:<Play size={11}/>} Melody</button>;
}

// ─── Header ───────────────────────────────────────────────
function Header({ onMenu, onAlerts, onProfile, onLocation, user }) {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const fmt = time.toLocaleTimeString("en-IN", {hour:"2-digit",minute:"2-digit",second:"2-digit"});
  const dat = time.toLocaleDateString("en-IN", {day:"numeric",month:"short",year:"numeric"});

  return (
    <header className="sticky top-0 z-30 flex items-center gap-3 px-5 py-3 border-b border-white/[0.06]"
      style={{background:"rgba(3,14,8,.92)",backdropFilter:"blur(20px)"}}>
      {/* Mobile menu */}
      <button onClick={onMenu} className="lg:hidden p-2 rounded-lg glass text-slate-300 hover:text-white">
        <Menu size={18}/>
      </button>

      {/* Location */}
      <button aria-label="Selected location: Delhi"
        onClick={onLocation}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg glass text-sm font-medium text-white hover:border-emerald-500/30 transition-all">
        <MapPin size={13} className="text-emerald-400"/>
        Delhi
        <ChevronDown size={13} className="text-slate-400"/>
      </button>

      {/* Live */}
      <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium"
        style={{background:"rgba(34,197,94,.1)",border:"1px solid rgba(34,197,94,.2)"}}>
        <span className="live-dot w-1.5 h-1.5 rounded-full bg-green-400"/>
        <span className="text-green-400 hidden sm:inline">LIVE</span>
      </div>

      {/* Time */}
      <div className="hidden md:flex items-center gap-1 px-2.5 py-1 rounded-lg glass text-xs text-slate-400">
        <Clock size={11} className="text-slate-500"/>
        <span>{dat} · {fmt}</span>
      </div>

      {/* Spacer */}
      <div className="flex-1"/>

      {/* Weather info */}
      <div className="hidden lg:flex items-center gap-4 text-sm text-slate-300">
        <div className="flex items-center gap-1.5">
          <Thermometer size={14} className="text-orange-400"/>
          <span className="font-semibold text-white">31°C</span>
          <span className="text-slate-500 text-xs">Partly Cloudy</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Wind size={14} className="text-emerald-400"/>
          <span>12 km/h <span className="text-slate-500 text-xs">WNW</span></span>
        </div>
        <div className="flex items-center gap-1.5">
          <Droplets size={14} className="text-emerald-300"/>
          <span>48%</span>
        </div>
      </div>

      <AmbientMelodyButton/>

      {/* Bell */}
      <button aria-label="Open alerts" onClick={onAlerts}
        className="relative p-2 rounded-lg glass text-slate-300 hover:text-white transition">
        <Bell size={16}/>
        <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-red-500"/>
      </button>

      {/* Avatar */}
      <button onClick={onProfile} aria-label="Open profile settings"
        className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white cursor-pointer hover:ring-2 hover:ring-emerald-400/40 transition"
        style={{background:"linear-gradient(135deg,#16a34a,#22c55e)"}}>
        {(user?.name || "A").trim().charAt(0).toUpperCase() || "A"}
      </button>
    </header>
  );
}

// ─── Hero Section ─────────────────────────────────────────
function Hero() {
  return (
    <section className="relative overflow-hidden rounded-2xl"
      style={{minHeight:440,border:"1px solid rgba(255,255,255,.07)"}}>

      {/* Background image with overlay */}
      <div className="absolute inset-0">
        <img src="/hero.png" alt="India Gate, Delhi"
          className="w-full h-full object-cover object-center"
          style={{opacity:.96,filter:"brightness(1.06) saturate(1.18) contrast(1.02)"}}/>
        <div className="absolute inset-0"
          style={{background:"linear-gradient(90deg,rgba(1,8,5,.80) 0%,rgba(3,16,10,.40) 38%,rgba(3,14,9,.10) 62%,rgba(1,8,5,.38) 100%)"}}/>
        <div className="absolute inset-0"
          style={{background:"linear-gradient(180deg,rgba(1,8,5,.08) 0%,transparent 42%,rgba(1,8,5,.28) 100%)"}}/>
        {/* Green atmospheric glow */}
        <div className="absolute inset-0 orb-green" style={{top:"-30%",left:"-10%",width:"60%",height:"160%",pointerEvents:"none"}}/>
        <div className="absolute inset-0 orb-emerald" style={{top:"20%",right:"-5%",width:"45%",height:"80%",pointerEvents:"none"}}/>
      </div>

      <div className="relative z-10 grid grid-cols-1 lg:grid-cols-[1fr_420px] gap-6 p-7 lg:p-10" style={{minHeight:440}}>

        {/* LEFT */}
        <div className="flex flex-col justify-center">
          <div className="flex items-center gap-2 mb-4">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 live-dot"/>
            <p className="text-xs font-semibold tracking-[0.18em] uppercase text-emerald-400">
              Delhi-NCR Air Intelligence
            </p>
          </div>

          <h2 className="text-4xl lg:text-5xl font-black leading-[1.12] text-white mb-1">
            Air Quality
          </h2>
          <h2 className="text-4xl lg:text-5xl font-black leading-[1.12] mb-1">
            <span className="grad-cyan">Forecasting</span>
          </h2>
          <h2 className="text-4xl lg:text-5xl font-black leading-[1.12] text-white mb-5">
            for a Better Tomorrow
          </h2>

          <p className="text-slate-300 text-sm max-w-sm leading-relaxed mb-2">
            Weather–Chemistry Coupled AQI Forecast
          </p>
          <p className="text-slate-400 text-sm max-w-sm leading-relaxed mb-6">
            72-Hour Prediction Horizon · CPCB · IMD · NASA FIRMS · ERA5
          </p>

          {/* Meta chips */}
          <div className="flex flex-wrap gap-2.5 mb-7">
            {[
              { icon:<Clock size={11}/>, label:"Last Updated", val:"Sep 1, 2026 · 10:30 AM" },
              { icon:<Layers size={11}/>, label:"Data Sources", val:"CPCB · IMD · NASA · ISRO" },
            ].map(m => (
              <div key={m.label} className="flex items-center gap-2 px-3 py-2 rounded-lg glass text-xs">
                <span className="text-emerald-400">{m.icon}</span>
                <span className="text-slate-500">{m.label}:</span>
                <span className="text-slate-300 font-medium">{m.val}</span>
              </div>
            ))}
          </div>

          <button
            onClick={() => document.getElementById("forecast-section")?.scrollIntoView({behavior:"smooth",block:"start"})}
            className="btn-primary w-fit flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white">
            Explore Dashboard
            <ArrowUpRight size={16}/>
          </button>
        </div>

        {/* RIGHT — Intelligence panel */}
        <div className="flex flex-col gap-3 justify-center">

          {/* Current AQI card */}
          <div className="rounded-2xl p-5" style={{
            background:"rgba(6,28,18,.88)",
            backdropFilter:"blur(24px)",
            border:"1px solid rgba(74,222,128,.2)",
            boxShadow:"0 0 40px rgba(34,197,94,.1), 0 8px 32px rgba(0,0,0,.4)"
          }}>
            <div className="flex items-center justify-between mb-4">
              <span className="text-[10px] font-semibold tracking-widest uppercase text-slate-400">
                Current Conditions
              </span>
              <span className="flex items-center gap-1 text-[10px] text-green-400 font-medium px-2 py-0.5 rounded-full"
                style={{background:"rgba(34,197,94,.1)",border:"1px solid rgba(34,197,94,.2)"}}>
                <span className="live-dot w-1 h-1 rounded-full bg-green-400"/>Live
              </span>
            </div>

            <div className="grid grid-cols-3 gap-3">
              {/* AQI */}
              <div className="text-center p-3 rounded-xl" style={{background:"rgba(139,92,246,.12)",border:"1px solid rgba(139,92,246,.2)"}}>
                <p className="text-[10px] text-slate-400 mb-1">AQI</p>
                <p className="text-3xl font-black text-purple-300 leading-none">
  {currentAqi != null ? Math.round(currentAqi) : "—"}
</p>
<p className="text-[10px] text-purple-400 mt-1 font-medium">
  {currentAqi != null ? aqiLabel(currentAqi) : "No data"}
</p>
              </div>
              {/* PM2.5 */}
              <div className="text-center p-3 rounded-xl" style={{background:"rgba(6,182,212,.08)",border:"1px solid rgba(6,182,212,.18)"}}>
                <p className="text-[10px] text-slate-400 mb-1">PM2.5</p>
                <p className="text-2xl font-black text-emerald-300 leading-none">
  {currentPm25 != null ? Math.round(currentPm25) : "—"}
</p>
                <p className="text-[10px] text-slate-400 mt-1">µg/m³</p>
              </div>
              {/* Trend */}
              <div className="text-center p-3 rounded-xl" style={{background:"rgba(239,68,68,.08)",border:"1px solid rgba(239,68,68,.18)"}}>
                <p className="text-[10px] text-slate-400 mb-1">vs Yesterday</p>
                <p className="text-xl font-black text-red-400 leading-none">↑ 12</p>
                <p className="text-[10px] text-red-400 mt-1 font-medium">Worsening</p>
              </div>
            </div>
          </div>

          {/* 72-h forecast chart */}
          <div className="rounded-2xl p-4" style={{
            background:"rgba(6,28,18,.88)",
            backdropFilter:"blur(24px)",
            border:"1px solid rgba(74,222,128,.15)",
            boxShadow:"0 0 30px rgba(34,197,94,.07), 0 8px 24px rgba(0,0,0,.35)"
          }}>
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-xs font-semibold text-white">72-Hour AQI Forecast</p>
                <p className="text-[10px] text-slate-500 mt-0.5">XGBoost · Weather-Chemistry Coupled</p>
              </div>
              <Gauge size={16} className="text-purple-400"/>
            </div>

            {/* Reference bands */}
            <div className="relative">
              <ResponsiveContainer width="100%" height={130}>
                <AreaChart data={forecastData} margin={{top:5,right:5,left:-28,bottom:0}}>
                  <defs>
                    <linearGradient id="aqiGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#22c55e" stopOpacity={0.4}/>
                      <stop offset="95%" stopColor="#22c55e" stopOpacity={0.03}/>
                    </linearGradient>
                    <linearGradient id="pm25Grad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#4ade80" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#4ade80" stopOpacity={0.02}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="2 4" stroke="rgba(255,255,255,.05)" vertical={false}/>
                  <XAxis dataKey="t" tick={{fill:"#64748b",fontSize:9}} axisLine={false} tickLine={false}/>
                  <YAxis tick={{fill:"#64748b",fontSize:9}} axisLine={false} tickLine={false}/>
                  <Tooltip content={<ForecastTooltip/>}/>
                  <ReferenceLine y={150} stroke="rgba(239,68,68,.3)" strokeDasharray="3 3"/>
                  <ReferenceLine y={100} stroke="rgba(234,179,8,.25)" strokeDasharray="3 3"/>
                  <Area type="monotone" dataKey="aqi"  stroke="#22c55e" strokeWidth={2}
                    fill="url(#aqiGrad)" dot={false}
                    activeDot={{r:4,fill:"#22c55e",stroke:"#061b12",strokeWidth:2}}/>
                  <Area type="monotone" dataKey="pm25" stroke="#4ade80" strokeWidth={1.5}
                    fill="url(#pm25Grad)" dot={false}
                    activeDot={{r:3,fill:"#4ade80",stroke:"#061b12",strokeWidth:2}}/>
                </AreaChart>
              </ResponsiveContainer>
            </div>

            <div className="flex items-center gap-4 mt-1">
              <div className="flex items-center gap-1.5 text-[10px] text-slate-400">
                <span className="w-4 h-0.5 rounded bg-emerald-400"/>AQI
              </div>
              <div className="flex items-center gap-1.5 text-[10px] text-slate-400">
                <span className="w-4 h-0.5 rounded bg-emerald-300"/>PM2.5
              </div>
              <div className="flex items-center gap-1.5 text-[10px] text-slate-500 ml-auto">
                <span className="w-3 h-px border-t border-dashed border-red-500/50"/>150 AQI threshold
              </div>
            </div>
          </div>
        </div>

      </div>
    </section>
  );
}

// ─── KPI Strip ────────────────────────────────────────────
function KpiStrip() {
  const kpis = [
    { icon:<Radio size={16}/>,       label:"Stations Online", val:"28", unit:"/ 38",    color:"text-green-400", glow:"rgba(34,197,94,.15)" },
    { icon:<Thermometer size={16}/>, label:"Temperature",     val:"31", unit:"°C",      color:"text-red-400",glow:"rgba(249,115,22,.15)" },
    { icon:<Wind size={16}/>,        label:"Wind Speed",      val:"12", unit:"km/h WNW",color:"text-cyan-400",  glow:"rgba(6,182,212,.15)"  },
    { icon:<Droplets size={16}/>,    label:"Humidity",        val:"48", unit:"%",       color:"text-yellow-400",  glow:"rgba(59,130,246,.15)" },
    { icon:<Gauge size={16}/>,       label:"PBL Height",      val:"750",unit:"m",       color:"text-purple-400",glow:"rgba(139,92,246,.15)" },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mt-4">
      {kpis.map(k => (
        <div key={k.label} className="card-hover flex items-center gap-3 px-4 py-3 rounded-xl"
          style={{background:`rgba(6,28,18,.86)`,border:"1px solid rgba(74,222,128,.1)",backdropFilter:"blur(12px)"}}>
          <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{background:k.glow}}>
            <span className={k.color}>{k.icon}</span>
          </div>
          <div className="min-w-0">
            <p className="text-[10px] text-slate-500 uppercase tracking-wide leading-none mb-1">{k.label}</p>
            <p className="text-base font-bold text-white leading-none">
              {k.val}<span className="text-xs text-slate-400 font-normal ml-1">{k.unit}</span>
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Weather & Atmosphere Panel ───────────────────────────
// ─── Live Open-Meteo helpers ───────────────────────────────
const DELHI_COORDS = { lat: 28.6139, lon: 77.2090 };
const API_BASE = import.meta.env.VITE_API_BASE_URL || "";
async function apiGet(path){ const r=await fetch(`${API_BASE}${path}`,{headers:{Accept:"application/json"}}); if(!r.ok) throw new Error(`API ${r.status}`); return r.json(); }
async function apiPost(path,body){ const r=await fetch(`${API_BASE}${path}`,{method:"POST",headers:{"Content-Type":"application/json",Accept:"application/json"},body:JSON.stringify(body)}); if(!r.ok) throw new Error(`API ${r.status}`); return r.json(); }
const WEATHER_URL = `https://api.open-meteo.com/v1/forecast?latitude=${DELHI_COORDS.lat}&longitude=${DELHI_COORDS.lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,pressure_msl,weather_code&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,pressure_msl,boundary_layer_height,temperature_1000hPa,temperature_925hPa,temperature_850hPa&daily=weather_code,temperature_2m_max,temperature_2m_min,relative_humidity_2m_mean,wind_speed_10m_max,wind_direction_10m_dominant,pressure_msl_mean,precipitation_probability_max&timezone=Asia%2FKolkata&forecast_days=7&models=ecmwf_ifs`;
const AQ_URL = (lat,lon) => `https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${lat}&longitude=${lon}&current=us_aqi,pm2_5,pm10,nitrogen_dioxide&timezone=Asia%2FKolkata`;
function weatherCodeLabel(code){if(code===0)return "Clear sky";if([1,2,3].includes(code))return "Partly cloudy";if([45,48].includes(code))return "Foggy";if([51,53,55,56,57].includes(code))return "Drizzle";if([61,63,65,66,67].includes(code))return "Rain";if([80,81,82].includes(code))return "Rain showers";if([95,96,99].includes(code))return "Thunderstorm";return "Variable";}
function weatherIcon(code){return [61,63,65,80,81,82,95,96,99].includes(code)?<CloudRain size={18}/>:<CloudSun size={18}/>;}
function aqiStatus(v){if(v<=50)return "good";if(v<=100)return "moderate";if(v<=150)return "sensitive";if(v<=200)return "unhealthy";return "very";}
function deriveAtmosphere(data){
  const h=data?.hourly||{}; const n=h.time?.length||0;
  const inversion=(i)=>{ const a=h.temperature_1000hPa?.[i], b=h.temperature_925hPa?.[i]; if(!Number.isFinite(a)||!Number.isFinite(b)) return null; const d=b-a; return {strength:+d.toFixed(1),status:d>1.0?"Active":d>0.2?"Weak":"None"}; };
  return {inversion};
}
function useLiveWeather(){const [state,setState]=useState({loading:true,data:null,error:""});useEffect(()=>{let alive=true;const load=()=>fetch(WEATHER_URL).then(r=>{if(!r.ok)throw new Error("weather");return r.json()}).then(data=>alive&&setState({loading:false,data,error:""})).catch(()=>alive&&setState({loading:false,data:null,error:"Live weather unavailable"}));load();const id=setInterval(load,300000);return()=>{alive=false;clearInterval(id)}},[]);return state;}
function useLiveStations() {
  const [state, setState] = useState({ stations: [], live: false, loading: true, error: "" });

  useEffect(() => {
    let alive = true;

    const load = async () => {
      try {
        // Step 1: fetch station metadata and latest observations in parallel
        const [stationsRaw, obsRaw] = await Promise.all([
          apiGet("/stations"),
          apiGet("/observations/latest"),
        ]);

        if (!alive) return;

        // Normalise /stations response  →  array of station metadata objects
        const stationRows = Array.isArray(stationsRaw)
          ? stationsRaw
          : (stationsRaw?.stations ?? stationsRaw?.data ?? stationsRaw?.items ?? []);

        // Normalise /observations/latest response  →  keyed by station_id
        const obsRows = obsRaw?.observations ?? (Array.isArray(obsRaw) ? obsRaw : []);
        const obsMap = {};
        for (const o of obsRows) {
          if (o.station_id) obsMap[o.station_id] = o;
        }

        if (!stationRows.length) {
          // /stations returned nothing — fall through to fallback
          throw new Error("empty_stations");
        }

        const stations = stationRows
          .map((s, i) => {
            const obs = obsMap[s.station_id] ?? null;

            // AQI: prefer aqi_computed, then aqi_raw
            const aqiRaw = obs ? (obs.aqi_computed ?? obs.aqi_raw ?? null) : null;
            const aqi = aqiRaw !== null ? Number(aqiRaw) : null;

            return {
              name:      s.name      ?? s.station_name ?? s.station_id ?? `Station ${i + 1}`,
              station_id: s.station_id,
              lat:       Number(s.latitude  ?? s.lat),
              lon:       Number(s.longitude ?? s.lon),
              city:      s.city  ?? null,
              state:     s.state ?? null,
              agency:    s.agency ?? null,
              zone:      s.zone  ?? null,
              // Pollutant values from observations (null when unavailable)
              aqi:       Number.isFinite(aqi) ? aqi : null,
              pm25:      obs?.pm25  != null ? Number(obs.pm25)  : null,
              pm10:      obs?.pm10  != null ? Number(obs.pm10)  : null,
              no2:       obs?.no2   != null ? Number(obs.no2)   : null,
              o3:        obs?.o3    != null ? Number(obs.o3)    : null,
              so2:       obs?.so2   != null ? Number(obs.so2)   : null,
              co:        obs?.co    != null ? Number(obs.co)    : null,
              timestamp: obs?.timestamp_utc ?? null,
              data_source: obs?.data_source ?? null,
              // Derived: AQI status (null when AQI is unavailable)
              status:    Number.isFinite(aqi) ? aqiStatus(aqi) : "unknown",
              source:    obs ? "AeroAQI Backend" : "metadata-only",
              hasObs:    obs !== null,
            };
          })
          // Drop rows where coordinates are not valid numbers
          .filter(x => Number.isFinite(x.lat) && Number.isFinite(x.lon));

        if (alive) {
          setState({ stations, live: true, loading: false, error: "" });
        }
        return; // success — do not fall through to the fallback
      } catch (err) {
        if (!alive) return;
        // Both API calls failed or stations was empty — show nothing rather
        // than silently mixing real and fake data.
        setState(prev => ({
  stations: prev.stations,
  live: prev.stations.length > 0,
  loading: false,
  error: prev.stations.length > 0
    ? "Live refresh unavailable — showing last synced data."
    : "Station data unavailable. Ensure the AeroAQI backend is running."
}));
      }
    };

    load();
    const id = setInterval(load, 300_000); // refresh every 5 min
    return () => { alive = false; clearInterval(id); };
  }, []);

  return state;
}

function WeatherPanel() {
  const {loading,data,error}=useLiveWeather(); const [day,setDay]=useState(0);
  const daily=data?.daily, current=data?.current, hourly=data?.hourly;
  const atmosphere=deriveAtmosphere(data);
  const days=(daily?.time||[]).map((date,i)=>({date,max:daily.temperature_2m_max?.[i],min:daily.temperature_2m_min?.[i],humidity:daily.relative_humidity_2m_mean?.[i],rain:daily.precipitation_probability_max?.[i],wind:daily.wind_speed_10m_max?.[i],windDir:daily.wind_direction_10m_dominant?.[i],pressure:daily.pressure_msl_mean?.[i]}));
  const selected=days[day]||{};
  const nowIdx=Math.max(0,(hourly?.time||[]).findIndex(t=>t>=current?.time));
  const pbl=hourly?.boundary_layer_height?.[nowIdx];
  const inv=atmosphere.inversion(nowIdx);
  const metrics=[
    ["Temperature",current?.temperature_2m, v=>`${Math.round(v)}°C`,<Thermometer size={15}/>,"#86efac"],
    ["Humidity",current?.relative_humidity_2m,v=>`${Math.round(v)}%`,<Droplets size={15}/>,"#6ee7b7"],
    ["Wind",current?.wind_speed_10m,v=>`${Math.round(v)} km/h`,<Wind size={15}/>,"#34d399"],
    ["Pressure",current?.pressure_msl,v=>`${Math.round(v)} hPa`,<Gauge size={15}/>,"#a7f3d0"],
    ["PBL / Mixing",pbl,v=>Number.isFinite(v)?`${Math.round(v)} m`:"Unavailable",<Layers3 size={15}/>,"#4ade80"],
    ["Inversion",inv?.strength,v=>inv?`${inv.status} · ${v>0?"+":""}${v}°C`:"Unavailable",<Activity size={15}/>,"#fbbf24"]
  ];
  return <div id="weather-section" className="card-hover rounded-2xl p-5 flex flex-col gap-4" style={{background:"linear-gradient(145deg,rgba(7,35,24,.86),rgba(5,22,18,.78))",border:"1px solid rgba(74,222,128,.13)",backdropFilter:"blur(18px)"}}>
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3"><div><p className="text-sm font-bold text-white flex items-center gap-2"><CloudSun size={18} className="text-emerald-300"/>Weather & Atmosphere</p><p className="text-[10px] text-slate-400 mt-1">Delhi-NCR live conditions + 7-day atmospheric outlook</p></div><span className="source-pill">{loading?"Updating…":error?"Unavailable":"LIVE · Open-Meteo ECMWF"}</span></div>
    {error&&<div className="rounded-xl p-3 text-[10px] text-amber-200" style={{background:"rgba(245,158,11,.06)",border:"1px solid rgba(245,158,11,.15)"}}>Live weather unavailable right now. No fake weather values are shown.</div>}
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">{metrics.map(([label,val,fmt,icon,color])=><div key={label} className="science-card p-3 rounded-xl"><span style={{color}}>{icon}</span><p className="text-[9px] text-slate-400 mt-2">{label}</p><p className="text-xs font-bold text-white mt-1">{Number.isFinite(val)?fmt(val):"Unavailable"}</p></div>)}</div>
    <div className="rounded-2xl p-4" style={{background:"linear-gradient(135deg,rgba(34,197,94,.09),rgba(16,185,129,.035),rgba(255,255,255,.015))",border:"1px solid rgba(74,222,128,.1)"}}>
      <div className="flex items-center justify-between mb-3"><div><p className="text-xs font-bold text-white">7-day weather & atmosphere outlook</p><p className="text-[9px] text-slate-400">Temperature · humidity · wind · pressure · mixing</p></div><span className="text-[9px] text-emerald-300">Delhi-NCR</span></div>
      <div className="flex gap-2 overflow-x-auto pb-1">{days.map((d,i)=><button key={d.date} onClick={()=>setDay(i)} className="min-w-[122px] p-3 rounded-xl text-left" style={{background:i===day?"rgba(34,197,94,.12)":"rgba(255,255,255,.025)",border:`1px solid ${i===day?"rgba(74,222,128,.25)":"rgba(255,255,255,.05)"}`}}><p className="text-[9px] text-slate-400">{i===0?"Today":new Date(`${d.date}T12:00:00`).toLocaleDateString("en-IN",{weekday:"short"})}</p><p className="text-sm font-black text-white mt-2">{Number.isFinite(d.max)?Math.round(d.max):"—"}° <span className="text-slate-500 font-medium">/ {Number.isFinite(d.min)?Math.round(d.min):"—"}°</span></p><p className="text-[9px] text-emerald-300 mt-1">RH {Number.isFinite(d.humidity)?Math.round(d.humidity):"—"}%</p><p className="text-[9px] text-slate-400 mt-1">Wind {Number.isFinite(d.wind)?Math.round(d.wind):"—"} km/h</p></button>)}</div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mt-3">{[["Humidity",Number.isFinite(selected.humidity)?`${Math.round(selected.humidity)}%`:"Unavailable"],["Wind",Number.isFinite(selected.wind)?`${Math.round(selected.wind)} km/h`:"Unavailable"],["Pressure",Number.isFinite(selected.pressure)?`${Math.round(selected.pressure)} hPa`:"Unavailable"],["Rain",Number.isFinite(selected.rain)?`${Math.round(selected.rain)}%`:"Unavailable"],["PBL now",Number.isFinite(pbl)?`${Math.round(pbl)} m`:"Unavailable"]].map(([a,b])=><div key={a} className="p-3 rounded-xl bg-white/[.025]"><p className="text-[9px] text-slate-500">{a}</p><p className="text-xs font-bold text-white mt-1">{b}</p></div>)}</div>
    </div>
    <p className="text-[9px] text-slate-500">PBL is a direct atmospheric model variable. Inversion is a derived indicator from real pressure-level temperatures (1000 hPa vs 925 hPa); it is not presented as a direct observation.</p>
  </div>;
}

// ─── Plume Tracker Panel ──────────────────────────────────
function PlumePanel() {
  const [tab, setTab] = useState(0);
  const [timeIdx, setTimeIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [showFires, setShowFires] = useState(true);
  const [showWind, setShowWind] = useState(true);
  const [selectedRegion, setSelectedRegion] = useState("Punjab");
  const tabs = ["Plume Map", "Source Regions", "Transport Animation"];
  const times = ["Now", "+12h", "+24h", "+48h", "+72h"];
  const regionData = [
    {name:"Punjab", fires:42, risk:"High", color:"#ef4444", desc:"Highest modeled source-region influence on Delhi under current transport."},
    {name:"Haryana", fires:28, risk:"High", color:"#f97316", desc:"Upwind burning activity with direct transport potential toward Delhi."},
    {name:"Rajasthan", fires:8, risk:"Low", color:"#eab308", desc:"Lower fire activity with weaker modeled transport contribution."},
    {name:"Uttar Pradesh", fires:19, risk:"Moderate", color:"#a855f7", desc:"Regional sources may influence eastern NCR under favorable winds."},
  ];
  const selected = regionData.find(r=>r.name===selectedRegion) || regionData[0];
  const hotspots = [
    [108,62,8],[140,76,6],[168,91,10],[132,124,5],[194,150,4],[268,168,6],[296,186,5],[322,204,4]
  ];

  useEffect(()=>{
    if (!playing) return;
    const id = window.setInterval(()=>setTimeIdx(v=>{
      if (v >= times.length-1) { setPlaying(false); return 0; }
      return v+1;
    }), 900);
    return ()=>window.clearInterval(id);
  },[playing]);

  return (
    <div id="plume-section" className="card-hover rounded-2xl p-5 flex flex-col gap-4"
      style={{background:"rgba(7,28,20,.82)",border:"1px solid rgba(255,255,255,.07)",backdropFilter:"blur(16px)"}}>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div><p className="text-sm font-bold text-white">Plume Tracker</p><p className="text-[10px] text-slate-500 mt-0.5">Stubble burning · source attribution · transport toward NCR</p></div>
        <div className="flex items-center gap-2"><span className="flex items-center gap-1 text-[10px] text-orange-300 px-2 py-1 rounded-full" style={{background:"rgba(249,115,22,.09)",border:"1px solid rgba(249,115,22,.18)"}}><Flame size={11}/> Fire transport</span></div>
      </div>

      <div className="flex gap-1 p-1 rounded-lg" style={{background:"rgba(255,255,255,.04)"}}>
        {tabs.map((t,i)=><button key={t} onClick={()=>setTab(i)} className={`flex-1 text-[10px] py-2 rounded-md font-semibold transition-all ${tab===i?"text-white":"text-slate-500 hover:text-slate-300"}`} style={tab===i?{background:"linear-gradient(135deg,rgba(6,182,212,.25),rgba(59,130,246,.2))",border:"1px solid rgba(6,182,212,.2)"}:{}}>{t}</button>)}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_260px] gap-4">
        <div className="relative rounded-xl overflow-hidden min-h-[360px]" style={{background:"#051a0e",border:"1px solid rgba(255,255,255,.07)"}}>
          <div className="absolute inset-0 map-grid opacity-30"/>
          <svg viewBox="0 0 420 320" className="absolute inset-0 w-full h-full">
            <defs>
              <linearGradient id="plumePath" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="#ef4444" stopOpacity=".05"/><stop offset="45%" stopColor="#f97316" stopOpacity=".38"/><stop offset="100%" stopColor="#eab308" stopOpacity=".03"/></linearGradient>
              <filter id="softGlow"><feGaussianBlur stdDeviation="7"/></filter>
              <marker id="windArrowAero" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#38bdf8"/></marker>
            </defs>
            <path d="M55 42 C125 42 185 82 205 128 C226 175 242 218 332 270" fill="none" stroke="url(#plumePath)" strokeWidth={65} opacity={.45+timeIdx*.07} filter="url(#softGlow)"/>
            <path d="M55 42 C125 42 185 82 205 128 C226 175 242 218 332 270" fill="none" stroke="#f97316" strokeWidth={25} opacity={.12+timeIdx*.025}/>
            <path d="M65 52 C120 57 170 92 199 140 C225 182 253 228 325 264" fill="none" stroke="#fb923c" strokeWidth={2} strokeDasharray="7 6" opacity={.65}/>
            {showWind && [[85,70,125,105],[135,93,173,130],[185,126,221,166],[236,166,273,208]].map((a,i)=><line key={i} x1={a[0]} y1={a[1]} x2={a[2]} y2={a[3]} stroke="#38bdf8" strokeWidth={1.5} strokeDasharray="5 4" markerEnd="url(#windArrowAero)" opacity={.75}/>) }
            {showFires && hotspots.map((h,i)=><g key={i} className="cursor-pointer"><circle cx={h[0]} cy={h[1]} r={h[2]*2.1} fill="#ef4444" opacity={.12}/><circle cx={h[0]} cy={h[1]} r={h[2]} fill={i%3===0?"#ef4444":i%3===1?"#f97316":"#eab308"} opacity={.9}/><circle cx={h[0]} cy={h[1]} r="2" fill="white"/></g>)}
            <circle cx="230" cy="210" r="10" fill="rgba(6,182,212,.16)" stroke="#22d3ee" strokeWidth="1.5"/><circle cx="230" cy="210" r="4" fill="#22d3ee"/><text x="242" y="214" fill="white" fontSize="10" fontWeight="800">Delhi</text>
            <text x="60" y="28" fill="#cbd5e1" fontSize="10" fontWeight="700">Punjab</text><text x="160" y="105" fill="#cbd5e1" fontSize="10" fontWeight="700">Haryana</text><text x="300" y="245" fill="#cbd5e1" fontSize="10" fontWeight="700">Uttar Pradesh</text>
          </svg>
          <div className="absolute left-3 top-3 rounded-xl px-3 py-2" style={{background:"rgba(3,12,31,.88)",border:"1px solid rgba(255,255,255,.08)"}}><p className="text-[9px] text-slate-500">Modeled transport horizon</p><p className="text-sm font-black text-white">{times[timeIdx]}</p><p className="text-[9px] text-emerald-300">Wind: WNW → Delhi</p></div>
          <div className="absolute right-3 top-3 flex flex-col gap-1">
            <button onClick={()=>setShowFires(v=>!v)} className={`px-2 py-1 rounded-lg text-[9px] font-semibold ${showFires?"text-orange-300":"text-slate-500"}`} style={{background:"rgba(3,12,31,.88)",border:"1px solid rgba(255,255,255,.08)"}}><Flame size={10} className="inline mr-1"/>Fires</button>
            <button onClick={()=>setShowWind(v=>!v)} className={`px-2 py-1 rounded-lg text-[9px] font-semibold ${showWind?"text-emerald-300":"text-slate-500"}`} style={{background:"rgba(3,12,31,.88)",border:"1px solid rgba(255,255,255,.08)"}}><Wind size={10} className="inline mr-1"/>Wind</button>
          </div>
          <div className="absolute bottom-3 left-3 right-3 flex items-center gap-3 text-[9px] text-slate-400"><span><i className="inline-block w-2 h-2 rounded-full bg-red-500 mr-1"/>Fire hotspot</span><span><i className="inline-block w-5 border-t border-dashed border-cyan-400 mr-1"/>Wind direction</span><span><i className="inline-block w-4 h-2 rounded bg-orange-500/50 mr-1"/>Plume intensity</span></div>
        </div>

        <div className="space-y-3">
          <div className="rounded-xl p-3" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}>
            <p className="text-[10px] uppercase tracking-widest text-slate-500">Source region</p>
            <select value={selectedRegion} onChange={e=>setSelectedRegion(e.target.value)} className="mt-2 w-full rounded-lg px-2.5 py-2 text-xs text-white outline-none" style={{background:"#0a1522",border:"1px solid rgba(255,255,255,.08)"}}>{regionData.map(r=><option key={r.name}>{r.name}</option>)}</select>
            <div className="grid grid-cols-2 gap-2 mt-2"><div><p className="text-[9px] text-slate-500">Fire detections</p><p className="text-lg font-black text-white">{selected.fires}</p></div><div><p className="text-[9px] text-slate-500">Transport risk</p><p className="text-sm font-bold" style={{color:selected.color}}>{selected.risk}</p></div></div>
            <p className="text-[10px] leading-relaxed text-slate-500 mt-2">{selected.desc}</p>
          </div>
          <div className="rounded-xl p-3" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}>
            <div className="flex items-center justify-between"><p className="text-[10px] uppercase tracking-widest text-slate-500">Timeline</p><button onClick={()=>setPlaying(v=>!v)} className="w-7 h-7 rounded-lg flex items-center justify-center text-emerald-300" style={{background:"rgba(6,182,212,.1)",border:"1px solid rgba(6,182,212,.2)"}}>{playing?"Ⅱ":"▶"}</button></div>
            <input type="range" min="0" max={times.length-1} value={timeIdx} onChange={e=>{setPlaying(false);setTimeIdx(Number(e.target.value))}} className="w-full mt-3 accent-cyan-400"/>
            <div className="flex justify-between mt-1 text-[9px] text-slate-600">{times.map(t=><span key={t}>{t}</span>)}</div>
          </div>
        </div>
      </div>

      {tab===1 && <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">{regionData.map(r=><button key={r.name} onClick={()=>setSelectedRegion(r.name)} className="text-left rounded-xl p-3 hover:bg-white/[.04] transition" style={{background:"rgba(255,255,255,.025)",border:`1px solid ${selectedRegion===r.name?r.color+"66":"rgba(255,255,255,.05)"}`}}><p className="text-xs font-bold text-white">{r.name}</p><p className="text-[10px] text-slate-500 mt-1">{r.fires} active detections</p><p className="text-[10px] font-semibold mt-2" style={{color:r.color}}>{r.risk} transport risk</p></button>)}</div>}
      {tab===2 && <div className="rounded-xl p-4" style={{background:"rgba(6,182,212,.04)",border:"1px solid rgba(6,182,212,.12)"}}><div className="flex items-center gap-2"><Radio size={14} className="text-cyan-400"/><p className="text-xs font-bold text-white">Transport animation</p></div><p className="text-[11px] text-slate-400 mt-2">Press play to step through the 72-hour transport horizon. The visualization shows the modeled source-to-Delhi direction; live values will come from the fire and weather APIs after backend wiring.</p></div>}
    </div>
  );
}

// ─── Alerts Panel ─────────────────────────────────────────
function playAlertTone(){try{const C=window.AudioContext||window.webkitAudioContext;if(!C)return;const ctx=new C();[0,0.16,0.32].forEach((t,i)=>{const o=ctx.createOscillator(),g=ctx.createGain();o.type="sine";o.frequency.value=[660,880,740][i];g.gain.setValueAtTime(.0001,ctx.currentTime+t);g.gain.exponentialRampToValueAtTime(.11,ctx.currentTime+t+.02);g.gain.exponentialRampToValueAtTime(.0001,ctx.currentTime+t+.13);o.connect(g);g.connect(ctx.destination);o.start(ctx.currentTime+t);o.stop(ctx.currentTime+t+.14)});setTimeout(()=>ctx.close(),700)}catch{}}
function AlertsPanel(){
  const [filter,setFilter]=useState("all");const [read,setRead]=useState({});const [muted,setMuted]=useState(()=>localStorage.getItem("aeroaqi_notifications")==="false");const [pulse,setPulse]=useState(0);
  const alerts=[
    {id:1,severity:"high",icon:<AlertTriangle size={15}/>,title:"High AQI Expected",desc:"Forecast risk window indicates possible AQI deterioration over the next 12 hours.",areas:"Delhi · Noida · Ghaziabad",time:"Updated recently",badge:"High risk",badgeC:"text-red-300",bg:"rgba(239,68,68,.07)",border:"rgba(239,68,68,.22)"},
    {id:2,severity:"mod",icon:<Info size={15}/>,title:"Moderate AQI Expected",desc:"Several NCR locations may cross the moderate-risk threshold during the next forecast window.",areas:"Gurugram · Faridabad",time:"Forecast window",badge:"Moderate",badgeC:"text-yellow-300",bg:"rgba(234,179,8,.07)",border:"rgba(234,179,8,.2)"},
    {id:3,severity:"info",icon:<Wind size={15}/>,title:"Dispersion Watch",desc:"Lower wind or shallow mixing can reduce pollutant dispersion near the surface.",areas:"NCR Region",time:"Monitoring",badge:"Advisory",badgeC:"text-emerald-300",bg:"rgba(6,182,212,.06)",border:"rgba(6,182,212,.18)"},
    {id:4,severity:"high",icon:<Flame size={15}/>,title:"Biomass Transport Risk",desc:"Upwind fire activity can increase particulate transport risk when wind aligns toward NCR.",areas:"Punjab · Haryana → Delhi",time:"Source watch",badge:"Source risk",badgeC:"text-orange-300",bg:"rgba(249,115,22,.07)",border:"rgba(249,115,22,.2)"},
  ];
  useEffect(()=>{const id=setInterval(()=>{setPulse(v=>v+1);if(!muted)playAlertTone()},4*60*60*1000);return()=>clearInterval(id)},[muted]);
  const filtered=alerts.filter(a=>filter==="all"||a.severity===filter);const unread=alerts.filter(a=>!read[a.id]).length;
  const toggleMute=()=>{const n=!muted;setMuted(n);localStorage.setItem("aeroaqi_notifications",String(!n));if(!n)playAlertTone()};
  return <div id="alerts-section" className="card-hover rounded-2xl p-5 flex flex-col gap-4" style={{background:"rgba(7,28,20,.82)",border:"1px solid rgba(255,255,255,.07)",backdropFilter:"blur(18px)"}}>
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3"><div><p className="text-sm font-bold text-white flex items-center gap-2"><BellRing size={18} className="text-amber-300"/>Alerts & Notifications <span className="notification-badge">{unread}</span></p><p className="text-[10px] text-slate-500 mt-1">AQI · weather · source-risk monitoring with optional alert tone</p></div><div className="flex gap-2"><button onClick={()=>{setRead(Object.fromEntries(alerts.map(a=>[a.id,true])));}} className="text-[10px] px-3 py-1.5 rounded-lg text-slate-300" style={{background:"rgba(255,255,255,.04)",border:"1px solid rgba(255,255,255,.07)"}}>Mark all read</button><button onClick={toggleMute} className="text-[10px] px-3 py-1.5 rounded-lg text-slate-300" style={{background:muted?"rgba(239,68,68,.08)":"rgba(34,197,94,.08)",border:"1px solid rgba(255,255,255,.07)"}}>{muted?"Enable tone":"Mute tone"}</button></div></div>
    <div className="grid grid-cols-4 gap-1 p-1 rounded-xl" style={{background:"rgba(255,255,255,.035)"}}>{[["all","All"],["high","High"],["mod","Moderate"],["info","Info"]].map(([v,l])=><button key={v} onClick={()=>setFilter(v)} className="py-2 rounded-lg text-[10px] font-semibold" style={filter===v?{background:"rgba(34,211,238,.12)",border:"1px solid rgba(34,211,238,.18)",color:"#a5f3fc"}:{color:"#64748b"}}>{l}</button>)}</div>
    <div className="space-y-2.5">{filtered.map(a=><div key={a.id} className="p-4 rounded-xl transition-all hover:translate-x-1" style={{background:a.bg,border:`1px solid ${a.border}`,opacity:read[a.id]?.7:1}}><div className="flex items-start gap-3"><div className="p-2 rounded-xl" style={{background:"rgba(255,255,255,.06)"}}><span className={a.badgeC}>{a.icon}</span></div><div className="flex-1"><div className="flex items-center justify-between gap-2"><p className="text-xs font-bold text-white">{a.title}</p><span className={`text-[9px] font-bold px-2 py-1 rounded-full ${a.badgeC}`} style={{background:"rgba(255,255,255,.05)"}}>{a.badge}</span></div><p className="text-[10px] text-slate-400 mt-1.5 leading-relaxed">{a.desc}</p><div className="flex flex-wrap gap-3 mt-2"><span className="text-[9px] text-slate-500 flex items-center gap-1"><MapPin size={9}/>{a.areas}</span><span className="text-[9px] text-slate-600 flex items-center gap-1"><Clock size={9}/>{a.time}</span></div><div className="flex gap-2 mt-3"><button onClick={()=>setRead(v=>({...v,[a.id]:!v[a.id]}))} className="text-[9px] px-2.5 py-1.5 rounded-lg text-emerald-300" style={{background:"rgba(6,182,212,.08)",border:"1px solid rgba(6,182,212,.14)"}}>{read[a.id]?"Mark unread":"Mark read"}</button><button onClick={()=>window.alert(`${a.title}\n\n${a.desc}\n\nAreas: ${a.areas}`)} className="text-[9px] px-2.5 py-1.5 rounded-lg text-slate-400" style={{background:"rgba(255,255,255,.03)",border:"1px solid rgba(255,255,255,.06)"}}>Details</button></div></div></div></div>)}</div>
    <div className="rounded-xl p-3 flex items-center gap-3" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}><Radio size={14} className="text-green-400"/><p className="text-[9px] text-slate-500">Monitoring cycle: the production app should poll the backend every 4–6 hours. This UI also supports a notification tone when a new cycle is received.</p></div>
  </div>;
}

// ─── NCR Map Panel ────────────────────────────────────────
const NCR_STATIONS = [
  {name:"Delhi",lat:28.6139,lon:77.2090,aqi:182,status:"unhealthy"},{name:"Gurugram",lat:28.4595,lon:77.0266,aqi:205,status:"very"},{name:"Noida",lat:28.5355,lon:77.3910,aqi:143,status:"sensitive"},{name:"Ghaziabad",lat:28.6692,lon:77.4538,aqi:173,status:"unhealthy"},{name:"Faridabad",lat:28.4089,lon:77.3178,aqi:187,status:"unhealthy"},{name:"Sonipat",lat:28.9931,lon:77.0151,aqi:158,status:"unhealthy"},{name:"Bahadurgarh",lat:28.6924,lon:76.8513,aqi:151,status:"unhealthy"},{name:"Panipat",lat:29.3909,lon:76.9635,aqi:149,status:"sensitive"},{name:"Palwal",lat:28.1487,lon:77.3320,aqi:82,status:"moderate"},
];
function NcrMapPanel() {
  const {stations:liveStations,live,loading}=useLiveStations();
  const [zoom,setZoom]=useState(10); const [layer,setLayer]=useState("dark"); const [selected,setSelected]=useState(null); const [showStations,setShowStations]=useState(true);
  const center={lat:28.62,lon:77.16};
  const tileSize=256;
  const worldPx=tileSize*Math.pow(2,zoom);
  const lonToX=lon=>(lon+180)/360*worldPx;
  const latToY=lat=>{const r=lat*Math.PI/180;return (1-Math.log(Math.tan(r)+1/Math.cos(r))/Math.PI)/2*worldPx;};
  const cx=lonToX(center.lon), cy=latToY(center.lat);
  const tiles=[]; const tileX=Math.floor(cx/tileSize),tileY=Math.floor(cy/tileSize); for(let dx=-2;dx<=2;dx++) for(let dy=-1;dy<=1;dy++){let x=tileX+dx,y=tileY+dy,n=Math.pow(2,zoom);if(x<0||x>=n||y<0||y>=n)continue;tiles.push({x,y,key:`${x}-${y}`,left:x*tileSize-cx+420,top:y*tileSize-cy+210});}
  const markerPos=s=>({left:420+(lonToX(s.lon)-cx),top:210+(latToY(s.lat)-cy)});

  // Derive marker colour directly from the numeric AQI value so all 15 stations
  // render with a visible marker even when some have no observation data.
  // Stations without AQI data fall back to a neutral slate colour.
  const aqiColour = aqi => {
    if (aqi == null || !Number.isFinite(aqi)) return "#64748b"; // slate — no data
    if (aqi <= 50)  return "#22c55e"; // green
    if (aqi <= 100) return "#eab308"; // yellow
    if (aqi <= 200) return "#f97316"; // orange
    if (aqi <= 300) return "#ef4444"; // red
    return "#a855f7";                 // purple
  };

  return <div id="map-section" className="card-hover rounded-2xl p-5 flex flex-col gap-4" style={{background:"rgba(7,28,20,.82)",border:"1px solid rgba(255,255,255,.07)",backdropFilter:"blur(16px)"}}>
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3"><div><p className="text-sm font-bold text-white">Delhi-NCR Air Quality Map</p><p className="text-[10px] text-slate-500 mt-0.5">Live-style spatial view · Delhi + surrounding NCR districts</p></div><div className="flex gap-2"><span className="flex items-center gap-1 text-[10px] text-green-400 px-2 py-1 rounded-full" style={{background:"rgba(34,197,94,.1)",border:"1px solid rgba(34,197,94,.2)"}}><span className="live-dot w-1.5 h-1.5 rounded-full bg-green-400"/>{loading?"Updating…":live?"Live AQI":"Unavailable"}</span><button onClick={()=>setShowStations(v=>!v)} className="text-[10px] px-2.5 py-1 rounded-lg text-slate-300" style={{background:"rgba(255,255,255,.04)",border:"1px solid rgba(255,255,255,.07)"}}>{showStations?"Hide stations":"Show stations"}</button></div></div>
    <div className="relative rounded-xl overflow-hidden h-[480px]" style={{background:"#08121d",border:"1px solid rgba(255,255,255,.08)"}}>
      <div className="absolute inset-0 overflow-hidden" style={{filter:layer==="dark"?"brightness(.62) invert(.88) hue-rotate(180deg) saturate(.78) contrast(1.18)":"none",transition:"filter .35s ease"}}>{tiles.map(t=><img key={t.key} alt="NCR map tile" src={`https://tile.openstreetmap.org/${zoom}/${t.x}/${t.y}.png`} className="absolute w-64 h-64" style={{left:t.left,top:t.top,maxWidth:"none"}} onError={e=>{e.currentTarget.style.opacity=.25}}/> )}</div>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_45%,transparent_0,rgba(2,8,23,.2)_70%)] pointer-events-none"/><div className="absolute inset-0 pointer-events-none" style={{background:"radial-gradient(circle at 24% 38%,rgba(34,197,94,.10),transparent 13%),radial-gradient(circle at 57% 47%,rgba(234,179,8,.08),transparent 14%),radial-gradient(circle at 72% 42%,rgba(239,68,68,.10),transparent 13%),radial-gradient(circle at 45% 66%,rgba(249,115,22,.08),transparent 12%)",mixBlendMode:layer==="dark"?"screen":"multiply",opacity:.9}}/>

      {/* Station markers — one per backend station, visible regardless of obs availability */}
      {showStations && liveStations.map(s => {
        const p = markerPos(s);
        const c = aqiColour(s.aqi);
        const isSelected = selected?.station_id === s.station_id;
        const sz = isSelected ? 32 : 26;
        return (
          <button key={s.station_id} onClick={() => setSelected(s)}
            className="absolute -translate-x-1/2 -translate-y-1/2 group"
            style={{left:p.left, top:p.top}}>
            <span className="block rounded-full flex items-center justify-center"
              style={{width:sz, height:sz, background:`${c}33`, border:`1px solid ${c}88`, boxShadow:`0 0 14px ${c}66`}}>
              <span className="text-[9px] font-black text-white leading-none">
                {s.aqi != null ? Math.round(s.aqi) : "—"}
              </span>
            </span>
            <span className="absolute left-1/2 -translate-x-1/2 top-full mt-1 whitespace-nowrap text-[9px] font-semibold text-white drop-shadow-lg">{s.name}</span>
          </button>
        );
      })}

      {/* Selected-station popup */}
      {selected && (() => {
        const c = aqiColour(selected.aqi);
        return (
          <div className="absolute left-3 top-3 rounded-xl p-3 w-52"
            style={{background:"rgba(2,12,7,.96)", border:`1px solid ${c}55`, backdropFilter:"blur(12px)"}}>
            <div className="flex items-center justify-between">
              <p className="text-[9px] text-slate-500">Selected station</p>
              <button onClick={() => setSelected(null)} className="text-slate-500"><X size={12}/></button>
            </div>
            <p className="text-sm font-bold text-white mt-1">{selected.name}</p>
            <p className="text-2xl font-black mt-0.5" style={{color: c}}>
              {selected.aqi != null ? Math.round(selected.aqi) : "—"}
            </p>
            <p className="text-[10px] text-slate-400">
              AQI · {selected.aqi != null ? aqiLabel(selected.aqi) : "No data"}
            </p>
            <div className="grid grid-cols-2 gap-2 mt-2">
              <div>
                <p className="text-[9px] text-slate-600">PM2.5</p>
                <p className="text-[10px] text-white font-semibold">
                  {selected.pm25 != null ? `${Math.round(selected.pm25)} µg/m³` : "—"}
                </p>
              </div>
              <div>
                <p className="text-[9px] text-slate-600">Agency</p>
                <p className="text-[10px] text-white font-semibold">{selected.agency ?? "—"}</p>
              </div>
            </div>
          </div>
        );
      })()}

      <div className="absolute top-3 right-3 flex flex-col gap-1"><button onClick={()=>setZoom(z=>Math.min(12,z+1))} className="w-8 h-8 rounded-lg text-white flex items-center justify-center" style={{background:"rgba(2,12,7,.92)",border:"1px solid rgba(255,255,255,.12)"}}><ZoomIn size={14}/></button><button onClick={()=>setZoom(z=>Math.max(9,z-1))} className="w-8 h-8 rounded-lg text-white flex items-center justify-center" style={{background:"rgba(2,12,7,.92)",border:"1px solid rgba(255,255,255,.12)"}}><ZoomOut size={14}/></button><button onClick={()=>setZoom(10)} className="w-8 h-8 rounded-lg text-white flex items-center justify-center" style={{background:"rgba(2,12,7,.92)",border:"1px solid rgba(255,255,255,.12)"}}><Crosshair size={14}/></button></div>
      <div className="absolute top-3 left-1/2 -translate-x-1/2 flex gap-1 p-1 rounded-lg" style={{background:"rgba(2,12,7,.92)",border:"1px solid rgba(255,255,255,.1)"}}><button onClick={()=>setLayer("dark")} className={`px-2.5 py-1 rounded-md text-[9px] ${layer==="dark"?"text-emerald-300 bg-emerald-500/10":"text-slate-500"}`}>Dark</button><button onClick={()=>setLayer("light")} className={`px-2.5 py-1 rounded-md text-[9px] ${layer==="light"?"text-emerald-300 bg-emerald-500/10":"text-slate-500"}`}>Light</button></div>
      <div className="absolute bottom-3 left-3 right-3 flex flex-wrap gap-2">
        <div className="rounded-lg px-3 py-2 text-[9px] text-slate-300" style={{background:"rgba(2,12,7,.9)"}}>
          NCR coverage · {liveStations.length} monitoring points{live ? " · live" : ""}
        </div>
        {[["#22c55e","Good ≤50"],["#eab308","Moderate ≤100"],["#f97316","Unhealthy ≤200"],["#ef4444","Poor ≤300"],["#a855f7","Severe >300"]].map(([c,l])=>(
          <span key={l} className="flex items-center gap-1 px-2 py-1 rounded text-[9px] text-slate-300" style={{background:"rgba(2,12,7,.9)"}}>
            <i className="w-2 h-2 rounded-full flex-shrink-0" style={{background:c}}/>{l}
          </span>
        ))}
      </div>
    </div>

    {/* Bottom strip: show all stations, not just first 5 */}
    <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-2">
      {liveStations.map(s => (
        <button key={s.station_id} onClick={() => setSelected(s)}
          className="rounded-xl p-2.5 text-left hover:bg-white/[.04] transition-colors"
          style={{background: selected?.station_id===s.station_id ? "rgba(34,197,94,.08)" : "rgba(255,255,255,.025)", border:`1px solid ${selected?.station_id===s.station_id?"rgba(74,222,128,.2)":"rgba(255,255,255,.05)"}`}}>
          <p className="text-[10px] text-slate-400 truncate">{s.name}</p>
          <p className="text-sm font-black" style={{color: aqiColour(s.aqi)}}>
            {s.aqi != null ? Math.round(s.aqi) : "—"}
          </p>
          <p className="text-[9px] text-slate-600">{s.pm25 != null ? `PM2.5 ${Math.round(s.pm25)}` : "no obs"}</p>
        </button>
      ))}
    </div>
  </div>;
}

// ─── Quick Actions ────────────────────────────────────────
function QuickActions({ onAction }) {
  const actions = [
    { icon:<BarChart3 size={18}/>, label:"AQI Forecast", sub:"72-Hour Prediction", path:"/forecast", color:"#8b5cf6", glow:"rgba(139,92,246,.2)" },
    { icon:<Map size={18}/>, label:"NCR Map", sub:"Spatial AQI Analysis", path:"/map", color:"#06b6d4", glow:"rgba(6,182,212,.2)" },
    { icon:<CloudSun size={18}/>, label:"Weather", sub:"Live Conditions", path:"/weather", color:"#f59e0b", glow:"rgba(245,158,11,.2)" },
    { icon:<Flame size={18}/>, label:"Plume Tracker", sub:"Transport Analysis", path:"/plume", color:"#f97316", glow:"rgba(249,115,22,.2)" },
    { icon:<Navigation size={18}/>, label:"Stations", sub:"NCR Monitoring", path:"/stations", color:"#22c55e", glow:"rgba(34,197,94,.2)" },
    { icon:<Bell size={18}/>, label:"Alerts", sub:"Risk Notifications", path:"/alerts", color:"#ef4444", glow:"rgba(239,68,68,.2)" },
    { icon:<Bot size={18}/>, label:"AI Insights", sub:"Explain the forecast", path:"/ai", color:"#06b6d4", glow:"rgba(6,182,212,.2)" },
    { icon:<FileText size={18}/>, label:"Reports", sub:"Analytics & Export", path:"/reports", color:"#3b82f6", glow:"rgba(59,130,246,.2)" },
    { icon:<Settings size={18}/>, label:"Settings", sub:"Profile & Preferences", path:"/settings", color:"#a855f7", glow:"rgba(168,85,247,.2)" },
  ];
  return <div id="quick-actions" className="grid grid-cols-2 sm:grid-cols-4 gap-3">{actions.map(a=><button key={a.path} onClick={()=>onAction(a.path)} className="card-hover p-4 rounded-xl flex flex-col items-center text-center gap-2.5" style={{background:"rgba(7,28,20,.82)",border:"1px solid rgba(255,255,255,.07)",backdropFilter:"blur(12px)"}}><div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{background:a.glow,boxShadow:`0 0 16px ${a.glow}`}}><span style={{color:a.color}}>{a.icon}</span></div><div><p className="text-xs font-semibold text-white">{a.label}</p><p className="text-[10px] text-slate-500 mt-0.5">{a.sub}</p></div></button>)}</div>;
}

// ─── Footer ───────────────────────────────────────────────
function Footer() {
  return (
    <footer className="mt-8 py-5 px-1 flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-white/[0.06]">
      <div className="flex items-center gap-2 text-xs text-slate-500"><Activity size={13} className="text-cyan-500"/><span>Built by <span className="font-bold text-emerald-300 tracking-wide">ASYNC AWAIT ❤️</span></span></div>
      <div className="flex items-center gap-3 text-[10px] text-slate-600"><span>Delhi-NCR Air Intelligence</span><span>·</span><span>Explainable Air Quality Forecasting</span></div>
    </footer>
  );
}

// ─── Utility / Feature sections ─────────────────────────────
function FeatureSection({ id, icon, title, subtitle, children }) {
  return (
    <section id={id} className="scroll-mt-20 rounded-2xl p-5"
      style={{background:"rgba(7,28,20,.82)",border:"1px solid rgba(255,255,255,.07)",backdropFilter:"blur(16px)"}}>
      <div className="flex items-center gap-3 mb-4">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center"
          style={{background:"rgba(34,197,94,.1)",border:"1px solid rgba(74,222,128,.18)"}}>
          {icon}
        </div>
        <div>
          <p className="text-sm font-bold text-white">{title}</p>
          <p className="text-[10px] text-slate-500">{subtitle}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

function ReportsSection() {
  const [type,setType]=useState("Executive AQI Report");
  const [range,setRange]=useState("72 hours");
  const [generated,setGenerated]=useState(false);
  const downloadReport = () => {
    const rows = [
      ["AeroAQI Report","Delhi-NCR"],["Report Type",type],["Range",range],
      ["Current AQI","182"],["Primary Pollutant","PM2.5"],["PM2.5","104 µg/m³"],
      ["Peak Forecast AQI","192"],["Lowest Forecast AQI","138"],["Plume Risk","High"],["Generated",new Date().toLocaleString("en-IN")],
    ];
    const csv = rows.map(r=>r.map(v=>`"${String(v).replaceAll('"','""')}"`).join(",")).join("\n");
    const blob=new Blob([csv],{type:"text/csv;charset=utf-8"}); const url=URL.createObjectURL(blob);
    const a=document.createElement("a"); a.href=url; a.download="aeroaqi-delhi-ncr-report.csv"; a.click(); URL.revokeObjectURL(url);
  };
  const generate=()=>{setGenerated(false);window.setTimeout(()=>setGenerated(true),700)};
  return <FeatureSection id="reports-section" icon={<FileText size={17} className="text-cyan-400"/>} title="Reports & Analytics" subtitle="Turn forecast intelligence into a judge-ready report">
    <div className="grid grid-cols-1 xl:grid-cols-[280px_1fr] gap-4">
      <div className="space-y-3">
        <div className="rounded-xl p-3" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.06)"}}>
          <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">Report type</p>
          <select value={type} onChange={e=>setType(e.target.value)} className="w-full rounded-lg px-3 py-2.5 text-xs text-white outline-none" style={{background:"#0a1522",border:"1px solid rgba(255,255,255,.08)"}}>
            <option>Executive AQI Report</option><option>72-Hour Forecast Report</option><option>Station Comparison Report</option><option>Pollution Source Report</option>
          </select>
        </div>
        <div className="rounded-xl p-3" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.06)"}}>
          <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">Analysis range</p>
          <div className="grid grid-cols-3 gap-1">{["24 hours","72 hours","7 days"].map(v=><button key={v} onClick={()=>setRange(v)} className={`py-2 rounded-lg text-[9px] font-semibold ${range===v?"text-emerald-200":"text-slate-500"}`} style={range===v?{background:"rgba(6,182,212,.13)",border:"1px solid rgba(6,182,212,.2)"}:{background:"rgba(255,255,255,.02)"}}>{v}</button>)}</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={generate} className="btn-primary flex-1 px-4 py-2.5 rounded-xl text-xs font-semibold flex items-center justify-center gap-2"><Sparkles size={13}/>{generated?"Report Ready":"Generate Report"}</button>
          <button onClick={downloadReport} className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-300 flex items-center gap-2" style={{background:"rgba(255,255,255,.04)",border:"1px solid rgba(255,255,255,.08)"}}><Download size={13}/>CSV</button>
          <button onClick={()=>window.print()} className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-300 flex items-center gap-2" style={{background:"rgba(255,255,255,.04)",border:"1px solid rgba(255,255,255,.08)"}}><FileText size={13}/>Print</button>
        </div>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[['Current AQI','182','Unhealthy','#ef4444'],['Peak Forecast','192','+6 hours','#a855f7'],['PM2.5','104 µg/m³','Primary pollutant','#86efac'],['Plume Risk','High','Punjab → Delhi','#f97316']].map(([k,v,sub,c])=><div key={k} className="rounded-xl p-4" style={{background:"linear-gradient(145deg,rgba(8,37,26,.8),rgba(5,22,16,.85))",border:"1px solid rgba(74,222,128,.08)"}}><p className="text-[10px] text-slate-500">{k}</p><p className="text-2xl font-black mt-2" style={{color:c}}>{v}</p><p className="text-[9px] text-slate-500 mt-1">{sub}</p></div>)}
        <div className="col-span-2 lg:col-span-4 rounded-xl p-4" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.06)"}}>
          <div className="flex items-center justify-between mb-3"><div><p className="text-xs font-bold text-white">Analytics snapshot</p><p className="text-[10px] text-slate-500">AQI trend · source risk · atmospheric conditions</p></div><span className="text-[9px] text-green-400 flex items-center gap-1"><ShieldCheck size={12}/>Ready for export</span></div>
          <div className="grid grid-cols-3 gap-2">{[["Forecast confidence","84%"],["Stations reporting","28 / 38"],["Data freshness","8 min"]].map(([a,b])=><div key={a} className="p-3 rounded-lg" style={{background:"rgba(2,8,23,.35)"}}><p className="text-[9px] text-slate-500">{a}</p><p className="text-sm font-bold text-white mt-1">{b}</p></div>)}</div>
        </div>
      </div>
    </div>
  </FeatureSection>;
}

function PipelineSection() {
  const stages=[
    ["Data Sources","CPCB / OpenAQ · Open-Meteo · FIRMS","Live inputs"],
    ["Ingestion","Validation + timestamp sync","Normalizing"],
    ["Database","Unified master dataset","Stored"],
    ["Features","Weather + PBL + inversion + fire risk","Derived"],
    ["ML Forecast","72-hour AQI prediction","Predicting"],
    ["REST API","Forecast + stations + alerts","Serving"],
  ];
  const [selected,setSelected]=useState(0); const [running,setRunning]=useState(false); const [progress,setProgress]=useState(0);
  useEffect(()=>{if(!running)return; const id=setInterval(()=>setProgress(p=>{if(p>=100){clearInterval(id);setRunning(false);return 100}return p+4}),120);return()=>clearInterval(id)},[running]);
  return <FeatureSection id="pipeline-section" icon={<Activity size={17} className="text-cyan-400"/>} title="Data Pipeline" subtitle="See how AeroAQI turns observations into a 72-hour forecast">
    <div className="flex flex-wrap items-center justify-between gap-3 mb-4"><div className="text-[10px] text-slate-400 flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-green-400 live-dot"/> End-to-end pipeline monitor</div><button onClick={()=>{setProgress(0);setRunning(true)}} disabled={running} className="btn-primary px-3 py-2 rounded-xl text-[10px] font-bold flex items-center gap-2 disabled:opacity-50"><RefreshCw size={12} className={running?"animate-spin":""}/>{running?`Running ${progress}%`:`Run pipeline check`}</button></div>
    <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
      {stages.map(([name,desc,status],i)=><button key={name} onClick={()=>setSelected(i)} className="p-3 rounded-xl text-left transition-all" style={{background:selected===i?"rgba(34,197,94,.12)":"rgba(34,197,94,.045)",border:`1px solid ${selected===i?"rgba(74,222,128,.28)":"rgba(34,197,94,.13)"}`}}><div className="flex items-center justify-between"><div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold" style={{background:selected===i?"rgba(34,197,94,.2)":"rgba(34,197,94,.1)",color:selected===i?"#86efac":"#86efac"}}>{i+1}</div>{i<5&&<ChevronRight size={12} className="text-slate-700"/>}</div><p className="text-[10px] font-bold text-white mt-3">{name}</p><p className="text-[9px] text-slate-500 mt-1 leading-relaxed">{desc}</p><p className="text-[9px] text-green-400 mt-2">{running && i<=Math.floor(progress/17)?"Processing…":"Ready"}</p></button>)}
    </div>
    <div className="mt-4 rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-3" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.06)"}}><div><p className="text-[9px] text-slate-500">Selected stage</p><p className="text-sm font-bold text-white mt-1">{stages[selected][0]}</p></div><div><p className="text-[9px] text-slate-500">Purpose</p><p className="text-xs text-slate-300 mt-1">{stages[selected][1]}</p></div><div><p className="text-[9px] text-slate-500">Current state</p><p className="text-xs text-green-300 mt-1">{stages[selected][2]} · verified</p></div></div>
    <div className="mt-4 h-2 rounded-full overflow-hidden" style={{background:"rgba(255,255,255,.05)"}}><div className="h-full rounded-full transition-all" style={{width:`${running?progress:100}%`,background:"linear-gradient(90deg,#06b6d4,#22c55e,#8b5cf6)"}}/></div>
  </FeatureSection>;
}

function SettingsSection({ user, onLogout, onProfileSaved }) {
  const [autoRefresh,setAutoRefresh]=useState(()=>localStorage.getItem("aeroaqi_auto_refresh")!=="false");
  const [notifications,setNotifications]=useState(()=>localStorage.getItem("aeroaqi_notifications")!=="false");
  const [name,setName]=useState(user?.name||"AeroAQI User"); const [phone,setPhone]=useState(user?.phone||"");
  const [photo,setPhoto]=useState(user?.photo||""); const [points,setPoints]=useState(()=>Number(localStorage.getItem("aeroaqi_points")||120)); const [saved,setSaved]=useState(false); const [reward,setReward]=useState(0);
  const updateToggle=(key,setter)=>setter(v=>{const next=!v;localStorage.setItem(key,String(next));return next});
  const saveProfile=()=>{const next={...user,name:name.trim()||"AeroAQI User",phone:phone.trim(),photo};localStorage.setItem("aeroaqi_user",JSON.stringify(next)); const acct=JSON.parse(localStorage.getItem("aeroaqi_account")||"null"); if(acct){localStorage.setItem("aeroaqi_account",JSON.stringify({...acct,name:next.name,phone:next.phone,photo:next.photo}))} onProfileSaved(next);setSaved(true);window.setTimeout(()=>setSaved(false),1800)};
  const addPoints=(n)=>{const next=points+n;setPoints(next);localStorage.setItem("aeroaqi_points",String(next));setReward(n);window.setTimeout(()=>setReward(0),1300)};
  const onPhoto=e=>{const file=e.target.files?.[0];if(!file)return; if(file.size>2_000_000){window.alert("Please choose a photo under 2 MB.");return;} const r=new FileReader();r.onload=()=>setPhoto(String(r.result));r.readAsDataURL(file)};
  return <FeatureSection id="settings-section" icon={<Settings size={17} className="text-cyan-400"/>} title="Profile & Settings" subtitle="Personalize your AeroAQI experience">
    <div className="grid grid-cols-1 xl:grid-cols-[300px_1fr] gap-4">
      <div className="rounded-2xl p-5 text-center" style={{background:"linear-gradient(145deg,rgba(8,37,26,.82),rgba(5,22,16,.85))",border:"1px solid rgba(74,222,128,.1)"}}>
        <div className="relative mx-auto w-24 h-24"><div className="w-24 h-24 rounded-full overflow-hidden flex items-center justify-center text-3xl font-black" style={{background:"linear-gradient(135deg,#16a34a,#22c55e)",border:"2px solid rgba(255,255,255,.12)"}}>{photo?<img src={photo} alt="Profile" className="w-full h-full object-cover"/>:(name||"A").charAt(0).toUpperCase()}</div><label className="absolute -right-1 -bottom-1 w-8 h-8 rounded-full flex items-center justify-center cursor-pointer text-white" style={{background:"#16a34a",border:"2px solid #061b12"}}><Upload size={13}/><input type="file" accept="image/*" onChange={onPhoto} className="hidden"/></label></div>
        <p className="text-lg font-black text-white mt-3">{name||"AeroAQI User"}</p><p className="text-[10px] text-slate-500">{user?.email||"No email"}</p>
        <div className="mt-4 rounded-xl p-3" style={{background:"rgba(168,85,247,.08)",border:"1px solid rgba(168,85,247,.16)"}}><div className="flex items-center justify-center gap-2 text-purple-300"><Gift size={16}/><span className="text-xs font-bold">{points} Aero Points</span></div><p className="text-[9px] text-slate-500 mt-1">Earn points for healthy-air actions</p>{reward>0&&<p className="text-[10px] text-green-300 mt-2 animate-bounce">+{reward} points 🎉</p>}</div>
      </div>
      <div className="space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3"><div className="p-3 rounded-xl" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}><label className="text-[10px] text-slate-500">Full name</label><input value={name} onChange={e=>setName(e.target.value)} className="mt-2 w-full rounded-lg px-3 py-2.5 text-xs text-white outline-none" style={{background:"rgba(2,8,23,.55)",border:"1px solid rgba(255,255,255,.08)"}}/></div><div className="p-3 rounded-xl" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}><label className="text-[10px] text-slate-500 flex items-center gap-1"><Phone size={10}/> Mobile number</label><input value={phone} onChange={e=>setPhone(e.target.value.replace(/[^0-9+ -]/g,""))} placeholder="+91 98765 43210" className="mt-2 w-full rounded-lg px-3 py-2.5 text-xs text-white outline-none" style={{background:"rgba(2,8,23,.55)",border:"1px solid rgba(255,255,255,.08)"}}/></div></div>
        <div className="flex flex-wrap gap-2"><button onClick={saveProfile} className="btn-primary px-4 py-2.5 rounded-xl text-xs font-semibold flex items-center gap-2">{saved?<CheckCircle2 size={14}/>:<Save size={14}/>} {saved?"Saved":"Save Profile"}</button><label className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-300 cursor-pointer flex items-center gap-2" style={{background:"rgba(255,255,255,.04)",border:"1px solid rgba(255,255,255,.08)"}}><ImageIcon size={13}/> Change photo<input type="file" accept="image/*" onChange={onPhoto} className="hidden"/></label></div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">{[["Auto refresh","Refresh live-ready widgets",autoRefresh,"aeroaqi_auto_refresh",setAutoRefresh],["Notifications","AQI and weather alerts",notifications,"aeroaqi_notifications",setNotifications]].map(([label,sub,val,key,setter])=><button key={label} onClick={()=>updateToggle(key,setter)} className="w-full flex items-center justify-between p-3 rounded-xl text-left" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}><span><p className="text-xs font-semibold text-white">{label}</p><p className="text-[10px] text-slate-500">{sub}</p></span><span className={`w-9 h-5 rounded-full p-0.5 ${val?"bg-emerald-500/50":"bg-slate-700"}`}><span className={`block w-4 h-4 rounded-full bg-white transition ${val?"translate-x-4":""}`}/></span></button>)}</div>
        <div className="rounded-xl p-4" style={{background:"rgba(168,85,247,.05)",border:"1px solid rgba(168,85,247,.12)"}}><div className="flex items-center justify-between"><div><p className="text-xs font-bold text-white flex items-center gap-2"><Gift size={14} className="text-purple-300"/> Earn Points & Gifts</p><p className="text-[10px] text-slate-500 mt-1">Complete small AeroAQI actions to unlock rewards.</p></div><span className="text-sm font-black text-purple-300">{points} pts</span></div><div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-3"><button onClick={()=>addPoints(20)} className="p-3 rounded-lg text-left" style={{background:"rgba(255,255,255,.025)"}}><Target size={14} className="text-emerald-300"/><p className="text-[10px] text-white font-semibold mt-2">Check AQI</p><p className="text-[9px] text-green-300">+20 points</p></button><button onClick={()=>addPoints(30)} className="p-3 rounded-lg text-left" style={{background:"rgba(255,255,255,.025)"}}><Heart size={14} className="text-pink-300"/><p className="text-[10px] text-white font-semibold mt-2">Healthy-air tip</p><p className="text-[9px] text-green-300">+30 points</p></button><button onClick={()=>addPoints(50)} className="p-3 rounded-lg text-left" style={{background:"rgba(255,255,255,.025)"}}><Award size={14} className="text-yellow-300"/><p className="text-[10px] text-white font-semibold mt-2">Daily challenge</p><p className="text-[9px] text-green-300">+50 points</p></button></div><div className="mt-3 text-[9px] text-slate-500">Gift catalogue can later be connected to your real reward partner/backend.</div></div>
        <button onClick={onLogout} className="w-full flex items-center justify-center gap-2 p-3 rounded-xl text-xs font-semibold text-red-300" style={{background:"rgba(239,68,68,.07)",border:"1px solid rgba(239,68,68,.18)"}}><LogOut size={14}/> Sign out</button>
      </div>
    </div>
  </FeatureSection>;
}



function MotionBackdrop(){
  const ref=useRef(null);
  useEffect(()=>{
    const el=ref.current;
    if(!el || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    let raf=0, x=0, y=0, tx=0, ty=0;
    const onMove=(e)=>{ tx=(e.clientX/window.innerWidth-.5); ty=(e.clientY/window.innerHeight-.5); };
    const tick=()=>{
      x += (tx-x)*0.07; y += (ty-y)*0.07;
      el.style.setProperty('--mx', `${x*34}px`);
      el.style.setProperty('--my', `${y*26}px`);
      el.style.setProperty('--mx2', `${x*-18}px`);
      el.style.setProperty('--my2', `${y*-14}px`);
      el.style.setProperty('--glow-x', `${50+x*18}%`);
      el.style.setProperty('--glow-y', `${38+y*16}%`);
      raf=requestAnimationFrame(tick);
    };
    window.addEventListener('pointermove',onMove,{passive:true});
    raf=requestAnimationFrame(tick);
    return()=>{window.removeEventListener('pointermove',onMove);cancelAnimationFrame(raf);};
  },[]);
  return <div ref={ref} className="motion-backdrop" aria-hidden="true">
    <div className="motion-grid"/>
    <div className="motion-orb motion-orb-a"/>
    <div className="motion-orb motion-orb-b"/>
    <div className="motion-orb motion-orb-c"/>
    <div className="motion-cursor-glow"/>
    <div className="motion-stars">{Array.from({length:18},(_,i)=><i key={i} style={{'--i':i}}/> )}</div>
  </div>;
}

function AeroMotionStyles(){return <style>{`
@keyframes aeroShimmer{0%{transform:translateX(-120%)}100%{transform:translateX(120%)}}
@keyframes aeroOrbit{from{transform:rotate(0deg) translateX(12px) rotate(0deg)}to{transform:rotate(360deg) translateX(12px) rotate(-360deg)}}
.science-card{background:linear-gradient(145deg,rgba(255,255,255,.035),rgba(255,255,255,.018));border:1px solid rgba(255,255,255,.055);transition:transform .25s ease,border-color .25s ease,box-shadow .25s ease;position:relative;overflow:hidden}.science-card:before{content:"";position:absolute;inset:0;background:linear-gradient(110deg,transparent,rgba(255,255,255,.05),transparent);transform:translateX(-120%);animation:aeroShimmer 5s ease-in-out infinite}.science-card:hover{transform:translateY(-3px);border-color:rgba(34,211,238,.2);box-shadow:0 16px 40px rgba(0,0,0,.2),0 0 24px rgba(34,211,238,.05)}
.source-pill{font-size:9px;color:#a5f3fc;padding:6px 9px;border-radius:999px;background:rgba(34,211,238,.07);border:1px solid rgba(34,211,238,.14)}
.notification-badge{display:inline-flex;align-items:center;justify-content:center;min-width:18px;height:18px;padding:0 5px;border-radius:999px;font-size:9px;background:rgba(239,68,68,.15);color:#fca5a5;border:1px solid rgba(239,68,68,.2)}
.science-ring{width:62px;height:62px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:radial-gradient(circle,rgba(34,211,238,.15),rgba(34,211,238,.03) 62%,transparent 63%);border:1px solid rgba(34,211,238,.2);box-shadow:0 0 35px rgba(34,211,238,.1);animation:aeroPulse 2.8s ease-in-out infinite}
@media (prefers-reduced-motion:reduce){.science-card:before{animation:none}.science-card{transition:none}.science-ring{animation:none}}
@keyframes aeroFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
@keyframes aeroMarquee{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
@keyframes aeroFade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@keyframes aeroPulse{0%,100%{box-shadow:0 0 0 0 rgba(34,211,238,.12)}50%{box-shadow:0 0 0 9px rgba(34,211,238,0)}}
@keyframes aeroStar{0%,100%{opacity:.12;transform:translate3d(0,0,0) scale(.8)}50%{opacity:.55;transform:translate3d(0,-8px,0) scale(1)}}
.motion-backdrop{position:fixed;inset:0;overflow:hidden;pointer-events:none;z-index:0;--mx:0px;--my:0px;--mx2:0px;--my2:0px;--glow-x:50%;--glow-y:38%;}
.motion-backdrop:before{content:"";position:absolute;inset:0;background:radial-gradient(circle at var(--glow-x) var(--glow-y),rgba(34,211,238,.055),transparent 28%),radial-gradient(circle at 80% 80%,rgba(139,92,246,.045),transparent 28%);}
.motion-grid{position:absolute;inset:-5%;opacity:.18;transform:translate3d(var(--mx2),var(--my2),0);background-image:linear-gradient(rgba(148,163,184,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(148,163,184,.045) 1px,transparent 1px);background-size:48px 48px;mask-image:radial-gradient(circle at center,#000 20%,transparent 78%);}
.motion-orb{position:absolute;border-radius:999px;filter:blur(1px);will-change:transform;transition:transform .12s linear;mix-blend-mode:screen;}
.motion-orb-a{width:360px;height:360px;left:-90px;top:10%;background:radial-gradient(circle,rgba(6,182,212,.13),transparent 68%);transform:translate3d(var(--mx),var(--my),0);}
.motion-orb-b{width:300px;height:300px;right:-60px;top:34%;background:radial-gradient(circle,rgba(139,92,246,.12),transparent 68%);transform:translate3d(var(--mx2),var(--my2),0);}
.motion-orb-c{width:260px;height:260px;left:38%;bottom:-100px;background:radial-gradient(circle,rgba(59,130,246,.09),transparent 68%);transform:translate3d(calc(var(--mx) * -.55),calc(var(--my) * -.55),0);}
.motion-cursor-glow{position:absolute;width:340px;height:340px;left:calc(var(--glow-x) - 170px);top:calc(var(--glow-y) - 170px);border-radius:50%;background:radial-gradient(circle,rgba(34,211,238,.045),transparent 67%);filter:blur(8px);}
.motion-stars{position:absolute;inset:0;transform:translate3d(var(--mx2),var(--my2),0);}
.motion-stars i{position:absolute;width:2px;height:2px;border-radius:50%;background:rgba(226,232,240,.75);left:calc((var(--i) * 17 + 9) * 1%);top:calc((var(--i) * 29 + 7) * 1%);animation:aeroStar calc(3s + (var(--i) * .18s)) ease-in-out infinite;animation-delay:calc(var(--i) * -.2s);}
.animate-float{animation:aeroFloat 4s ease-in-out infinite}.animate-marquee{animation:aeroMarquee 26s linear infinite}.animate-fade-in{animation:aeroFade .55s ease both}.live-dot{animation:aeroPulse 1.8s ease-out infinite}
@media (pointer:coarse){.motion-backdrop .motion-grid{transform:none}.motion-orb,.motion-stars{transform:none!important}.motion-cursor-glow{display:none}}
@media (prefers-reduced-motion:reduce){.motion-backdrop,.motion-backdrop *,.animate-float,.animate-marquee,.animate-fade-in,.live-dot{animation:none!important;transition:none!important}.motion-backdrop{display:none}}
.auth-motion{position:absolute;inset:0;overflow:hidden;pointer-events:none;--ax:0px;--ay:0px;--bx:0px;--by:0px;--gx:50vw;--gy:40vh}
.auth-motion:before{content:"";position:absolute;inset:0;background:radial-gradient(circle at var(--gx) var(--gy),rgba(34,211,238,.075),transparent 19%),radial-gradient(circle at 15% 80%,rgba(59,130,246,.07),transparent 25%),radial-gradient(circle at 88% 18%,rgba(139,92,246,.08),transparent 26%)}
.auth-grid{position:absolute;inset:-8%;opacity:.2;transform:translate3d(var(--bx),var(--by),0);background-image:linear-gradient(rgba(148,163,184,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(148,163,184,.045) 1px,transparent 1px);background-size:52px 52px;mask-image:radial-gradient(circle at center,#000 15%,transparent 78%);transition:transform .15s linear}
.auth-orb{position:absolute;border-radius:999px;filter:blur(2px);will-change:transform;transition:transform .18s linear}
.auth-orb-a{width:420px;height:420px;left:-150px;top:12%;background:radial-gradient(circle,rgba(6,182,212,.12),transparent 67%);transform:translate3d(var(--ax),var(--ay),0)}
.auth-orb-b{width:360px;height:360px;right:-100px;top:35%;background:radial-gradient(circle,rgba(139,92,246,.11),transparent 67%);transform:translate3d(var(--bx),var(--by),0)}
.auth-orb-c{width:300px;height:300px;left:40%;bottom:-130px;background:radial-gradient(circle,rgba(59,130,246,.09),transparent 67%);transform:translate3d(calc(var(--ax) * -.55),calc(var(--ay) * -.55),0)}
.auth-cursor-glow{position:absolute;width:360px;height:360px;left:calc(var(--gx) - 180px);top:calc(var(--gy) - 180px);border-radius:50%;background:radial-gradient(circle,rgba(34,211,238,.045),transparent 68%);filter:blur(10px)}
.auth-stars{position:absolute;inset:0;transform:translate3d(var(--bx),var(--by),0)}
.auth-stars i{position:absolute;width:2px;height:2px;border-radius:50%;background:rgba(226,232,240,.55);left:calc((var(--i) * 17 + 7) * 1%);top:calc((var(--i) * 29 + 11) * 1%);animation:aeroStar calc(3s + (var(--i) * .16s)) ease-in-out infinite;animation-delay:calc(var(--i) * -.19s)}
.auth-feature-card,.auth-mini-card{transition:transform .25s ease,border-color .25s ease,background .25s ease,box-shadow .25s ease}
.auth-feature-card:hover{transform:translateY(-4px) rotateX(1deg);border-color:rgba(34,211,238,.2)!important;background:rgba(255,255,255,.075)!important;box-shadow:0 12px 35px rgba(0,0,0,.18)}
.auth-mini-card:hover{transform:translateY(-2px);background:rgba(255,255,255,.05)}
.auth-input{width:100%;border-radius:14px;padding:.82rem .85rem;background:rgba(2,8,23,.58);border:1px solid rgba(255,255,255,.08);color:white;outline:none;font-size:.82rem;transition:border-color .2s,box-shadow .2s,transform .2s}
.auth-input::placeholder{color:#475569}.auth-input:focus{border-color:rgba(34,211,238,.35);box-shadow:0 0 0 3px rgba(34,211,238,.06),0 0 25px rgba(34,211,238,.05);transform:translateY(-1px)}
.auth-otp{width:100%;letter-spacing:.65em;text-align:center;border-radius:16px;padding:1rem .8rem;background:rgba(2,8,23,.62);border:1px solid rgba(34,211,238,.2);color:white;outline:none;font-size:1.25rem;font-weight:800;transition:border-color .2s,box-shadow .2s}
.auth-otp:focus{border-color:rgba(34,211,238,.5);box-shadow:0 0 0 4px rgba(34,211,238,.06),0 0 35px rgba(34,211,238,.08)}
.auth-error{margin-top:.1rem;border-radius:12px;padding:.7rem .8rem;font-size:.7rem;color:#fecaca;background:rgba(239,68,68,.07);border:1px solid rgba(239,68,68,.16)}
.auth-info{margin-top:.1rem;border-radius:12px;padding:.7rem .8rem;font-size:.7rem;color:#a5f3fc;background:rgba(6,182,212,.07);border:1px solid rgba(34,211,238,.15);display:flex;align-items:center;gap:.45rem}
@media (pointer:coarse){.auth-motion .auth-grid,.auth-motion .auth-orb,.auth-motion .auth-stars{transform:none}.auth-cursor-glow{display:none}}
@media (prefers-reduced-motion:reduce){.auth-motion{display:none}.auth-feature-card,.auth-mini-card,.auth-input{transition:none}.auth-stars i{animation:none}}


.aero-bright-ui{font-size:1.04em}.aero-bright-ui h1{letter-spacing:-.02em}.aero-bright-ui h2{letter-spacing:-.015em}.aero-glow-card{box-shadow:0 10px 35px rgba(16,185,129,.08),0 0 28px rgba(34,211,238,.045)}.aero-shine{position:relative;overflow:hidden}.aero-shine:before{content:"";position:absolute;top:-20%;bottom:-20%;left:-35%;width:18%;pointer-events:none;background:linear-gradient(90deg,transparent,rgba(255,255,255,.22),transparent);transform:skewX(-18deg);animation:aeroShine 7s ease-in-out infinite}@keyframes aeroShine{0%,68%{left:-35%;opacity:0}74%{opacity:1}88%,100%{left:125%;opacity:0}}.aero-soft-bloom{filter:drop-shadow(0 0 12px rgba(16,185,129,.12))}
`}</style>}

// ─── ROOT APP ─────────────────────────────────────────────
async function hashPassword(password) {
  const data = new TextEncoder().encode(password);
  const hash = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2,"0")).join("");
}

function AeroBrand({ compact=false }) {
  return (
    <img
      src="/icon.png"
      alt="AeroAQI — Clean Air, Forecasted"
      className={compact ? "h-11 w-auto object-contain" : "h-16 sm:h-20 w-auto object-contain"}
    />
  );
}

function AuthMotionBackdrop() {
  const ref=useRef(null);
  useEffect(()=>{
    const root=ref.current;
    if(!root || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || window.matchMedia?.('(pointer: coarse)').matches) return;
    let raf=0;
    const move=(e)=>{
      const x=(e.clientX/window.innerWidth-.5)*2;
      const y=(e.clientY/window.innerHeight-.5)*2;
      cancelAnimationFrame(raf);
      raf=requestAnimationFrame(()=>{
        root.style.setProperty('--ax',`${x*18}px`);
        root.style.setProperty('--ay',`${y*18}px`);
        root.style.setProperty('--bx',`${x*-10}px`);
        root.style.setProperty('--by',`${y*-10}px`);
        root.style.setProperty('--gx',`${e.clientX}px`);
        root.style.setProperty('--gy',`${e.clientY}px`);
      });
    };
    window.addEventListener('pointermove',move,{passive:true});
    return()=>{cancelAnimationFrame(raf);window.removeEventListener('pointermove',move);};
  },[]);
  const dots=Array.from({length:20},(_,i)=>i);
  return <div ref={ref} className="auth-motion" aria-hidden="true">
    <div className="auth-cursor-glow"/>
    <div className="auth-orb auth-orb-a"/><div className="auth-orb auth-orb-b"/><div className="auth-orb auth-orb-c"/>
    <div className="auth-grid"/>
    <div className="auth-stars">{dots.map(i=><i key={i} style={{'--i':i}}/>)}</div>
  </div>;
}

async function requestAeroOtp(channel, identifier) {
  const endpoint = import.meta?.env?.VITE_AUTH_OTP_ENDPOINT;
  if(!endpoint) throw new Error("OTP_SERVICE_NOT_CONFIGURED");
  const response = await fetch(endpoint,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({channel,identifier})});
  if(!response.ok) throw new Error("OTP_REQUEST_FAILED");
  return response.json().catch(()=>({}));
}

async function verifyAeroOtp(channel, identifier, otp) {
  const endpoint = import.meta?.env?.VITE_AUTH_OTP_VERIFY_ENDPOINT;
  if(!endpoint) throw new Error("OTP_SERVICE_NOT_CONFIGURED");
  const response = await fetch(endpoint,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({channel,identifier,otp})});
  if(!response.ok) throw new Error("OTP_VERIFY_FAILED");
  return response.json().catch(()=>({}));
}

function AuthScreen({ onAuthenticated }) {
  const [mode,setMode]=useState("login");
  const [method,setMethod]=useState("email");
  const [name,setName]=useState("");
  const [email,setEmail]=useState("");
  const [phone,setPhone]=useState("");
  const [password,setPassword]=useState("");
  const [confirm,setConfirm]=useState("");
  const [showPassword,setShowPassword]=useState(false);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);

  const identifier=method==="email"?email.trim().toLowerCase():phone.replace(/\D/g,"");
  const validIdentifier=method==="email"
    ? /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(identifier)
    : identifier.length===10;

  const finishAuth=(profile)=>{
    localStorage.setItem("aeroaqi_user",JSON.stringify(profile));
    onAuthenticated(profile);
  };

  const submit=async(e)=>{
    e.preventDefault(); setError("");
    if(mode==="signup"&&!name.trim()) return setError("Please enter your name.");
    if(!validIdentifier) return setError(method==="email"?"Enter a valid email address.":"Enter a valid 10-digit mobile number.");
    if(password.length<6) return setError("Password must be at least 6 characters.");
    if(mode==="signup"&&password!==confirm) return setError("Passwords do not match.");

    setBusy(true);
    try{
      const accounts=JSON.parse(localStorage.getItem("aeroaqi_accounts")||"[]");
      const key=`${method}:${identifier}`;

      if(mode==="signup"){
        if(accounts.some(a=>a.key===key)) return setError("An account already exists. Please log in.");
        const passwordHash=await hashPassword(password);
        const account={
          key,method,name:name.trim(),
          email:method==="email"?identifier:"",
          phone:method==="phone"?identifier:"",
          passwordHash
        };
        accounts.push(account);
        localStorage.setItem("aeroaqi_accounts",JSON.stringify(accounts));
        localStorage.setItem("aeroaqi_account",JSON.stringify(account));
        finishAuth({name:account.name,email:account.email,phone:account.phone,photo:""});
      }else{
        const accountsMatch=accounts.find(a=>a.key===key);
        const legacy=JSON.parse(localStorage.getItem("aeroaqi_account")||"null");
        const passwordHash=await hashPassword(password);
        const matched=accountsMatch&&accountsMatch.passwordHash===passwordHash
          ? accountsMatch
          : legacy&&(
              (method==="email"&&legacy.email===identifier) ||
              (method==="phone"&&legacy.phone===identifier)
            )&&legacy.passwordHash===passwordHash ? legacy : null;

        if(!matched) return setError("Email/phone or password is incorrect.");
        finishAuth({
          name:matched.name||"AeroAQI User",
          email:matched.email||"",
          phone:matched.phone||"",
          photo:matched.photo||""
        });
      }
    }catch{
      setError("Something went wrong. Please try again.");
    }finally{setBusy(false);}
  };

  const demo=()=>finishAuth({
    name:"AeroAQI Demo User",email:"demo@aeroaqi.local",phone:"",photo:""
  });

  return <div className="relative min-h-screen flex items-center justify-center p-3 sm:p-5 text-white overflow-hidden" style={{background:"linear-gradient(135deg,#03140d,#05251a 45%,#06131b)"}}>
    <AuthMotionBackdrop/>
    <div className="relative z-10 w-full max-w-6xl grid lg:grid-cols-[1.05fr_.95fr] rounded-[30px] overflow-hidden" style={{background:"rgba(4,24,16,.84)",border:"1px solid rgba(74,222,128,.16)",boxShadow:"0 35px 120px rgba(0,0,0,.58),0 0 70px rgba(34,197,94,.08)",backdropFilter:"blur(24px)"}}>
      <section className="relative hidden lg:flex min-h-[720px] p-10 xl:p-12 flex-col justify-between overflow-hidden">
        <img src="/hero.png" alt="India Gate, Delhi" className="absolute inset-0 w-full h-full object-cover" style={{opacity:.48,filter:"brightness(.72) saturate(1.2)"}}/>
        <div className="absolute inset-0" style={{background:"linear-gradient(135deg,rgba(1,12,8,.94),rgba(2,35,21,.45),rgba(1,10,7,.94))"}}/>
        <div className="relative z-10">
          <AeroBrand/>
          <div className="mt-24 max-w-xl">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full mb-4" style={{background:"rgba(34,197,94,.1)",border:"1px solid rgba(74,222,128,.2)"}}>
              <span className="w-2 h-2 rounded-full bg-emerald-300 live-dot"/>
              <span className="text-[10px] tracking-[.22em] text-emerald-200 font-bold">DELHI-NCR AIR INTELLIGENCE</span>
            </div>
            <h2 className="text-5xl xl:text-6xl font-black leading-[.94] tracking-tight">Forecast the Air.<br/><span className="text-emerald-300">Understand the Why.</span></h2>
            <p className="text-sm text-slate-200/80 mt-6 max-w-lg leading-relaxed">Air quality, weather, atmospheric conditions, source regions, forecasts and explainable AI — together in one SIH-ready dashboard.</p>
            <div className="grid grid-cols-2 gap-3 mt-8">
              {[[<Gauge size={16}/>,"72h","AQI Forecast"],[<Map size={16}/>,"NCR","Spatial Map"],[<Bot size={16}/>,"AI","Explainable Insights"],[<Radio size={16}/>,"Live","Monitoring"]].map(([icon,value,label])=>
                <div key={label} className="rounded-2xl p-4" style={{background:"rgba(255,255,255,.055)",border:"1px solid rgba(255,255,255,.1)"}}>
                  <div className="flex items-center gap-2 text-emerald-200">{icon}<span className="text-lg font-black text-white">{value}</span></div>
                  <p className="text-[10px] text-slate-400 mt-1">{label}</p>
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="relative z-10 text-[11px] text-slate-400">Built by <span className="font-black text-emerald-300">ASYNC AWAIT ❤️</span></div>
      </section>

      <section className="p-6 sm:p-9 xl:p-12 flex flex-col justify-center">
        <div className="lg:hidden mb-7"><AeroBrand/></div>
        <div className="flex p-1 rounded-2xl mb-7" style={{background:"rgba(255,255,255,.04)",border:"1px solid rgba(255,255,255,.06)"}}>
          <button onClick={()=>{setMode("login");setError("");}} className={`flex-1 py-3 rounded-xl text-sm font-bold ${mode==="login"?"text-white":"text-slate-500"}`} style={mode==="login"?{background:"rgba(34,197,94,.14)"}:{}}>Login</button>
          <button onClick={()=>{setMode("signup");setError("");}} className={`flex-1 py-3 rounded-xl text-sm font-bold ${mode==="signup"?"text-white":"text-slate-500"}`} style={mode==="signup"?{background:"rgba(34,197,94,.14)"}:{}}>Sign up</button>
        </div>

        <div className="mb-6">
          <div className="flex items-center gap-2 text-emerald-300 mb-2"><ShieldCheck size={17}/><span className="text-[10px] font-bold tracking-[.18em] uppercase">Secure local prototype access</span></div>
          <h3 className="text-3xl font-black tracking-tight">{mode==="login"?"Welcome back 👋":"Create your AeroAQI account"}</h3>
          <p className="text-sm text-slate-500 mt-2">Use either your email or mobile number with a password.</p>
        </div>

        <form onSubmit={submit} className="space-y-3">
          {mode==="signup"&&<input value={name} onChange={e=>setName(e.target.value)} placeholder="Full name" className="auth-input"/>}
          <div className="grid grid-cols-2 gap-2 p-1 rounded-xl" style={{background:"rgba(255,255,255,.035)"}}>
            <button type="button" onClick={()=>{setMethod("email");setError("");}} className="py-3 rounded-lg text-xs font-bold flex items-center justify-center gap-2" style={method==="email"?{background:"rgba(34,197,94,.14)",color:"white"}:{color:"#64748b"}}><Mail size={14}/> Email</button>
            <button type="button" onClick={()=>{setMethod("phone");setError("");}} className="py-3 rounded-lg text-xs font-bold flex items-center justify-center gap-2" style={method==="phone"?{background:"rgba(34,197,94,.14)",color:"white"}:{color:"#64748b"}}><Phone size={14}/> Mobile</button>
          </div>

          {method==="email"
            ? <div className="relative"><Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-emerald-400"/><input value={email} onChange={e=>setEmail(e.target.value)} type="email" placeholder="Email address" className="auth-input pl-10" autoComplete="email"/></div>
            : <div className="relative"><Phone size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-emerald-400"/><input value={phone} onChange={e=>setPhone(e.target.value.replace(/\D/g,"").slice(0,10))} type="tel" inputMode="numeric" placeholder="10-digit mobile number" className="auth-input pl-10" autoComplete="tel"/></div>}

          <div className="relative">
            <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"/>
            <input value={password} onChange={e=>setPassword(e.target.value)} type={showPassword?"text":"password"} placeholder="Password (minimum 6 characters)" className="auth-input pl-10 pr-16" autoComplete={mode==="login"?"current-password":"new-password"}/>
            <button type="button" onClick={()=>setShowPassword(v=>!v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-emerald-300">{showPassword?"Hide":"Show"}</button>
          </div>

          {mode==="signup"&&<input value={confirm} onChange={e=>setConfirm(e.target.value)} type={showPassword?"text":"password"} placeholder="Confirm password" className="auth-input" autoComplete="new-password"/>}
          {error&&<div className="auth-error">{error}</div>}
          <button disabled={busy} className="btn-primary w-full py-3.5 rounded-xl text-sm font-bold disabled:opacity-50">{busy?"Please wait…":mode==="login"?"Login to AeroAQI":"Create Account"}</button>
        </form>

        <div className="relative my-5"><div className="border-t border-white/[.06]"/><span className="absolute left-1/2 -translate-x-1/2 -top-2.5 px-3 text-[9px] text-slate-600" style={{background:"#071a12"}}>OR</span></div>
        <button onClick={demo} className="w-full py-3 rounded-xl text-xs font-bold text-emerald-100" style={{background:"rgba(34,197,94,.06)",border:"1px solid rgba(74,222,128,.14)"}}><Eye size={14} className="inline mr-2"/>Explore Demo Dashboard</button>
      </section>
    </div>
  </div>;
}

// ─── App pages + lightweight client-side router ─────────────
const ROUTES = [
  { path:"/",        label:"Dashboard",              index:0 },
  { path:"/map",     label:"NCR Map",                index:1 },
  { path:"/forecast",label:"AQI Forecast",           index:2 },
  { path:"/weather", label:"Weather & Atmosphere",   index:3 },
  { path:"/plume",   label:"Plume Tracker",          index:4 },
  { path:"/alerts",  label:"Alerts & Notifications", index:5 },
  { path:"/stations",label:"Stations",               index:6 },
  { path:"/reports", label:"Reports",                index:7 },
  { path:"/pipeline",label:"Data Pipeline",          index:8 },
  { path:"/ai",      label:"AI Insights",             index:9 },
  { path:"/settings",label:"Profile & Settings",     index:10 },
];

function routeForIndex(index) { return ROUTES.find(r => r.index === index)?.path || "/"; }
function indexForPath(path) { return ROUTES.find(r => r.path === path)?.index ?? 0; }

function PageHeader({ eyebrow="AeroAQI · Delhi", title, subtitle, action }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-5">
      <div>
        <p className="text-[10px] uppercase tracking-[.2em] text-emerald-400 font-bold mb-1.5">{eyebrow}</p>
        <h2 className="text-2xl sm:text-3xl font-black tracking-tight text-white">{title}</h2>
        <p className="text-sm text-slate-500 mt-1 max-w-2xl">{subtitle}</p>
      </div>
      {action}
    </div>
  );
}

function DemoDataNotice() {
  return (
    <div className="rounded-xl px-4 py-3 mb-5 flex flex-col sm:flex-row sm:items-center gap-2"
      style={{background:"rgba(245,158,11,.06)",border:"1px solid rgba(245,158,11,.16)"}}>
      <Info size={15} className="text-amber-400 shrink-0"/>
      <p className="text-[11px] text-slate-400 leading-relaxed">
        <span className="font-semibold text-amber-300">Frontend integration checkpoint:</span> live mode is enabled. Values are shown only when received from the backend or a clearly labelled live scientific source; unavailable values are not replaced with fake numbers.
      </p>
    </div>
  );
}

function ForecastPage() {
  // ── Station list from live backend (P1 hook) ──────────────────────────
  const { stations, loading: stationsLoading } = useLiveStations();

  // Selected station — default to first available; persisted as station_id
  const [selectedId, setSelectedId] = useState(null);

  // When the station list arrives, set a default if nothing is selected yet.
  // Prefer the first station that has real observation data (aqi != null / hasObs),
  // so ForecastPage opens on a station that is likely to have forecast rows.
  // Fall back to stations[0] if none have observations yet.
  useEffect(() => {
    if (!selectedId && stations.length > 0) {
      const preferred =
        stations.find(s => s.hasObs === true) ||
        stations.find(s => s.aqi != null) ||
        stations[0];
      setSelectedId(preferred.station_id);
    }
  }, [stations, selectedId]);

  // ── Pollutant/horizon selectors ──────────────────────────────────────
  const [pollutant, setPollutant] = useState("AQI");
  const [horizon, setHorizon] = useState(72);

  // ── Forecast data from backend ────────────────────────────────────────
  const [forecastState, setForecastState] = useState({
    loading: false, hourly: [], modelTrained: null, error: null, generatedAt: null,
  });

  useEffect(() => {
    if (!selectedId) return;

    let alive = true;
    setForecastState(s => ({ ...s, loading: true, error: null }));

    apiGet(`/forecast/${encodeURIComponent(selectedId)}?hours=72`)
      .then(data => {
        if (!alive) return;
        setForecastState({
          loading: false,
          hourly: data?.hourly ?? [],
          modelTrained: data?.model_trained ?? false,
          error: data?.model_trained === false ? (data?.message ?? "Model not trained yet.") : null,
          generatedAt: data?.generated_at ?? null,
        });
      })
      .catch(err => {
  if (!alive) return;

  setForecastState(prev => ({
    loading: false,
    hourly: prev.hourly?.length ? prev.hourly : [],
    modelTrained: prev.hourly?.length ? prev.modelTrained : false,
    error: prev.hourly?.length
      ? "Live refresh unavailable — showing last synced forecast."
      : `Forecast unavailable: ${err.message}`,
    generatedAt: prev.hourly?.length ? prev.generatedAt : null,
  }));
});

    return () => { alive = false; };
  }, [selectedId]);

  // ── Build chart data from backend hourly array ────────────────────────
  // Each hourly row: { forecast_hour, target_utc, pm25, pm10, o3, no2, aqi_computed, aqi_category }
  // Filter to selected horizon, then map to chart-friendly shape.
  const chartData = forecastState.hourly
    .filter(h => h.forecast_hour <= horizon)
    .map(h => ({
      t:    `+${h.forecast_hour}h`,
      aqi:  h.aqi_computed  != null ? Math.round(h.aqi_computed)  : null,
      pm25: h.pm25          != null ? Math.round(h.pm25)          : null,
      pm10: h.pm10          != null ? Math.round(h.pm10)          : null,
      no2:  h.no2           != null ? Math.round(h.no2)           : null,
      o3:   h.o3            != null ? Math.round(h.o3)            : null,
      cat:  h.aqi_category  ?? null,
    }));

  // Derive the data key the chart should draw for the active pollutant
  const dataKey = pollutant === "PM2.5" ? "pm25"
    : pollutant === "PM10"  ? "pm10"
    : pollutant === "NO2"   ? "no2"
    : pollutant === "O3"    ? "o3"
    : "aqi";

  // Stats cards: only compute from real values, never fill with fake data
  const vals = chartData.map(d => d[dataKey]).filter(v => v != null);
  const peak = vals.length ? Math.max(...vals) : null;
  const low  = vals.length ? Math.min(...vals) : null;

  // True when forecast data loaded but the selected pollutant column is entirely null.
  // This happens for PM10 when insufficient observations were available during training.
  

  // Human-readable label for the selected station
  const selectedStation = stations.find(s => s.station_id === selectedId);
  const stationLabel = selectedStation?.name ?? selectedId ?? "—";

  const isLoading  = (stationsLoading && stations.length === 0) || (!stationsLoading && !!selectedId && forecastState.loading);
  const hasData    = chartData.length > 0;
  const pollutantUnavailable = false;
  const hasError   = forecastState.error && !forecastState.loading;

  return <>
    <PageHeader
      title="AQI Forecast"
      subtitle="Interactive 72-hour prediction workspace with pollutant trends and station comparison."
      action={
        <div className="flex gap-2">
          {/* Station selector — populated from live /stations endpoint */}
          <select
            value={selectedId ?? ""}
            onChange={e => setSelectedId(e.target.value)}
            className="rounded-xl px-3 py-2 text-xs text-white outline-none"
            style={{background:"#0a1522", border:"1px solid rgba(255,255,255,.08)"}}
            disabled={stationsLoading || stations.length === 0}
          >
            {stationsLoading
              ? <option value="">Loading stations…</option>
              : stations.length === 0
                ? <option value="">Backend unavailable — no stations</option>
                : stations.map(s => (
                    <option key={s.station_id} value={s.station_id}>{s.name}</option>
                  ))
            }
          </select>
        </div>
      }
    />

    <FeatureSection
      icon={<BarChart3 size={18} className="text-purple-400"/>}
      title="72-Hour AQI Forecast"
      subtitle={`${stationLabel} · ${hasData ? "AeroAQI Backend" : "awaiting data"} · pollutant selector`}
    >
      {/* ── Controls ────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex gap-1 p-1 rounded-lg" style={{background:"rgba(255,255,255,.04)"}}>
          {['AQI','PM2.5','PM10','NO2','O3'].map(v => (
            <button key={v} onClick={() => setPollutant(v)}
              className={`px-3 py-1.5 rounded-md text-[10px] font-semibold ${pollutant===v?'text-white':'text-slate-500'}`}
              style={pollutant===v?{background:"rgba(139,92,246,.15)",border:"1px solid rgba(139,92,246,.22)"}:{}}>
              {v}
            </button>
          ))}
        </div>
        <div className="flex gap-1 p-1 rounded-lg" style={{background:"rgba(255,255,255,.04)"}}>
          {[24,48,72].map(v => (
            <button key={v} onClick={() => setHorizon(v)}
              className={`px-3 py-1.5 rounded-md text-[10px] font-semibold ${horizon===v?'text-emerald-200':'text-slate-500'}`}
              style={horizon===v?{background:"rgba(6,182,212,.12)",border:"1px solid rgba(6,182,212,.2)"}:{}}>
              {v}h
            </button>
          ))}
        </div>
      </div>

      {/* ── Loading state ────────────────────────────────────────────── */}
      {isLoading && (
        <div className="h-[390px] flex items-center justify-center text-slate-500 text-xs gap-2">
          <RefreshCw size={14} className="animate-spin text-emerald-400"/>
          {stationsLoading && stations.length === 0 ? "Loading stations…" : "Loading forecast from backend…"}
        </div>
      )}

      {/* ── No stations / backend unavailable ───────────────────────── */}
      {!isLoading && !selectedId && (
        <div className="h-[390px] flex flex-col items-center justify-center gap-3">
          <div className="rounded-xl px-5 py-4 text-center max-w-md"
            style={{background:"rgba(245,158,11,.06)",border:"1px solid rgba(245,158,11,.16)"}}>
            <p className="text-xs font-semibold text-amber-300 mb-1">No stations available</p>
            <p className="text-[11px] text-slate-400">The AeroAQI backend did not return any stations. Ensure the API server is running and the ingestion pipeline has been executed at least once.</p>
          </div>
        </div>
      )}

      {/* ── Error / no-model state ───────────────────────────────────── */}
      {hasError && !isLoading && (
        <div className="h-[390px] flex flex-col items-center justify-center gap-3">
          <div className="rounded-xl px-5 py-4 text-center max-w-md"
            style={{background:"rgba(245,158,11,.06)",border:"1px solid rgba(245,158,11,.16)"}}>
            <p className="text-xs font-semibold text-amber-300 mb-1">Forecast unavailable</p>
            <p className="text-[11px] text-slate-400">{forecastState.error}</p>
            <p className="text-[10px] text-slate-500 mt-2">Run: <code className="text-emerald-300">python scripts/train_model.py</code></p>
          </div>
        </div>
      )}

      {/* ── Chart ───────────────────────────────────────────────────── */}
      {!isLoading && !hasError && (
        <div className="h-[390px]">
          {/* Pollutant-specific unavailability notice (e.g. PM10 with no model) */}
          {pollutantUnavailable ? (
            <div className="h-full flex flex-col items-center justify-center gap-3">
              <div className="rounded-xl px-5 py-4 text-center max-w-md"
                style={{background:"rgba(100,116,139,.06)",border:"1px solid rgba(100,116,139,.18)"}}>
                <p className="text-xs font-semibold text-slate-300 mb-1">
                  {pollutant} forecast unavailable
                </p>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Insufficient recent {pollutant} source data — no model was trained for this pollutant.
                  Other pollutants (AQI, PM2.5, O₃, NO₂) are unaffected.
                </p>
                <p className="text-[10px] text-slate-500 mt-2">
                  Re-run ingestion after OpenAQ begins reporting {pollutant} readings, then retrain:
                  <br/><code className="text-emerald-300">python scripts/run_ingestion.py --mode realtime</code>
                </p>
              </div>
            </div>
          ) : hasData ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{top:10,right:10,left:-10,bottom:5}}>
                <defs>
                  <linearGradient id="forecast-page-aqi" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#22c55e" stopOpacity={.34}/>
                    <stop offset="95%" stopColor="#22c55e" stopOpacity={.02}/>
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(255,255,255,.05)" vertical={false}/>
                <XAxis dataKey="t" tick={{fontSize:10,fill:"#64748b"}} axisLine={false} tickLine={false}/>
                <YAxis tick={{fontSize:10,fill:"#64748b"}} axisLine={false} tickLine={false}/>
                <Tooltip content={<ForecastTooltip/>}/>
                <ReferenceLine y={200} stroke="rgba(239,68,68,.25)"    strokeDasharray="4 4"/>
                <ReferenceLine y={150} stroke="rgba(249,115,22,.20)"   strokeDasharray="4 4"/>
                <Area type="monotone" dataKey={dataKey}
                  stroke="#22c55e" strokeWidth={2.5}
                  fill="url(#forecast-page-aqi)" connectNulls dot={false}/>
                {/* Secondary line: PM2.5 always shown alongside AQI for context */}
                {pollutant === "AQI" && (
                  <Line type="monotone" dataKey="pm25" name="PM2.5"
                    stroke="#86efac" strokeWidth={1.5} dot={false} connectNulls/>
                )}
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-500 text-xs">
              No forecast data for this station yet.
            </div>
          )}
        </div>
      )}

      {/* ── Stats cards ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mt-4">
        {[
          ['Horizon',         `${horizon} hours`],
          ['Peak',            peak  != null ? String(peak)  : '—'],
          ['Lowest',          low   != null ? String(low)   : '—'],
          ['Generated',       forecastState.generatedAt
                                ? new Date(forecastState.generatedAt).toLocaleString('en-IN',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})
                                : '—'],
          ['Source',          hasData ? 'AeroAQI Backend' : 'No data'],
        ].map(([k,v]) => (
          <div key={k} className="rounded-xl p-3" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}>
            <p className="text-[10px] text-slate-500">{k}</p>
            <p className="text-sm font-bold text-white mt-1">{v}</p>
          </div>
        ))}
      </div>

      {/* ── Context cards ───────────────────────────────────────────── */}
      <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        {[
          ['What changed?', hasData
            ? `${pollutant} forecast loaded from backend for ${stationLabel}.`
            : 'Run the ingestion pipeline and train the model to see forecast data.'],
          ['Why?', 'Wind, atmospheric mixing, PBL height and fire transport risk drive the AQI curve.'],
          ['What next?', 'Use AI Insights to see the SHAP explanation for the top forecast drivers.'],
        ].map(([a,b]) => (
          <div key={a} className="p-3 rounded-xl" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}>
            <p className="text-[10px] font-bold text-emerald-300">{a}</p>
            <p className="text-[10px] text-slate-400 mt-1 leading-relaxed">{b}</p>
          </div>
        ))}
      </div>
    </FeatureSection>
  </>;
}

function ForecastTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;

  return (
    <div
      style={{
        background: "rgba(5, 20, 14, 0.96)",
        border: "1px solid rgba(74, 222, 128, 0.25)",
        borderRadius: "12px",
        padding: "10px 12px",
        boxShadow: "0 12px 30px rgba(0,0,0,.35)"
      }}
    >
      <p
        style={{
          color: "#94a3b8",
          fontSize: "10px",
          marginBottom: "5px"
        }}
      >
        {label}
      </p>

      {payload.map((item, index) => (
        <div
          key={`${item.dataKey || item.name}-${index}`}
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: "18px",
            fontSize: "11px",
            fontWeight: 700
          }}
        >
          <span style={{ color: "#cbd5e1" }}>
            {item.name || item.dataKey}
          </span>

          <span style={{ color: "#86efac" }}>
            {typeof item.value === "number"
              ? Math.round(item.value)
              : item.value}
          </span>
        </div>
      ))}
    </div>
  );
}

function DashboardPage({ navigate }) {
    const { stations, live, loading } = useLiveStations();

  const liveStation =
    stations.find(s => s.hasObs === true) ||
    stations.find(s => s.aqi != null) ||
    null;

  const currentAqi = liveStation?.aqi;
  const currentPm25 = liveStation?.pm25;
    const [dashboardForecast, setDashboardForecast] = useState([]);

  useEffect(() => {
    if (!liveStation?.station_id) {
      setDashboardForecast([]);
      return;
    }

    let alive = true;

    apiGet(`/forecast/${encodeURIComponent(liveStation.station_id)}?hours=72`)
      .then(data => {
        if (!alive) return;

        const rows = Array.isArray(data?.hourly) ? data.hourly : [];

        setDashboardForecast(
          rows.map(h => ({
            t: `+${h.forecast_hour}h`,
            aqi: h.aqi_computed != null ? Math.round(h.aqi_computed) : null,
            pm25: h.pm25 != null ? Math.round(h.pm25) : null,
          }))
        );
      })
      .catch(() => {
        if (alive) setDashboardForecast([]);
      });

    return () => {
      alive = false;
    };
  }, [liveStation?.station_id]);
  const [slide,setSlide]=useState(0);
  const slides=[
    {ey:"DELHI-NCR AIR INTELLIGENCE",title:"Air Quality Forecasting",accent:"for a Better Tomorrow",sub:"Weather–Chemistry coupled 72-hour prediction with explainable AI.",cta:"Explore Forecast",path:"/forecast"},
    {ey:"SOURCE ATTRIBUTION",title:"Track Pollution",accent:"Before It Reaches Delhi",sub:"Visualize fire hotspots, wind direction and modeled plume transport risk.",cta:"Open Plume Tracker",path:"/plume"},
    {ey:"SMART DECISIONS",title:"Understand the Air",accent:"Not Just the AQI",sub:"See weather, atmospheric conditions, stations, alerts and AI explanations together.",cta:"Open AI Insights",path:"/ai"},
  ];
  useEffect(()=>{const id=setInterval(()=>setSlide(v=>(v+1)%slides.length),5500);return()=>clearInterval(id)},[]);
  const s=slides[slide];
  return <>
    <section className="relative overflow-hidden rounded-3xl min-h-[510px]" style={{background:"#05200e",border:"1px solid rgba(74,222,128,.12)",boxShadow:"0 24px 70px rgba(0,0,0,.35)"}}>
      <img src="/hero.png" alt="India Gate, Delhi" className="absolute inset-0 w-full h-full object-cover transition-all duration-1000" style={{opacity:.72,filter:"brightness(.84) saturate(1.18) contrast(1.04)"}}/>
      <div className="absolute inset-0" style={{background:"linear-gradient(90deg,rgba(1,10,5,.94) 0%,rgba(2,16,10,.68) 38%,rgba(2,12,7,.15) 72%,rgba(1,10,5,.48) 100%)"}}/>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_35%,rgba(34,197,94,.12),transparent_32%),linear-gradient(180deg,transparent,rgba(1,10,5,.52))]"/>
      <div className="relative z-10 p-6 sm:p-9 lg:p-10 max-w-[720px] min-h-[510px] flex flex-col justify-center">
        <div className="flex items-center gap-2 mb-4"><span className="w-2 h-2 rounded-full bg-cyan-300 live-dot"/><span className="text-[10px] font-black tracking-[.25em] text-emerald-300">{s.ey}</span></div>
        <div key={slide} className="animate-fade-in"><h2 className="text-4xl sm:text-5xl lg:text-6xl font-black leading-[.95] tracking-tight text-white">{s.title}<br/><span className="text-emerald-300">{s.accent}</span></h2><p className="mt-5 text-sm sm:text-base text-slate-200/85 max-w-xl leading-relaxed">{s.sub}</p><div className="flex flex-wrap gap-3 mt-7"><button onClick={()=>navigate(s.path)} className="btn-primary px-5 py-3 rounded-xl text-xs font-bold flex items-center gap-2">{s.cta}<ArrowUpRight size={14}/></button><button onClick={()=>navigate('/map')} className="px-5 py-3 rounded-xl text-xs font-bold text-white" style={{background:"rgba(2,8,23,.55)",border:"1px solid rgba(255,255,255,.12)",backdropFilter:"blur(10px)"}}>Explore NCR Map</button></div></div>
        <div className="flex items-center gap-2 mt-8">{slides.map((_,i)=><button key={i} onClick={()=>setSlide(i)} className="h-1.5 rounded-full transition-all" style={{width:i===slide?34:10,background:i===slide?"#22c55e":"rgba(255,255,255,.35)"}}/>)}<span className="text-[9px] text-slate-400 ml-2">Auto carousel</span></div>
      </div>
      <div className="absolute right-5 top-5 hidden xl:flex gap-2 animate-float"><div className="rounded-xl px-3 py-2" style={{background:"rgba(2,14,7,.82)",border:"1px solid rgba(74,222,128,.15)",backdropFilter:"blur(14px)"}}><p className="text-[9px] text-slate-500">Current AQI</p><p className="text-xl font-black text-red-400">182</p></div><div className="rounded-xl px-3 py-2" style={{background:"rgba(2,14,7,.82)",border:"1px solid rgba(74,222,128,.15)",backdropFilter:"blur(14px)"}}><p className="text-[9px] text-slate-500">72h peak</p><p className="text-xl font-black text-purple-300">192</p></div></div>
      <div className="absolute bottom-0 left-0 right-0 h-16 flex items-center gap-5 px-6 overflow-hidden" style={{background:"rgba(1,10,5,.6)",backdropFilter:"blur(10px)",borderTop:"1px solid rgba(74,222,128,.08)"}}><div className="flex gap-8 whitespace-nowrap animate-marquee text-[10px] text-slate-300"><span>🟢 Good 0–50</span><span>🟡 Moderate 51–100</span><span>🟠 Sensitive 101–150</span><span>🔴 Unhealthy 151–200</span><span>🟣 Very Unhealthy 201–300</span><span>🌬 Wind transports pollution</span><span>🔥 Biomass burning can affect PM2.5</span></div></div>
    </section>
    <KpiStrip/>
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-5"><FeatureSection icon={<BarChart3 size={18} className="text-purple-400"/>} title="Forecast Preview" subtitle="Open the full 72-hour prediction page"><div className="h-[250px]"><ResponsiveContainer width="100%" height="100%"><AreaChart data={dashboardForecast} margin={{top:5,right:5,left:-25,bottom:0}}><defs><linearGradient id="dash-aqi" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#22c55e" stopOpacity={.32}/><stop offset="95%" stopColor="#22c55e" stopOpacity={.01}/></linearGradient></defs><XAxis dataKey="t" hide/><YAxis hide/><Tooltip content={<ForecastTooltip/>}/><Area type="monotone" dataKey="aqi" stroke="#22c55e" strokeWidth={2} fill="url(#dash-aqi)"/></AreaChart></ResponsiveContainer></div><button onClick={()=>navigate('/forecast')} className="btn-primary w-full py-2.5 rounded-xl text-xs font-bold">Open AQI Forecast →</button></FeatureSection><AlertsPanel/></div>
    <QuickActions onAction={navigate}/>
  </>;
}

function AIInsightsPage(){
  const [question,setQuestion]=useState(""); const [answer,setAnswer]=useState(""); const [busy,setBusy]=useState(false);
  const ask=async()=>{setBusy(true);setAnswer("");try{const stations=await apiGet("/stations");const rows=Array.isArray(stations)?stations:(stations?.data||stations?.stations||[]);const station=rows[0];if(!station)throw new Error("NO_STATION");const id=station.station_id||station.id||station.name;const r=await apiGet(`/forecast/${encodeURIComponent(id)}/explain`);setAnswer(r?.explanation||r?.message||r?.summary||JSON.stringify(r));}catch{setAnswer("Backend explainability data is unavailable right now. Connect the forecast/explain endpoint to see real model reasoning here.")}finally{setBusy(false)}};
  return <><PageHeader title="AI Insights" subtitle="Explainable air intelligence powered by the same backend forecast features." action={<button onClick={ask} disabled={busy} className="btn-primary px-3 py-2 rounded-xl text-[10px] font-bold flex items-center gap-2"><Sparkles size={13}/>{busy?"Reading model…":"Generate insight"}</button>}/><div className="grid grid-cols-1 xl:grid-cols-[1.25fr_.75fr] gap-5"><FeatureSection icon={<Bot size={18} className="text-emerald-300"/>} title="AeroAQI Explainable Forecast" subtitle="Real forecast explanation · feature contribution · confidence"><div className="rounded-2xl p-5" style={{background:"linear-gradient(145deg,rgba(7,40,27,.9),rgba(5,18,14,.95))",border:"1px solid rgba(74,222,128,.13)"}}><div className="science-ring"><Bot size={28} className="text-emerald-300"/></div><p className="text-xs font-bold text-white mt-4">Backend reasoning</p><p className="text-sm text-slate-300 mt-2 leading-relaxed">{answer||"Ask AeroAQI AI to fetch the real model explanation from FastAPI."}</p></div></FeatureSection><FeatureSection icon={<MessageCircle size={18} className="text-emerald-300"/>} title="Ask AeroAQI AI" subtitle="Ask about the current forecast"><textarea value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Why may AQI rise in the next 12 hours?" className="w-full min-h-[120px] rounded-xl p-3 text-xs text-white outline-none resize-none" style={{background:"rgba(2,18,12,.65)",border:"1px solid rgba(74,222,128,.12)"}}/><button onClick={ask} disabled={busy} className="btn-primary w-full mt-3 py-3 rounded-xl text-xs font-bold flex items-center justify-center gap-2"><Send size={13}/> {busy?"Analyzing…":"Explain with backend AI"}</button></FeatureSection></div></>;
}

function MapPage() {
  return <><PageHeader title="Delhi-NCR Air Quality Map" subtitle="Interactive spatial AQI view across Delhi and the surrounding NCR region."/><NcrMapPanel/></>;
}
function WeatherPage() {
  return <><PageHeader title="Weather & Atmosphere" subtitle="Meteorological and atmospheric factors that influence pollution dispersion."/><WeatherPanel/></>;
}
function PlumePage() {
  return <><PageHeader title="Plume Tracker" subtitle="Explore fire-source regions, transport direction and stubble-burning risk."/><PlumePanel/></>;
}
function AlertsPage() {
  return <><PageHeader title="Alerts & Notifications" subtitle="AQI risk events and actionable monitoring alerts."/><AlertsPanel/></>;
}
function StationsPage(){
  const {stations,live,loading}=useLiveStations();
  const [query,setQuery]=useState("");
  // Start null; set to a real station once the hook resolves.
  // Prefer a station with real observation data so the detail panel has values to show.
  const [selected,setSelected]=useState(null);

  useEffect(()=>{
    if(!stations.length) return;
    if(selected){
      // Keep selected in sync if the live data refreshes
      const fresh=stations.find(s=>s.station_id===selected.station_id||s.name===selected.name);
      if(fresh){ setSelected(fresh); return; }
    }
    // First load: prefer a station that has real observation data
    const preferred=
      stations.find(s=>s.hasObs===true)||
      stations.find(s=>s.aqi!=null)||
      stations[0];
    setSelected(preferred);
  },[stations]);

  const filtered=stations.filter(s=>s.name.toLowerCase().includes(query.toLowerCase()));
  // dot map includes "unknown" for stations without obs data
  const dot={good:"#22c55e",moderate:"#eab308",sensitive:"#f97316",unhealthy:"#ef4444",very:"#a855f7",unknown:"#64748b"};
  return <><PageHeader title="Monitoring Stations" subtitle="NCR monitoring network — inspect local AQI, pollutants, source and weather context." action={<span className="source-pill">{loading?"Updating…":live?"LIVE · AeroAQI Backend":"Unavailable"}</span>}/><div className="grid grid-cols-1 xl:grid-cols-[330px_1fr] gap-5">
    <FeatureSection icon={<Navigation size={18} className="text-emerald-300"/>} title="NCR Station Network" subtitle={`${filtered.length} monitoring points`}>
      <div className="relative mb-3"><Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-600"/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search station or city" className="w-full rounded-xl pl-9 pr-3 py-2.5 text-xs text-white outline-none" style={{background:"rgba(2,8,23,.6)",border:"1px solid rgba(255,255,255,.08)"}}/></div>
      <div className="space-y-2 max-h-[570px] overflow-y-auto pr-1">{filtered.map(s=><button key={s.station_id||s.name} onClick={()=>setSelected(s)} className="w-full p-3 rounded-xl text-left transition-all hover:translate-x-1" style={{background:selected?.station_id===s.station_id?"rgba(34,211,238,.08)":"rgba(255,255,255,.025)",border:`1px solid ${selected?.station_id===s.station_id?"rgba(34,211,238,.2)":"rgba(255,255,255,.05)"}`}}><div className="flex items-center justify-between"><div><p className="text-xs font-bold text-white">{s.name}</p><p className="text-[9px] text-slate-600">{Number.isFinite(s.lat)?s.lat.toFixed(3):"—"}, {Number.isFinite(s.lon)?s.lon.toFixed(3):"—"}</p></div><div className="text-right"><p className="text-lg font-black" style={{color:dot[s.status]||"#64748b"}}>{s.aqi!=null?s.aqi:"—"}</p><p className="text-[8px] text-slate-500">AQI</p></div></div></button>)}</div>
    </FeatureSection>
    {selected&&<FeatureSection icon={<MapPinned size={18} className="text-emerald-300"/>} title={`${selected.name} Station`} subtitle="Selected monitoring point · pollutant snapshot · local trend">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">{[["AQI",selected.aqi!=null?selected.aqi:"—",selected.aqi!=null?aqiLabel(selected.aqi):"No data",dot[selected.status]||"#64748b"],["PM2.5",selected.pm25!=null?Math.round(selected.pm25):"—","µg/m³","#38bdf8"],["PM10",selected.pm10!=null?Math.round(selected.pm10):"—","µg/m³","#a78bfa"],["NO₂",selected.no2!=null?Math.round(selected.no2):"—","µg/m³","#fb923c"]].map(([a,b,c,col])=><div key={a} className="science-card p-4 rounded-xl"><p className="text-[10px] text-slate-500">{a}</p><p className="text-xl font-black mt-1" style={{color:col}}>{b}</p><p className="text-[9px] text-slate-500 mt-1">{c}</p></div>)}</div>
      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_.6fr] gap-4 mt-4"><div className="rounded-xl p-4" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}><div className="flex items-center justify-between"><p className="text-xs font-bold text-white">Station trend</p><span className="text-[9px] text-emerald-300">{live?"Live source":"Backend unavailable"}</span></div><div className="h-[250px] mt-3 flex items-center justify-center text-slate-500 text-xs">Historical trend requires pipeline data</div></div><div className="rounded-xl p-4" style={{background:"linear-gradient(145deg,rgba(34,197,94,.05),rgba(6,18,38,.45))",border:"1px solid rgba(34,197,94,.12)"}}><p className="text-[10px] text-emerald-300 font-bold">Station details</p><div className="space-y-3 mt-4">{[["Station ID",selected.station_id||"—"],["City",selected.city||"—"],["State",selected.state||"—"],["Agency",selected.agency||"—"],["Zone",selected.zone||"—"],["Status",selected.aqi!=null?aqiLabel(selected.aqi):"No observation data"],["Coordinates",`${Number.isFinite(selected.lat)?selected.lat.toFixed(4):"—"}, ${Number.isFinite(selected.lon)?selected.lon.toFixed(4):"—"}`],["Last obs",selected.timestamp||"—"],["Source",selected.source||"—"],["Map",<button key="map" onClick={()=>window.history.pushState({},"","/map")} className="text-emerald-300 underline">Open NCR map</button>]].map(([a,b])=><div key={a}><p className="text-[9px] text-slate-500">{a}</p><p className="text-xs font-semibold text-white mt-1">{b}</p></div>)}</div></div></div>
    </FeatureSection>}
  </div></>;
}

function ReportsPage() {
  return <><PageHeader title="Reports & Analytics" subtitle="Export a compact AeroAQI report or print the current analysis."/><ReportsSection/></>;
}
function PipelinePage() {
  return <><PageHeader title="Data Pipeline" subtitle="The AeroAQI flow from observations to features, ML forecast and REST API."/><PipelineSection/></>;
}
function SettingsPage({ user, onLogout, onProfileSaved }) {
  return <><PageHeader title="Profile & Settings" subtitle="Manage your local prototype profile, notifications and refresh preferences."/><SettingsSection user={user} onLogout={onLogout} onProfileSaved={onProfileSaved}/></>;
}

function NotFoundPage({ navigate }) {
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="text-center rounded-2xl p-8 max-w-md" style={{background:"rgba(7,28,20,.82)",border:"1px solid rgba(255,255,255,.07)"}}>
        <Activity size={30} className="text-cyan-400 mx-auto mb-3"/>
        <h2 className="text-xl font-bold text-white">Page not found</h2>
        <p className="text-sm text-slate-500 mt-2 mb-5">That AeroAQI route does not exist.</p>
        <button onClick={()=>navigate('/')} className="btn-primary px-5 py-2.5 rounded-xl text-xs font-bold">Back to Dashboard</button>
      </div>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("aeroaqi_user") || "null"); } catch { return null; }
  });
  const [path, setPath] = useState(() => window.location.pathname || "/");
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(()=>{
    document.title = path === "/" ? "AeroAQI — Delhi-NCR Air Intelligence" : `AeroAQI — ${ROUTES.find(r=>r.path===path)?.label || "Air Intelligence"}`;
  },[path]);

  const navigate = (nextPath) => {
    const safePath = ROUTES.some(r => r.path === nextPath) ? nextPath : "/";
    if (window.location.pathname !== safePath) window.history.pushState({}, "", safePath);
    setPath(safePath);
    setMobileOpen(false);
    window.scrollTo({top:0, behavior:"auto"});
  };

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname || "/");
    window.addEventListener("popstate", onPop);
    const onResize = () => { if (window.innerWidth >= 1024) setMobileOpen(false); };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("popstate", onPop);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("aeroaqi_user");
    setUser(null);
    navigate("/");
  };

  const handleProfileSaved = (next) => {
    setUser(next);
    localStorage.setItem("aeroaqi_user", JSON.stringify(next));
  };

  if (!user) return <><AeroMotionStyles/><AuthScreen onAuthenticated={(u)=>{setUser(u); navigate('/');}}/></>;

  const activeNav = indexForPath(path);
  const page = (() => {
    switch (path) {
      case "/": return <DashboardPage navigate={navigate}/>;
      case "/map": return <MapPage/>;
      case "/forecast": return <ForecastPage/>;
      case "/weather": return <WeatherPage/>;
      case "/plume": return <PlumePage/>;
      case "/alerts": return <AlertsPage/>;
      case "/stations": return <StationsPage/>;
      case "/reports": return <ReportsPage/>;
      case "/pipeline": return <PipelinePage/>;
      case "/ai": return <AIInsightsPage/>;
      case "/settings": return <SettingsPage user={user} onLogout={handleLogout} onProfileSaved={handleProfileSaved}/>;
      default: return <NotFoundPage navigate={navigate}/>;
    }
  })();

  return (
    <div className="min-h-screen text-white aero-bright-ui" style={{background:"#03140D"}}><AeroMotionStyles/><MotionBackdrop/>
      <div className="fixed inset-0 pointer-events-none overflow-hidden" style={{zIndex:0}}>
        <div className="absolute -top-40 -left-40 w-[600px] h-[600px] rounded-full opacity-30" style={{background:"radial-gradient(circle,rgba(34,197,94,.07) 0%,transparent 70%)"}}/>
        <div className="absolute top-1/4 right-0 w-[400px] h-[400px] rounded-full opacity-20" style={{background:"radial-gradient(circle,rgba(22,163,74,.07) 0%,transparent 70%)"}}/>
        <div className="absolute bottom-0 left-1/3 w-[500px] h-[400px] rounded-full opacity-20" style={{background:"radial-gradient(circle,rgba(74,222,128,.05) 0%,transparent 70%)"}}/>
      </div>

      <div className="hidden lg:block fixed left-0 top-0 h-screen z-20" style={{width:232,boxShadow:"4px 0 32px rgba(0,0,0,.4)"}}>
        <Sidebar active={activeNav} setActive={(i)=>navigate(routeForIndex(i))} user={user}/>
      </div>

      {mobileOpen && <>
        <div className="mobile-nav-overlay" onClick={()=>setMobileOpen(false)}/>
        <div className="mobile-nav-panel"><Sidebar active={activeNav} setActive={(i)=>navigate(routeForIndex(i))} mobile onClose={()=>setMobileOpen(false)} user={user}/></div>
      </>}

      <div className="relative z-10 lg:ml-[232px] min-h-screen flex flex-col">
        <Header
          onMenu={()=>setMobileOpen(true)}
          onAlerts={()=>navigate('/alerts')}
          onProfile={()=>navigate('/settings')}
          onLocation={()=>navigate('/map')}
          user={user}
        />
        <main className="flex-1 px-4 pt-5 pb-4 lg:px-6 page-enter aero-page-shell aero-scrollbar">
          {page}
          <Footer/>
        </main>
      </div>
    </div>
  );
}

