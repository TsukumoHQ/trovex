import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@react-sigma/core/lib/style.css'
import '../index.css'
import './graph.css'
import Graph from './Graph'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Graph />
  </StrictMode>,
)
