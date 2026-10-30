import AnomalyPanel from '../../components/shared/AnomalyPanel'
import { useEffect, useState, useCallback, useRef } from 'react'
import { Zap, Activity, TrendingUp, AlertTriangle, Download, Database, UploadCloud } from 'lucide-react'
import { energyService } from '../../services/energyService'
import KpiCard from '../../components/cards/KpiCard'
import ConsumptionChart from '../../components/charts/ConsumptionChart'
import BreakdownChart from '../../components/charts/BreakdownChart'
import RecommendationsList from '../../components/cards/RecommendationsList'
import ForecastCard from '../../components/cards/ForecastCard'
import ModelReliabilityChart from '../../components/charts/ModelReliabilityChart'
import BriefingCard from '../../components/cards/BriefingCard'
import AgentInvestigationPanel from '../../components/agent/AgentInvestigationPanel'
import DashboardHeader from '../../components/ui/DashboardHeader'
import HeroStatCard from '../../components/cards/HeroStatCard'
import SystemAssetGrid from '../../components/energy/SystemAssetGrid'
import SectionTabs from '../../components/energy/SectionTabs'
import ForecastModelComparison from '../../components/energy/ForecastModelComparison'
import DataManagerModal from '../../components/shared/DataManagerModal'
import DatasetUploadPanel from '../../components/shared/DatasetUploadPanel'
import DashboardSkeleton from '../../components/ui/DashboardSkeleton'

const ENERGY_FIELDS = [
  { key: 'total_kwh', label: 'Total kWh', type: 'number', required: true, step: 0.01 },
  { key: 'hvac_kwh', label: 'HVAC kWh', type: 'number', step: 0.01, defaultValue: 0 },
  { key: 'lighting_kwh', label: 'Lighting kWh', type: 'number', step: 0.01, defaultValue: 0 },
  { key: 'plug_load_kwh', label: 'Plug load kWh', type: 'number', step: 0.01, defaultValue: 0 },
  { key: 'outdoor_temp_c', label: 'Outdoor temp °C (optional)', type: 'number', step: 0.1 },
  { key: 'timestamp', label: 'Timestamp', type: 'datetime-local' },
]
const ENERGY_COLUMNS = [
  { key: 'sensor_id', label: 'sensor' },
  { key: 'total_kwh', label: 'kWh' },
]

const DEFAULT_RANGE = 672 // 7 days at 15-min resolution
const POLL_INTERVAL_MS = 30_000

