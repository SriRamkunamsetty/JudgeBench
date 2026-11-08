let pairsData = [];
let currentReport = null;
let selectedPairId = null;

const btnLoadSample = document.getElementById('btn-load-sample');
const btnCalibrate = document.getElementById('btn-calibrate');
const btnExportMd = document.getElementById('btn-export-md');
const filterDisagreements = document.getElementById('filter-disagreements');
const tableBody = document.getElementById('pairs-table-body');
const pairCountSpan = document.getElementById('pair-count');

// Inspector DOM
const inspectorEmpty = document.getElementById('inspector-empty');
const inspectorBody = document.getElementById('inspector-body');
const inspectorBadge = document.getElementById('inspector-badge');
const inspectorPrompt = document.getElementById('inspector-prompt');
const inspectorResponse = document.getElementById('inspector-response');
const inspectorHumanScore = document.getElementById('inspector-human-score');
const inspectorHumanRationale = document.getElementById('inspector-human-rationale');
const inspectorAiScore = document.getElementById('inspector-ai-score');
const inspectorAiRationale = document.getElementById('inspector-ai-rationale');
const inspectorCriterion = document.getElementById('inspector-criterion');
const inspectorModel = document.getElementById('inspector-model');
const inspectorLength = document.getElementById('inspector-length');
const inspectorDelta = document.getElementById('inspector-delta');

// KPI DOM
const kpiPearson = document.getElementById('kpi-pearson');
const kpiKappa = document.getElementById('kpi-kappa');
const kpiMae = document.getElementById('kpi-mae');
const kpiVerbosity = document.getElementById('kpi-verbosity');
const biasLeniency = document.getElementById('bias-leniency');
const biasDisagreements = document.getElementById('bias-disagreements');
const biasStatus = document.getElementById('bias-status');

btnLoadSample.addEventListener('click', async () => {
  try {
    const res = await fetch('/api/benchmark-dataset');
    if (!res.ok) throw new Error('Failed to load dataset');
    const data = await res.json();
    pairsData = data.items || [];
    renderTable();
    await runCalibration();
  } catch (err) {
    console.error(err);
    alert('Error loading sample benchmark dataset.');
  }
});

btnCalibrate.addEventListener('click', async () => {
  if (pairsData.length === 0) {
    alert('Please load or import evaluation pairs first.');
    return;
  }
  await runCalibration();
});

filterDisagreements.addEventListener('change', () => {
  renderTable();
});

async function runCalibration() {
  if (pairsData.length === 0) return;

  const payload = {
    scale: 5.0,
    human_rater_id: 'human-expert-consensus',
    judge_model_id: 'gpt-4o-judge',
    pairs: pairsData.map(p => ({
      pair_id: p.pair_id,
      prompt: p.prompt,
      response: p.response,
      human_score: p.human_score,
      judge_score: p.judge_score,
      human_rationale: p.human_rationale || null,
      judge_rationale: p.judge_rationale || null,
      rubric_criterion: p.rubric_criterion || 'General Quality',
      model_evaluated: p.model_evaluated || 'unknown'
    }))
  };

  try {
    const res = await fetch('/api/calibrate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Calibration failed');
    currentReport = await res.json();
    updateKPIs(currentReport);
    renderTable();
  } catch (err) {
    console.error(err);
    alert('Calibration error: ' + err.message);
  }
}

function updateKPIs(report) {
  const agr = report.agreement;
  const bias = report.bias;

  kpiPearson.textContent = agr.pearson_correlation !== null ? agr.pearson_correlation.toFixed(3) : 'N/A';
  kpiKappa.textContent = agr.cohen_weighted_kappa !== null ? agr.cohen_weighted_kappa.toFixed(3) : 'N/A';
  kpiMae.textContent = agr.mean_absolute_error.toFixed(2);
  kpiVerbosity.textContent = bias.verbosity_bias_correlation !== null ? bias.verbosity_bias_correlation.toFixed(3) : 'N/A';

  const leniencySign = bias.judge_systematic_inflation >= 0 ? '+' : '';
  biasLeniency.textContent = `${leniencySign}${bias.judge_systematic_inflation.toFixed(2)} pts`;
  biasDisagreements.textContent = bias.severe_disagreements;

  const r = agr.pearson_correlation !== null ? agr.pearson_correlation : 0;
  biasStatus.className = 'status-badge ' + (r >= 0.75 ? 'status-calibrated' : (r >= 0.5 ? 'status-warning' : 'status-danger'));
  biasStatus.textContent = report.reliability_tier || (r >= 0.75 ? 'Calibrated' : 'Disagreement Alert');
}

