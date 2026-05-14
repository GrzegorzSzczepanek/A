// results-view.jsx — Results explorer, validation, export, comparison

// ===== PROJECT EXPLORER (left panel) =====
function ProjectExplorer({ results, selectedIdx, onSelectResult, selectedTopicId, onSelectTopic }) {
  const [search, setSearch] = React.useState('');

  const filteredResults = React.useMemo(() => {
    if (!search) return results;
    return results.filter(r => 
      (r.doc_title || '').toLowerCase().includes(search.toLowerCase()) ||
      r.topics.some(t => t.filename.toLowerCase().includes(search.toLowerCase()))
    );
  }, [results, search]);

  return (
    <div className="card project-explorer">
      <div className="search-container">
        <input
          type="text"
          className="search-input"
          placeholder="Search docs or topics..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {filteredResults.map((result, resIdx) => {
          // Find original index in results array for selection
          const originalIdx = results.indexOf(result);
          const isActive = selectedIdx === originalIdx;
          
          return (
            <div key={originalIdx} className={`doc-node ${isActive ? 'doc-node--active' : ''}`}>
              <div className="doc-node__header" onClick={() => onSelectResult(originalIdx)}>
                <IconChevron dir={isActive ? 'down' : 'right'} />
                <IconDoc />
                <span className="doc-node__title" title={result.doc_title}>
                  {result.doc_title || result.ditamap?.filename || 'Untitled Document'}
                </span>
              </div>
              
              {isActive && (
                <div className="doc-node__content">
                  <div className="tree-children">
                    {/* Map node */}
                    <div
                      className={`tree-node ${selectedTopicId === '__map' ? 'tree-node--selected' : ''}`}
                      onClick={(e) => { e.stopPropagation(); onSelectTopic('__map'); }}
                    >
                      <IconTree />
                      <span className="tree-node__label" style={{ fontWeight: 500, fontSize: 11 }}>
                        {result.ditamap.filename}
                      </span>
                    </div>

                    {/* Topic nodes */}
                    {result.topics.map(topic => (
                      <div
                        key={topic.id}
                        className={`tree-node ${selectedTopicId === topic.id ? 'tree-node--selected' : ''}`}
                        onClick={(e) => { e.stopPropagation(); onSelectTopic(topic.id); }}
                      >
                        <span className={`type-dot type-dot--${topic.type}`}></span>
                        <span className="tree-node__label" title={topic.title} style={{ fontSize: 11 }}>
                          {topic.filename}
                        </span>
                      </div>
                    ))}
                  </div>
                  
                  {/* Local Export inside accordion */}
                  <div style={{ padding: '8px 12px 4px' }}>
                    <button className="btn btn--sm btn--ghost" style={{ width: '100%', fontSize: 10 }}
                      onClick={(e) => { e.stopPropagation(); MockAPI.downloadZip(result.ditamap.sessionId); }}>
                      <IconDownload /> Download ZIP
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ===== PREVIEW PANE (center) =====
function PreviewPane({ topic, ditamap, selectedId, previewMode, onModeChange }) {
  const isMap = selectedId === '__map';
  const currentXml = isMap ? ditamap.xml : (topic?.xml || '');
  const currentHtml = topic?.html || '';
  const currentFilename = isMap ? ditamap.filename : (topic?.filename || '');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, height: '100%' }}>
      {/* File header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: 8,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 500 }}>
            {currentFilename}
          </span>
          {topic && !isMap && <TypeBadge type={topic.type} />}
        </div>
        {!isMap && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', marginRight: 4 }}>
              <Kbd>X</Kbd> / <Kbd>H</Kbd>
            </span>
            <button
              className={`btn btn--sm ${previewMode === 'xml' ? 'btn--primary' : ''}`}
              onClick={() => onModeChange('xml')}
            >XML</button>
            <button
              className={`btn btn--sm ${previewMode === 'html' ? 'btn--primary' : ''}`}
              onClick={() => onModeChange('html')}
            >HTML5</button>
          </div>
        )}
      </div>

      {/* Content */}
      {(previewMode === 'xml' || isMap) ? (
        <div className="code-preview" style={{ flex: 1 }}>
          <CodeBlock code={currentXml} language="xml" />
        </div>
      ) : (
        <div className="html-preview" style={{ flex: 1 }}
          dangerouslySetInnerHTML={{ __html: currentHtml }}>
        </div>
      )}
    </div>
  );
}

// ===== VALIDATION PANEL (right) =====
function ValidationPanel({ validation, onShowComparison }) {
  const v = validation;
  const checks = [v.ditaot, v.xmlWellformed, v.classAttr, v.contentModel];

  return (
    <div className="card" style={{ padding: 12, height: '100%', overflow: 'auto' }}>
      {/* Overall status */}
      <div style={{
        textAlign: 'center', padding: '12px 0 16px',
        borderBottom: '1px solid var(--border-light)',
        marginBottom: 12,
      }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          background: 'var(--success-bg)', color: 'var(--success)',
          padding: '6px 14px', borderRadius: 7,
          fontSize: 13, fontWeight: 700,
          fontFamily: 'var(--font-heading)',
        }}>
          <StatusDot status="done" />
          ALL CHECKS PASS
        </div>
      </div>

      {/* Checks */}
      <div className="section-label">Validation Checks</div>
      {checks.map((c, i) => (
        <div className="val-item" key={i}>
          <StatusDot status={c.status} />
          <div>
            <div className="val-label">{c.label}</div>
            <div className="val-detail">{c.detail}</div>
          </div>
        </div>
      ))}

      <div className="divider"></div>

      {/* Metrics */}
      <div className="section-label">Metrics</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 12 }}>
        <div className="metric-card">
          <div className="metric-card__label">Topics</div>
          <div className="metric-card__value">{v.metrics.topicsGenerated}</div>
        </div>
        <div className="metric-card">
          <div className="metric-card__label">Elements</div>
          <div className="metric-card__value">{v.metrics.totalElements}</div>
        </div>
        <div className="metric-card">
          <div className="metric-card__label">@class</div>
          <div className="metric-card__value metric-card__value--pass">{v.metrics.classCoverage}</div>
        </div>
        <div className="metric-card">
          <div className="metric-card__label">Time</div>
          <div className="metric-card__value">{v.metrics.processingTime}s</div>
        </div>
      </div>

      <div className="divider"></div>

      {/* Semantic richness */}
      <div className="section-label">Semantic Elements</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {Object.entries(v.semantic).map(([key, count]) => (
          <span className="sem-tag" key={key}>
            {key} <span className="sem-tag__count">x{count}</span>
          </span>
        ))}
      </div>

      <div className="divider"></div>

      {/* Requirements */}
      <div className="section-label">Requirements (a-k)</div>
      <div style={{ fontSize: 12 }}>
        {v.features.map(f => (
          <div key={f.key} style={{
            display: 'flex', alignItems: 'flex-start', gap: 6,
            padding: '4px 0',
          }}>
            <StatusDot status={f.status} />
            <div>
              <span style={{ fontWeight: 500, color: 'var(--text)' }}>{f.key}.</span>{' '}
              <span style={{ color: 'var(--text-secondary)' }}>{f.label}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="divider"></div>

      {/* Comparison button */}
      <button className="btn btn--sm" style={{ width: '100%', justifyContent: 'center' }}
        onClick={onShowComparison}>
        <IconCompare /> PDF vs DITA <Kbd>B</Kbd>
      </button>
    </div>
  );
}

// ===== COMPARISON OVERLAY =====
function ComparisonOverlay({ onClose }) {
  const pdfStruct = MockAPI.PDF_STRUCTURE;
  const ditaStruct = MockAPI.DITA_STRUCTURE;

  React.useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const typeColors = {
    heading: 'var(--primary)',
    paragraph: 'var(--text-muted)',
    list: 'var(--text-secondary)',
    table: 'var(--ref-color)',
    image: 'var(--concept-color)',
    page: 'var(--text-secondary)',
    concept: 'var(--concept-color)',
    task: 'var(--task-color)',
    reference: 'var(--ref-color)',
    map: 'var(--primary)',
  };

  const renderNode = (node, i) => (
    <div key={i}>
      <div className="struct-node">
        <span style={{
          width: 6, height: 6, borderRadius: '50%',
          background: typeColors[node.type] || 'var(--text-muted)',
          flexShrink: 0,
        }}></span>
        <span style={{ flex: 1, fontSize: 12 }}>{node.label}</span>
        {node.topicId && <TypeBadge type={node.type} />}
      </div>
      {node.children && (
        <div className="struct-children">
          {node.children.map((c, j) => renderNode(c, j))}
        </div>
      )}
    </div>
  );

  return (
    <div className="comparison-overlay" onClick={onClose}>
      <div className="comparison-panel" onClick={e => e.stopPropagation()}>
        <div className="comparison-header">
          <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: 15, fontWeight: 600 }}>
            Structure Comparison
          </h3>
          <button className="btn btn--sm btn--ghost" onClick={onClose}>
            <IconX /> Close <Kbd>Esc</Kbd>
          </button>
        </div>
        <div className="comparison-body">
          <div className="comparison-col">
            <div className="comparison-col__title">Source PDF Structure</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
              Manage 2a-7 Processing.pdf - 4 pages
            </div>
            {pdfStruct.map((node, i) => renderNode(node, i))}
          </div>
          <div className="comparison-col">
            <div className="comparison-col__title">DITA Output Structure</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
              4 typed topics + ditamap
            </div>
            {ditaStruct.map((node, i) => renderNode(node, i))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ===== RESULTS VIEW (compositor) =====
function ResultsView({ results, selectedIdx, onSelectResult }) {
  const currentResult = results[selectedIdx] || results[0];
  const { topics, ditamap, validation, doc_title } = currentResult;
  
  const [selectedId, setSelectedId] = React.useState(topics[0]?.id || null);
  const [previewMode, setPreviewMode] = React.useState('xml');
  const [showComparison, setShowComparison] = React.useState(false);

  // Update selection when current result changes
  React.useEffect(() => {
    setSelectedId(topics[0]?.id || null);
  }, [selectedIdx, topics]);

  const selectedTopic = topics.find(t => t.id === selectedId) || null;
  const isMap = selectedId === '__map';

  // Keyboard: X/H to switch mode, B for comparison, up/down to nav topics
  React.useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.key === 'x' || e.key === 'X') { e.preventDefault(); setPreviewMode('xml'); }
      if (e.key === 'h' || e.key === 'H') { e.preventDefault(); setPreviewMode('html'); }
      if (e.key === 'b' || e.key === 'B') { e.preventDefault(); setShowComparison(v => !v); }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        const allIds = ['__map', ...topics.map(t => t.id)];
        const idx = allIds.indexOf(selectedId);
        if (e.key === 'ArrowDown' && idx < allIds.length - 1) setSelectedId(allIds[idx + 1]);
        if (e.key === 'ArrowUp' && idx > 0) setSelectedId(allIds[idx - 1]);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [selectedId, topics]);

  return (
    <div className="view-enter">
      {/* Summary bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: 16, flexWrap: 'wrap', gap: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: 18, fontWeight: 700, letterSpacing: '-0.02em' }}>
            Output Explorer
          </h2>

          <div style={{ display: 'flex', gap: 6 }}>
            {['concept', 'task', 'reference'].map(type => {
              const count = topics.filter(t => t.type === type).length;
              if (!count) return null;
              return <TypeBadge key={type} type={type} />;
            })}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-muted)' }}>
          <Kbd>↑</Kbd><Kbd>↓</Kbd> navigate
          <span style={{ margin: '0 4px' }}>-</span>
          <Kbd>X</Kbd>/<Kbd>H</Kbd> toggle view
          <span style={{ margin: '0 4px' }}>-</span>
          <Kbd>B</Kbd> compare
        </div>
      </div>

      {/* Three-column grid */}
      <div className="results-grid">
        <ProjectExplorer
          results={results}
          selectedIdx={selectedIdx}
          onSelectResult={onSelectResult}
          selectedTopicId={selectedId}
          onSelectTopic={setSelectedId}
        />
        <PreviewPane
          topic={selectedTopic}
          ditamap={ditamap}
          selectedId={selectedId}
          previewMode={previewMode}
          onModeChange={setPreviewMode}
        />
        <ValidationPanel
          validation={validation}
          onShowComparison={() => setShowComparison(true)}
        />
      </div>

      {showComparison && <ComparisonOverlay onClose={() => setShowComparison(false)} />}
    </div>
  );
}

Object.assign(window, { ResultsView, TopicTree, PreviewPane, ValidationPanel, ComparisonOverlay });
