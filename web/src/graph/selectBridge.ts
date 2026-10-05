import { createContext } from 'react'

// A tiny bridge so the side panel can re-select nodes without prop-drilling
// through SigmaContainer. Graph provides it; SidePanel consumes it. Kept in its
// own module so both component files stay fast-refresh friendly.
export const SelectBridge = createContext<(id: string) => void>(() => {})