function renderTable() {
  const onlyDisagreements = filterDisagreements.checked;
  const filtered = pairsData.filter(p => {
    if (!onlyDisagreements) return true;
    return Math.abs(p.human_score - p.judge_score) >= 1.0;
  });

  pairCountSpan.textContent = filtered.length;
  tableBody.innerHTML = '';

  if (filtered.length === 0) {
    tableBody.innerHTML = `<tr><td colspan="6" class="empty-state">No matching evaluation pairs.</td></tr>`;
    return;
  }

  filtered.forEach(p => {
    const delta = Math.abs(p.human_score - p.judge_score);
    const tr = document.createElement('tr');
    if (selectedPairId === p.pair_id) tr.classList.add('selected');

    let badgeClass = 'badge-pass';
    let badgeText = 'Aligned';
    if (delta >= 1.5) {
      badgeClass = 'badge-fail';
      badgeText = 'Severe Divergence';
    } else if (delta >= 0.8) {
      badgeClass = 'badge-warn';
      badgeText = 'Minor Drift';
    }

    const preview = p.prompt.length > 55 ? p.prompt.substring(0, 55) + '...' : p.prompt;

    tr.innerHTML = `
      <td><code>${p.pair_id}</code></td>
      <td>${escapeHtml(preview)}</td>
      <td><strong>${p.human_score.toFixed(1)}</strong></td>
      <td><strong>${p.judge_score.toFixed(1)}</strong></td>
      <td><code>${(p.judge_score - p.human_score).toFixed(2)}</code></td>
      <td><span class="badge ${badgeClass}">${badgeText}</span></td>
    `;

    tr.addEventListener('click', () => {
      selectedPairId = p.pair_id;
      renderTable();
      displayInspector(p);
    });

    tableBody.appendChild(tr);
  });
}

function displayInspector(pair) {
  inspectorEmpty.classList.add('hidden');
  inspectorBody.classList.remove('hidden');

  inspectorBadge.textContent = pair.pair_id;
  inspectorPrompt.textContent = pair.prompt;
  inspectorResponse.textContent = pair.response;
  inspectorHumanScore.textContent = pair.human_score.toFixed(1);
  inspectorHumanRationale.textContent = pair.human_rationale || 'No rationale provided';
  inspectorAiScore.textContent = pair.judge_score.toFixed(1);
  inspectorAiRationale.textContent = pair.judge_rationale || 'No rationale provided';

  inspectorCriterion.textContent = pair.rubric_criterion || 'General Quality';
  inspectorModel.textContent = pair.model_evaluated || 'Unknown';
  inspectorLength.textContent = pair.response ? pair.response.length : 0;
  
  const diff = pair.judge_score - pair.human_score;
  const sign = diff >= 0 ? '+' : '';
  inspectorDelta.textContent = `${sign}${diff.toFixed(2)}`;
}

btnExportMd.addEventListener('click', async () => {
  if (pairsData.length === 0) {
    alert('Please load evaluation data before exporting a report.');
    return;
  }
  const payload = {
    scale: 5.0,
    human_rater_id: 'human-expert-consensus',
    judge_model_id: 'gpt-4o-judge',
    pairs: pairsData
  };
  try {
    const res = await fetch('/api/reports/markdown', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Markdown generation failed');
    const mdText = await res.text();
    downloadFile(mdText, 'judgebench-calibration-report.md', 'text/markdown');
  } catch (err) {
    console.error(err);
    alert('Failed to export markdown report.');
  }
});

function downloadFile(content, fileName, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>"']/g, m => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  })[m]);
}
