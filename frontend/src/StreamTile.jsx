/**
 * One monitored stream: live preview, a banner for Gemini's most recent flag,
 * and a strip showing the outcome of each analyzed clip.
 */
import { useEffect, useRef, useState } from 'react'
import { CATEGORY_LABELS, embedUrl, fmtDollars, sourceLabel } from './format.js'

const FLAG_BANNER_MS = 10000

export default function StreamTile({ session, localStream, chunks, flags, selected, onSelect, onStop }) {
  const videoRef = useRef(null)
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    if (videoRef.current && localStream) videoRef.current.srcObject = localStream
  }, [localStream])

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])

  const embed = session.source === 'url' ? embedUrl(session.url) : null
  const latest = flags[0]
  const showBanner = latest && now - new Date(latest.detected_at).getTime() < FLAG_BANNER_MS
  const tipped = flags.filter((f) => f.tipped).reduce((sum, f) => sum + f.suggested_tip_cents, 0)
  const lastClip = chunks[0]

  return (
    <div className={`tile ${selected ? 'selected' : ''} ${showBanner ? 'flashing' : ''}`} onClick={onSelect}>
      <div className="tile-preview">
        {localStream && <video ref={videoRef} autoPlay muted playsInline />}
        {!localStream && embed && <iframe src={embed} allow="autoplay; fullscreen" title={session.streamer_id} />}
        {!localStream && !embed && (
          <div className="placeholder">
            {session.source === 'browser' ? 'Preview only in the tab that started it' : session.url}
          </div>
        )}
        <span className={`badge ${session.source_exited ? 'ended' : 'live'}`}>
          {session.source_exited ? 'ENDED' : 'LIVE'}
        </span>
        {showBanner && (
          <div className="flag-banner">
            <b>Gemini flag</b> · {CATEGORY_LABELS[latest.category] || latest.category}
            {latest.brand && ` · ${latest.brand}`} · {Math.round(latest.confidence * 100)}%
          </div>
        )}
      </div>

      <div className="tile-body">
        <div className="tile-title">
          <b>{session.streamer_id}</b>
          <span className="muted">{sourceLabel(session)}</span>
          <button className="stop small-btn" onClick={(e) => { e.stopPropagation(); onStop() }}>Stop</button>
        </div>
        <div className="tile-stats">
          <span><b>{flags.length}</b> flags</span>
          <span><b>{session.chunks_analyzed}</b> clips</span>
          <span className="tip-total">{fmtDollars(tipped)} tips</span>
          <span className="muted">
            {lastClip
              ? `last clip: ${lastClip.status.replace('_', ' ')}`
              : session.chunks_analyzed > 0 ? 'watching' : 'waiting for first clip'}
          </span>
        </div>
        <div className="clip-strip" title="Each square is one analyzed clip, newest on the right">
          {[...chunks].slice(0, 40).reverse().map((c) => (
            <span key={c.chunk_index} className={`clip ${c.status}`} title={`#${c.chunk_index} ${c.status}`} />
          ))}
        </div>
      </div>
    </div>
  )
}
