import { useLayoutEffect, useRef } from 'react'

/** Shows a shared DOM node here. The node moves between slots without remounting, so its React state is kept. */
export function Slot({ host, className }: { host: HTMLElement; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.appendChild(host)
    return () => { if (host.parentNode === el) el.removeChild(host) }
  }, [host])
  return <div ref={ref} className={className} />
}
