/**
 * Dashboard: start a session (stream URL, webcam, or screen-share), watch the
 * preview, and see beverage moments + per-chunk pipeline status live.
 */
import { useEffect, useRef, useState } from 'react'
import { useEventStream } from './useEventStream.js'
import { startClipUploader } from './browserCapture.js'

const CATEGORY_LABELS = {
  sports_drink_mention: 'Sports drink mention',
  drinking_water: 'Drinking water',
  drinking_other: 'Drinking (other)',
  holding_or_showing_beverage: 'Showing a beverage',
  verbal_beverage_mention: 'Talks about drinks',
}

function embedUrl(url) {
  try {
    const u = new URL(url)
    const host = u.hostname.replace('www.', '')
    if (host.endsWith('twitch.tv')) {
      const channel = u.pathname.split('/').filter(Boolean)[0]
      return `https://player.twitch.tv/?channel=${channel}&parent=${location.hostname}&muted=true`
    }
    if (host === 'youtu.be') return `https://www.youtube.com/embed/${u.pathname.slice(1)}?autoplay=1&mute=1`
    if (host.endsWith('youtube.com')) {
      const parts = u.pathname.split('/').filter(Boolean)
      const id = u.searchParams.get('v') || (parts[0] === 'live' || parts[0] === 'shorts' ? parts[1] : null)
      if (id) return `https://www.youtube.com/embed/${id}?autoplay=1&mute=1`
    }
  } catch {}
  return null
}

function fmtTime(s) {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}

