// mock-data.js — Cleanly separated mock data layer
// Replace MockAPI methods with real fetch() calls to connect to the backend

(function () {

const TOPICS = [
  {
    id: 'c_manage_2a7_processing',
    type: 'concept',
    title: 'Manage 2a-7 Processing',
    filename: 'c_manage_2a7_processing.dita',
    xml: `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE concept PUBLIC "-//OASIS//DTD DITA Concept//EN" "concept.dtd">
<concept id="c_manage_2a7_processing">
  <title>Manage 2a-7 Processing</title>
  <shortdesc>The 2a-7 processing module provides automated compliance
    monitoring and shadow NAV calculations for money market funds
    under SEC Rule 2a-7.</shortdesc>
  <prolog>
    <metadata>
      <keywords>
        <keyword>2a-7 processing</keyword>
        <keyword>money market fund</keyword>
        <keyword>compliance monitoring</keyword>
        <keyword>shadow NAV</keyword>
      </keywords>
    </metadata>
  </prolog>
  <conbody>
    <p><ph keyref="product-name"/> supports automated 2a-7 processing
      for money market funds. Portfolio managers can maintain compliance
      with SEC Rule 2a-7 through real-time monitoring and automated
      shadow NAV calculations.</p>
    <p>The system processes the following fund types:</p>
    <ul>
      <li><option>CNAV</option> - Constant Net Asset Value funds</li>
      <li><option>VNAV</option> - Variable Net Asset Value funds</li>
      <li><option>IMMM</option> - Institutional Money Market funds</li>
    </ul>
    <section>
      <title>Key capabilities</title>
      <p>Navigate to
        <menucascade>
          <uicontrol>Setup</uicontrol>
          <uicontrol>Portfolio Setup</uicontrol>
          <uicontrol>Mutual Funds</uicontrol>
        </menucascade> to configure fund parameters.</p>
      <p>The <wintitle>Fund Configuration</wintitle> panel displays
        current processing rules and deviation thresholds for each
        registered fund.</p>
    </section>
  </conbody>
</concept>`,
    html: `<article class="dita-preview"><h1>Manage 2a-7 Processing</h1><p class="shortdesc">The 2a-7 processing module provides automated compliance monitoring and shadow NAV calculations for money market funds under SEC Rule 2a-7.</p><p><em>Data Analytics Platform</em> supports automated 2a-7 processing for money market funds. Portfolio managers can maintain compliance with SEC Rule 2a-7 through real-time monitoring and automated shadow NAV calculations.</p><p>The system processes the following fund types:</p><ul><li><code>CNAV</code> - Constant Net Asset Value funds</li><li><code>VNAV</code> - Variable Net Asset Value funds</li><li><code>IMMM</code> - Institutional Money Market funds</li></ul><h2>Key capabilities</h2><p>Navigate to <span class="ui-path">Setup &gt; Portfolio Setup &gt; Mutual Funds</span> to configure fund parameters.</p><p>The <span class="wintitle">Fund Configuration</span> panel displays current processing rules and deviation thresholds for each registered fund.</p></article>`,
  },
  {
    id: 'c_2a7_workflow',
    type: 'concept',
    title: '2a-7 Workflow',
    filename: 'c_2a7_workflow.dita',
    xml: `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE concept PUBLIC "-//OASIS//DTD DITA Concept//EN" "concept.dtd">
<concept id="c_2a7_workflow">
  <title>2a-7 Workflow</title>
  <shortdesc>The 2a-7 workflow automates the end-to-end process from
    data ingestion through compliance reporting for money market
    fund portfolios.</shortdesc>
  <prolog>
    <metadata>
      <keywords>
        <keyword>workflow</keyword>
        <keyword>data ingestion</keyword>
        <keyword>compliance reporting</keyword>
      </keywords>
    </metadata>
  </prolog>
  <conbody>
    <p>The processing workflow consists of five sequential stages.
      Each stage validates its output before passing data to the
      next stage.</p>
    <ol>
      <li><b>Data ingestion</b> - Import portfolio holdings from
        upstream systems through the
        <wintitle>Data Import</wintitle> interface.</li>
      <li><b>Portfolio analysis</b> - Classify securities by maturity,
        credit quality, and liquidity tier.</li>
      <li><b>NAV calculation</b> - Compute mark-to-market and
        amortized cost NAV per share.</li>
      <li><b>Compliance check</b> - Evaluate portfolio against
        Rule 2a-7 concentration and maturity limits.</li>
      <li><b>Report generation</b> - Produce regulatory filings
        and internal dashboards.</li>
    </ol>
    <p>For configuration details, see
      <xref href="r_2a7_processing_settings.dita">2a-7 Processing
      Settings</xref>.</p>
    <fig>
      <title>2a-7 Processing Workflow</title>
      <image href="image_1.png">
        <alt>Diagram showing the five-stage 2a-7 processing
          workflow from data ingestion to report generation</alt>
      </image>
    </fig>
  </conbody>
</concept>`,
    html: `<article class="dita-preview"><h1>2a-7 Workflow</h1><p class="shortdesc">The 2a-7 workflow automates the end-to-end process from data ingestion through compliance reporting for money market fund portfolios.</p><p>The processing workflow consists of five sequential stages. Each stage validates its output before passing data to the next stage.</p><ol><li><strong>Data ingestion</strong> - Import portfolio holdings from upstream systems through the <span class="wintitle">Data Import</span> interface.</li><li><strong>Portfolio analysis</strong> - Classify securities by maturity, credit quality, and liquidity tier.</li><li><strong>NAV calculation</strong> - Compute mark-to-market and amortized cost NAV per share.</li><li><strong>Compliance check</strong> - Evaluate portfolio against Rule 2a-7 concentration and maturity limits.</li><li><strong>Report generation</strong> - Produce regulatory filings and internal dashboards.</li></ol><p>For configuration details, see <a href="#">2a-7 Processing Settings</a>.</p><figure><figcaption>2a-7 Processing Workflow</figcaption><div class="img-placeholder">[ workflow diagram ]</div></figure></article>`,
  },
  {
    id: 't_set_up_master_fund',
    type: 'task',
    title: 'Set Up Master Fund for 2a-7 Processing',
    filename: 't_set_up_master_fund.dita',
    xml: `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE task PUBLIC "-//OASIS//DTD DITA Task//EN" "task.dtd">
<task id="t_set_up_master_fund">
  <title>Set Up Master Fund for 2a-7 Processing</title>
  <shortdesc>Configure a master fund entity and assign 2a-7
    processing rules before the first NAV calculation
    cycle.</shortdesc>
  <prolog>
    <metadata>
      <keywords>
        <keyword>master fund</keyword>
        <keyword>fund setup</keyword>
        <keyword>2a-7 configuration</keyword>
      </keywords>
    </metadata>
  </prolog>
  <taskbody>
    <prereq>You must have the <uicontrol>Fund Administrator</uicontrol>
      role assigned in <ph keyref="product-name"/>. Verify that the
      fund's legal entity record exists in the
      <wintitle>Entity Manager</wintitle>.</prereq>
    <steps>
      <step>
        <cmd>Navigate to
          <menucascade>
            <uicontrol>Setup</uicontrol>
            <uicontrol>Portfolio Setup</uicontrol>
            <uicontrol>Mutual Funds</uicontrol>
          </menucascade>.</cmd>
        <stepresult>The <wintitle>Fund List</wintitle> panel
          opens.</stepresult>
      </step>
      <step>
        <cmd>Click <uicontrol>Create Master Fund</uicontrol>.</cmd>
        <info>If the button is disabled, confirm that your
          permissions include fund creation rights.</info>
      </step>
      <step>
        <cmd>Enter the fund name, CUSIP, and select the fund type
          (<option>CNAV</option>, <option>VNAV</option>, or
          <option>IMMM</option>).</cmd>
      </step>
      <step>
        <cmd>Set the deviation threshold to
          <userinput>0.0025</userinput> (25 basis points).</cmd>
        <stepxmp>For a CNAV fund with a target NAV of $1.00, the
          threshold triggers an alert when shadow NAV deviates by
          more than $0.0025.</stepxmp>
      </step>
      <step>
        <cmd>Click <uicontrol>Save</uicontrol>.</cmd>
        <stepresult>The fund appears in the
          <wintitle>Fund List</wintitle> with status
          <uicontrol>Active</uicontrol>.</stepresult>
      </step>
    </steps>
  </taskbody>
</task>`,
    html: `<article class="dita-preview"><h1>Set Up Master Fund for 2a-7 Processing</h1><p class="shortdesc">Configure a master fund entity and assign 2a-7 processing rules before the first NAV calculation cycle.</p><div class="prereq"><strong>Before you begin:</strong> You must have the <span class="ui-ctrl">Fund Administrator</span> role assigned in <em>Data Analytics Platform</em>. Verify that the fund's legal entity record exists in the <span class="wintitle">Entity Manager</span>.</div><ol class="steps"><li><p>Navigate to <span class="ui-path">Setup &gt; Portfolio Setup &gt; Mutual Funds</span>.</p><p class="step-result">The <span class="wintitle">Fund List</span> panel opens.</p></li><li><p>Click <span class="ui-ctrl">Create Master Fund</span>.</p><p class="step-info">If the button is disabled, confirm that your permissions include fund creation rights.</p></li><li><p>Enter the fund name, CUSIP, and select the fund type (<code>CNAV</code>, <code>VNAV</code>, or <code>IMMM</code>).</p></li><li><p>Set the deviation threshold to <kbd>0.0025</kbd> (25 basis points).</p></li><li><p>Click <span class="ui-ctrl">Save</span>.</p><p class="step-result">The fund appears in the <span class="wintitle">Fund List</span> with status <span class="ui-ctrl">Active</span>.</p></li></ol></article>`,
  },
  {
    id: 'r_2a7_processing_settings',
    type: 'reference',
    title: '2a-7 Processing Settings',
    filename: 'r_2a7_processing_settings.dita',
    xml: `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE reference PUBLIC "-//OASIS//DTD DITA Reference//EN" "reference.dtd">
<reference id="r_2a7_processing_settings">
  <title>2a-7 Processing Settings</title>
  <shortdesc>Reference guide for all configurable parameters in the
    2a-7 processing module, including calculation methods, pricing
    frequency, and compliance thresholds.</shortdesc>
  <prolog>
    <metadata>
      <keywords>
        <keyword>processing settings</keyword>
        <keyword>configuration</keyword>
        <keyword>thresholds</keyword>
        <keyword>compliance parameters</keyword>
      </keywords>
    </metadata>
  </prolog>
  <refbody>
    <table>
      <title>Processing configuration parameters</title>
      <tgroup cols="4">
        <colspec colname="setting" colwidth="1.2*"/>
        <colspec colname="type" colwidth="0.8*"/>
        <colspec colname="default" colwidth="0.8*"/>
        <colspec colname="description" colwidth="2*"/>
        <thead>
          <row>
            <entry>Setting</entry>
            <entry>Type</entry>
            <entry>Default</entry>
            <entry>Description</entry>
          </row>
        </thead>
        <tbody>
          <row>
            <entry>Calculation method</entry>
            <entry>Enum</entry>
            <entry>Amortized cost</entry>
            <entry>NAV calculation methodology:
              amortized cost or mark-to-market</entry>
          </row>
          <row>
            <entry>Pricing frequency</entry>
            <entry>Enum</entry>
            <entry>Daily</entry>
            <entry>How often the system recalculates NAV:
              daily, weekly, or on-demand</entry>
          </row>
          <row>
            <entry>Deviation threshold</entry>
            <entry>Decimal</entry>
            <entry>0.0025</entry>
            <entry>Maximum permitted deviation between
              shadow NAV and stable NAV (basis points)</entry>
          </row>
          <row>
            <entry>Maturity limit (days)</entry>
            <entry>Integer</entry>
            <entry>397</entry>
            <entry>Maximum weighted average maturity in
              calendar days per SEC Rule 2a-7</entry>
          </row>
          <row>
            <entry>Liquidity threshold</entry>
            <entry>Percentage</entry>
            <entry>10%</entry>
            <entry>Minimum daily liquid asset ratio
              required for compliance</entry>
          </row>
        </tbody>
      </tgroup>
    </table>
  </refbody>
</reference>`,
    html: `<article class="dita-preview"><h1>2a-7 Processing Settings</h1><p class="shortdesc">Reference guide for all configurable parameters in the 2a-7 processing module, including calculation methods, pricing frequency, and compliance thresholds.</p><table class="ref-table"><caption>Processing configuration parameters</caption><thead><tr><th>Setting</th><th>Type</th><th>Default</th><th>Description</th></tr></thead><tbody><tr><td>Calculation method</td><td>Enum</td><td>Amortized cost</td><td>NAV calculation methodology: amortized cost or mark-to-market</td></tr><tr><td>Pricing frequency</td><td>Enum</td><td>Daily</td><td>How often the system recalculates NAV: daily, weekly, or on-demand</td></tr><tr><td>Deviation threshold</td><td>Decimal</td><td>0.0025</td><td>Maximum permitted deviation between shadow NAV and stable NAV (basis points)</td></tr><tr><td>Maturity limit (days)</td><td>Integer</td><td>397</td><td>Maximum weighted average maturity in calendar days per SEC Rule 2a-7</td></tr><tr><td>Liquidity threshold</td><td>Percentage</td><td>10%</td><td>Minimum daily liquid asset ratio required for compliance</td></tr></tbody></table></article>`,
  },
];

const DITAMAP = {
  filename: 'm_manage_2a7_processing.ditamap',
  xml: `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE map PUBLIC "-//OASIS//DTD DITA Map//EN" "map.dtd">
<map id="m_manage_2a7_processing">
  <title>Manage 2a-7 Processing</title>
  <keydef keys="product-name">
    <topicmeta>
      <keywords>
        <keyword>Data Analytics Platform</keyword>
      </keywords>
    </topicmeta>
  </keydef>
  <topicref href="c_manage_2a7_processing.dita" type="concept"/>
  <topicref href="c_2a7_workflow.dita" type="concept"/>
  <topicref href="t_set_up_master_fund.dita" type="task"/>
  <topicref href="r_2a7_processing_settings.dita" type="reference"/>
</map>`,
};

const STAGES = [
  { id: 'ingest', name: 'Ingestion', detail: 'Extracting layout-tagged blocks via pdfplumber' },
  { id: 'normalize', name: 'Normalization', detail: 'Grouping blocks into hierarchical sections' },
  { id: 'detect', name: 'Structure Detection', detail: 'LLM planning topic types and boundaries' },
  { id: 'transform', name: 'Transformation', detail: 'Generating semantic DITA body XML' },
  { id: 'validate', name: 'Validation', detail: 'DITA-OT 4.3.1 HTML5 strict build' },
  { id: 'export', name: 'Export', detail: 'Writing .dita files and ditamap' },
];

const LOG_MESSAGES = [
  { stage: 'Ingestion', msg: 'Extracted 47 blocks from 4 pages (headings: 4, paragraphs: 18, lists: 6, tables: 1, images: 1)' },
  { stage: 'Normalization', msg: 'Grouped into 4 sections under 4 headings; deduplicated 1 running-header echo' },
  { stage: 'Structure Detection', msg: 'Planned 4 topics: concept x2, task x1, reference x1' },
  { stage: 'Transformation', msg: 'Classified 4/4 topics; semantic elements: uicontrol=10, option=5, wintitle=3, menucascade=1' },
  { stage: 'Validation', msg: 'DITA-OT HTML5 strict build: PASS (rc=0, 0 errors, 0 warnings)' },
  { stage: 'Export', msg: 'Wrote 4 .dita files + 1 .ditamap + 1 image (total: 6 artifacts)' },
];

const VALIDATION = {
  ditaot: { status: 'pass', label: 'DITA-OT HTML5 Strict', detail: 'rc=0, zero errors, zero warnings' },
  xmlWellformed: { status: 'pass', label: 'XML Well-formedness', detail: '4/4 files pass lxml check' },
  classAttr: { status: 'pass', label: '@class Coverage', detail: '114/114 elements (100%)' },
  contentModel: { status: 'pass', label: 'Content Model', detail: 'All nesting constraints satisfied' },
  metrics: {
    topicsGenerated: 4,
    totalElements: 114,
    classCoverage: '100%',
    processingTime: '2.4',
    model: 'gemini-2.5-pro',
    mode: 'LLM',
  },
  semantic: {
    uicontrol: 10, option: 5, wintitle: 3, menucascade: 1,
    codeblock: 1, shortdesc: 4, keyword: 12, xref: 2,
    image: 1, alt: 1, fig: 1, table: 1,
  },
  features: [
    { key: 'a', label: 'Topic-type detection', status: 'pass', detail: 'concept x2, task x1, reference x1' },
    { key: 'b', label: 'Document map', status: 'pass', detail: 'ditamap with keydef + 4 topicrefs' },
    { key: 'c', label: 'CALS tables', status: 'pass', detail: '1 table with colspec, thead, tbody' },
    { key: 'd', label: 'Best practices', status: 'pass', detail: 'No Latin abbreviations, no passive voice' },
    { key: 'e', label: 'Short descriptions', status: 'pass', detail: '4/4 topics have shortdesc' },
    { key: 'f', label: 'Product-name variable', status: 'pass', detail: 'keydef + ph keyref in 2 topics' },
    { key: 'g', label: 'Keywords', status: 'pass', detail: '3-4 keywords per topic in prolog' },
    { key: 'h', label: 'Hyperlinks', status: 'pass', detail: '2 xref elements (1 internal, 1 external)' },
    { key: 'i', label: 'Image optimization', status: 'pass', detail: '1 image, 847x412 px, 34 KB PNG' },
    { key: 'j', label: 'Alt text', status: 'pass', detail: '1/1 images have descriptive alt' },
    { key: 'k', label: 'Batch processing', status: 'pass', detail: 'batch.py + /batch endpoint available' },
  ],
};

const PDF_STRUCTURE = [
  { label: 'Page 1', type: 'page', children: [
    { label: 'Heading: "Manage 2a-7 Processing"', type: 'heading' },
    { label: 'Paragraph (3 blocks)', type: 'paragraph' },
    { label: 'Bulleted list (3 items)', type: 'list' },
  ]},
  { label: 'Page 2', type: 'page', children: [
    { label: 'Heading: "2a-7 Workflow"', type: 'heading' },
    { label: 'Paragraph (2 blocks)', type: 'paragraph' },
    { label: 'Numbered list (5 items)', type: 'list' },
    { label: 'Image: workflow diagram', type: 'image' },
  ]},
  { label: 'Page 3', type: 'page', children: [
    { label: 'Heading: "Set Up Master Fund..."', type: 'heading' },
    { label: 'Paragraph (1 block)', type: 'paragraph' },
    { label: 'Numbered list (5 steps)', type: 'list' },
  ]},
  { label: 'Page 4', type: 'page', children: [
    { label: 'Heading: "2a-7 Processing Settings"', type: 'heading' },
    { label: 'Paragraph (1 block)', type: 'paragraph' },
    { label: 'Table (5 rows x 4 cols)', type: 'table' },
  ]},
];

const DITA_STRUCTURE = [
  { label: 'm_manage_2a7_processing.ditamap', type: 'map', children: [
    { label: 'c_manage_2a7_processing.dita', type: 'concept', topicId: 'c_manage_2a7_processing' },
    { label: 'c_2a7_workflow.dita', type: 'concept', topicId: 'c_2a7_workflow' },
    { label: 't_set_up_master_fund.dita', type: 'task', topicId: 't_set_up_master_fund' },
    { label: 'r_2a7_processing_settings.dita', type: 'reference', topicId: 'r_2a7_processing_settings' },
  ]},
];

// --- Public API ---

window.MockAPI = {
  TOPICS,
  DITAMAP,
  STAGES,
  VALIDATION,
  PDF_STRUCTURE,
  DITA_STRUCTURE,

  getTopicById(id) {
    return TOPICS.find(t => t.id === id) || null;
  },

  getMockFile() {
    return { name: 'Manage 2a-7 Processing.pdf', size: 204800, pages: 4, status: 'ready' };
  },

  _BACKEND_STAGE_MAP: {
    'PDF parsing':       'ingest',
    'Section grouping':  'normalize',
    'Topic planning':    'detect',
    'DITA generation':   'transform',
    'File emission':     'export',
    'XML validation':    'validate',
  },

  async runPipeline(onStageUpdate, onLog, input) {
    // Mock fallback when called without a File (legacy demo path).
    if (!input) {
      return this._runMockPipeline(onStageUpdate, onLog);
    }

    const isBatch = Array.isArray(input);
    const files = isBatch ? input : [input];

    const stages = STAGES.map(s => ({ ...s, status: 'queued', time: null }));
    onStageUpdate([...stages]);

    // Backend does NOT stream stage updates - it sends them all at once
    // when /convert returns. We do two things while waiting:
    //   1. "ticker": every 200ms, recompute the active stage's elapsed
    //      seconds from a wall-clock timestamp so the user sees a live
    //      counter instead of "...".
    //   2. "advance": every ~1.8s, optimistically mark the active stage
    //      done (locking its time) and promote the next stage.
    // When the response arrives, real backend timings replace whatever
    // the optimistic clock guessed.
    let activeIdx = 0;
    stages[0].status = 'active';
    stages[0].time = 0;
    let activeStartedAt = Date.now();
    onStageUpdate(stages.map(s => ({ ...s })));

    if (onLog) onLog({ stage: 'System', msg: `Starting pipeline for ${files.length} file(s)...`, time: '-' });
    if (onLog) onLog({ stage: stages[0].name, msg: `Initializing ${stages[0].name.toLowerCase()}...`, time: '-' });

    const ticker = setInterval(() => {
      const elapsed = (Date.now() - activeStartedAt) / 1000;
      // Show one decimal so the counter visibly moves.
      stages[activeIdx].time = elapsed.toFixed(1);
      onStageUpdate(stages.map(s => ({ ...s })));
    }, 200);

    const advance = setInterval(() => {
      if (activeIdx < stages.length - 1) {
        // Lock the currently active stage's time at the wall-clock value
        // it had just before we advance.
        stages[activeIdx].status = 'done';
        stages[activeIdx].time = ((Date.now() - activeStartedAt) / 1000).toFixed(1);
        activeIdx += 1;
        stages[activeIdx].status = 'active';
        stages[activeIdx].time = 0;
        activeStartedAt = Date.now();
        onStageUpdate(stages.map(s => ({ ...s })));

        if (onLog) {
          onLog({
            stage: stages[activeIdx].name,
            msg: `Running ${stages[activeIdx].name.toLowerCase()}...`,
            time: '-'
          });
        }
      }
    }, 1800);

    let data;
    try {
      const form = new FormData();
      if (isBatch) {
        files.forEach(f => form.append('files', f));
        const resp = await fetch('/batch', { method: 'POST', body: form });
        data = await resp.json();
      } else {
        form.append('file', files[0]);
        const resp = await fetch('/convert', { method: 'POST', body: form });
        data = await resp.json();
      }
    } catch (e) {
      clearInterval(advance);
      clearInterval(ticker);
      stages[activeIdx].status = 'error';
      onStageUpdate(stages.map(s => ({ ...s })));
      throw e;
    }
    clearInterval(advance);
    clearInterval(ticker);

    if (data.error) {
      stages[activeIdx].status = 'error';
      onStageUpdate(stages.map(s => ({ ...s })));
      throw new Error(data.error);
    }

    // If batch, we might have multiple results. Return an array of adapted results.
    if (isBatch && data.results) {
      const allResults = data.results.filter(r => !r.error);
      if (allResults.length === 0 && data.results.length > 0) {
        throw new Error(data.results[0].error || 'Batch processing failed');
      }
      
      // Use the first result's stages for the UI
      this._updateStagesFromBackend(stages, allResults[0].stages, onStageUpdate, onLog);
      
      // Return array of adapted results
      return allResults.map(r => this._adaptBackendResponse(r));
    }

    this._updateStagesFromBackend(stages, data.stages, onStageUpdate, onLog);
    return this._adaptBackendResponse(data);
  },

  _updateStagesFromBackend(stages, backendStages, onStageUpdate, onLog) {
    if (Array.isArray(backendStages)) {
      const stageMap = this._BACKEND_STAGE_MAP;
      for (const bs of backendStages) {
        const uiId = stageMap[bs.name];
        if (!uiId) continue;
        const s = stages.find(x => x.id === uiId);
        if (s) {
          s.status = bs.status === 'done' ? 'done' : (bs.status === 'error' ? 'error' : 'active');
          s.time = bs.time != null ? String(bs.time) : s.time;
          if (onLog && bs.detail) {
            onLog({ stage: bs.name, msg: bs.detail, time: s.time });
          }
        }
      }
    }
    stages.forEach(s => {
      if (s.status !== 'error') s.status = 'done';
      // null/undefined/'...' means we never measured this stage -> show "-".
      // Numeric 0 is a valid (very fast) timing, keep it as-is.
      if (s.time == null || s.time === '...') s.time = '-';
    });
    onStageUpdate(stages.map(s => ({ ...s })));
  },

  async _runMockPipeline(onStageUpdate, onLog) {
    const stages = STAGES.map(s => ({ ...s, status: 'queued', time: null }));
    onStageUpdate([...stages]);
    await new Promise(r => setTimeout(r, 300));
    for (let i = 0; i < stages.length; i++) {
      stages[i].status = 'active';
      onStageUpdate(stages.map(s => ({ ...s })));
      const delay = 280 + Math.random() * 220;
      await new Promise(r => setTimeout(r, delay));
      stages[i].status = 'done';
      stages[i].time = (delay / 1000).toFixed(2);
      onStageUpdate(stages.map(s => ({ ...s })));
      if (onLog && LOG_MESSAGES[i]) {
        onLog({ ...LOG_MESSAGES[i], time: stages[i].time });
      }
    }
    return { topics: TOPICS, ditamap: DITAMAP, validation: VALIDATION };
  },

  // Friendly labels for the a-k requirements coming out of the backend.
  _FEATURE_LABELS: {
    a: 'Topic-type detection',
    b: 'Document map',
    c: 'CALS tables',
    d: 'Best practices',
    e: 'Short descriptions',
    f: 'Product-name variable',
    g: 'Keywords',
    h: 'Hyperlinks',
    i: 'Image optimization',
    j: 'Alt text',
    k: 'Batch processing',
  },

  _adaptBackendResponse(data) {
    const files = data.files || {};
    const sessionId = data.session_id;
    const m = data.metrics || {};
    const plan = data.plan || [];
    const fileNames = Object.keys(files);
    const ditamapName = fileNames.find(n => n.endsWith('.ditamap'));
    
    // Improved title logic: AI title > backend filename > ditamap name > fallback
    let doc_title = data.doc_title;
    if (!doc_title || doc_title === 'Untitled Document') {
      doc_title = data.filename || ditamapName || 'Untitled Document';
    }

    const topicNames = fileNames.filter(n => n !== ditamapName);

    const typeFromPrefix = (name) => {
      if (name.startsWith('c_')) return 'concept';
      if (name.startsWith('t_')) return 'task';
      if (name.startsWith('r_')) return 'reference';
      return 'concept';
    };
    const titleFor = (name) => {
      const stem = name.replace(/\.dita$/, '').replace(/^[ctr]_/, '');
      const guess = stem.replace(/_/g, ' ');
      const p = plan.find(p => {
        const slug = (p.title || '').toLowerCase()
          .replace(/[^a-z0-9\s_-]/g, '').replace(/[\s-]+/g, '_').replace(/^_+|_+$/g, '');
        return name.includes(slug.slice(0, 30));
      });
      return p ? p.title : guess.replace(/\b\w/g, c => c.toUpperCase());
    };

    // The backend exposes m.html5 (bool) and m.html5_url (relative path).
    // Older builds used dita_ot_passed/html5_available; honor both.
    const ditaOtBool = (m.html5 != null) ? !!m.html5 : m.dita_ot_passed;
    const html5Url = m.html5_url || ('/html5/' + sessionId + '/index.html');

    const topics = topicNames.map(name => ({
      id: name.replace(/\.dita$/, ''),
      type: typeFromPrefix(name),
      title: titleFor(name),
      filename: name,
      xml: files[name],
      html: ditaOtBool
        ? '<iframe class="dita-preview-frame" src="' + html5Url + '" sandbox="allow-same-origin" style="width:100%;height:540px;border:0;background:white;border-radius:8px"></iframe>'
        : '<div style="padding:20px;color:#888"><em>HTML5 preview unavailable: DITA-OT validation did not pass on this run.</em></div>',
      sessionId,
    }));

    const ditamap = ditamapName
      ? { filename: ditamapName, xml: files[ditamapName], sessionId }
      : { filename: 'unknown.ditamap', xml: '', sessionId };

    // Backend now computes semantic counts + features itself; just adapt the
    // shape. Features come as { a: {status, detail}, ... } -> array for UI.
    const semantic = m.semantic || {};
    const totalElems = Object.values(semantic).reduce((a, b) => a + (b || 0), 0);
    const featuresDict = m.features || {};
    const features = Object.keys(featuresDict).sort().map(key => ({
      key,
      label: this._FEATURE_LABELS[key] || key.toUpperCase(),
      status: featuresDict[key].status || 'pass',
      detail: featuresDict[key].detail || '',
    }));

    const ditaOt = ditaOtBool === true ? 'pass'
                 : ditaOtBool === false ? 'fail'
                 : 'warn';

    return {
      topics,
      ditamap,
      validation: {
        ditaot: { status: ditaOt, label: 'DITA-OT HTML5 Strict',
                  detail: ditaOtBool === true ? 'rc=0, zero errors'
                         : ditaOtBool === false ? 'build failed'
                         : 'validator not available' },
        xmlWellformed: { status: m.xml_valid === m.xml_total && m.xml_total > 0 ? 'pass' : 'fail',
                         label: 'XML Well-formedness',
                         detail: (m.xml_valid||0) + '/' + (m.xml_total||0) + ' files pass lxml' },
        classAttr: { status: 'pass', label: '@class Coverage', detail: m.class_coverage || '100%' },
        contentModel: { status: 'pass', label: 'Content Model', detail: 'All nesting constraints satisfied' },
        metrics: {
          topicsGenerated: m.topics_generated || topics.length,
          totalElements: totalElems,
          classCoverage: m.class_coverage || '100%',
          processingTime: m.processing_time != null ? String(m.processing_time) : '?',
          model: m.model || 'gemini',
          mode: m.mode || 'LLM',
        },
        semantic,
        features,
      },
      doc_title,
    };
  },

  _summarizeTypes(topics) {
    const c = topics.filter(t => t.type === 'concept').length;
    const t = topics.filter(t => t.type === 'task').length;
    const r = topics.filter(t => t.type === 'reference').length;
    const parts = [];
    if (c) parts.push('concept x' + c);
    if (t) parts.push('task x' + t);
    if (r) parts.push('reference x' + r);
    return parts.join(', ');
  },

  downloadFile(filename, content, sessionId) {
    // If session_id is known, hit the server's /file/{session}/{name}
    // endpoint - that route serves a human-readable Content-Disposition name.
    if (sessionId) {
      const a = document.createElement('a');
      a.href = '/file/' + sessionId + '/' + encodeURIComponent(filename);
      a.download = filename;
      a.click();
      return;
    }
    const blob = new Blob([content], { type: 'application/xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  },

  async downloadZip(sessionId) {
    // Prefer server-bundled zip (uses friendly filename derived from PDF).
    if (sessionId) {
      const a = document.createElement('a');
      a.href = '/zip/' + sessionId;
      a.download = 'dita.zip';
      a.click();
      return;
    }
    if (typeof JSZip === 'undefined') return;
    const zip = new JSZip();
    TOPICS.forEach(t => zip.file(t.filename, t.xml));
    zip.file(DITAMAP.filename, DITAMAP.xml);
    const blob = await zip.generateAsync({ type: 'blob' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'dita_output.zip'; a.click();
    URL.revokeObjectURL(url);
  },
};

})();
