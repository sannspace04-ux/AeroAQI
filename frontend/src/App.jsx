/**
 * AeroAQI — Premium Dashboard
 * Delhi-NCR Air Intelligence Platform
 * Smart India Hackathon 2026 · PS 82
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

// Use a clear Red Fort photograph at: src/assets/hero.png
// Keep the filename exactly "hero.png" so the import below remains stable.
import heroImg from "./assets/hero.png";

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
function ForecastTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tooltip-label rounded-lg px-3 py-2 text-xs" style={{
      background:"rgba(4,14,38,.95)",border:"1px solid rgba(6,182,212,.25)",
    }}>
      <p className="font-semibold text-cyan-400 mb-1">{label}</p>
      <p>AQI: <span className="text-purple-300 font-bold">{payload[0]?.value}</span></p>
      {payload[1] && <p>PM2.5: <span className="text-blue-300">{payload[1].value} µg/m³</span></p>}
    </div>
  );
}

// ─── Nav Item ─────────────────────────────────────────────
function NavItem({ icon, label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 text-left group
        ${active
          ? "nav-active text-cyan-300"
          : "text-slate-400 hover:text-white hover:bg-white/[0.05]"
        }`}
    >
      <span className={`${active ? "text-cyan-400" : "text-slate-500 group-hover:text-cyan-400"} transition-colors`}>
        {icon}
      </span>
      <span className="truncate">{label}</span>
      {active && <ChevronRight size={14} className="ml-auto text-cyan-400/60" />}
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
    <aside className={`flex flex-col h-full w-[232px] bg-[#040e26] border-r border-white/[0.07] ${mobile ? "" : "fixed left-0 top-0"}`}>
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 pt-6 pb-5 border-b border-white/[0.06]">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center"
          style={{background:"linear-gradient(135deg,#0891b2,#3b82f6)",boxShadow:"0 0 18px rgba(6,182,212,.35)"}}>
          <Activity size={18} className="text-white" />
        </div>
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
          style={{background:"linear-gradient(135deg,#8b5cf6,#3b82f6)"}}>{initial}</div>
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
  const start=()=>{try{const Ctx=window.AudioContext||window.webkitAudioContext; if(!Ctx)return; const ctx=new Ctx();ctxRef.current=ctx;let i=0;const play=()=>{const o=ctx.createOscillator(),g=ctx.createGain();o.type='sine';o.frequency.value=notes[i%notes.length];g.gain.setValueAtTime(.0001,ctx.currentTime);g.gain.exponentialRampToValueAtTime(.035,ctx.currentTime+.03);g.gain.exponentialRampToValueAtTime(.0001,ctx.currentTime+.55);o.connect(g);g.connect(ctx.destination);o.start();o.stop(ctx.currentTime+.58);i++};play();timerRef.current=setInterval(play,620);setOn(true)}catch{setOn(false)}};
  useEffect(()=>()=>stop(),[]);
  return <button onClick={on?stop:start} title="Original ambient melody" className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-semibold" style={{background:on?"rgba(6,182,212,.12)":"rgba(255,255,255,.035)",border:`1px solid ${on?"rgba(6,182,212,.22)":"rgba(255,255,255,.07)"}`,color:on?"#67e8f9":"#94a3b8"}}>{on?<Pause size={11}/>:<Play size={11}/>} Melody</button>;
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
      style={{background:"rgba(4,14,38,.9)",backdropFilter:"blur(20px)"}}>
      {/* Mobile menu */}
      <button onClick={onMenu} className="lg:hidden p-2 rounded-lg glass text-slate-300 hover:text-white">
        <Menu size={18}/>
      </button>

      {/* Location */}
      <button aria-label="Selected location: Delhi"
        onClick={onLocation}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg glass text-sm font-medium text-white hover:border-cyan-500/30 transition-all">
        <MapPin size={13} className="text-cyan-400"/>
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
          <Wind size={14} className="text-cyan-400"/>
          <span>12 km/h <span className="text-slate-500 text-xs">WNW</span></span>
        </div>
        <div className="flex items-center gap-1.5">
          <Droplets size={14} className="text-blue-400"/>
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
        className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white cursor-pointer hover:ring-2 hover:ring-cyan-400/40 transition"
        style={{background:"linear-gradient(135deg,#0891b2,#3b82f6)"}}>
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
        <img src={heroImg} alt="Red Fort, Delhi"
          className="w-full h-full object-cover object-center"
          style={{opacity:.94,filter:"brightness(1.08) saturate(1.12) contrast(1.04)"}}/>
        <div className="absolute inset-0"
          style={{background:"linear-gradient(90deg,rgba(2,8,23,.84) 0%,rgba(4,14,38,.48) 42%,rgba(4,14,38,.18) 68%,rgba(2,8,23,.42) 100%)"}}/>
        <div className="absolute inset-0"
          style={{background:"linear-gradient(180deg,rgba(2,8,23,.12) 0%,transparent 45%,rgba(2,8,23,.34) 100%)"}}/>
        {/* Cyan atm glow */}
        <div className="absolute inset-0 orb-cyan" style={{top:"-30%",left:"-10%",width:"60%",height:"160%",pointerEvents:"none"}}/>
        <div className="absolute inset-0 orb-purple" style={{top:"20%",right:"-5%",width:"45%",height:"80%",pointerEvents:"none"}}/>
      </div>

      <div className="relative z-10 grid grid-cols-1 lg:grid-cols-[1fr_420px] gap-6 p-7 lg:p-10" style={{minHeight:440}}>

        {/* LEFT */}
        <div className="flex flex-col justify-center">
          <div className="flex items-center gap-2 mb-4">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 live-dot"/>
            <p className="text-xs font-semibold tracking-[0.18em] uppercase text-cyan-400">
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
                <span className="text-cyan-400">{m.icon}</span>
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
            background:"rgba(7,25,54,.82)",
            backdropFilter:"blur(24px)",
            border:"1px solid rgba(139,92,246,.25)",
            boxShadow:"0 0 40px rgba(139,92,246,.12), 0 8px 32px rgba(0,0,0,.4)"
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
                <p className="text-3xl font-black text-purple-300 leading-none">182</p>
                <p className="text-[10px] text-purple-400 mt-1 font-medium">Unhealthy</p>
              </div>
              {/* PM2.5 */}
              <div className="text-center p-3 rounded-xl" style={{background:"rgba(6,182,212,.08)",border:"1px solid rgba(6,182,212,.18)"}}>
                <p className="text-[10px] text-slate-400 mb-1">PM2.5</p>
                <p className="text-2xl font-black text-cyan-300 leading-none">104</p>
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
            background:"rgba(7,25,54,.82)",
            backdropFilter:"blur(24px)",
            border:"1px solid rgba(59,130,246,.2)",
            boxShadow:"0 0 30px rgba(59,130,246,.08), 0 8px 24px rgba(0,0,0,.35)"
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
                      <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.4}/>
                      <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.03}/>
                    </linearGradient>
                    <linearGradient id="pm25Grad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#06b6d4" stopOpacity={0.02}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="2 4" stroke="rgba(255,255,255,.05)" vertical={false}/>
                  <XAxis dataKey="t" tick={{fill:"#64748b",fontSize:9}} axisLine={false} tickLine={false}/>
                  <YAxis tick={{fill:"#64748b",fontSize:9}} axisLine={false} tickLine={false}/>
                  <Tooltip content={<ForecastTooltip/>}/>
                  <ReferenceLine y={150} stroke="rgba(239,68,68,.3)" strokeDasharray="3 3"/>
                  <ReferenceLine y={100} stroke="rgba(234,179,8,.25)" strokeDasharray="3 3"/>
                  <Area type="monotone" dataKey="aqi"  stroke="#8b5cf6" strokeWidth={2}
                    fill="url(#aqiGrad)" dot={false}
                    activeDot={{r:4,fill:"#8b5cf6",stroke:"#0f1c3f",strokeWidth:2}}/>
                  <Area type="monotone" dataKey="pm25" stroke="#06b6d4" strokeWidth={1.5}
                    fill="url(#pm25Grad)" dot={false}
                    activeDot={{r:3,fill:"#06b6d4",stroke:"#0f1c3f",strokeWidth:2}}/>
                </AreaChart>
              </ResponsiveContainer>
            </div>

            <div className="flex items-center gap-4 mt-1">
              <div className="flex items-center gap-1.5 text-[10px] text-slate-400">
                <span className="w-4 h-0.5 rounded bg-purple-400"/>AQI
              </div>
              <div className="flex items-center gap-1.5 text-[10px] text-slate-400">
                <span className="w-4 h-0.5 rounded bg-cyan-400"/>PM2.5
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
    { icon:<Thermometer size={16}/>, label:"Temperature",     val:"31", unit:"°C",      color:"text-orange-400",glow:"rgba(249,115,22,.15)" },
    { icon:<Wind size={16}/>,        label:"Wind Speed",      val:"12", unit:"km/h WNW",color:"text-cyan-400",  glow:"rgba(6,182,212,.15)"  },
    { icon:<Droplets size={16}/>,    label:"Humidity",        val:"48", unit:"%",       color:"text-blue-400",  glow:"rgba(59,130,246,.15)" },
    { icon:<Gauge size={16}/>,       label:"PBL Height",      val:"750",unit:"m",       color:"text-purple-400",glow:"rgba(139,92,246,.15)" },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mt-4">
      {kpis.map(k => (
        <div key={k.label} className="card-hover flex items-center gap-3 px-4 py-3 rounded-xl"
          style={{background:`rgba(7,25,54,.7)`,border:"1px solid rgba(255,255,255,.07)",backdropFilter:"blur(12px)"}}>
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
function WeatherPanel() {
  const miniCharts = [
    { label:"PBL Height", unit:"m", data:pblData, key:"v", color:"#06b6d4", val:"750 m", status:"Moderate", statusC:"text-yellow-400" },
    { label:"Mixing Index",unit:"m²/s",data:mixData,key:"v",color:"#8b5cf6",val:"88",   status:"Favorable",statusC:"text-green-400"  },
    { label:"Inversion",  unit:"°C", data:invData, key:"v", color:"#ef4444", val:"2.8°C",status:"Weak",     statusC:"text-orange-400" },
  ];

  const metrics = [
    { label:"Temperature",   val:"31°C",     icon:<Thermometer size={14}/>, color:"#f97316" },
    { label:"Humidity",      val:"48%",      icon:<Droplets size={14}/>,    color:"#3b82f6" },
    { label:"Wind Speed",    val:"12 km/h",  icon:<Wind size={14}/>,        color:"#06b6d4" },
    { label:"Pressure",      val:"1013 hPa", icon:<Gauge size={14}/>,       color:"#8b5cf6" },
    { label:"Mixing Volume", val:"88 m²/s",  icon:<Activity size={14}/>,    color:"#10b981" },
    { label:"Vent. Coeff",   val:"640",      icon:<Eye size={14}/>,         color:"#a855f7" },
  ];

  return (
    <div id="weather-section" className="card-hover rounded-2xl p-5 flex flex-col gap-4"
      style={{background:"rgba(7,25,54,.7)",border:"1px solid rgba(255,255,255,.07)",backdropFilter:"blur(16px)"}}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-bold text-white">Weather & Atmosphere</p>
          <p className="text-[10px] text-slate-500 mt-0.5">Meteorological Conditions</p>
        </div>
        <CloudSun size={18} className="text-cyan-400"/>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {metrics.map(m => (
          <div key={m.label} className="flex items-center gap-2 p-2.5 rounded-xl"
            style={{background:"rgba(255,255,255,.03)",border:"1px solid rgba(255,255,255,.05)"}}>
            <span style={{color:m.color}}>{m.icon}</span>
            <div>
              <p className="text-[10px] text-slate-500 leading-none">{m.label}</p>
              <p className="text-xs font-bold text-white mt-0.5">{m.val}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-2.5">
        {miniCharts.map(c => (
          <div key={c.label} className="p-3 rounded-xl"
            style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.04)"}}>
            <div className="flex items-center justify-between mb-2">
              <p className="text-[10px] text-slate-400 font-medium">{c.label}</p>
              <div className="flex items-center gap-2">
                <span className={`text-[10px] font-semibold ${c.statusC}`}>{c.status}</span>
                <span className="text-[10px] text-slate-300 font-bold">{c.val}</span>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={42}>
              <AreaChart data={c.data} margin={{top:2,right:2,left:-35,bottom:0}}>
                <defs>
                  <linearGradient id={`g-${c.label}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={c.color} stopOpacity={.35}/>
                    <stop offset="95%" stopColor={c.color} stopOpacity={.01}/>
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey={c.key} stroke={c.color} strokeWidth={1.5}
                  fill={`url(#g-${c.label})`} dot={false}/>
                <XAxis dataKey="t" hide/>
                <YAxis hide/>
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ))}
      </div>
    </div>
  );
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
      style={{background:"rgba(7,25,54,.7)",border:"1px solid rgba(255,255,255,.07)",backdropFilter:"blur(16px)"}}>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div><p className="text-sm font-bold text-white">Plume Tracker</p><p className="text-[10px] text-slate-500 mt-0.5">Stubble burning · source attribution · transport toward NCR</p></div>
        <div className="flex items-center gap-2"><span className="flex items-center gap-1 text-[10px] text-orange-300 px-2 py-1 rounded-full" style={{background:"rgba(249,115,22,.09)",border:"1px solid rgba(249,115,22,.18)"}}><Flame size={11}/> Fire transport</span></div>
      </div>

      <div className="flex gap-1 p-1 rounded-lg" style={{background:"rgba(255,255,255,.04)"}}>
        {tabs.map((t,i)=><button key={t} onClick={()=>setTab(i)} className={`flex-1 text-[10px] py-2 rounded-md font-semibold transition-all ${tab===i?"text-white":"text-slate-500 hover:text-slate-300"}`} style={tab===i?{background:"linear-gradient(135deg,rgba(6,182,212,.25),rgba(59,130,246,.2))",border:"1px solid rgba(6,182,212,.2)"}:{}}>{t}</button>)}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_260px] gap-4">
        <div className="relative rounded-xl overflow-hidden min-h-[360px]" style={{background:"#061127",border:"1px solid rgba(255,255,255,.07)"}}>
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
          <div className="absolute left-3 top-3 rounded-xl px-3 py-2" style={{background:"rgba(3,12,31,.88)",border:"1px solid rgba(255,255,255,.08)"}}><p className="text-[9px] text-slate-500">Modeled transport horizon</p><p className="text-sm font-black text-white">{times[timeIdx]}</p><p className="text-[9px] text-cyan-300">Wind: WNW → Delhi</p></div>
          <div className="absolute right-3 top-3 flex flex-col gap-1">
            <button onClick={()=>setShowFires(v=>!v)} className={`px-2 py-1 rounded-lg text-[9px] font-semibold ${showFires?"text-orange-300":"text-slate-500"}`} style={{background:"rgba(3,12,31,.88)",border:"1px solid rgba(255,255,255,.08)"}}><Flame size={10} className="inline mr-1"/>Fires</button>
            <button onClick={()=>setShowWind(v=>!v)} className={`px-2 py-1 rounded-lg text-[9px] font-semibold ${showWind?"text-cyan-300":"text-slate-500"}`} style={{background:"rgba(3,12,31,.88)",border:"1px solid rgba(255,255,255,.08)"}}><Wind size={10} className="inline mr-1"/>Wind</button>
          </div>
          <div className="absolute bottom-3 left-3 right-3 flex items-center gap-3 text-[9px] text-slate-400"><span><i className="inline-block w-2 h-2 rounded-full bg-red-500 mr-1"/>Fire hotspot</span><span><i className="inline-block w-5 border-t border-dashed border-cyan-400 mr-1"/>Wind direction</span><span><i className="inline-block w-4 h-2 rounded bg-orange-500/50 mr-1"/>Plume intensity</span></div>
        </div>

        <div className="space-y-3">
          <div className="rounded-xl p-3" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}>
            <p className="text-[10px] uppercase tracking-widest text-slate-500">Source region</p>
            <select value={selectedRegion} onChange={e=>setSelectedRegion(e.target.value)} className="mt-2 w-full rounded-lg px-2.5 py-2 text-xs text-white outline-none" style={{background:"#071932",border:"1px solid rgba(255,255,255,.08)"}}>{regionData.map(r=><option key={r.name}>{r.name}</option>)}</select>
            <div className="grid grid-cols-2 gap-2 mt-2"><div><p className="text-[9px] text-slate-500">Fire detections</p><p className="text-lg font-black text-white">{selected.fires}</p></div><div><p className="text-[9px] text-slate-500">Transport risk</p><p className="text-sm font-bold" style={{color:selected.color}}>{selected.risk}</p></div></div>
            <p className="text-[10px] leading-relaxed text-slate-500 mt-2">{selected.desc}</p>
          </div>
          <div className="rounded-xl p-3" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}>
            <div className="flex items-center justify-between"><p className="text-[10px] uppercase tracking-widest text-slate-500">Timeline</p><button onClick={()=>setPlaying(v=>!v)} className="w-7 h-7 rounded-lg flex items-center justify-center text-cyan-300" style={{background:"rgba(6,182,212,.1)",border:"1px solid rgba(6,182,212,.2)"}}>{playing?"Ⅱ":"▶"}</button></div>
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
function AlertsPanel() {
  const [filter, setFilter] = useState("all");
  const [read, setRead] = useState({});
  const [muted, setMuted] = useState(false);
  const alerts = [
    {id:1,severity:"high",icon:<AlertTriangle size={14}/>,title:"High AQI Expected",desc:"AQI may reach 200+ in the next 12 hours",areas:"Delhi · Noida · Ghaziabad",time:"2h ago",badge:"Unhealthy",badgeC:"text-red-400",bg:"rgba(239,68,68,.08)",border:"rgba(239,68,68,.2)"},
    {id:2,severity:"mod",icon:<Info size={14}/>,title:"Moderate AQI Expected",desc:"AQI may reach 100+ in the next 24 hours",areas:"Gurugram · Faridabad",time:"4h ago",badge:"Moderate",badgeC:"text-yellow-400",bg:"rgba(234,179,8,.08)",border:"rgba(234,179,8,.2)"},
    {id:3,severity:"info",icon:<Wind size={14}/>,title:"Weather Alert",desc:"Low wind and shallow mixing height may cause AQI deterioration",areas:"NCR Region",time:"6h ago",badge:"Advisory",badgeC:"text-blue-400",bg:"rgba(59,130,246,.08)",border:"rgba(59,130,246,.2)"},
    {id:4,severity:"high",icon:<Flame size={14}/>,title:"Biomass Transport Risk",desc:"Upwind fire activity may increase PM2.5 contribution",areas:"Punjab · Haryana → Delhi",time:"8h ago",badge:"Source Risk",badgeC:"text-orange-400",bg:"rgba(249,115,22,.08)",border:"rgba(249,115,22,.2)"},
  ];
  const filtered = alerts.filter(a=>filter==="all"||a.severity===filter);
  return (
    <div id="alerts-section" className="card-hover rounded-2xl p-5 flex flex-col gap-4" style={{background:"rgba(7,25,54,.7)",border:"1px solid rgba(255,255,255,.07)",backdropFilter:"blur(16px)"}}>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3"><div><p className="text-sm font-bold text-white">Alerts & Notifications</p><p className="text-[10px] text-slate-500 mt-0.5">{muted?"Notifications muted":"4 active monitoring events"}</p></div><button onClick={()=>setMuted(v=>!v)} className="text-[10px] px-3 py-1.5 rounded-lg text-slate-300" style={{background:"rgba(255,255,255,.04)",border:"1px solid rgba(255,255,255,.07)"}}>{muted?"Unmute":"Mute notifications"}</button></div>
      <div className="flex gap-1 p-1 rounded-lg" style={{background:"rgba(255,255,255,.04)"}}>{[["all","All"],["high","High"],["mod","Moderate"],["info","Info"]].map(([v,l])=><button key={v} onClick={()=>setFilter(v)} className={`flex-1 py-1.5 rounded-md text-[10px] font-semibold ${filter===v?"text-white":"text-slate-500"}`} style={filter===v?{background:"rgba(6,182,212,.14)",border:"1px solid rgba(6,182,212,.2)"}:{}}>{l}</button>)}</div>
      <div className="space-y-2.5">{filtered.map(a=><div key={a.id} className={`p-3.5 rounded-xl transition ${read[a.id]?"opacity-55":""}`} style={{background:a.bg,border:`1px solid ${a.border}`}}><div className="flex items-start gap-3"><div className="mt-0.5 p-1.5 rounded-lg" style={{background:"rgba(255,255,255,.07)"}}><span className={a.badgeC}>{a.icon}</span></div><div className="flex-1"><div className="flex items-center justify-between gap-2"><p className="text-xs font-semibold text-white">{a.title}</p><span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${a.badgeC}`} style={{background:"rgba(255,255,255,.06)"}}>{a.badge}</span></div><p className="text-[10px] text-slate-400 mt-1 leading-relaxed">{a.desc}</p><div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mt-2"><span className="flex items-center gap-1 text-[10px] text-slate-500"><MapPin size={9}/>{a.areas}</span><span className="flex items-center gap-1 text-[10px] text-slate-600"><Clock size={9}/>{a.time}</span></div><div className="flex gap-2 mt-3"><button onClick={()=>setRead(v=>({...v,[a.id]:!v[a.id]}))} className="text-[9px] px-2 py-1 rounded-md text-cyan-300" style={{background:"rgba(6,182,212,.08)",border:"1px solid rgba(6,182,212,.14)"}}>{read[a.id]?"Mark unread":"Mark read"}</button><button onClick={()=>window.alert(`${a.title}\n\n${a.desc}\n\nAreas: ${a.areas}`)} className="text-[9px] px-2 py-1 rounded-md text-slate-400" style={{background:"rgba(255,255,255,.03)",border:"1px solid rgba(255,255,255,.06)"}}>Details</button></div></div></div></div>)}</div>
      {filtered.length===0&&<div className="text-center py-8 text-xs text-slate-500">No alerts in this category.</div>}
    </div>
  );
}

// ─── NCR Map Panel ────────────────────────────────────────
const NCR_STATIONS = [
  {name:"Delhi",lat:28.6139,lon:77.2090,aqi:182,status:"unhealthy"},{name:"Gurugram",lat:28.4595,lon:77.0266,aqi:205,status:"very"},{name:"Noida",lat:28.5355,lon:77.3910,aqi:143,status:"sensitive"},{name:"Ghaziabad",lat:28.6692,lon:77.4538,aqi:173,status:"unhealthy"},{name:"Faridabad",lat:28.4089,lon:77.3178,aqi:187,status:"unhealthy"},{name:"Sonipat",lat:28.9931,lon:77.0151,aqi:158,status:"unhealthy"},{name:"Bahadurgarh",lat:28.6924,lon:76.8513,aqi:151,status:"unhealthy"},{name:"Panipat",lat:29.3909,lon:76.9635,aqi:149,status:"sensitive"},{name:"Palwal",lat:28.1487,lon:77.3320,aqi:82,status:"moderate"},
];
function NcrMapPanel() {
  const [zoom,setZoom]=useState(10); const [layer,setLayer]=useState("dark"); const [selected,setSelected]=useState(null); const [showStations,setShowStations]=useState(true);
  const center={lat:28.62,lon:77.16};
  const tileSize=256;
  const worldPx=tileSize*Math.pow(2,zoom);
  const lonToX=lon=>(lon+180)/360*worldPx;
  const latToY=lat=>{const r=lat*Math.PI/180;return (1-Math.log(Math.tan(r)+1/Math.cos(r))/Math.PI)/2*worldPx;};
  const cx=lonToX(center.lon), cy=latToY(center.lat);
  const tiles=[]; const tileX=Math.floor(cx/tileSize),tileY=Math.floor(cy/tileSize); for(let dx=-2;dx<=2;dx++) for(let dy=-1;dy<=1;dy++){let x=tileX+dx,y=tileY+dy,n=Math.pow(2,zoom);if(x<0||x>=n||y<0||y>=n)continue;tiles.push({x,y,key:`${x}-${y}`,left:x*tileSize-cx+420,top:y*tileSize-cy+210});}
  const markerPos=s=>({left:420+(lonToX(s.lon)-cx),top:210+(latToY(s.lat)-cy)});
  const dot={good:"#22c55e",moderate:"#eab308",sensitive:"#f97316",unhealthy:"#ef4444",very:"#a855f7"};
  return <div id="map-section" className="card-hover rounded-2xl p-5 flex flex-col gap-4" style={{background:"rgba(7,25,54,.7)",border:"1px solid rgba(255,255,255,.07)",backdropFilter:"blur(16px)"}}>
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3"><div><p className="text-sm font-bold text-white">Delhi-NCR Air Quality Map</p><p className="text-[10px] text-slate-500 mt-0.5">Live-style spatial view · Delhi + surrounding NCR districts</p></div><div className="flex gap-2"><span className="flex items-center gap-1 text-[10px] text-green-400 px-2 py-1 rounded-full" style={{background:"rgba(34,197,94,.1)",border:"1px solid rgba(34,197,94,.2)"}}><span className="live-dot w-1.5 h-1.5 rounded-full bg-green-400"/>Live-ready</span><button onClick={()=>setShowStations(v=>!v)} className="text-[10px] px-2.5 py-1 rounded-lg text-slate-300" style={{background:"rgba(255,255,255,.04)",border:"1px solid rgba(255,255,255,.07)"}}>{showStations?"Hide stations":"Show stations"}</button></div></div>
    <div className="relative rounded-xl overflow-hidden h-[480px]" style={{background:"#071329",border:"1px solid rgba(255,255,255,.08)"}}>
      <div className="absolute inset-0 overflow-hidden" style={{filter:layer==="dark"?"brightness(.8) saturate(.8) contrast(1.05)":"none"}}>{tiles.map(t=><img key={t.key} alt="NCR map tile" src={`https://tile.openstreetmap.org/${zoom}/${t.x}/${t.y}.png`} className="absolute w-64 h-64" style={{left:t.left,top:t.top,maxWidth:"none"}} onError={e=>{e.currentTarget.style.opacity=.25}}/> )}</div>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_45%,transparent_0,rgba(2,8,23,.2)_70%)] pointer-events-none"/>
      {showStations&&NCR_STATIONS.map(s=>{const p=markerPos(s),c=dot[s.status];return <button key={s.name} onClick={()=>setSelected(s)} className="absolute -translate-x-1/2 -translate-y-1/2 group" style={{left:p.left,top:p.top}}><span className="block rounded-full" style={{width:selected?.name===s.name?32:26,height:selected?.name===s.name?32:26,background:`${c}33`,border:`1px solid ${c}77`,boxShadow:`0 0 18px ${c}66`}}><span className="flex items-center justify-center h-full text-[9px] font-black text-white">{s.aqi}</span></span><span className="absolute left-1/2 -translate-x-1/2 top-full mt-1 whitespace-nowrap text-[9px] font-semibold text-white drop-shadow-lg">{s.name}</span></button>})}
      {selected&&<div className="absolute left-3 top-3 rounded-xl p-3 w-48" style={{background:"rgba(3,12,31,.94)",border:`1px solid ${dot[selected.status]}55`,backdropFilter:"blur(12px)"}}><div className="flex items-center justify-between"><p className="text-[9px] text-slate-500">Selected station</p><button onClick={()=>setSelected(null)} className="text-slate-500"><X size={12}/></button></div><p className="text-sm font-bold text-white mt-1">{selected.name}</p><p className="text-2xl font-black" style={{color:dot[selected.status]}}>{selected.aqi}</p><p className="text-[10px] text-slate-400">AQI · {aqiLabel(selected.aqi)}</p><div className="grid grid-cols-2 gap-2 mt-2"><div><p className="text-[9px] text-slate-600">PM2.5</p><p className="text-[10px] text-white font-semibold">104 µg/m³</p></div><div><p className="text-[9px] text-slate-600">Trend</p><p className="text-[10px] text-red-300 font-semibold">↑ 12</p></div></div></div>}
      <div className="absolute top-3 right-3 flex flex-col gap-1"><button onClick={()=>setZoom(z=>Math.min(12,z+1))} className="w-8 h-8 rounded-lg text-white flex items-center justify-center" style={{background:"rgba(3,12,31,.9)",border:"1px solid rgba(255,255,255,.12)"}}><ZoomIn size={14}/></button><button onClick={()=>setZoom(z=>Math.max(9,z-1))} className="w-8 h-8 rounded-lg text-white flex items-center justify-center" style={{background:"rgba(3,12,31,.9)",border:"1px solid rgba(255,255,255,.12)"}}><ZoomOut size={14}/></button><button onClick={()=>setZoom(10)} className="w-8 h-8 rounded-lg text-white flex items-center justify-center" style={{background:"rgba(3,12,31,.9)",border:"1px solid rgba(255,255,255,.12)"}}><Crosshair size={14}/></button></div>
      <div className="absolute top-3 left-1/2 -translate-x-1/2 flex gap-1 p-1 rounded-lg" style={{background:"rgba(3,12,31,.9)",border:"1px solid rgba(255,255,255,.1)"}}><button onClick={()=>setLayer("dark")} className={`px-2.5 py-1 rounded-md text-[9px] ${layer==="dark"?"text-cyan-300 bg-cyan-500/10":"text-slate-500"}`}>Dark</button><button onClick={()=>setLayer("light")} className={`px-2.5 py-1 rounded-md text-[9px] ${layer==="light"?"text-cyan-300 bg-cyan-500/10":"text-slate-500"}`}>Light</button></div>
      <div className="absolute bottom-3 left-3 right-3 flex flex-wrap gap-2"><div className="rounded-lg px-3 py-2 text-[9px] text-slate-300" style={{background:"rgba(3,12,31,.88)"}}>NCR coverage · {NCR_STATIONS.length} monitoring points</div>{[["#22c55e","Good"],["#eab308","Moderate"],["#f97316","Sensitive"],["#ef4444","Unhealthy"],["#a855f7","Very Unhealthy"]].map(([c,l])=><span key={l} className="flex items-center gap-1 px-2 py-1 rounded text-[9px] text-slate-300" style={{background:"rgba(3,12,31,.88)"}}><i className="w-2 h-2 rounded-full" style={{background:c}}/>{l}</span>)}</div>
    </div>
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">{NCR_STATIONS.slice(0,5).map(s=><button key={s.name} onClick={()=>setSelected(s)} className="rounded-xl p-2.5 text-left hover:bg-white/[.04]" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}><p className="text-[10px] text-slate-400 truncate">{s.name}</p><p className="text-sm font-black" style={{color:dot[s.status]}}>{s.aqi}</p></button>)}</div>
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
  return <div id="quick-actions" className="grid grid-cols-2 sm:grid-cols-4 gap-3">{actions.map(a=><button key={a.path} onClick={()=>onAction(a.path)} className="card-hover p-4 rounded-xl flex flex-col items-center text-center gap-2.5" style={{background:"rgba(7,25,54,.7)",border:"1px solid rgba(255,255,255,.07)",backdropFilter:"blur(12px)"}}><div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{background:a.glow,boxShadow:`0 0 16px ${a.glow}`}}><span style={{color:a.color}}>{a.icon}</span></div><div><p className="text-xs font-semibold text-white">{a.label}</p><p className="text-[10px] text-slate-500 mt-0.5">{a.sub}</p></div></button>)}</div>;
}

// ─── Footer ───────────────────────────────────────────────
function Footer() {
  return (
    <footer className="mt-8 py-5 px-1 flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-white/[0.06]">
      <div className="flex items-center gap-2 text-xs text-slate-500"><Activity size={13} className="text-cyan-500"/><span>Built by <span className="font-bold text-cyan-300 tracking-wide">ASYNC AWAIT ❤️</span></span></div>
      <div className="flex items-center gap-3 text-[10px] text-slate-600"><span>Smart India Hackathon 2026</span><span>·</span><span>PS 82</span><span>·</span><span>Delhi-NCR Air Intelligence</span></div>
    </footer>
  );
}

// ─── Utility / Feature sections ─────────────────────────────
function FeatureSection({ id, icon, title, subtitle, children }) {
  return (
    <section id={id} className="scroll-mt-20 rounded-2xl p-5"
      style={{background:"rgba(7,25,54,.7)",border:"1px solid rgba(255,255,255,.07)",backdropFilter:"blur(16px)"}}>
      <div className="flex items-center gap-3 mb-4">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center"
          style={{background:"rgba(6,182,212,.1)",border:"1px solid rgba(6,182,212,.16)"}}>
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
          <select value={type} onChange={e=>setType(e.target.value)} className="w-full rounded-lg px-3 py-2.5 text-xs text-white outline-none" style={{background:"#071932",border:"1px solid rgba(255,255,255,.08)"}}>
            <option>Executive AQI Report</option><option>72-Hour Forecast Report</option><option>Station Comparison Report</option><option>Pollution Source Report</option>
          </select>
        </div>
        <div className="rounded-xl p-3" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.06)"}}>
          <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">Analysis range</p>
          <div className="grid grid-cols-3 gap-1">{["24 hours","72 hours","7 days"].map(v=><button key={v} onClick={()=>setRange(v)} className={`py-2 rounded-lg text-[9px] font-semibold ${range===v?"text-cyan-200":"text-slate-500"}`} style={range===v?{background:"rgba(6,182,212,.13)",border:"1px solid rgba(6,182,212,.2)"}:{background:"rgba(255,255,255,.02)"}}>{v}</button>)}</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={generate} className="btn-primary flex-1 px-4 py-2.5 rounded-xl text-xs font-semibold flex items-center justify-center gap-2"><Sparkles size={13}/>{generated?"Report Ready":"Generate Report"}</button>
          <button onClick={downloadReport} className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-300 flex items-center gap-2" style={{background:"rgba(255,255,255,.04)",border:"1px solid rgba(255,255,255,.08)"}}><Download size={13}/>CSV</button>
          <button onClick={()=>window.print()} className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-300 flex items-center gap-2" style={{background:"rgba(255,255,255,.04)",border:"1px solid rgba(255,255,255,.08)"}}><FileText size={13}/>Print</button>
        </div>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[['Current AQI','182','Unhealthy','#ef4444'],['Peak Forecast','192','+6 hours','#a855f7'],['PM2.5','104 µg/m³','Primary pollutant','#38bdf8'],['Plume Risk','High','Punjab → Delhi','#f97316']].map(([k,v,sub,c])=><div key={k} className="rounded-xl p-4" style={{background:"linear-gradient(145deg,rgba(17,48,96,.65),rgba(6,18,43,.75))",border:"1px solid rgba(255,255,255,.06)"}}><p className="text-[10px] text-slate-500">{k}</p><p className="text-2xl font-black mt-2" style={{color:c}}>{v}</p><p className="text-[9px] text-slate-500 mt-1">{sub}</p></div>)}
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
      {stages.map(([name,desc,status],i)=><button key={name} onClick={()=>setSelected(i)} className="p-3 rounded-xl text-left transition-all" style={{background:selected===i?"rgba(6,182,212,.1)":"rgba(34,197,94,.045)",border:`1px solid ${selected===i?"rgba(6,182,212,.25)":"rgba(34,197,94,.13)"}`}}><div className="flex items-center justify-between"><div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold" style={{background:selected===i?"rgba(6,182,212,.18)":"rgba(34,197,94,.1)",color:selected===i?"#67e8f9":"#86efac"}}>{i+1}</div>{i<5&&<ChevronRight size={12} className="text-slate-700"/>}</div><p className="text-[10px] font-bold text-white mt-3">{name}</p><p className="text-[9px] text-slate-500 mt-1 leading-relaxed">{desc}</p><p className="text-[9px] text-green-400 mt-2">{running && i<=Math.floor(progress/17)?"Processing…":"Ready"}</p></button>)}
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
      <div className="rounded-2xl p-5 text-center" style={{background:"linear-gradient(145deg,rgba(16,44,88,.7),rgba(6,18,42,.8))",border:"1px solid rgba(255,255,255,.07)"}}>
        <div className="relative mx-auto w-24 h-24"><div className="w-24 h-24 rounded-full overflow-hidden flex items-center justify-center text-3xl font-black" style={{background:"linear-gradient(135deg,#06b6d4,#8b5cf6)",border:"2px solid rgba(255,255,255,.12)"}}>{photo?<img src={photo} alt="Profile" className="w-full h-full object-cover"/>:(name||"A").charAt(0).toUpperCase()}</div><label className="absolute -right-1 -bottom-1 w-8 h-8 rounded-full flex items-center justify-center cursor-pointer text-white" style={{background:"#0891b2",border:"2px solid #061127"}}><Upload size={13}/><input type="file" accept="image/*" onChange={onPhoto} className="hidden"/></label></div>
        <p className="text-lg font-black text-white mt-3">{name||"AeroAQI User"}</p><p className="text-[10px] text-slate-500">{user?.email||"No email"}</p>
        <div className="mt-4 rounded-xl p-3" style={{background:"rgba(168,85,247,.08)",border:"1px solid rgba(168,85,247,.16)"}}><div className="flex items-center justify-center gap-2 text-purple-300"><Gift size={16}/><span className="text-xs font-bold">{points} Aero Points</span></div><p className="text-[9px] text-slate-500 mt-1">Earn points for healthy-air actions</p>{reward>0&&<p className="text-[10px] text-green-300 mt-2 animate-bounce">+{reward} points 🎉</p>}</div>
      </div>
      <div className="space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3"><div className="p-3 rounded-xl" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}><label className="text-[10px] text-slate-500">Full name</label><input value={name} onChange={e=>setName(e.target.value)} className="mt-2 w-full rounded-lg px-3 py-2.5 text-xs text-white outline-none" style={{background:"rgba(2,8,23,.55)",border:"1px solid rgba(255,255,255,.08)"}}/></div><div className="p-3 rounded-xl" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}><label className="text-[10px] text-slate-500 flex items-center gap-1"><Phone size={10}/> Mobile number</label><input value={phone} onChange={e=>setPhone(e.target.value.replace(/[^0-9+ -]/g,""))} placeholder="+91 98765 43210" className="mt-2 w-full rounded-lg px-3 py-2.5 text-xs text-white outline-none" style={{background:"rgba(2,8,23,.55)",border:"1px solid rgba(255,255,255,.08)"}}/></div></div>
        <div className="flex flex-wrap gap-2"><button onClick={saveProfile} className="btn-primary px-4 py-2.5 rounded-xl text-xs font-semibold flex items-center gap-2">{saved?<CheckCircle2 size={14}/>:<Save size={14}/>} {saved?"Saved":"Save Profile"}</button><label className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-300 cursor-pointer flex items-center gap-2" style={{background:"rgba(255,255,255,.04)",border:"1px solid rgba(255,255,255,.08)"}}><ImageIcon size={13}/> Change photo<input type="file" accept="image/*" onChange={onPhoto} className="hidden"/></label></div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">{[["Auto refresh","Refresh live-ready widgets",autoRefresh,"aeroaqi_auto_refresh",setAutoRefresh],["Notifications","AQI and weather alerts",notifications,"aeroaqi_notifications",setNotifications]].map(([label,sub,val,key,setter])=><button key={label} onClick={()=>updateToggle(key,setter)} className="w-full flex items-center justify-between p-3 rounded-xl text-left" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}><span><p className="text-xs font-semibold text-white">{label}</p><p className="text-[10px] text-slate-500">{sub}</p></span><span className={`w-9 h-5 rounded-full p-0.5 ${val?"bg-cyan-500/50":"bg-slate-700"}`}><span className={`block w-4 h-4 rounded-full bg-white transition ${val?"translate-x-4":""}`}/></span></button>)}</div>
        <div className="rounded-xl p-4" style={{background:"rgba(168,85,247,.05)",border:"1px solid rgba(168,85,247,.12)"}}><div className="flex items-center justify-between"><div><p className="text-xs font-bold text-white flex items-center gap-2"><Gift size={14} className="text-purple-300"/> Earn Points & Gifts</p><p className="text-[10px] text-slate-500 mt-1">Complete small AeroAQI actions to unlock rewards.</p></div><span className="text-sm font-black text-purple-300">{points} pts</span></div><div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-3"><button onClick={()=>addPoints(20)} className="p-3 rounded-lg text-left" style={{background:"rgba(255,255,255,.025)"}}><Target size={14} className="text-cyan-300"/><p className="text-[10px] text-white font-semibold mt-2">Check AQI</p><p className="text-[9px] text-green-300">+20 points</p></button><button onClick={()=>addPoints(30)} className="p-3 rounded-lg text-left" style={{background:"rgba(255,255,255,.025)"}}><Heart size={14} className="text-pink-300"/><p className="text-[10px] text-white font-semibold mt-2">Healthy-air tip</p><p className="text-[9px] text-green-300">+30 points</p></button><button onClick={()=>addPoints(50)} className="p-3 rounded-lg text-left" style={{background:"rgba(255,255,255,.025)"}}><Award size={14} className="text-yellow-300"/><p className="text-[10px] text-white font-semibold mt-2">Daily challenge</p><p className="text-[9px] text-green-300">+50 points</p></button></div><div className="mt-3 text-[9px] text-slate-500">Gift catalogue can later be connected to your real reward partner/backend.</div></div>
        <button onClick={onLogout} className="w-full flex items-center justify-center gap-2 p-3 rounded-xl text-xs font-semibold text-red-300" style={{background:"rgba(239,68,68,.07)",border:"1px solid rgba(239,68,68,.18)"}}><LogOut size={14}/> Sign out</button>
      </div>
    </div>
  </FeatureSection>;
}


function AeroMotionStyles(){return <style>{`
@keyframes aeroFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
@keyframes aeroMarquee{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
@keyframes aeroFade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@keyframes aeroPulse{0%,100%{box-shadow:0 0 0 0 rgba(34,211,238,.12)}50%{box-shadow:0 0 0 9px rgba(34,211,238,0)}}
.animate-float{animation:aeroFloat 4s ease-in-out infinite}.animate-marquee{animation:aeroMarquee 26s linear infinite}.animate-fade-in{animation:aeroFade .55s ease both}.live-dot{animation:aeroPulse 1.8s ease-out infinite}
`}</style>}

// ─── ROOT APP ─────────────────────────────────────────────
async function hashPassword(password) {
  const data = new TextEncoder().encode(password);
  const hash = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2,"0")).join("");
}

function AuthScreen({ onAuthenticated }) {
  const [mode,setMode]=useState("login"); const [name,setName]=useState(""); const [email,setEmail]=useState(""); const [password,setPassword]=useState(""); const [confirm,setConfirm]=useState(""); const [showPassword,setShowPassword]=useState(false); const [error,setError]=useState(""); const [busy,setBusy]=useState(false);
  const submit=async e=>{e.preventDefault();setError("");const clean=email.trim().toLowerCase();if(!clean.includes("@"))return setError("Please enter a valid email address.");if(password.length<6)return setError("Password must be at least 6 characters.");if(mode==='signup'&&!name.trim())return setError("Please enter your name.");if(mode==='signup'&&password!==confirm)return setError("Passwords do not match.");setBusy(true);try{const stored=JSON.parse(localStorage.getItem("aeroaqi_account")||"null");const passwordHash=await hashPassword(password);if(mode==='signup'){if(stored?.email===clean)return setError("Account already exists. Please log in.");const account={name:name.trim(),email:clean,passwordHash};localStorage.setItem("aeroaqi_account",JSON.stringify(account));const profile={name:account.name,email:account.email,phone:"",photo:""};localStorage.setItem("aeroaqi_user",JSON.stringify(profile));onAuthenticated(profile)}else{if(!stored||stored.email!==clean||stored.passwordHash!==passwordHash)return setError("Email or password is incorrect.");const profile={name:stored.name,email:stored.email,phone:stored.phone||"",photo:stored.photo||""};localStorage.setItem("aeroaqi_user",JSON.stringify(profile));onAuthenticated(profile)}}finally{setBusy(false)}};
  const demo=()=>{const profile={name:"AeroAQI Demo User",email:"demo@aeroaqi.local",phone:"",photo:""};localStorage.setItem("aeroaqi_user",JSON.stringify(profile));onAuthenticated(profile)};
  return <div className="min-h-screen flex items-center justify-center p-4 text-white overflow-hidden" style={{background:"radial-gradient(circle at 10% 10%,rgba(6,182,212,.14),transparent 30%),radial-gradient(circle at 90% 90%,rgba(139,92,246,.13),transparent 32%),#020817"}}><div className="w-full max-w-5xl grid lg:grid-cols-[1.05fr_.95fr] rounded-[28px] overflow-hidden" style={{background:"rgba(5,18,42,.86)",border:"1px solid rgba(255,255,255,.08)",boxShadow:"0 30px 100px rgba(0,0,0,.5)",backdropFilter:"blur(22px)"}}>
    <div className="relative hidden lg:flex min-h-[640px] p-10 flex-col justify-between overflow-hidden"><img src={heroImg} alt="Delhi landmark" className="absolute inset-0 w-full h-full object-cover" style={{opacity:.48,filter:"brightness(.72) saturate(1.2)"}}/><div className="absolute inset-0" style={{background:"linear-gradient(135deg,rgba(2,8,23,.94),rgba(2,8,23,.48),rgba(2,8,23,.82))"}}/><div className="relative z-10"><div className="flex items-center gap-3"><div className="w-11 h-11 rounded-2xl flex items-center justify-center" style={{background:"linear-gradient(135deg,#0891b2,#3b82f6)"}}><Activity size={21}/></div><div><h1 className="text-xl font-black">AeroAQI</h1><p className="text-[10px] text-slate-400">Clean Air, Better Tomorrow</p></div></div><div className="mt-24"><p className="text-[10px] tracking-[.25em] text-cyan-300 font-bold">DELHI-NCR AIR INTELLIGENCE</p><h2 className="text-5xl font-black leading-[.98] mt-3">Forecast the Air.<br/><span className="text-cyan-300">Understand the Why.</span></h2><p className="text-sm text-slate-300/75 mt-5 max-w-md">AeroAQI couples air quality, weather, atmospheric conditions and biomass-burning transport into one explainable 72-hour intelligence dashboard.</p><div className="grid grid-cols-2 gap-2 mt-7">{[["72h","Forecast horizon"],["NCR","Spatial coverage"],["AI","Explainability"],["Live","Monitoring ready"]].map(([a,b])=><div key={a} className="rounded-xl p-3" style={{background:"rgba(255,255,255,.045)",border:"1px solid rgba(255,255,255,.07)"}}><p className="text-lg font-black text-white">{a}</p><p className="text-[9px] text-slate-500 mt-1">{b}</p></div>)}</div></div></div><div className="relative z-10 text-[10px] text-slate-500">Built by <span className="font-bold text-cyan-300">ASYNC AWAIT ❤️</span> · SIH 2026 · PS 82</div></div>
    <div className="p-6 sm:p-9 flex flex-col justify-center"><div className="lg:hidden flex items-center gap-3 mb-7"><div className="w-11 h-11 rounded-2xl flex items-center justify-center" style={{background:"linear-gradient(135deg,#0891b2,#3b82f6)"}}><Activity size={21}/></div><div><h1 className="text-xl font-bold">AeroAQI</h1><p className="text-xs text-slate-400">Clean Air, Better Tomorrow</p></div></div><div className="flex p-1 rounded-xl mb-6" style={{background:"rgba(255,255,255,.04)"}}>{['login','signup'].map(m=><button key={m} onClick={()=>{setMode(m);setError("")}} className={`flex-1 py-2.5 rounded-lg text-xs font-bold ${mode===m?"text-white":"text-slate-500"}`} style={mode===m?{background:"rgba(6,182,212,.15)",border:"1px solid rgba(6,182,212,.2)"}:{}}>{m==='login'?"Login":"Create account"}</button>)}</div><div className="mb-5"><h3 className="text-2xl font-black">{mode==='login'?"Welcome back 👋":"Join AeroAQI"}</h3><p className="text-xs text-slate-500 mt-1">{mode==='login'?"Continue exploring Delhi-NCR air intelligence.":"Create your local prototype profile in seconds."}</p></div><form onSubmit={submit} className="space-y-3">{mode==='signup'&&<input value={name} onChange={e=>setName(e.target.value)} placeholder="Full name" className="w-full rounded-xl px-3 py-3 text-sm text-white outline-none placeholder:text-slate-600" style={{background:"rgba(2,8,23,.55)",border:"1px solid rgba(255,255,255,.08)"}}/>}<input value={email} onChange={e=>setEmail(e.target.value)} type="email" placeholder="Email address" className="w-full rounded-xl px-3 py-3 text-sm text-white outline-none placeholder:text-slate-600" style={{background:"rgba(2,8,23,.55)",border:"1px solid rgba(255,255,255,.08)"}}/><div className="relative"><Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"/><input value={password} onChange={e=>setPassword(e.target.value)} type={showPassword?'text':'password'} placeholder="Password" className="w-full rounded-xl px-3 py-3 text-sm text-white outline-none placeholder:text-slate-600 pl-9 pr-20" style={{background:"rgba(2,8,23,.55)",border:"1px solid rgba(255,255,255,.08)"}}/><button type="button" onClick={()=>setShowPassword(v=>!v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-cyan-400">{showPassword?'Hide':'Show'}</button></div>{mode==='signup'&&<input value={confirm} onChange={e=>setConfirm(e.target.value)} type="password" placeholder="Confirm password" className="w-full rounded-xl px-3 py-3 text-sm text-white outline-none placeholder:text-slate-600" style={{background:"rgba(2,8,23,.55)",border:"1px solid rgba(255,255,255,.08)"}}/>}{error&&<div className="text-xs text-red-300 rounded-lg p-3" style={{background:"rgba(239,68,68,.08)",border:"1px solid rgba(239,68,68,.18)"}}>{error}</div>}<button disabled={busy} className="btn-primary w-full py-3 rounded-xl text-sm font-bold disabled:opacity-50">{busy?'Please wait…':mode==='login'?'Login to AeroAQI':'Create AeroAQI Account'}</button></form><div className="relative my-5"><div className="border-t border-white/[.06]"/><span className="absolute left-1/2 -translate-x-1/2 -top-2.5 px-3 text-[9px] text-slate-600" style={{background:"#07122a"}}>OR</span></div><button onClick={demo} className="w-full py-3 rounded-xl text-xs font-bold text-cyan-200 flex items-center justify-center gap-2" style={{background:"rgba(6,182,212,.06)",border:"1px solid rgba(6,182,212,.15)"}}><Eye size={13}/> Explore demo dashboard</button><div className="grid grid-cols-3 gap-2 mt-5">{[[<Bot size={14}/>,'AI Insights'],[<Map size={14}/>,'NCR Map'],[<Flame size={14}/>,'Plume']].map(([ic,t])=><div key={t} className="p-2 rounded-lg text-center" style={{background:"rgba(255,255,255,.025)"}}><span className="text-cyan-300">{ic}</span><p className="text-[8px] text-slate-500 mt-1">{t}</p></div>)}</div><p className="text-[9px] text-slate-600 text-center mt-5">Prototype authentication is local. Production login should use the backend authentication service.</p></div>
  </div></div>;
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
        <p className="text-[10px] uppercase tracking-[.2em] text-cyan-400 font-bold mb-1.5">{eyebrow}</p>
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
        <span className="font-semibold text-amber-300">Frontend integration checkpoint:</span> this screen is fully interactive, but displayed sensor/forecast numbers are demo placeholders until the exact FastAPI response fields are wired in. No demo number should be presented as live government data.
      </p>
    </div>
  );
}

function ForecastPage() {
  const [pollutant,setPollutant]=useState("AQI"); const [horizon,setHorizon]=useState(72); const [station,setStation]=useState("Delhi");
  const visible=forecastData.filter((_,i)=>i===0||i*6<=horizon); const vals=visible.map(x=>x.aqi); const peak=Math.max(...vals), low=Math.min(...vals);
  return <><PageHeader title="AQI Forecast" subtitle="Interactive 72-hour prediction workspace with pollutant trends, confidence and station comparison." action={<div className="flex gap-2"><select value={station} onChange={e=>setStation(e.target.value)} className="rounded-xl px-3 py-2 text-xs text-white outline-none" style={{background:"#071932",border:"1px solid rgba(255,255,255,.08)"}}>{NCR_STATIONS.map(s=><option key={s.name}>{s.name}</option>)}</select></div>}/><DemoDataNotice/><FeatureSection icon={<BarChart3 size={18} className="text-purple-400"/>} title="72-Hour AQI Forecast" subtitle={`${station} · Prediction horizon · AI-ready forecast response`}>
    <div className="flex flex-wrap items-center justify-between gap-3 mb-4"><div className="flex gap-1 p-1 rounded-lg" style={{background:"rgba(255,255,255,.04)"}}>{['AQI','PM2.5','PM10','NO2'].map(v=><button key={v} onClick={()=>setPollutant(v)} className={`px-3 py-1.5 rounded-md text-[10px] font-semibold ${pollutant===v?'text-white':'text-slate-500'}`} style={pollutant===v?{background:"rgba(139,92,246,.15)",border:"1px solid rgba(139,92,246,.22)"}:{}}>{v}</button>)}</div><div className="flex gap-1 p-1 rounded-lg" style={{background:"rgba(255,255,255,.04)"}}>{[24,48,72].map(v=><button key={v} onClick={()=>setHorizon(v)} className={`px-3 py-1.5 rounded-md text-[10px] font-semibold ${horizon===v?'text-cyan-200':'text-slate-500'}`} style={horizon===v?{background:"rgba(6,182,212,.12)",border:"1px solid rgba(6,182,212,.2)"}:{}}>{v}h</button>)}</div></div>
    <div className="h-[390px]"><ResponsiveContainer width="100%" height="100%"><AreaChart data={visible} margin={{top:10,right:10,left:-10,bottom:5}}><defs><linearGradient id="forecast-page-aqi" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#8b5cf6" stopOpacity={.34}/><stop offset="95%" stopColor="#8b5cf6" stopOpacity={.02}/></linearGradient></defs><CartesianGrid stroke="rgba(255,255,255,.05)" vertical={false}/><XAxis dataKey="t" tick={{fontSize:10,fill:"#64748b"}} axisLine={false} tickLine={false}/><YAxis tick={{fontSize:10,fill:"#64748b"}} axisLine={false} tickLine={false}/><Tooltip content={<ForecastTooltip/>}/><ReferenceLine y={200} stroke="rgba(239,68,68,.25)" strokeDasharray="4 4"/><Area type="monotone" dataKey="aqi" stroke="#8b5cf6" strokeWidth={2.5} fill="url(#forecast-page-aqi)"/><Line type="monotone" dataKey="pm25" stroke="#38bdf8" strokeWidth={2} dot={false}/></AreaChart></ResponsiveContainer></div>
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mt-4">{[['Horizon',`${horizon} hours`],['Peak AQI',peak],['Lowest AQI',low],['Primary pollutant','PM2.5'],['Confidence','84%']].map(([k,v])=><div key={k} className="rounded-xl p-3" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}><p className="text-[10px] text-slate-500">{k}</p><p className="text-sm font-bold text-white mt-1">{v}</p></div>)}</div>
    <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">{[['What changed?','PM2.5 trend is driving the AQI curve.'],['Why?','Wind + atmospheric dispersion influence transport and accumulation.'],['What next?','Use AI Insights to explain the forecast factors.']].map(([a,b],i)=><div key={a} className="p-3 rounded-xl" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}><p className="text-[10px] font-bold text-cyan-300">{a}</p><p className="text-[10px] text-slate-400 mt-1 leading-relaxed">{b}</p></div>)}</div>
  </FeatureSection></>;
}

function DashboardPage({ navigate }) {
  const [slide,setSlide]=useState(0);
  const slides=[
    {ey:"DELHI-NCR AIR INTELLIGENCE",title:"Air Quality Forecasting",accent:"for a Better Tomorrow",sub:"Weather–Chemistry coupled 72-hour prediction with explainable AI.",cta:"Explore Forecast",path:"/forecast"},
    {ey:"SOURCE ATTRIBUTION",title:"Track Pollution",accent:"Before It Reaches Delhi",sub:"Visualize fire hotspots, wind direction and modeled plume transport risk.",cta:"Open Plume Tracker",path:"/plume"},
    {ey:"SMART DECISIONS",title:"Understand the Air",accent:"Not Just the AQI",sub:"See weather, atmospheric conditions, stations, alerts and AI explanations together.",cta:"Open AI Insights",path:"/ai"},
  ];
  useEffect(()=>{const id=setInterval(()=>setSlide(v=>(v+1)%slides.length),5500);return()=>clearInterval(id)},[]);
  const s=slides[slide];
  return <>
    <section className="relative overflow-hidden rounded-3xl min-h-[510px]" style={{background:"#07152d",border:"1px solid rgba(255,255,255,.08)",boxShadow:"0 24px 70px rgba(0,0,0,.35)"}}>
      <img src={heroImg} alt="India Gate, Delhi" className="absolute inset-0 w-full h-full object-cover transition-all duration-1000" style={{opacity:.68,filter:"brightness(.82) saturate(1.15) contrast(1.05)"}}/>
      <div className="absolute inset-0" style={{background:"linear-gradient(90deg,rgba(2,8,23,.96) 0%,rgba(2,8,23,.72) 42%,rgba(2,8,23,.18) 78%,rgba(2,8,23,.5) 100%)"}}/>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_35%,rgba(6,182,212,.18),transparent_30%),linear-gradient(180deg,transparent,rgba(2,8,23,.55))]"/>
      <div className="relative z-10 p-6 sm:p-9 lg:p-10 max-w-[720px] min-h-[510px] flex flex-col justify-center">
        <div className="flex items-center gap-2 mb-4"><span className="w-2 h-2 rounded-full bg-cyan-300 live-dot"/><span className="text-[10px] font-black tracking-[.25em] text-cyan-300">{s.ey}</span></div>
        <div key={slide} className="animate-fade-in"><h2 className="text-4xl sm:text-5xl lg:text-6xl font-black leading-[.95] tracking-tight text-white">{s.title}<br/><span className="text-cyan-300">{s.accent}</span></h2><p className="mt-5 text-sm sm:text-base text-slate-200/85 max-w-xl leading-relaxed">{s.sub}</p><div className="flex flex-wrap gap-3 mt-7"><button onClick={()=>navigate(s.path)} className="btn-primary px-5 py-3 rounded-xl text-xs font-bold flex items-center gap-2">{s.cta}<ArrowUpRight size={14}/></button><button onClick={()=>navigate('/map')} className="px-5 py-3 rounded-xl text-xs font-bold text-white" style={{background:"rgba(2,8,23,.55)",border:"1px solid rgba(255,255,255,.12)",backdropFilter:"blur(10px)"}}>Explore NCR Map</button></div></div>
        <div className="flex items-center gap-2 mt-8">{slides.map((_,i)=><button key={i} onClick={()=>setSlide(i)} className="h-1.5 rounded-full transition-all" style={{width:i===slide?34:10,background:i===slide?"#22d3ee":"rgba(255,255,255,.35)"}}/>)}<span className="text-[9px] text-slate-400 ml-2">Auto carousel</span></div>
      </div>
      <div className="absolute right-5 top-5 hidden xl:flex gap-2 animate-float"><div className="rounded-xl px-3 py-2" style={{background:"rgba(3,12,31,.72)",border:"1px solid rgba(255,255,255,.1)",backdropFilter:"blur(14px)"}}><p className="text-[9px] text-slate-500">Current AQI</p><p className="text-xl font-black text-red-400">182</p></div><div className="rounded-xl px-3 py-2" style={{background:"rgba(3,12,31,.72)",border:"1px solid rgba(255,255,255,.1)",backdropFilter:"blur(14px)"}}><p className="text-[9px] text-slate-500">72h peak</p><p className="text-xl font-black text-purple-300">192</p></div></div>
      <div className="absolute bottom-0 left-0 right-0 h-16 flex items-center gap-5 px-6 overflow-hidden" style={{background:"rgba(2,8,23,.55)",backdropFilter:"blur(10px)",borderTop:"1px solid rgba(255,255,255,.06)"}}><div className="flex gap-8 whitespace-nowrap animate-marquee text-[10px] text-slate-300"><span>🟢 Good 0–50</span><span>🟡 Moderate 51–100</span><span>🟠 Sensitive 101–150</span><span>🔴 Unhealthy 151–200</span><span>🟣 Very Unhealthy 201–300</span><span>🌬 Wind transports pollution</span><span>🔥 Biomass burning can affect PM2.5</span></div></div>
    </section>
    <KpiStrip/>
    <DemoDataNotice/>
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-5"><FeatureSection icon={<BarChart3 size={18} className="text-purple-400"/>} title="Forecast Preview" subtitle="Open the full 72-hour prediction page"><div className="h-[250px]"><ResponsiveContainer width="100%" height="100%"><AreaChart data={forecastData} margin={{top:5,right:5,left:-25,bottom:0}}><defs><linearGradient id="dash-aqi" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#8b5cf6" stopOpacity={.3}/><stop offset="95%" stopColor="#8b5cf6" stopOpacity={.01}/></linearGradient></defs><XAxis dataKey="t" hide/><YAxis hide/><Tooltip content={<ForecastTooltip/>}/><Area type="monotone" dataKey="aqi" stroke="#8b5cf6" strokeWidth={2} fill="url(#dash-aqi)"/></AreaChart></ResponsiveContainer></div><button onClick={()=>navigate('/forecast')} className="btn-primary w-full py-2.5 rounded-xl text-xs font-bold">Open AQI Forecast →</button></FeatureSection><AlertsPanel/></div>
    <QuickActions onAction={navigate}/>
  </>;
}

function MapPage() {
  return <><PageHeader title="Delhi-NCR Air Quality Map" subtitle="Interactive spatial AQI view across Delhi and the surrounding NCR region."/><DemoDataNotice/><NcrMapPanel/></>;
}
function WeatherPage() {
  return <><PageHeader title="Weather & Atmosphere" subtitle="Meteorological and atmospheric factors that influence pollution dispersion."/><DemoDataNotice/><WeatherPanel/></>;
}
function PlumePage() {
  return <><PageHeader title="Plume Tracker" subtitle="Explore fire-source regions, transport direction and stubble-burning risk."/><DemoDataNotice/><PlumePanel/></>;
}
function AlertsPage() {
  return <><PageHeader title="Alerts & Notifications" subtitle="AQI risk events and actionable monitoring alerts."/><AlertsPanel/></>;
}
function StationsPage() {
  const [query,setQuery]=useState(""); const [selected,setSelected]=useState(NCR_STATIONS[0]); const filtered=NCR_STATIONS.filter(s=>s.name.toLowerCase().includes(query.toLowerCase()));
  const dot={good:"#22c55e",moderate:"#eab308",sensitive:"#f97316",unhealthy:"#ef4444",very:"#a855f7"};
  return <><PageHeader title="Monitoring Stations" subtitle="NCR monitoring network — select a station to inspect AQI, pollutants and local conditions." action={<button onClick={()=>window.location.reload()} className="px-3 py-2 rounded-xl text-xs text-slate-300 flex items-center gap-2" style={{background:"rgba(255,255,255,.04)",border:"1px solid rgba(255,255,255,.08)"}}><RefreshCw size={12}/>Refresh</button>}/><DemoDataNotice/><div className="grid grid-cols-1 xl:grid-cols-[330px_1fr] gap-5"><FeatureSection icon={<Navigation size={18} className="text-green-400"/>} title="NCR Station Network" subtitle={`${filtered.length} matching monitoring points`}><div className="relative mb-3"><Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-600"/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search station or city" className="w-full rounded-xl pl-9 pr-3 py-2.5 text-xs text-white outline-none" style={{background:"rgba(2,8,23,.55)",border:"1px solid rgba(255,255,255,.08)"}}/></div><div className="space-y-2 max-h-[560px] overflow-y-auto pr-1">{filtered.map(s=><button key={s.name} onClick={()=>setSelected(s)} className="w-full p-3 rounded-xl text-left transition" style={{background:selected.name===s.name?"rgba(6,182,212,.09)":"rgba(255,255,255,.025)",border:`1px solid ${selected.name===s.name?"rgba(6,182,212,.2)":"rgba(255,255,255,.05)"}`}}><div className="flex items-center justify-between"><div><p className="text-xs font-bold text-white">{s.name}</p><p className="text-[9px] text-slate-600">{s.lat.toFixed(3)}, {s.lon.toFixed(3)}</p></div><div className="text-right"><p className="text-lg font-black" style={{color:dot[s.status]}}>{s.aqi}</p><p className="text-[8px] text-slate-500">AQI</p></div></div></button>)}</div></FeatureSection><FeatureSection icon={<MapPinned size={18} className="text-cyan-400"/>} title={`${selected.name} Station`} subtitle="Selected monitoring point details"><div className="grid grid-cols-2 lg:grid-cols-4 gap-3">{[['AQI',selected.aqi,aqiLabel(selected.aqi)],['PM2.5','104','µg/m³'],['PM10','176','µg/m³'],['Status',selected.status,'Current']].map(([a,b,c])=><div key={a} className="rounded-xl p-4" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}><p className="text-[10px] text-slate-500">{a}</p><p className="text-xl font-black text-white mt-1" style={a==='AQI'?{color:dot[selected.status]}:{}}>{b}</p><p className="text-[9px] text-slate-500 mt-1">{c}</p></div>)}</div><div className="mt-4 rounded-xl p-4" style={{background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.05)"}}><div className="flex items-center justify-between"><p className="text-xs font-bold text-white">Station trend</p><span className="text-[9px] text-green-300">Reporting · 8 min ago</span></div><div className="h-[240px] mt-3"><ResponsiveContainer width="100%" height="100%"><LineChart data={forecastData}><CartesianGrid stroke="rgba(255,255,255,.04)" vertical={false}/><XAxis dataKey="t" tick={{fontSize:9,fill:"#64748b"}}/><YAxis tick={{fontSize:9,fill:"#64748b"}}/><Tooltip content={<ForecastTooltip/>}/><Line dataKey="aqi" stroke="#8b5cf6" strokeWidth={2.5} dot={false}/></LineChart></ResponsiveContainer></div></div><button onClick={()=>window.location.href='/map'} className="mt-3 btn-primary px-4 py-2.5 rounded-xl text-xs font-bold">View this station on NCR Map →</button></FeatureSection></div></>;
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
      <div className="text-center rounded-2xl p-8 max-w-md" style={{background:"rgba(7,25,54,.7)",border:"1px solid rgba(255,255,255,.07)"}}>
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
    <div className="min-h-screen text-white" style={{background:"#020817"}}><AeroMotionStyles/>
      <div className="fixed inset-0 pointer-events-none overflow-hidden" style={{zIndex:0}}>
        <div className="absolute -top-40 -left-40 w-[600px] h-[600px] rounded-full opacity-30" style={{background:"radial-gradient(circle,rgba(6,182,212,.07) 0%,transparent 70%)"}}/>
        <div className="absolute top-1/4 right-0 w-[400px] h-[400px] rounded-full opacity-20" style={{background:"radial-gradient(circle,rgba(139,92,246,.08) 0%,transparent 70%)"}}/>
        <div className="absolute bottom-0 left-1/3 w-[500px] h-[400px] rounded-full opacity-20" style={{background:"radial-gradient(circle,rgba(59,130,246,.06) 0%,transparent 70%)"}}/>
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
        <main className="flex-1 px-4 pt-5 pb-4 lg:px-6 page-enter">
          {page}
          <Footer/>
        </main>
      </div>
    </div>
  );
}
