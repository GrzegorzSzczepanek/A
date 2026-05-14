// shared-ui.jsx — Shared UI primitives

const { useState, useEffect, useRef, useMemo, useCallback } = React;

// ===== TYPE BADGE =====
function TypeBadge({ type, size = 'sm' }) {
  const labels = { concept: 'Concept', task: 'Task', reference: 'Reference', map: 'Map' };
  return (
    <span className={`type-badge type-badge--${type}`}>
      <span className={`type-dot type-dot--${type}`}></span>
      {labels[type] || type}
    </span>
  );
}

// ===== STATUS DOT =====
function StatusDot({ status }) {
  return <span className={`status-dot status-dot--${status}`}></span>;
}

// ===== CODE BLOCK with line numbers =====
function CodeBlock({ code, language = 'xml', filename }) {
  const highlighted = useMemo(() => {
    if (!code) return '';
    try {
      return hljs.highlight(code.trim(), { language }).value;
    } catch {
      return code.trim().replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
  }, [code, language]);

  const lines = highlighted.split('\n');

  return (
    <div className="code-preview__body">
      <div className="code-lines">
        {lines.map((line, i) => (
          <div className="code-line" key={i}>
            <span className="code-gutter">{i + 1}</span>
            <span className="code-content" dangerouslySetInnerHTML={{ __html: line || ' ' }}></span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ===== SVG ICONS =====
function IconDoc() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M5 2h6l4 4v10a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z"/>
      <path d="M11 2v4h4"/>
    </svg>
  );
}

function IconUpload() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M3 14v2a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-2"/>
      <path d="M10 12V3"/>
      <path d="M6 7l4-4 4 4"/>
    </svg>
  );
}

function IconCheck() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 7l3 3 5-5"/>
    </svg>
  );
}

function IconChevron({ dir = 'right' }) {
  const rotation = { right: 0, down: 90, left: 180, up: 270 };
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5"
      style={{ transform: `rotate(${rotation[dir]}deg)`, transition: 'transform 0.2s' }}>
      <path d="M4.5 2.5l3.5 3.5-3.5 3.5"/>
    </svg>
  );
}

function IconDownload() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M2 10v2h10v-2"/>
      <path d="M7 2v7"/>
      <path d="M4 7l3 3 3-3"/>
    </svg>
  );
}

function IconCompare() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="1" y="1" width="5" height="12" rx="1"/>
      <rect x="8" y="1" width="5" height="12" rx="1"/>
    </svg>
  );
}

function IconX() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M3 3l8 8M11 3l-8 8"/>
    </svg>
  );
}

function IconSun() {
  return (
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" strokeWidth="1.3">
      <circle cx="7.5" cy="7.5" r="3"/>
      <path d="M7.5 1v2M7.5 12v2M1 7.5h2M12 7.5h2M3.1 3.1l1.4 1.4M10.5 10.5l1.4 1.4M3.1 11.9l1.4-1.4M10.5 4.5l1.4-1.4"/>
    </svg>
  );
}

function IconMoon() {
  return (
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" strokeWidth="1.3">
      <path d="M13 8.5a5.5 5.5 0 1 1-6.5-6.5 4.5 4.5 0 0 0 6.5 6.5z"/>
    </svg>
  );
}

function IconTree() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.3">
      <path d="M2 2h4v3H2zM8 5h4v3H8zM8 10h4v3H8zM6 3.5h2v3M8 6.5v5"/>
    </svg>
  );
}

// ===== STAGE ICONS =====
function StageIcon({ stageId, size = 14 }) {
  const icons = {
    ingest: <svg width={size} height={size} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4"><path d="M4 1h4l3 3v8a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1z"/><path d="M8 1v3h3"/></svg>,
    normalize: <svg width={size} height={size} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4"><rect x="2" y="2" width="10" height="3" rx="0.5"/><rect x="2" y="7" width="10" height="2" rx="0.5"/><rect x="2" y="11" width="6" height="2" rx="0.5"/></svg>,
    detect: <svg width={size} height={size} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4"><circle cx="7" cy="5" r="3"/><path d="M4 10l1-2M10 10l-1-2M7 8v3"/></svg>,
    transform: <svg width={size} height={size} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4"><path d="M3 3l2 4-2 4M11 3l-2 4 2 4M6 12l2-10"/></svg>,
    validate: <svg width={size} height={size} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4"><path d="M7 1l6 3v4c0 3-2.5 4.5-6 6-3.5-1.5-6-3-6-6V4z"/><path d="M5 7l2 2 3-3"/></svg>,
    export: <svg width={size} height={size} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4"><path d="M2 9v3h10V9"/><path d="M7 2v7"/><path d="M4 7l3 3 3-3"/></svg>,
  };
  return icons[stageId] || null;
}

// ===== KEYBOARD HINT =====
function Kbd({ children }) {
  return <span className="kbd">{children}</span>;
}

// ===== FORMAT FILE SIZE =====
function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

// Export to window
Object.assign(window, {
  TypeBadge, StatusDot, CodeBlock,
  IconDoc, IconUpload, IconCheck, IconChevron, IconDownload, IconCompare, IconX, IconSun, IconMoon, IconTree,
  StageIcon, Kbd, formatSize,
});
