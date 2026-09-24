'use strict';

/* ---------- Tab 切换 ---------- */

const tabs = document.querySelectorAll('.tab');
const singleForm = document.getElementById('check-form');
const sizesForm = document.getElementById('sizes-form');
const singleResult = document.getElementById('result');
const sizesResult = document.getElementById('sizes-result');

tabs.forEach((tab) => {
  tab.addEventListener('click', () => {
    tabs.forEach((t) => t.classList.toggle('active', t === tab));
    const isSizes = tab.dataset.mode === 'sizes';
    singleForm.hidden = isSizes;
    sizesForm.hidden = !isSizes;
    singleResult.hidden = true;
    sizesResult.hidden = true;
  });
});

/* ---------- 单尺码 ---------- */

const form = singleForm;
const castOnInput = document.getElementById('cast-on');
const patternInput = document.getElementById('pattern');
const resultSection = singleResult;
const summaryBox = document.getElementById('summary');
const errorBox = document.getElementById('error-box');
const rowsTable = document.getElementById('rows-table');
const rowsTbody = rowsTable.querySelector('tbody');

const EXAMPLE = [
  '(k2tog yo)*6',
  'p*12',
  '(k2tog)*6',
  '(yo k2tog)*3',
  'k*6',
].join('\n');

document.getElementById('fill-example').addEventListener('click', () => {
  castOnInput.value = '12';
  patternInput.value = EXAMPLE;
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  summaryBox.textContent = '校验中…';
  summaryBox.className = '';
  resultSection.hidden = false;
  errorBox.hidden = true;
  rowsTable.hidden = true;

  let data;
  try {
    const res = await fetch('/api/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cast_on: castOnInput.value,
        pattern: patternInput.value,
      }),
    });
    data = await res.json();
  } catch (err) {
    summaryBox.textContent = '请求失败：' + err.message;
    summaryBox.className = 'error';
    return;
  }
  renderSingle(data);
});

function errorText(err) {
  if (err.type === 'cast_on') {
    return '起针数错误：' + err.message;
  }
  if (err.type === 'parse') {
    const where = err.column ? '第 ' + err.column + ' 个字符处：' : '';
    return '第 ' + err.line + ' 行指令无法解析（' + where + '）：' + err.message;
  }
  const kind = err.diff > 0 ? '针数不足' : '针数超出';
  return '第 ' + err.line + ' 行' + kind + '（差额 ' + Math.abs(err.diff) + ' 针）：' + err.message;
}

function renderSingle(data) {
  // 有效行表格
  rowsTbody.replaceChildren();
  for (const row of data.rows) {
    const tr = document.createElement('tr');
    for (const value of [row.line, row.instruction, row.in, row.consume, row.produce, row.out]) {
      const td = document.createElement('td');
      td.textContent = value;
      tr.appendChild(td);
    }
    rowsTbody.appendChild(tr);
  }
  rowsTable.hidden = data.rows.length === 0;

  // 首个错误（若有）
  if (data.error) {
    errorBox.textContent = errorText(data.error);
    errorBox.hidden = false;
    summaryBox.textContent = '校验未通过：' + data.rows.length + ' 行有效，首个错误见下。错误行及之后的行未参与推算。';
    summaryBox.className = 'error';
  } else {
    summaryBox.textContent = '校验通过：共 ' + data.rows.length + ' 行，最终剩余 ' + data.final + ' 针。';
    summaryBox.className = 'ok';
  }
}

/* ---------- 多尺码 ---------- */

const sizeRowsBox = document.getElementById('size-rows');
const sizesPatternInput = document.getElementById('sizes-pattern');
const sizesSummary = document.getElementById('sizes-summary');
const sizesRequestError = document.getElementById('sizes-request-error');
const sizeCards = document.getElementById('size-cards');

const SIZES_EXAMPLE = [
  '(k2tog yo)*{3|4|5}',
  'p*{6|8|10}',
  '(k2tog)*{3|4|5}',
].join('\n');

