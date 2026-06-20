import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../index.css'
import './savings.css'
import Savings from './Savings'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Savings />
  </StrictMode>,
)
