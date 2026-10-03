/**
 * Subscribes to the backend WebSocket and keeps events, chunk statuses and
 * session summaries in React state. Reconnects automatically.
 */
import { useEffect, useState } from 'react'

export function useEventStream() {
  const [events, setEvents] = useState([])
  const [chunks, setChunks] = useState({})
  const [sessions, setSessions] = useState({})
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    let ws
    let closed = false
    let retry

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/ws/events`)
      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        if (!closed) retry = setTimeout(connect, 1500)
      }
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data)
        if (msg.type === 'event') {
          setEvents((prev) => [{ ...msg.data, tipped: msg.tipped }, ...prev].slice(0, 200))
        } else if (msg.type === 'chunk') {
          const c = msg.data
          setChunks((prev) => ({ ...prev, [`${c.session_id}:${c.chunk_index}`]: c }))
        } else if (msg.type === 'session') {
          setSessions((prev) => ({ ...prev, [msg.data.id]: msg.data }))
        } else if (msg.type === 'session_stopped') {
          setSessions((prev) => {
            const next = { ...prev }
            delete next[msg.data.id]
            return next
          })
        }
      }
    }

    fetch('/api/events')
      .then((r) => r.json())
      .then((recent) => setEvents(recent.map((m) => ({ ...m.data, tipped: m.tipped })).reverse()))
      .catch(() => {})
    connect()
    return () => {
      closed = true
      clearTimeout(retry)
      ws?.close()
    }
  }, [])

  return { events, chunks, sessions, connected }
}
