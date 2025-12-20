import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import DivergenceMeter from './DivergenceMeter.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <DivergenceMeter />
  </StrictMode>,
)
