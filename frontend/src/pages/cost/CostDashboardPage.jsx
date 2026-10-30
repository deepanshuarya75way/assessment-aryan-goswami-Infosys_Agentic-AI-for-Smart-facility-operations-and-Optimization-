import AnomalyPanel from '../../components/shared/AnomalyPanel'
import { useEffect, useState, useCallback } from 'react'
import { IndianRupee, Database, UploadCloud } from 'lucide-react'
import { costService, formatINR } from '../../services/costService'
import CostKpiRow from '../../components/cost/CostKpiRow'
import CategorySpendChart from '../../components/cost/CategorySpendChart'
import BudgetComplianceList from '../../components/cost/BudgetComplianceList'
import FlaggedInvoicesList from '../../components/cost/FlaggedInvoicesList'
import VendorConcentrationCard from '../../components/cost/VendorConcentrationCard'
import SpendTrendChart from '../../components/cost/SpendTrendChart'
import CostModelComparison from '../../components/cost/CostModelComparison'
import CostAlertsList from '../../components/cost/CostAlertsList'
import SectionHeader from '../../components/maintenance/SectionHeader'
import AgentInvestigationPanel from '../../components/agent/AgentInvestigationPanel'
import DashboardHeader from '../../components/ui/DashboardHeader'
import HeroStatCard from '../../components/cards/HeroStatCard'
import DataManagerModal from '../../components/shared/DataManagerModal'
import DatasetUploadPanel from '../../components/shared/DatasetUploadPanel'
import DashboardSkeleton from '../../components/ui/DashboardSkeleton'
import DataDriftBanner from '../../components/ui/DataDriftBanner'

const COST_FIELDS = [
  { key: 'vendor_name', label: 'Vendor', type: 'text', required: true, placeholder: 'Acme Facilities Ltd' },
  { key: 'category', label: 'Category', type: 'text', required: true, placeholder: 'Repairs & Maintenance' },
  { key: 'amount_inr', label: 'Amount (₹)', type: 'number', required: true },
  { key: 'date', label: 'Date', type: 'datetime-local' },
]
const COST_COLUMNS = [
  { key: 'vendor_name', label: 'vendor' },
  { key: 'category', label: 'category' },
  { key: 'amount_inr', label: 'amount', format: v => formatINR(Number(v)) },
]

