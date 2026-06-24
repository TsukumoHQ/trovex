import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../index.css'
import './audit.css'
import Audit from './Audit'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Audit />
  </StrictMode>,
)
