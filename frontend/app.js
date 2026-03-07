const folderInput = document.getElementById('folderPath');
const scanBtn = document.getElementById('scanBtn');
const convertBtn = document.getElementById('convertBtn');
const resultsPanel = document.getElementById('resultsPanel');
const logPanel = document.getElementById('logPanel');
const resultsBody = document.getElementById('resultsBody');
const summaryText = document.getElementById('summaryText');
const statsGrid = document.getElementById('statsGrid');
const logList = document.getElementById('logList');

let currentImages = [];

function setButtonState(button, busy, busyLabel, idleLabel) {
  button.disabled = busy;
  button.textContent = busy ? busyLabel : idleLabel;
}

function renderStats(counts = {}) {
  const cards = [
    ['Direct images', counts.direct_images ?? 0],
    ['CSV referenced', counts.csv_referenced_images ?? 0],
    ['Total unique', counts.total_unique_images ?? 0],
  ];
  statsGrid.innerHTML = cards.map(([label, value]) => `
    <article class="stat-card">
      <span>${label}</span>
      <strong>${value}</strong>
    </article>
  `).join('');
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
  if (!response.ok || !data.ok) {
    throw new Error(data.error || 'Request failed');
  }
  return data;
}

scanBtn.addEventListener('click', async () => {
  const folderPath = folderInput.value.trim();
  if (!folderPath) {
    addLog('Enter a folder path first.', true);
    return;
  }

  try {
    setButtonState(scanBtn, true, 'Scanning...', 'Scan Folder');
    resultsPanel.classList.add('hidden');
    const data = await postJson('/api/scan', { folderPath });
    currentImages = data.images || [];
    renderStats(data.counts);
    summaryText.textContent = `${currentImages.length} unique image(s) discovered under ${data.folder}`;
    resultsBody.innerHTML = currentImages.map((item) => `
      <tr>
        <td><code>${item.source}</code></td>
        <td><code>${item.output}</code></td>
      </tr>
    `).join('');
    resultsPanel.classList.remove('hidden');
    addLog(`Scan complete: ${currentImages.length} image(s) queued from ${data.folder}`);
  } catch (error) {
    addLog(`Scan failed: ${error.message}`, true);
    renderStats();
  } finally {
    setButtonState(scanBtn, false, 'Scanning...', 'Scan Folder');
  }
});

convertBtn.addEventListener('click', async () => {
  if (!currentImages.length) {
    addLog('There are no images to convert.', true);
    return;
  }

  try {
    setButtonState(convertBtn, true, 'Converting...', 'Convert All To Lossless WebP');
    const data = await postJson('/api/convert', { images: currentImages });
    data.converted.forEach((item) => {
      addLog(`Created ${item.output} (${item.bytes.toLocaleString()} bytes)`);
    });
    addLog(`Finished converting ${data.count} image(s).`);
  } catch (error) {
    addLog(`Conversion failed: ${error.message}`, true);
  } finally {
    setButtonState(convertBtn, false, 'Converting...', 'Convert All To Lossless WebP');
  }
});

renderStats();
