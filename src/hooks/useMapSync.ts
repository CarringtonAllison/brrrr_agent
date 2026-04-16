import { useCallback, useRef } from 'react'

/**
 * Syncs map pin highlight with card selection.
 * Call `registerCard(id, el)` for each DealCard's DOM node.
 * Call `scrollToCard(id)` when a map pin is clicked.
 */
export function useMapSync() {
  const cardRefs = useRef<Map<string, HTMLElement>>(new Map())

  const registerCard = useCallback((id: string, el: HTMLElement | null) => {
    if (el) cardRefs.current.set(id, el)
    else cardRefs.current.delete(id)
  }, [])

  const scrollToCard = useCallback((id: string) => {
    const el = cardRefs.current.get(id)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [])

  return { registerCard, scrollToCard }
}