export default function CostDashboardPage() {
  const [data, setData] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [investigation, setInvestigation] = useState(null)
  const [investigating, setInvestigating] = useState(false)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [error, setError] = useState(null)
  const [managerFor, setManagerFor] = useState(null)
  const [uploadOpen, setUploadOpen] = useState(false)

  const load = useCallback(async () => {
    const [building, alertsData] = await Promise.all([
      costService.getBuilding(),
      costService.getAlerts(),
    ])
    setData(building)
    setAlerts(alertsData.alerts)
    setLastUpdated(new Date())
  }, [])

  const refreshNow = useCallback(async () => {
    setRefreshing(true)
    try { await load() } catch (err) { setError(err.message) } finally { setRefreshing(false) }
  }, [load])

  useEffect(() => {
    let cancelled = false
    async function init() {
      try {
        setLoading(true)
        await load()
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    init()
    return () => { cancelled = true }
  }, [load])

  const runInvestigation = useCallback(async () => {
    setInvestigating(true)
    setInvestigation(null)
    try {
      const result = await costService.getInvestigation()
      setInvestigation(result)
      const alertsData = await costService.getAlerts()
      setAlerts(alertsData.alerts)
    } catch (err) {
      setError(err.message)
    } finally {
      setInvestigating(false)
    }
  }, [])

  if (loading) {
    return (
      <DashboardSkeleton message="RECONCILING LEDGERS…" kpiCount={5} />
    )
  }

  if (error) {
    return <div className="p-6 text-red-500 dark:text-red-400 text-sm font-mono">connection failed: {error}</div>
  }

  return (
    <div className="dashboard-page">
      <div className="pointer-events-none absolute -top-32 -left-20 w-[420px] h-[420px] rounded-full bg-amber-500/10 dark:bg-amber-500/[0.08] blur-[110px]" />
      <div className="pointer-events-none absolute top-40 -right-32 w-[380px] h-[380px] rounded-full bg-teal-400/10 dark:bg-teal-400/[0.07] blur-[110px]" />

      <DashboardHeader Icon={IndianRupee} agentLabel="COST OPTIMIZATION AGENT" title="Cost" emphasis="Intelligence" description="vendor spend, budget & anomaly monitoring" buildingId={data.building_id} lastUpdated={lastUpdated} isRefreshing={refreshing} onRefresh={refreshNow} accent="amber" />
      <AnomalyPanel domain="cost" buildingId={data.building_id} />

      <div className="dashboard-content">
        <section className="flex flex-col gap-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <SectionHeader title="Spend Overview" subtitle="Real vendor invoice data (see Manage Dataset for the source disclosure), scored for anomalies and budget risk" />
            <div className="flex items-center gap-2 shrink-0">
              <button onClick={() => setUploadOpen(true)} className="flex items-center gap-1.5 font-mono text-[10px] text-amber-700 dark:text-signal border border-amber-500/30 dark:border-signal/30 bg-amber-500/5 dark:bg-signal/5 rounded-full px-3 py-1.5 hover:bg-amber-500/10 transition-colors">
                <UploadCloud size={12} /> UPLOAD DATASET
              </button>
              <button onClick={() => setManagerFor({})} className="flex items-center gap-1.5 font-mono text-[10px] text-amber-700 dark:text-signal border border-amber-500/30 dark:border-signal/30 bg-amber-500/5 dark:bg-signal/5 rounded-full px-3 py-1.5 hover:bg-amber-500/10 transition-colors">
                <Database size={12} /> MANAGE DATASET
              </button>
            </div>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            <div className="lg:col-span-4">
              <HeroStatCard label="Total Spend" value={formatINR(data.summary.total_spend_inr)} unit="real + derived, combined" icon={IndianRupee} />
            </div>
            <div className="lg:col-span-8">
              <CostKpiRow summary={data.summary} forecast={data.forecast} hideHero />
            </div>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
            <CategorySpendChart breakdown={data.category_breakdown} />
            <VendorConcentrationCard concentration={data.vendor_concentration} />
          </div>
          <SpendTrendChart forecast={data.forecast} />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
            <BudgetComplianceList compliance={data.budget_compliance} />
            <FlaggedInvoicesList invoices={data.flagged_invoices} />
          </div>
          <CostModelComparison anomalyPrimary={data.anomaly_model_confidence} anomalyComparison={data.anomaly_comparison_confidence} forecastConfidence={data.forecast_confidence} />
          <DataDriftBanner drift={data.data_drift} subject="the currently loaded spend data" />
        </section>

        <AgentInvestigationPanel investigation={investigation} isLoading={investigating} onRun={runInvestigation} buildingId={data.building_id} title="Ask the Cost Agent" prompt="It weighs budget risk, flagged invoices, and vendor concentration together, and opens only the alerts that deserve escalation." traceTitle="Cost Agent Trace" hint="A real-time activity trace of evidence, risk assessment, and escalations." buttonLabel="INVESTIGATE FACILITY SPEND" accent="violet" />

        <section className="flex flex-col gap-4">
          <SectionHeader title="Alerts" subtitle="Budget-overrun and anomaly-driven cost alerts" />
          <CostAlertsList alerts={alerts} />
        </section>
      </div>

      <DataManagerModal
        open={!!managerFor}
        onClose={() => setManagerFor(null)}
        title="Manage Cost Dataset"
        subtitle="Real BBMP (Bengaluru) tenders + derived cross-agent operational cost, in ₹ — see build_cost_dataset.py for the full disclosure"
        fields={COST_FIELDS}
        columns={COST_COLUMNS}
        fetchRecords={limit => costService.getRecentRecords(null, limit)}
        addRecord={payload => costService.addRecord(payload)}
        deleteRecord={id => costService.deleteRecord(id)}
        clearAllRecords={() => costService.clearAllRecords()}
        onChanged={refreshNow}
      />

      <DatasetUploadPanel
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        title="Upload Cost Dataset"
        subtitle="CSV/Excel with vendor_name, category, date, amount_inr"
        uploadFn={file => costService.uploadDataset(file)}
        onUploaded={refreshNow}
        accentClass="amber"
      />
    </div>
  )
}
