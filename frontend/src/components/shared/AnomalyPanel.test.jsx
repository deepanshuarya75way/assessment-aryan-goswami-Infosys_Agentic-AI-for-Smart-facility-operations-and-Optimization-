// @vitest-environment jsdom
import React from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import AnomalyPanel from './AnomalyPanel'
import api from '../../services/energyService'

vi.mock('../../services/energyService', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }))
afterEach(() => { cleanup(); vi.resetAllMocks() })

test('loads evidence, scans and persists a review through the API', async () => {
  const event = { id: 1, severity: 'high', status: 'open', description: 'Unexpected energy use', evidence: { occupancy: 0, occupancy_basis: 'Same timestamp', z_score: 3 } }
  api.get.mockImplementation(async () => ({ data: { total: 1, items: [{ ...event }] } }))
  api.post.mockResolvedValue({ data: { created: 0, existing: 1 } })
  api.patch.mockImplementation(async (url, body) => { event.status = body.status; return { data: event } })
  render(<AnomalyPanel domain="energy" buildingId="A" />)
  expect(await screen.findByText('Unexpected energy use')).toBeInTheDocument()
  expect(screen.getByText('0', { selector: 'strong' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Scan anomalies' }))
  expect(await screen.findByText('0 new alerts; 1 already saved.')).toBeInTheDocument()
  await waitFor(() => expect(screen.getByRole('button', { name: 'Dismiss' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
  expect(await screen.findByText('dismissed')).toBeInTheDocument()
  expect(api.patch).toHaveBeenCalledWith('/anomalies/1', { status: 'dismissed' }, { params: { building_id: 'A', domain: 'energy' } })
})

test('shows API failure and supports retry', async () => {
  api.get.mockRejectedValueOnce({ response: { data: { detail: 'Please log in' } } })
    .mockResolvedValue({ data: { total: 0, items: [] } })
  render(<AnomalyPanel domain="cost" buildingId="A" />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Please log in')
  fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))
  expect(await screen.findByText(/No matching saved findings/)).toBeInTheDocument()
})
