import { useEffect } from 'react'
import { trackSectionViews } from './analytics'

/**
 * Scroll-depth tracking, mounted at the root so App.tsx (cro-lead's file) stays
 * untouched. Fires `section_viewed` once per landing section as it scrolls in.
 * Renders nothing.
 */
export default function SectionViews() {
  useEffect(() => trackSectionViews(), [])
  return null
}
