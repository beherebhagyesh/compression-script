// --- DOM refs ---
const sourceInput      = document.getElementById('sourcePath');
const outputBaseInput  = document.getElementById('outputBasePath');
const outputFolderInput= document.getElementById('outputFolderName');
const scanBtn          = document.getElementById('scanBtn');
const convertBtn       = document.getElementById('convertBtn');
const resultsPanel     = document.getElementById('resultsPanel');
const logPanel         = document.getElementById('logPanel');
const resultsBody      = document.getElementById('resultsBody');
const summaryText      = document.getElementById('summaryText');
const resultsTitle     = document.getElementById('resultsTitle');
const statsGrid        = document.getElementById('statsGrid');
const logList          = document.getElementById('logList');
const scanHint         = document.getElementById('scanHint');
const modeGroup        = document.getElementById('modeGroup');
const presetGroup      = document.getElementById('presetGroup');
const outputFormatField= document.getElementById('outputFormatField');
const outputFormatSel  = document.getElementById('outputFormat');
const qualityRange     = document.getElementById('qualityRange');
const qualityInput     = document.getElementById('qualityInput');
const maxWidthInput    = document.getElementById('maxWidth');
const maxHeightInput   = document.getElementById('maxHeight');
const targetKbInput    = document.getElementById('targetKb');
const stripMetaChk     = document.getElementById('stripMeta');

// --- State ---
let currentImages  = [];
let outputRoot     = '';
let scanDone       = false;

// --- Mode/preset selection ---
let activeMode   = 'keep_format';
let activePreset = 'balanced';

const PRESET_DEFAULTS = {
  lossless:   { quality: 100, lossless: true,  max_width: null,  max_height: null },
  balanced:   { quality: 82,  lossless: false, max_width: 2000,  max_height: null },
  small_file: { quality: 68,  lossless: false, max_width: 1600,  max_height: null },
};

// Modes where the output format selector makes sense
const MODES_WITH_FORMAT = new Set(['convert_compress']);

// What extension does each mode produce for a given source ext?
function previewOutputExt(mode, sourceExt, outputFormat) {
  if (mode === 'keep_format') {
    return sourceExt === '.jpeg' ? '.jpg' : sourceExt;
  }
  if (mode === 'to_webp_lossy' || mode === 'to_webp_lossless') {
    return '.webp';
  }
  // convert_compress
  const fmt = (outputFormat || 'webp').toLowerCase();
  return '.' + (fmt === 'jpg' || fmt === 'jpeg' ? 'jpg' : fmt);
}

function updateModeUI() {
  document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.mode === activeMode);
  });
  // Show output format only for convert_compress
  outputFormatField.style.display = MODES_WITH_FORMAT.has(activeMode) ? '' : 'none';
  updateConvertBtnLabel();
  if (scanDone) refreshPreviewTable();
}

function updatePresetUI() {
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.preset === activePreset);
  });
  applyPresetToAdvanced(activePreset);
}

function applyPresetToAdvanced(preset) {
  const p = PRESET_DEFAULTS[preset];
  if (!p) return;
  qualityRange.value  = p.quality;
  qualityInput.value  = p.quality;
  maxWidthInput.value = p.max_width  || '';
  maxHeightInput.value= p.max_height || '';
}

function updateConvertBtnLabel() {
  const labels = {
    keep_format:      'Compress Images',
    to_webp_lossy:    'Convert to WebP',
    to_webp_lossless: 'Convert to WebP (Lossless)',
    convert_compress: 'Convert & Compress',
  };
  convertBtn.textContent = labels[activeMode] || 'Convert';
}

modeGroup.addEventListener('click', e => {
  const btn = e.target.closest('.mode-btn');
  if (!btn) return;
  activeMode = btn.dataset.mode;
  updateModeUI();
});

presetGroup.addEventListener('click', e => {
  const btn = e.target.closest('.preset-btn');
  if (!btn) return;
  activePreset = btn.dataset.preset;
  updatePresetUI();
});

// Quality slider ↔ number input sync
qualityRange.addEventListener('input', () => { qualityInput.value = qualityRange.value; });
qualityInput.addEventListener('input', () => {
  const v = Math.min(100, Math.max(1, parseInt(qualityInput.value) || 82));
  qualityRange.value = v;
  qualityInput.value = v;
});

// Output format change refreshes preview table
outputFormatSel.addEventListener('change', () => { if (scanDone) refreshPreviewTable(); });

// --- Helpers ---
function fmt(label) { return label.replace(/^\./, '').toUpperCase(); }
function kb(bytes) { return bytes ? (bytes / 1024).toFixed(1) + ' KB' : '—'; }
function pct(val) {
  if (val > 0)  return `<span class="saved-positive">▼ ${val}%</span>`;
  if (val < 0)  return `<span class="saved-negative">▲ ${Math.abs(val)}%</span>`;
  return '0%';
}

function setButtonState(button, busy, busyLabel) {
  button.disabled = busy;
  if (busy) button.dataset.idleLabel = button.textContent;
  button.textContent = busy ? busyLabel : (button.dataset.idleLabel || button.textContent);
}

function addLog(message, isError = false) {
  logPanel.classList.remove('hidden');
  const li = document.createElement('li');
  li.textContent = message;
  if (isError) li.classList.add('error');
  logList.appendChild(li);
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.error || 'Request failed');
  return data;
}

function renderStats(counts = {}) {
  statsGrid.classList.remove('hidden');
  statsGrid.innerHTML = `
    <article class="stat-card">
      <span>Images found</span>
      <strong>${counts.total_images ?? 0}</strong>
    </article>
  `;
}

