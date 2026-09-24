'use strict';

const form = document.getElementById('check-form');
const castOnInput = document.getElementById('cast-on');
const patternInput = document.getElementById('pattern');
const resultSection = document.getElementById('result');
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
  render(data);
});

function render(data) {
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
    const err = data.error;
    let text;
    if (err.type === 'cast_on') {
      text = '起针数错误：' + err.message;
    } else if (err.type === 'parse') {
      text = '第 ' + err.line + ' 行指令无法解析：' + err.message;
    } else {
      const kind = err.diff > 0 ? '针数不足' : '针数超出';
      text = '第 ' + err.line + ' 行' + kind + '（差额 ' + Math.abs(err.diff) + ' 针）：' + err.message;
    }
    errorBox.textContent = text;
    errorBox.hidden = false;
    summaryBox.textContent = '校验未通过：' + data.rows.length + ' 行有效，首个错误见下。错误行及之后的行未参与推算。';
    summaryBox.className = 'error';
  } else {
    summaryBox.textContent = '校验通过：共 ' + data.rows.length + ' 行，最终剩余 ' + data.final + ' 针。';
    summaryBox.className = 'ok';
  }
}
