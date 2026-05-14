// app.jsx — Main application shell, routing, keyboard shortcuts, theme

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "light"
}/*EDITMODE-END*/;

function App() {
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [view, setView] = React.useState('upload'); // upload | processing | results
  const [files, setFiles] = React.useState([]);
  const [stages, setStages] = React.useState([]);
  const [logs, setLogs] = React.useState([]);
  const [results, setResults] = React.useState(null);

  // Apply theme
  React.useEffect(() => {
    document.documentElement.setAttribute('data-theme', tweaks.theme);
  }, [tweaks.theme]);

  const toggleTheme = React.useCallback(() => {
    setTweak('theme', tweaks.theme === 'light' ? 'dark' : 'light');
  }, [tweaks.theme]);

  // Add files from drop/browse
  const handleFilesAdded = React.useCallback((newFiles) => {
    const processed = newFiles.map(f => ({
      name: f.name,
      size: f.size,
      pages: Math.max(1, Math.round(f.size / 50000)),
      status: 'ready',
      _raw: f,  // preserve File handle for the POST /convert upload
    }));
    setFiles(prev => [...prev, ...processed]);
  }, []);

  // Load sample file (mock path - no real File object available)
  const handleLoadSample = React.useCallback(() => {
    setFiles([MockAPI.getMockFile()]);
  }, []);

  // Start conversion - posts to /convert when a real File is available,
  // otherwise falls back to the mock pipeline (sample button).
  const startConversion = React.useCallback(async () => {
    if (files.length === 0) return;
    setView('processing');
    setLogs([]);
    setStages(MockAPI.STAGES.map(s => ({ ...s, status: 'queued', time: null })));

    try {
      const realFile = files[0] && files[0]._raw;
      const result = await MockAPI.runPipeline(
        (updatedStages) => setStages([...updatedStages]),
        (logEntry) => setLogs(prev => [...prev, logEntry]),
        realFile,
      );
      setResults(result);
    } catch (err) {
      console.error('Conversion failed', err);
      setLogs(prev => [...prev, { stage: 'Error', msg: String(err.message || err), time: '-' }]);
    }
  }, [files]);

  const handlePipelineComplete = React.useCallback(() => {
    setView('results');
  }, []);

  const handleReset = React.useCallback(() => {
    setView('upload');
    setFiles([]);
    setStages([]);
    setLogs([]);
    setResults(null);
  }, []);

  // Global keyboard shortcuts
  React.useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

      // T - toggle theme
      if (e.key === 't' || e.key === 'T') {
        // Only handle if not in results view (results has its own handlers)
        if (view !== 'results') {
          e.preventDefault();
          toggleTheme();
        } else {
          // Let it through for theme only
          e.preventDefault();
          toggleTheme();
        }
      }

      // S - load sample (upload view only)
      if ((e.key === 's' || e.key === 'S') && view === 'upload' && files.length === 0) {
        e.preventDefault();
        handleLoadSample();
      }

      // Enter - start conversion (upload view with files)
      if (e.key === 'Enter' && view === 'upload' && files.length > 0) {
        e.preventDefault();
        startConversion();
      }

      // Escape - back to upload
      if (e.key === 'Escape' && view !== 'upload') {
        e.preventDefault();
        handleReset();
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [view, files, toggleTheme, startConversion, handleLoadSample, handleReset]);

  const viewLabels = [
    { id: 'upload', label: 'Upload' },
    { id: 'processing', label: 'Processing' },
    { id: 'results', label: 'Results' },
  ];

  const canNavigateTo = (viewId) => {
    if (viewId === 'upload') return true;
    if (viewId === 'processing') return view === 'processing';
    if (viewId === 'results') return results !== null;
    return false;
  };

  return (
    <div>
      {/* Header */}
      <header className="app-header">
        <div className="app-header__brand">
          <div className="app-header__logo">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M2 7l5-5 5 5-5 5z" fill="white" opacity="0.9"/>
            </svg>
          </div>
          <div>
            <div className="app-header__title">PDF to DITA</div>
            <div className="app-header__subtitle">BNY Data and Analytics Platform</div>
          </div>
        </div>

        <div className="app-header__nav">
          {/* Breadcrumb navigation */}
          <div className="breadcrumb">
            {viewLabels.map((v, i) => (
              <React.Fragment key={v.id}>
                {i > 0 && <span className="breadcrumb__sep">/</span>}
                <button
                  className={`breadcrumb__item ${view === v.id ? 'breadcrumb__item--active' : ''}`}
                  onClick={() => {
                    if (v.id === 'upload') handleReset();
                    else if (v.id === 'results' && results) setView('results');
                  }}
                  disabled={!canNavigateTo(v.id)}
                  style={{ opacity: canNavigateTo(v.id) ? 1 : 0.4 }}
                >
                  {v.label}
                </button>
              </React.Fragment>
            ))}
          </div>

          {/* Theme toggle */}
          <button className="theme-toggle" onClick={toggleTheme} title={`Switch to ${tweaks.theme === 'light' ? 'dark' : 'light'} mode (T)`}>
            {tweaks.theme === 'light' ? <IconMoon /> : <IconSun />}
          </button>
        </div>
      </header>

      {/* Main content */}
      <main className="view-container">
        {view === 'upload' && (
          <UploadView
            files={files}
            onFilesAdded={handleFilesAdded}
            onStartConversion={startConversion}
            onLoadSample={handleLoadSample}
          />
        )}

        {view === 'processing' && (
          <PipelineView
            stages={stages}
            logs={logs}
            onComplete={handlePipelineComplete}
          />
        )}

        {view === 'results' && results && (
          <ResultsView
            topics={results.topics}
            ditamap={results.ditamap}
            validation={results.validation}
          />
        )}
      </main>

      {/* Tweaks panel */}
      <TweaksPanel>
        <TweakSection title="Appearance">
          <TweakRadio
            label="Color theme"
            value={tweaks.theme}
            options={['light', 'dark']}
            onChange={(v) => setTweak('theme', v)}
          />
        </TweakSection>
      </TweaksPanel>
    </div>
  );
}

// Mount
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