// --- Preview table (before conversion) ---
function refreshPreviewTable() {
  const outputExt = previewOutputExt(activeMode, '', outputFormatSel.value);
  resultsBody.innerHTML = currentImages.map(item => {
    const outExt = previewOutputExt(activeMode, item.source_ext, outputFormatSel.value);
    return `
      <tr>
        <td><code>${item.relative}</code></td>
        <td><span class="badge">${fmt(item.source_ext)}</span></td>
        <td><span class="badge badge-out">${fmt(outExt)}</span></td>
        <td class="hidden"></td>
        <td class="hidden"></td>
        <td class="hidden"></td>
        <td class="hidden"></td>
      </tr>`;
  }).join('');
}

// --- Results table (after conversion) ---
function showPostConvertTable(results) {
  // Reveal extra columns
  ['colSizeIn','colSizeOut','colReduction','colStatus'].forEach(id => {
    document.getElementById(id).classList.remove('hidden');
  });

  resultsBody.innerHTML = results.map(r => {
    const statusCell = r.status === 'ok'
      ? `<span class="status-ok">✓</span>`
      : `<span class="status-err" title="${r.error || ''}">✗ ${r.error || 'Error'}</span>`;
    const warningTags = (r.warnings || []).map(w =>
      `<span class="warning-tag" title="${w}">⚠</span>`
    ).join(' ');

    return `
      <tr class="${r.status !== 'ok' ? 'row-error' : ''}">
        <td><code>${Path.basename(r.source)}</code>${warningTags ? ' ' + warningTags : ''}</td>
        <td><span class="badge">${fmt(r.source_ext)}</span></td>
        <td><span class="badge badge-out">${fmt(r.output_ext)}</span></td>
        <td>${kb(r.bytes_in)}</td>
        <td>${kb(r.bytes_out)}</td>
        <td>${pct(r.reduction_pct)}</td>
        <td>${statusCell}</td>
      </tr>`;
  }).join('');
}

// Tiny helper — Path.basename equivalent in browser
const Path = { basename: s => (s || '').replace(/\\/g, '/').split('/').pop() };

// --- Scan ---
scanBtn.addEventListener('click', async () => {
  const sourcePath      = sourceInput.value.trim();
  const outputBasePath  = outputBaseInput.value.trim();
  const outputFolderName= outputFolderInput.value.trim();

  if (!sourcePath || !outputBasePath || !outputFolderName) {
    addLog('Fill in source path, output base path, and output folder name first.', true);
    return;
  }

  try {
    setButtonState(scanBtn, true, 'Scanning…');
    resultsPanel.classList.add('hidden');
    statsGrid.classList.add('hidden');
    // Reset post-convert columns
    ['colSizeIn','colSizeOut','colReduction','colStatus'].forEach(id => {
      document.getElementById(id).classList.add('hidden');
    });

    const data = await postJson('/api/scan', { sourcePath, outputBasePath, outputFolderName });
    currentImages = data.images || [];
    outputRoot    = data.output_root;
    scanDone      = true;

    renderStats(data.counts);
    summaryText.textContent = `${currentImages.length} image(s) found in ${data.working_folder}`;
    resultsTitle.textContent = 'Discovered Images — Preview';
    refreshPreviewTable();
    resultsPanel.classList.remove('hidden');
    convertBtn.disabled = currentImages.length === 0;
    addLog(`Scan complete: ${currentImages.length} image(s) found. Output → ${data.output_root}`);
  } catch (err) {
    addLog(`Scan failed: ${err.message}`, true);
    renderStats();
  } finally {
    setButtonState(scanBtn, false);
  }
});

// --- Convert ---
convertBtn.addEventListener('click', async () => {
  if (!currentImages.length) {
    addLog('No images to convert. Scan first.', true);
    return;
  }

  const busyLabel = convertBtn.textContent + '…';
  try {
    setButtonState(convertBtn, true, busyLabel);
    setButtonState(scanBtn, true, 'Please wait…');

    const data = await postJson('/api/convert', {
      images:       currentImages,
      outputRoot,
      mode:         activeMode,
      preset:       activePreset,
      outputFormat: outputFormatSel.value,
      quality:      parseInt(qualityInput.value) || null,
      max_width:    parseInt(maxWidthInput.value)  || null,
      max_height:   parseInt(maxHeightInput.value) || null,
      target_kb:    parseInt(targetKbInput.value)  || null,
      strip_metadata: stripMetaChk.checked,
    });

    resultsTitle.textContent = 'Conversion Results';
    showPostConvertTable(data.results);

    const ok  = data.results.filter(r => r.status === 'ok').length;
    const err = data.results.length - ok;
    const totalIn  = data.results.reduce((s, r) => s + r.bytes_in, 0);
    const totalOut = data.results.reduce((s, r) => s + r.bytes_out, 0);
    const overallPct = totalIn ? ((1 - totalOut / totalIn) * 100).toFixed(1) : 0;

    summaryText.textContent = `${ok} converted${err ? `, ${err} failed` : ''} — ${kb(totalIn)} → ${kb(totalOut)} (${overallPct}% reduction)`;
    addLog(`Done. ${ok} converted, ${err} failed. Total saved: ${overallPct}%.`);

    // Log warnings
    data.results.forEach(r => {
      (r.warnings || []).forEach(w => addLog(`⚠ ${Path.basename(r.source)}: ${w}`));
    });

  } catch (err) {
    addLog(`Conversion failed: ${err.message}`, true);
  } finally {
    setButtonState(convertBtn, false);
    setButtonState(scanBtn, false);
  }
});

// --- Init ---
updateModeUI();
updatePresetUI();
