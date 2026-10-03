/**
 * Monitor dashboard: watch several streams at once (stream URLs, webcam, or
 * screen-share), each as a tile, next to a combined feed of every beverage
 * moment Gemini flagged.
 */
import { useEffect, useRef, useState } from 'react'
import { useEventStream } from './useEventStream.js'
import { startClipUploader } from './browserCapture.js'
import { fmtDollars } from './format.js'
import StreamTile from './StreamTile.jsx'
import FlagFeed from './FlagFeed.jsx'

export default function App() {
  const { events, chunks, sessions, connected } = useEventStream()
  const [health, setHealth] = useState(null)
  const [url, setUrl] = useState('')
  const [streamerId, setStreamerId] = useState('demo-streamer')
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState('')
  // Browser-captured streams owned by this tab: id -> {stream, stopUploader}
  const local = useRef({})
  const [, rerender] = useState(0)

  useEffect(() => {
    fetch('/api/health').then((r) => r.json()).then(setHealth).catch(() => setHealth(null))
  }, [])

  async function createSession(body) {
    const r = await fetch('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...body, streamer_id: streamerId.trim() || 'streamer' }),
    })
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText)
    return r.json()
  }

  async function addUrl() {
    setError('')
    try {
      await createSession({ source: 'url', url: url.trim() })
      setUrl('')
    } catch (e) {
      setError(String(e.message || e))
    }
  }

  async function addBrowser(kind) {
    setError('')
    try {
      const stream =
        kind === 'webcam'
          ? await navigator.mediaDevices.getUserMedia({ video: { width: 854, height: 480 }, audio: true })
          : await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: 15 }, audio: true })
      const s = await createSession({ source: 'browser' })
      const stopUploader = startClipUploader(stream, s.id, health?.chunk_seconds || 10, setError)
      local.current[s.id] = { stream, stopUploader }
      stream.getVideoTracks()[0].addEventListener('ended', () => stop(s.id))
      rerender((n) => n + 1)
    } catch (e) {
      setError(String(e.message || e))
    }
  }

  function stop(id) {
    const l = local.current[id]
    if (l) {
      l.stopUploader()
      l.stream.getTracks().forEach((t) => t.stop())
      delete local.current[id]
    }
    if (selected === id) setSelected(null)
    fetch(`/api/sessions/${id}`, { method: 'DELETE' })
  }

  const streams = Object.values(sessions).sort((a, b) => a.started_at - b.started_at)
  const chunksBySession = {}
  for (const c of Object.values(chunks)) (chunksBySession[c.session_id] ||= []).push(c)
  for (const list of Object.values(chunksBySession)) list.sort((a, b) => b.chunk_index - a.chunk_index)
  const flagsBySession = {}
  for (const e of events) (flagsBySession[e.session_id] ||= []).push(e)

  const totalClips = streams.reduce((sum, s) => sum + s.chunks_analyzed, 0)
  const totalTips = events.filter((e) => e.tipped).reduce((sum, e) => sum + e.suggested_tip_cents, 0)
  const feedFlags = selected ? flagsBySession[selected] || [] : events

  return (
    <div className="app">
      <header>
        <h1>Beverage Moment Monitor</h1>
        <div className="status">
          <span className={connected ? 'dot ok' : 'dot bad'} /> {connected ? 'connected' : 'disconnected'}
          {health && (
            <span className="muted">
              {' '}· {health.model} · {health.chunk_seconds}s clips
              {!health.api_key_set && <b className="warn"> · GEMINI_API_KEY missing</b>}
            </span>
          )}
        </div>
      </header>

      <section className="kpis">
        <div><span>{streams.length}</span>streams live</div>
        <div><span>{totalClips}</span>clips analyzed</div>
        <div><span>{events.length}</span>Gemini flags</div>
        <div><span>{fmtDollars(totalTips)}</span>suggested tips</div>
      </section>

      <section className="controls">
        <input className="streamer" value={streamerId} onChange={(e) => setStreamerId(e.target.value)}
               placeholder="streamer id" />
        <input className="url" value={url} onChange={(e) => setUrl(e.target.value)}
               placeholder="https://twitch.tv/... or YouTube live URL (or local file path)"
               onKeyDown={(e) => e.key === 'Enter' && url && addUrl()} />
        <button onClick={addUrl} disabled={!url}>Add stream</button>
        <span className="muted">or</span>
        <button onClick={() => addBrowser('webcam')}>Webcam</button>
        <button onClick={() => addBrowser('screen')}>Screen-share a tab</button>
        {error && <div className="error">{error}</div>}
      </section>

      <main>
        <div className="grid">
          {streams.length === 0 && (
            <div className="empty">No streams yet. Add a Twitch or YouTube live URL, or use your webcam.</div>
          )}
          {streams.map((s) => (
            <StreamTile
              key={s.id}
              session={s}
              localStream={local.current[s.id]?.stream}
              chunks={chunksBySession[s.id] || []}
              flags={flagsBySession[s.id] || []}
              selected={selected === s.id}
              onSelect={() => setSelected(selected === s.id ? null : s.id)}
              onStop={() => stop(s.id)}
            />
          ))}
        </div>
        <FlagFeed
          flags={feedFlags}
          filterName={selected && sessions[selected]?.streamer_id}
          onClearFilter={() => setSelected(null)}
        />
      </main>
    </div>
  )
}
