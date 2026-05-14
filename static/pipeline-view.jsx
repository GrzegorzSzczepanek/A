// pipeline-view.jsx — Processing pipeline visualization

function PipelineView({ stages, logs, onComplete }) {
  const doneCount = stages.filter(s => s.status === 'done').length;
  const totalStages = stages.length;
  const fillPercent = totalStages > 0 ? (doneCount / totalStages) * 100 : 0;
  const allDone = doneCount === totalStages;
  const logEndRef = React.useRef(null);

  React.useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [logs.length]);

  React.useEffect(() => {
    if (allDone && onComplete) {
      const t = setTimeout(onComplete, 600);
      return () => clearTimeout(t);
    }
  }, [allDone]);

  const now = new Date();
  const timeBase = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;

  return (
    <div className="view-enter" style={{ maxWidth: 800, margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: 24 }}>
        <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: 20, fontWeight: 700, letterSpacing: '-0.02em' }}>
          {allDone ? 'Conversion Complete' : 'Processing Pipeline'}
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>
          {allDone
            ? 'All stages passed - preparing results'
            : `Stage ${Math.min(doneCount + 1, totalStages)} of ${totalStages}`
          }
        </p>
      </div>

      <div className="card" style={{ overflow: 'hidden' }}>
        {/* Stepper */}
        <div style={{ position: 'relative', padding: '28px 40px 12px' }}>
          {/* Connecting line */}
          <div style={{
            position: 'absolute',
            top: 46,
            left: 80,
            right: 80,
            height: 2,
            background: 'var(--border)',
            zIndex: 1,
          }}>
            <div style={{
              height: '100%',
              width: `${fillPercent}%`,
              background: 'var(--success)',
              transition: 'width 0.4s ease',
              borderRadius: 1,
            }}></div>
          </div>

          <div className="pipeline-stepper">
            {stages.map((stage, i) => (
              <div className="pipeline-stage" key={stage.id}>
                <div className={`pipeline-node ${
                  stage.status === 'active' ? 'pipeline-node--active' :
                  stage.status === 'done' ? 'pipeline-node--done' :
                  stage.status === 'error' ? 'pipeline-node--error' : ''
                }`}>
                  {stage.status === 'done' ? (
                    <IconCheck />
                  ) : (
                    <span style={{ color: stage.status === 'active' ? 'var(--primary)' : 'var(--text-muted)' }}>
                      <StageIcon stageId={stage.id} />
                    </span>
                  )}
                  {stage.status === 'active' && (
                    <span style={{
                      position: 'absolute', inset: -4,
                      borderRadius: '50%',
                      border: '2px solid var(--primary)',
                      opacity: 0.3,
                      animation: 'pulse-dot 1.2s ease-in-out infinite',
                    }}></span>
                  )}
                </div>
                <div className="pipeline-label">{stage.name}</div>
                {stage.time && (
                  <div className="pipeline-time">{stage.time}s</div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Progress bar */}
        <div style={{ padding: '0 20px 12px' }}>
          <div style={{
            height: 3,
            background: 'var(--surface-sunken)',
            borderRadius: 2,
            overflow: 'hidden',
          }}>
            <div style={{
              height: '100%',
              width: `${fillPercent}%`,
              background: allDone ? 'var(--success)' : 'var(--primary)',
              transition: 'width 0.4s ease, background 0.3s',
              borderRadius: 2,
            }}></div>
          </div>
        </div>

        {/* Log panel */}
        {logs.length > 0 && (
          <div className="log-panel">
            {logs.map((log, i) => (
              <div className="log-entry" key={i}>
                <span className="log-time">[{timeBase}:{String(i * 3 + 1).padStart(2,'0')}]</span>
                <span className="log-stage">{log.stage}</span>
                <span className="log-msg">{log.msg}</span>
              </div>
            ))}
            <div ref={logEndRef}></div>
          </div>
        )}
      </div>

      {allDone && (
        <div style={{ textAlign: 'center', marginTop: 20, animation: 'slide-up 0.3s ease' }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            background: 'var(--success-bg)', color: 'var(--success)',
            padding: '8px 16px', borderRadius: 8,
            fontSize: 13, fontWeight: 600,
          }}>
            <StatusDot status="done" />
            DITA-OT HTML5 strict: PASS
          </div>
        </div>
      )}
    </div>
  );
}

Object.assign(window, { PipelineView });
