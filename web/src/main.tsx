import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Analytics } from '@vercel/analytics/react'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
    {/* Vercel Web Analytics: pageviews + Web Vitals, cookieless. Complements the
        Plausible custom-event funnel + GEO attribution; does not replace it.
        Data appears only after a Vercel deploy with Analytics enabled. */}
    <Analytics />
  </StrictMode>,
)