export default function EnergyDashboardPage() {
  const [dashboard, setDashboard] = useState(null)
  const [readings, setReadings] = useState([])
  const [readingsLimit, setReadingsLimit] = useState(DEFAULT_RANGE)
  const [briefing, setBriefing] = useState(null)
  const [forecastScatter, setForecastScatter] = useState(null)
  const [investigation, setInvestigation] = useState(null)
  const [investigating, setInvestigating] = useState(false)
  const [loading, setLoading] = useState(true)
  const [rangeLoading, setRangeLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [error, setError] = useState(null)
  const [managerOpen, setManagerOpen] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)
  const pollRef = useRef(null)

  const fetchAll = useCallback(async (limit) => {
    const [dash, readingsData, briefingData, scatterData] = await Promise.all([
      energyService.getDashboard('BLD-HQ-01', limit),
      energyService.getReadings('BLD-HQ-01', limit),
      energyService.getBriefing().catch(() => null),
      energyService.getForecastScatter('1h').catch(() => null),
    ])
    setDashboard(dash)
    setReadings(readingsData.readings)
    setBriefing(briefingData)
    setForecastScatter(scatterData)
    setLastUpdated(new Date())
  }, [])

  const refreshNow = useCallback(async () => {
    setRefreshing(true)
    try {
      await fetchAll(readingsLimit)
    } catch (err) {
      setError(err.message)
    } finally {
      setRefreshing(false)
    }
  }, [fetchAll, readingsLimit])

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        setLoading(true)
        await fetchAll(DEFAULT_RANGE)
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [fetchAll])

  // Silent background polling on the current range, same idea as the
  // Maintenance dashboard — keeps "LIVE" honest rather than decorative.
  useEffect(() => {
    pollRef.current = setInterval(() => {
      setRefreshing(true)
      fetchAll(readingsLimit).catch(() => {}).finally(() => setRefreshing(false))
    }, POLL_INTERVAL_MS)
    return () => clearInterval(pollRef.current)
  }, [fetchAll, readingsLimit])

  // Range change now refetches BOTH the chart data AND the KPI/analytics
  // summary for that same window — previously only the chart updated while
  // Total/Avg/Peak/Anomalies stayed pinned to the full-dataset numbers.
  const handleRangeChange = useCallback(async (limit) => {
    setReadingsLimit(limit)
    setRangeLoading(true)
    try {
      const [readingsData, dash] = await Promise.all([
        energyService.getReadings('BLD-HQ-01', limit),
        energyService.getDashboard('BLD-HQ-01', limit),
      ])
      setReadings(readingsData.readings)
      setDashboard(dash)
      setLastUpdated(new Date())
    } catch (err) {
      setError(err.message)
    } finally {
      setRangeLoading(false)
    }
  }, [])

  const runInvestigation = useCallback(async () => {
    setInvestigating(true)
    setInvestigation(null)
    try {
      const result = await energyService.getInvestigation()
      setInvestigation(result)
      setLastUpdated(new Date())
    } catch (err) {
      setError(err.message)
    } finally {
      setInvestigating(false)
    }
  }, [])

  // Real CSV export of the currently loaded readings — not decorative.
  const exportReport = useCallback(() => {
    if (!readings.length) return
    const header = 'timestamp,total_kwh,hvac_kwh,lighting_kwh,plug_load_kwh,other_kwh\n'
    const rows = readings
      .map((r) => `${r.timestamp},${r.total_kwh},${r.hvac_kwh},${r.lighting_kwh},${r.plug_load_kwh},${r.other_kwh}`)
      .join('\n')
    const blob = new Blob([header + rows], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `energy-readings-${dashboard?.building_id || 'export'}-${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }, [readings, dashboard])

  if (loading) {
    return (
      <DashboardSkeleton message="INITIALIZING FACILITY LINK…" kpiCount={5} />
    )
  }

  if (error) {
    return (
      <div className="p-6 text-red-500 dark:text-red-400 text-sm font-mono">
        connection failed: {error} — confirm the FastAPI server is running on :8000
      </div>
    )
  }

  const { consumption, breakdown, trend_pct_vs_prev_period, anomaly_count, top_recommendations } = dashboard

  return (
    <div className="dashboard-page">
      {/* ambient background glow — purely decorative, sits behind everything */}
      <div className="pointer-events-none absolute -top-32 -left-20 w-[420px] h-[420px] rounded-full bg-blue-500/10 dark:bg-blue-500/[0.08] blur-[110px]" />
      <div className="pointer-events-none absolute top-40 -right-32 w-[380px] h-[380px] rounded-full bg-teal-400/10 dark:bg-teal-400/[0.07] blur-[110px]" />
      <div className="pointer-events-none absolute bottom-0 left-1/3 w-[300px] h-[300px] rounded-full bg-violet-500/[0.06] dark:bg-violet-500/[0.06] blur-[110px]" />

      {/* Sticky utility bar — section nav + export */}
      <div className="sticky top-0 z-20 backdrop-blur-md bg-paper/80 dark:bg-graphite/80 border-b border-slate-200 dark:border-slate-800/80">
        <div className="px-6 md:px-10 py-3 flex items-center justify-between gap-4 flex-wrap">
          <SectionTabs />
          <div className="flex items-center gap-2">
            <button
              onClick={() => setUploadOpen(true)}
              className="flex items-center gap-1.5 font-mono text-xs text-slate-500 hover:text-blue-600 dark:hover:text-blue-400
                         border border-slate-200 dark:border-slate-800 rounded-full px-3 py-1.5 transition-colors"
            >
              <UploadCloud size={12} /> Upload dataset
            </button>
            <button
              onClick={() => setManagerOpen(true)}
              className="flex items-center gap-1.5 font-mono text-xs text-slate-500 hover:text-blue-600 dark:hover:text-blue-400
                         border border-slate-200 dark:border-slate-800 rounded-full px-3 py-1.5 transition-colors"
            >
              <Database size={12} /> Manage dataset
            </button>
            <button
              onClick={exportReport}
              className="flex items-center gap-1.5 font-mono text-xs text-slate-500 hover:text-teal-600 dark:hover:text-teal-400
                         border border-slate-200 dark:border-slate-800 rounded-full px-3 py-1.5 transition-colors"
            >
              <Download size={12} /> Export report
            </button>
          </div>
        </div>
      </div>

      <div id="overview" className="scroll-mt-16">
        <DashboardHeader Icon={Zap} agentLabel="ENERGY AGENT" title="Energy" emphasis="Monitoring" description={consumption.period} buildingId={dashboard.building_id} lastUpdated={lastUpdated} isRefreshing={refreshing} onRefresh={refreshNow} accent="blue" />
      <AnomalyPanel domain="energy" buildingId={dashboard.building_id} />
      </div>

      <div className="dashboard-content">

        {/* --- Overview: hero stat + supporting KPIs --- */}
        <div className="flex flex-col gap-4">
          <div className={`grid grid-cols-1 lg:grid-cols-12 gap-4 transition-opacity ${rangeLoading ? 'opacity-50' : ''}`}>
            <div className="lg:col-span-4">
              <HeroStatCard
                label="Total Consumption"
                value={consumption.total_kwh.toLocaleString()}
                unit="kWh"
                icon={Zap}
              />
            </div>
            <div className="lg:col-span-8 grid grid-cols-1 sm:grid-cols-3 gap-4">
              <KpiCard label="Avg Hourly Load" value={consumption.avg_hourly_kwh} unit="kWh"
                       trend={trend_pct_vs_prev_period} accent="violet" icon={Activity} />
              <KpiCard label="Peak Load" value={consumption.peak_kwh} unit="kWh" accent="amber" icon={TrendingUp} />
              <KpiCard label="Anomalies Detected" value={anomaly_count} unit="events"
                       accent={anomaly_count > 0 ? 'alert' : 'emerald'} icon={AlertTriangle} />
            </div>
          </div>
        </div>

        {/* --- Telemetry: main chart + load breakdown --- */}
        <div id="telemetry" className="flex flex-col gap-4 scroll-mt-16">
          <div className={`transition-opacity ${rangeLoading ? 'opacity-50' : ''}`}>
            <ConsumptionChart readings={readings} selectedRange={readingsLimit} onRangeChange={handleRangeChange} />
          </div>
          <div className={`transition-opacity ${rangeLoading ? 'opacity-50' : ''}`}>
            <BreakdownChart breakdown={breakdown} />
          </div>
        </div>

        {/* --- Assets: real load-category breakdown, styled as asset cards --- */}
        <div id="assets" className="flex flex-col gap-4 scroll-mt-16">
          <div className="flex items-baseline justify-between">
            <h2 className="font-display text-lg font-semibold text-ink dark:text-slate-100">System Load</h2>
            <span className="font-mono text-[10px] text-slate-400">4 categories monitored</span>
          </div>
          <SystemAssetGrid breakdown={breakdown} totalKwh={consumption.total_kwh} />
        </div>

        {/* --- Efficiency: forecasting + model reliability --- */}
        <div id="efficiency" className="flex flex-col gap-4 scroll-mt-16">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ForecastCard />
            <BriefingCard briefing={briefing} />
          </div>
          <ModelReliabilityChart
            title="1h Forecast Model Reliability"
            subtitle="Actual vs. predicted consumption on held-out test data"
            data={forecastScatter}
            unit="kWh"
          />
          <ForecastModelComparison horizon="1h" />
        </div>

        {/* Investigation zone — visually distinct glass panel, separated from the rest of the page */}
        <AgentInvestigationPanel investigation={investigation} isLoading={investigating} onRun={runInvestigation} buildingId={dashboard.building_id} title="Ask the Energy Agent" prompt="It chooses the evidence to inspect, connects consumption with building conditions, then recommends the next practical move." traceTitle="Energy Agent Trace" hint="A live, self-directed tool sequence — not a preset checklist." buttonLabel="INVESTIGATE ENERGY EFFICIENCY" accent="blue" />

        <RecommendationsList recommendations={top_recommendations} />
      </div>

      <DataManagerModal
        open={managerOpen}
        onClose={() => setManagerOpen(false)}
        title="Manage Energy Dataset"
        subtitle="Raw meter readings"
        fields={ENERGY_FIELDS}
        columns={ENERGY_COLUMNS}
        fetchRecords={limit => energyService.getRecentRecords(limit)}
        addRecord={payload => energyService.addRecord(payload)}
        deleteRecord={id => energyService.deleteRecord(id)}
        clearAllRecords={() => energyService.clearAllRecords()}
        onChanged={refreshNow}
      />

      <DatasetUploadPanel
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        title="Upload Energy Dataset"
        subtitle="CSV/Excel with timestamp + total_kwh (or a Kaggle-style export — columns auto-detected)"
        uploadFn={file => energyService.uploadDataset(file)}
        onUploaded={refreshNow}
        accentClass="blue"
      />
    </div>
  )
}
