// Deploys this week: a React page as claude.ai's React artifacts are, served by
// rrotor's React shell with no build. Imports only from the shell's import map
// (react, recharts); Tailwind classes; the default export is what the shell
// mounts into #root.
import React from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

type Day = { day: string; production: number; staging: number }

// Static numbers. For live ones, make them a function the page calls as the
// viewer (programs/app_dashboard) and set the type to dashboard.
const DEPLOYS: Day[] = [
  { day: 'Mon', production: 4, staging: 9 },
  { day: 'Tue', production: 6, staging: 11 },
  { day: 'Wed', production: 3, staging: 7 },
  { day: 'Thu', production: 8, staging: 12 },
  { day: 'Fri', production: 2, staging: 5 },
]

export default function Deploys() {
  const total = DEPLOYS.reduce((n, d) => n + d.production + d.staging, 0)
  return (
    <main className="mx-auto max-w-3xl p-8 font-sans text-gray-900">
      <h1 className="text-2xl font-semibold">Deploys this week</h1>
      <p className="mb-6 text-sm text-gray-500">
        {total} deploys, Monday to Friday, by environment.
      </p>
      <div className="h-72 rounded-xl border border-gray-200 p-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={DEPLOYS}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="day" />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Legend />
            <Bar dataKey="production" name="Production" fill="#2563eb" radius={[4, 4, 0, 0]} />
            <Bar dataKey="staging" name="Staging" fill="#93c5fd" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </main>
  )
}
