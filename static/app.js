let currentFilename = null;
let mode = 'text';
let annotations = [];
let dragStart = null;

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}

function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 2800);
}

function setMode(v) { mode = v; }

function clearAnnotations() {
  annotations = [];
  updateAnnotationCount();
  toast('Annotations cleared');
}

function updateAnnotationCount() {
  const el = document.getElementById('annotationCount');
  el.textContent = annotations.length > 0 ? `${annotations.length} annotation(s) pending` : '';
}

async function viewPdf() {
  const fileInput = document.getElementById('pdfFile');
  const file = fileInput.files[0];
  if (!file) { toast('Choose a PDF file first.'); return; }
  const formData = new FormData();
  formData.append('file', file);
  toast('Loading PDF...');
  const res = await fetch('/view_pdf', { method: 'POST', body: formData });
  const data = await res.json();
  currentFilename = data.filename;
  document.getElementById('pdfInfo').innerHTML =
    `Opened <b>${data.filename}</b> &mdash; ${data.total_pages} page(s)`;
  const viewer = document.getElementById('viewer');
  viewer.innerHTML = '';
  data.images.forEach(img => {
    const wrap = document.createElement('div');
    wrap.className = 'page-wrap';
    wrap.dataset.page = img.page;
    const label = document.createElement('div');
    label.className = 'label';
    label.textContent = `Page ${img.page}`;
    const image = document.createElement('img');
    image.src = `data:image/png;base64,${img.data}`;
    image.addEventListener('click', e => handleClick(e, wrap, image));
    image.addEventListener('mousedown', e => startDraw(e, wrap, image));
    image.addEventListener('mouseup', e => endDraw(e, wrap, image));
    image.addEventListener('touchstart', e => startDraw(e.touches[0], wrap, image), {passive:true});
    image.addEventListener('touchend', e => endDraw(e.changedTouches[0], wrap, image), {passive:true});
    wrap.appendChild(label);
    wrap.appendChild(image);
    viewer.appendChild(wrap);
  });
  toast(`Opened ${data.total_pages} page(s)`);
}

function relPos(event, img) {
  const rect = img.getBoundingClientRect();
  const scaleX = img.naturalWidth / rect.width;
  const scaleY = img.naturalHeight / rect.height;
  return {
    x: (event.clientX - rect.left) * scaleX,
    y: (event.clientY - rect.top) * scaleY
  };
}

function handleClick(event, wrap, img) {
  if (mode !== 'text') return;
  const text = document.getElementById('textInput').value.trim();
  if (!text) { toast('Enter annotation text first.'); return; }
  const pos = relPos(event, img);
  annotations.push({ type: 'text', page: Number(wrap.dataset.page), x: pos.x, y: pos.y, text, size: 12 });
  updateAnnotationCount();
  toast(`Text added on page ${wrap.dataset.page}`);
}

function startDraw(event, wrap, img) {
  if (mode === 'rect' || mode === 'highlight') dragStart = { ...relPos(event, img), page: Number(wrap.dataset.page) };
}

function endDraw(event, wrap, img) {
  if (!dragStart || (mode !== 'rect' && mode !== 'highlight')) return;
  const end = relPos(event, img);
  annotations.push({
    type: mode,
    page: Number(wrap.dataset.page),
    x1: Math.min(dragStart.x, end.x),
    y1: Math.min(dragStart.y, end.y),
    x2: Math.max(dragStart.x, end.x),
    y2: Math.max(dragStart.y, end.y)
  });
  dragStart = null;
  updateAnnotationCount();
  toast(`${mode} added on page ${wrap.dataset.page}`);
}

async function saveEdits() {
  if (!currentFilename) { toast('Open a PDF first.'); return; }
  if (annotations.length === 0) { toast('No annotations to save.'); return; }
  toast('Saving...');
  const res = await fetch('/edit_pdf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename: currentFilename, annotations })
  });
  const data = await res.json();
  if (data.output) {
    document.getElementById('pdfInfo').innerHTML +=
      `<div class="note">✅ Saved: <a href="/download/${data.output}">${data.output}</a></div>`;
    toast('PDF saved!');
  } else {
    toast(data.error || 'Failed to save edits.');
  }
}

async function convertToPdf() {
  const fileInput = document.getElementById('convertFile');
  const file = fileInput.files[0];
  if (!file) { toast('Choose a file to convert.'); return; }
  const formData = new FormData();
  formData.append('file', file);
  toast('Converting...');
  const res = await fetch('/convert_to_pdf', { method: 'POST', body: formData });
  const data = await res.json();
  const el = document.getElementById('convertResult');
  if (data.output) {
    el.innerHTML = `✅ Done: <a href="/download/${data.output}">${data.output}</a>`;
    toast('Conversion complete!');
  } else {
    el.textContent = data.error || 'Conversion failed.';
    toast('Conversion failed.');
  }
}