export default function App() {
  const { events, chunks, sessions, connected } = useEventStream()
  const [health, setHealth] = useState(null)
  const [url, setUrl] = useState('')
  const [streamerId, setStreamerId] = useState('demo-streamer')
  const [active, setActive] = useState(null) // {id, source, url?, stream?}
  const [error, setError] = useState('')
  const videoRef = useRef(null)
  const stopUploaderRef = useRef(null)

  useEffect(() => {
    fetch('/api/health').then((r) => r.json()).then(setHealth).catch(() => setHealth(null))
  }, [])

  useEffect(() => {
    if (videoRef.current && active?.stream) videoRef.current.srcObject = active.stream
  }, [active])

  async function createSession(body) {
    const r = await fetch('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...body, streamer_id: streamerId }),
    })
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText)
    return r.json()
  }

  async function startUrl() {
    setError('')
    try {
      const s = await createSession({ source: 'url', url: url.trim() })
      setActive({ id: s.id, source: 'url', url: url.trim() })
    } catch (e) {
      setError(String(e.message || e))
    }
  }

  async function startBrowser(kind) {
    setError('')
    try {
      const stream =
        kind === 'webcam'
          ? await navigator.mediaDevices.getUserMedia({ video: { width: 854, height: 480 }, audio: true })
          : await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: 15 }, audio: true })
      const s = await createSession({ source: 'browser' })
      stopUploaderRef.current = startClipUploader(stream, s.id, health?.chunk_seconds || 10, setError)
      stream.getVideoTracks()[0].addEventListener('ended', () => stop())
      setActive({ id: s.id, source: kind, stream })
    } catch (e) {
      setError(String(e.message || e))
    }
  }

  async function stop() {
    stopUploaderRef.current?.()
    stopUploaderRef.current = null
    setActive((cur) => {
      cur?.stream?.getTracks().forEach((t) => t.stop())
      if (cur) fetch(`/api/sessions/${cur.id}`, { method: 'DELETE' })
      return null
    })
  }

  const session = active ? sessions[active.id] : null
  const sessionChunks = Object.values(chunks)
    .filter((c) => !active || c.session_id === active.id)
    .sort((a, b) => b.chunk_index - a.chunk_index)
    .slice(0, 30)
  const tippedTotal = events.filter((e) => e.tipped).reduce((sum, e) => sum + e.suggested_tip_cents, 0)
  const embed = active?.source === 'url' ? embedUrl(active.url) : null

  return (
    <div className="app">
      <header>
        <h1>Beverage Moment Detector</h1>
        <div className="status">
          <span className={connected ? 'dot ok' : 'dot bad'} /> {connected ? 'live' : 'disconnected'}
          {health && (
            <span className="muted">
              {' '}· {health.model} · {health.chunk_seconds}s clips
              {!health.api_key_set && <b className="warn"> · GEMINI_API_KEY missing</b>}
            </span>
          )}
        </div>
      </header>

      <section className="controls">
        {!active ? (
          <>
            <input className="streamer" value={streamerId} onChange={(e) => setStreamerId(e.target.value)}
                   placeholder="streamer id" />
            <input className="url" value={url} onChange={(e) => setUrl(e.target.value)}
                   placeholder="https://twitch.tv/... or YouTube live URL (or local file path)"
                   onKeyDown={(e) => e.key === 'Enter' && url && startUrl()} />
            <button onClick={startUrl} disabled={!url}>Watch URL</button>
            <span className="muted">or</span>
            <button onClick={() => startBrowser('webcam')}>Webcam</button>
            <button onClick={() => startBrowser('screen')}>Screen-share a tab</button>
          </>
        ) : (
          <>
            <span>
              Watching <b>{active.source === 'url' ? active.url : active.source}</b> as <b>{streamerId}</b>
              {session && <span className="muted"> · {session.chunks_analyzed} clips analyzed · {session.events_detected} moments</span>}
              {session?.source_exited && <b className="warn"> · stream ended</b>}
            </span>
            <button className="stop" onClick={stop}>Stop</button>
          </>
        )}
        {error && <div className="error">{error}</div>}
      </section>

      <main>
        <div className="left">
          <div className="preview">
            {active?.stream && <video ref={videoRef} autoPlay muted playsInline />}
            {embed && <iframe src={embed} allow="autoplay; fullscreen" allowFullScreen title="stream" />}
            {active?.source === 'url' && !embed && <div className="placeholder">Analyzing {active.url}</div>}
            {!active && <div className="placeholder">Start a session to see the stream here</div>}
          </div>

          <h2>Pipeline</h2>
          <div className="chunks">
            {sessionChunks.length === 0 && <div className="muted">No clips yet. The first one arrives after one clip length.</div>}
            {sessionChunks.map((c) => (
              <div key={`${c.session_id}:${c.chunk_index}`} className={`chunk ${c.status}`}>
                <span>#{c.chunk_index}</span>
                <span>{fmtTime(c.stream_offset_seconds)}</span>
                <span className="chunk-status">{c.status.replace('_', ' ')}</span>
                <span className="muted">{c.latency_ms != null ? `${(c.latency_ms / 1000).toFixed(1)}s` : ''}</span>
                {c.error && <span className="chunk-error" title={c.error}>{c.error}</span>}
              </div>
            ))}
          </div>
        </div>

        <div className="right">
          <h2>
            Beverage moments <span className="muted">· ${(tippedTotal / 100).toFixed(2)} suggested tips</span>
          </h2>
          <div className="events">
            {events.length === 0 && <div className="muted">Nothing detected yet. Take a sip of water on camera.</div>}
            {events.map((e) => (
              <div key={e.event_id} className={`event ${e.tipped ? 'tipped' : 'cooldown'}`}>
                <div className="event-head">
                  <span className="cat">{CATEGORY_LABELS[e.category] || e.category}</span>
                  {e.brand && <span className="brand">{e.brand}</span>}
                  <span className="conf">{Math.round(e.confidence * 100)}%</span>
                  <span className="muted">@ {fmtTime(e.stream_offset_seconds)}</span>
                  <span className={e.tipped ? 'tip' : 'tip off'}>
                    {e.tipped ? `would tip $${(e.suggested_tip_cents / 100).toFixed(2)}` : 'cooldown'}
                  </span>
                </div>
                <div className="desc">{e.description}</div>
                {e.quote && <div className="quote">"{e.quote}"</div>}
                <div className="muted small">{e.streamer_id} · {new Date(e.detected_at).toLocaleTimeString()}</div>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  )
}