function addSizeRow(name = '', castOn = '') {
  const row = document.createElement('div');
  row.className = 'size-row';

  const nameInput = document.createElement('input');
  nameInput.type = 'text';
  nameInput.className = 'size-name';
  nameInput.placeholder = '尺码名（如 S）';
  nameInput.value = name;
  nameInput.required = true;

  const castInput = document.createElement('input');
  castInput.type = 'number';
  castInput.className = 'size-cast-on';
  castInput.placeholder = '起针数';
  castInput.min = '1';
  castInput.step = '1';
  castInput.value = castOn;
  castInput.required = true;

  const removeBtn = document.createElement('button');
  removeBtn.type = 'button';
  removeBtn.className = 'secondary remove-size';
  removeBtn.textContent = '删除';
  removeBtn.addEventListener('click', () => {
    if (sizeRowsBox.children.length > 1) {
      row.remove();
    }
  });

  row.append(nameInput, castInput, removeBtn);
  sizeRowsBox.appendChild(row);
}

document.getElementById('add-size').addEventListener('click', () => addSizeRow());

document.getElementById('fill-sizes-example').addEventListener('click', () => {
  sizeRowsBox.replaceChildren();
  [['S', '6'], ['M', '8'], ['L', '10']].forEach(([name, castOn]) => addSizeRow(name, castOn));
  sizesPatternInput.value = SIZES_EXAMPLE;
});

sizesForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  sizesResult.hidden = false;
  sizeCards.replaceChildren();
  sizesRequestError.hidden = true;
  sizesSummary.textContent = '校验中…';
  sizesSummary.className = '';

  const sizes = [...sizeRowsBox.querySelectorAll('.size-row')].map((row) => ({
    name: row.querySelector('.size-name').value,
    cast_on: row.querySelector('.size-cast-on').value,
  }));

  let data;
  try {
    const res = await fetch('/api/validate-sizes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sizes, pattern: sizesPatternInput.value }),
    });
    data = await res.json();
  } catch (err) {
    sizesSummary.textContent = '请求失败：' + err.message;
    sizesSummary.className = 'error';
    return;
  }
  renderSizes(data);
});

function renderSizes(data) {
  if (data.error) {
    // 请求级错误（尺码/起针数入参不合法）
    sizesRequestError.textContent = data.error.message;
    sizesRequestError.hidden = false;
    sizesSummary.textContent = '无法开始校验，请先修正上方输入。';
    sizesSummary.className = 'error';
    return;
  }

  const failed = data.sizes.filter((s) => !s.ok);
  if (failed.length === 0) {
    const finals = data.sizes.map((s) => s.name + '=' + s.final).join('，');
    sizesSummary.textContent = '全部 ' + data.sizes.length + ' 个尺码校验通过，最终针数：' + finals + '。';
    sizesSummary.className = 'ok';
  } else {
    sizesSummary.textContent =
      failed.length + ' / ' + data.sizes.length + ' 个尺码出现错误；其余尺码仍正常推算。各尺码独立沿用上一行产出继续计算。';
    sizesSummary.className = 'error';
  }

  for (const size of data.sizes) {
    sizeCards.appendChild(renderSizeCard(size));
  }
}

function renderSizeCard(size) {
  const card = document.createElement('div');
  card.className = 'size-card' + (size.ok ? ' ok' : ' bad');

  const header = document.createElement('h3');
  header.textContent = size.name + '（起针 ' + size.cast_on + '）';
  card.appendChild(header);

  const status = document.createElement('div');
  status.className = 'size-status';
  if (size.ok) {
    status.classList.add('ok');
    status.textContent = '通过：' + size.rows.length + ' 行有效，最终 ' + size.final + ' 针';
  } else {
    status.classList.add('error');
    status.textContent = errorText(size.error);
  }
  card.appendChild(status);

  const table = document.createElement('table');
  const thead = document.createElement('thead');
  thead.innerHTML =
    '<tr><th>行号</th><th>指令</th><th>入针</th><th>消耗</th><th>产出</th><th>出针</th></tr>';
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  for (const row of size.rows) {
    const tr = document.createElement('tr');
    for (const value of [row.line, row.instruction, row.in, row.consume, row.produce, row.out]) {
      const td = document.createElement('td');
      td.textContent = value;
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  card.appendChild(table);

  return card;
}

/* 默认三个尺码行 */
[['S', '6'], ['M', '8'], ['L', '10']].forEach(([name, castOn]) => addSizeRow(name, castOn));
