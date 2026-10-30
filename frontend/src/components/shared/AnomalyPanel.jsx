import { useEffect, useState } from 'react'
import api from '../../services/energyService'

export default function AnomalyPanel({ domain, buildingId }) {
  return <ReviewPanel key={`${domain}:${buildingId}`} domain={domain} buildingId={buildingId} />
}

function ReviewPanel({ domain, buildingId }) {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [revision, setRevision] = useState(0)
  const params = { building_id: buildingId, domain }
  const explain = error => typeof error.response?.data?.detail === 'string'
    ? error.response.data.detail : 'Request failed. Please retry.'

  useEffect(() => {
    let active = true
    setBusy(true)
    setError('')
    api.get('/anomalies', { params: { building_id: buildingId, domain, offset, limit: 20, ...(status ? { status } : {}) } })
      .then(({ data }) => { if (active) { setItems(data.items); setTotal(data.total) } })
      .catch(error => { if (active) setError(explain(error)) })
      .finally(() => { if (active) setBusy(false) })
    return () => { active = false }
  }, [buildingId, domain, offset, status, revision])

  async function act(id, review) {
    setBusy(true)
    setError('')
    setMessage('')
    try {
      if (id != null) {
        await api.patch(`/anomalies/${id}`, { status: review }, { params })
        setMessage('Review saved.')
      } else {
        const { data } = await api.post('/anomalies/scan', null, { params })
        setMessage(`${data.created} new alerts; ${data.existing} already saved.`)
      }
      setRevision(value => value + 1)
    } catch (error) {
      setError(explain(error))
      setBusy(false)
    }
  }

  const button = 'rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:opacity-40 hover:bg-slate-100 dark:hover:bg-slate-800'
  return (
    <section className="rounded-2xl border border-slate-200 bg-white dark:bg-slate-900 p-5 space-y-4" aria-label={`${domain} anomaly review`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h2 className="text-lg font-semibold">Anomaly Review</h2><p className="text-sm text-slate-500">Saved findings with supporting signals and occupancy context.</p></div>
        <button className={button} disabled={busy} onClick={() => act(null)}>Scan anomalies</button>
      </div>
      <div className="flex flex-wrap gap-3 items-center">
        <label>Status <select className="rounded border p-2 bg-transparent" disabled={busy} value={status} onChange={e => { setStatus(e.target.value); setOffset(0) }}>
          <option value="">All</option><option value="open">Open</option><option value="confirmed">Confirmed</option><option value="dismissed">Dismissed</option>
        </select></label>
        <button className={button} disabled={busy} onClick={() => setRevision(v => v + 1)}>Refresh</button>
        <span className="text-sm">{total} saved findings</span>
      </div>
      {busy && <p role="status">Loading…</p>}
      {error && <p role="alert" className="text-red-600">{error}</p>}
      {message && <p role="status" className="text-sm">{message}</p>}
      {!busy && !error && !items.length && <p>No matching saved findings. Scan to check the available records.</p>}
      {!error && items.map(item => (
        <article key={item.id} className="rounded-xl border border-slate-200 p-4 space-y-2">
          <div className="flex gap-2 text-xs uppercase"><strong>{item.severity}</strong><span>{item.status}</span></div>
          <p>{item.description}</p>
          <p className="text-sm">Occupancy: <strong>{item.evidence.occupancy ?? 'Unavailable'}</strong> — {item.evidence.occupancy_basis}</p>
          <details><summary className="cursor-pointer text-sm">Supporting signals</summary>
            <dl className="text-sm grid gap-1 mt-2">{Object.entries(item.evidence).filter(([key]) => !key.startsWith('occupancy')).map(([key, value]) => (
              <div key={key} className="break-words"><dt className="inline font-medium">{key.replaceAll('_', ' ')}: </dt><dd className="inline">{value == null ? 'Unavailable' : String(value)}</dd></div>
            ))}</dl>
          </details>
          {item.reviewed_by && <p className="text-xs text-slate-500">Reviewed by {item.reviewed_by} · {item.reviewed_at}</p>}
          <div className="flex gap-2">{['confirmed', 'dismissed'].map(value => <button key={value} className={button} disabled={busy || item.status === value} onClick={() => act(item.id, value)}>{value === 'confirmed' ? 'Confirm' : 'Dismiss'}</button>)}</div>
        </article>
      ))}
      <div className="flex gap-2"><button className={button} disabled={busy || offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous</button><button className={button} disabled={busy || offset + 20 >= total} onClick={() => setOffset(offset + 20)}>Next</button></div>
      <p className="text-xs text-slate-500">Statistical findings need human review. Missing occupancy is not zero occupancy. Reviewed source events stay suppressed on repeat scans; distinct new events can still alert.</p>
    </section>
  )
}
