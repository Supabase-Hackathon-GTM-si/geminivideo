/**
 * Every beverage moment Gemini flagged, newest first, optionally filtered to
 * one stream.
 */
import { CATEGORY_LABELS, fmtDollars, fmtTime } from './format.js'

export default function FlagFeed({ flags, filterName, onClearFilter }) {
  return (
    <div className="feed">
      <h2>
        Gemini flags
        {filterName && (
          <span className="filter-chip" onClick={onClearFilter}>{filterName} ×</span>
        )}
      </h2>
      <div className="events">
        {flags.length === 0 && <div className="muted">Nothing flagged yet.</div>}
        {flags.map((e) => (
          <div key={e.event_id} className={`event ${e.tipped ? 'tipped' : 'cooldown'}`}>
            <div className="event-head">
              <span className="cat">{CATEGORY_LABELS[e.category] || e.category}</span>
              {e.brand && <span className="brand">{e.brand}</span>}
              <span className="conf">{Math.round(e.confidence * 100)}%</span>
              <span className={e.tipped ? 'tip' : 'tip off'}>
                {e.tipped ? `would tip ${fmtDollars(e.suggested_tip_cents)}` : 'cooldown'}
              </span>
            </div>
            <div className="desc">{e.description}</div>
            {e.quote && <div className="quote">"{e.quote}"</div>}
            <div className="muted small">
              <b>{e.streamer_id}</b> · stream time {fmtTime(e.stream_offset_seconds)} ·{' '}
              {new Date(e.detected_at).toLocaleTimeString()}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
