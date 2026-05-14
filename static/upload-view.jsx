// upload-view.jsx — Upload / Ingestion view

function UploadView({ files, onFilesAdded, onStartConversion, onLoadSample }) {
  const [dragActive, setDragActive] = React.useState(false);
  const inputRef = React.useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDragIn = (e) => {
    e.preventDefault();
    setDragActive(true);
  };

  const handleDragOut = (e) => {
    e.preventDefault();
    setDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    const dropped = [...e.dataTransfer.files].filter(f => f.name.toLowerCase().endsWith('.pdf'));
    if (dropped.length) onFilesAdded(dropped);
  };

  const handleFileInput = (e) => {
    const selected = [...e.target.files];
    if (selected.length) onFilesAdded(selected);
    e.target.value = '';
  };

  const hasFiles = files.length > 0;

  return (
    <div className="view-enter" style={{ maxWidth: 680, margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: 32 }}>
        <h1 style={{ fontFamily: 'var(--font-heading)', fontSize: 24, fontWeight: 700, marginBottom: 6, letterSpacing: '-0.02em' }}>
          PDF to DITA Conversion
        </h1>
        <p style={{ fontSize: 14, color: 'var(--text-muted)' }}>
          Upload PDF documentation to convert into validated DITA 1.3 XML
        </p>
      </div>

      <div
        className={`dropzone ${dragActive ? 'dropzone--active' : ''}`}
        onDragEnter={handleDragIn}
        onDragLeave={handleDragOut}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <div className="dropzone__icon">
          <IconUpload />
        </div>
        <div className="dropzone__title">Drop PDF files here</div>
        <div className="dropzone__sub">or click to browse - multiple files supported</div>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          multiple
          style={{ display: 'none' }}
          onChange={handleFileInput}
        />
        <button className="sample-btn" onClick={(e) => { e.stopPropagation(); onLoadSample(); }}>
          Load included sample
        </button>
      </div>

      {hasFiles && (
        <div className="card" style={{ marginTop: 20, animation: 'slide-up 0.25s ease' }}>
          <table className="file-table">
            <thead>
              <tr>
                <th>File</th>
                <th>Size</th>
                <th>Pages</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {files.map((f, i) => (
                <tr key={i}>
                  <td style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <IconDoc />
                    <span style={{ fontWeight: 500 }}>{f.name}</span>
                  </td>
                  <td style={{ color: 'var(--text-muted)' }}>{formatSize(f.size)}</td>
                  <td style={{ color: 'var(--text-muted)' }}>{f.pages}</td>
                  <td>
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: 5,
                      fontSize: 12, color: 'var(--success)', fontWeight: 500,
                    }}>
                      <StatusDot status="done" /> Ready
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {hasFiles && (
        <div style={{ textAlign: 'center', marginTop: 20 }}>
          <button className="btn btn--primary" style={{ minWidth: 200, padding: '10px 24px', fontSize: 14 }}
            onClick={onStartConversion}>
            Start Conversion
          </button>
          <div style={{ marginTop: 10, fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            or press <Kbd>Enter</Kbd>
          </div>
        </div>
      )}

      {!hasFiles && (
        <div style={{ textAlign: 'center', marginTop: 28, fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
          Press <Kbd>S</Kbd> to load the sample file
        </div>
      )}
    </div>
  );
}

Object.assign(window, { UploadView });
