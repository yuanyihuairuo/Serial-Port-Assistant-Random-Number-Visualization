// ==================== 串口助手 · 随机数分析 —— 前端应用逻辑 ====================
const { createApp, reactive, ref, computed, onMounted, onBeforeUnmount, nextTick } = Vue;

const state = reactive({
  // 配置
  mode: 'sim',                 // serial | sim
  pattern: 'random',           // demo pattern key (mode=sim)
  demoPatterns: [],
  port: '',
  ports: [],
  baud: 115200,
  databits: 8,
  parity: 'N',
  stopbits: 1,
  accumulate: true,
  // 页面
  appMode: 'terminal',         // terminal | analysis
  activeChart: 'time',
  // 数据流
  connected: false,
  rx: 0,
  tx: 0,
  bufferLen: 0,
  stats: {},
  score: null,                 // {score, level, issues}
  // 终端
  terminalLines: [],
  rxFormat: 'HEX',
  txFormat: 'HEX',
  autoScroll: true,
  autoSend: false,
  sendText: 'Hello 48 65 6C 6C 6F',
  // 分析
  analyzeSize: 1000,
});

const CHART_TABS = [
  { key: 'time', label: '时域波形' },
  { key: 'hist', label: '分布直方图' },
  { key: 'scatter', label: '相关性散点' },
  { key: 'autocorr', label: '自相关分析' },
];
const PARITY = [{v:'N',label:'None'},{v:'E',label:'Even'},{v:'O',label:'Odd'},{v:'M',label:'Mark'},{v:'S',label:'Space'}];
const STAT_ITEMS = [
  { key:'mean', label:'平均值' }, { key:'std', label:'标准差' },
  { key:'min', label:'最小值' }, { key:'max', label:'最大值' },
  { key:'range', label:'范围' }, { key:'cv', label:'变异系数' },
  { key:'median', label:'中位数' }, { key:'kurtosis', label:'峰度' },
];

let ws = null;
let wsRetry = null;
let autoSendTimer = null;
let charts = {};

// ==================== 辅助函数 ====================
function fmtCount(n) {
  return (n || 0).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}
function fmtStat(v) {
  return (v === undefined || v === null || isNaN(v)) ? '--' : Number(v).toFixed(4);
}
function escapeHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function nowTime() {
  const d = new Date();
  return [d.getHours(), d.getMinutes(), d.getSeconds()]
    .map(x => String(x).padStart(2,'0')).join(':') + '.' +
    String(d.getMilliseconds()).padStart(3,'0');
}
function scoreColor() {
  const s = state.score ? state.score.score : 0;
  return s >= 75 ? '#34d399' : s >= 60 ? '#8a9cff' : s >= 50 ? '#fbbf24' : '#f87171';
}
function scoreBarBg() {
  const s = state.score ? state.score.score : 0;
  const c = scoreColor();
  return `linear-gradient(90deg, ${c}, #2dd4bf)`;
}
const parityMap = computed(() => PARITY);
const chartTabs = CHART_TABS;
const bauds = [9600,19200,38400,57600,115200,230400,460800,921600];
const statItems = STAT_ITEMS;

// ==================== WebSocket ====================
function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => {
    pushAutoAnalyze();
  };
  ws.onmessage = (ev) => handleWS(JSON.parse(ev.data));
  ws.onclose = () => {
    clearTimeout(wsRetry);
    wsRetry = setTimeout(connectWS, 1500);
  };
  ws.onerror = () => { try { ws.close(); } catch(e){} };
}

function pushAutoAnalyze() {
  if (!ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({ type: 'set_auto_analyze', enabled: state.appMode === 'analysis' }));
}

function handleWS(msg) {
  if (msg.type === 'rx') {
    appendRx(msg.data);
    return;
  }
  if (msg.type === 'update') {
    const s = msg.status;
    state.connected = s.connected;
    state.rx = s.rx;
    state.tx = s.tx;
    state.bufferLen = s.buffer_len || 0;
    state.stats = msg.stats || {};
    renderCharts(msg.charts || {});
    return;
  }
  if (msg.type === 'analysis') {
    if (msg.ok) { state.score = msg.summary; }
    return;
  }
  if (msg.type === 'ports') {
    state.ports = msg.ports;
  }
}

// ==================== 终端显示 ====================
function formatBytes(hexStr, fmt) {
  const bytes = hexStr === '' ? [] : hexStr.split(' ').map(h => parseInt(h, 16));
  if (fmt === 'HEX') return hexStr;
  if (fmt === 'ASCII') return bytes.map(b => String.fromCharCode(b)).join('');
  return '';
}

function appendRx(hexStr) {
  const content = formatBytes(hexStr, state.rxFormat);
  const time = nowTime();
  state.terminalLines.push({
    role: 'rx',
    time,
    tag: state.rxFormat,
    color: '#8a9cff',
    html: `<div class="bubble rx">${escapeHtml(content)}</div>`,
  });
  trimLog();
  nextTick(scrollLog);
}

function appendTx(content) {
  const time = nowTime();
  state.terminalLines.push({
    role: 'tx',
    time,
    tag: 'TX',
    color: '#2dd4bf',
    html: `<div class="bubble tx">${escapeHtml(content)}</div>`,
  });
  trimLog();
  nextTick(scrollLog);
}

function appendSystem(content) {
  const time = nowTime();
  state.terminalLines.push({
    role: 'sys',
    time,
    tag: '系统',
    color: '#b4b4bc',
    html: `<div class="bubble sys">${escapeHtml(content)}</div>`,
  });
  trimLog();
  nextTick(scrollLog);
}

function trimLog() {
  const MAX = 2000;
  if (state.terminalLines.length > MAX) {
    state.terminalLines.splice(0, state.terminalLines.length - MAX);
  }
}

function getLogEl() {
  return document.querySelector('.terminal-log');
}

let pendingProgrammatic = false;

function scrollLog() {
  if (!state.autoScroll) return;
  const el = getLogEl();
  if (!el) return;
  pendingProgrammatic = true;
  el.scrollTop = el.scrollHeight;
  // 兜底：若已在底部（无 scroll 事件触发）则稍后清除标记
  clearTimeout(scrollLog._t);
  scrollLog._t = setTimeout(() => { pendingProgrammatic = false; }, 100);
}

function isAtBottom() {
  const el = getLogEl();
  if (!el) return true;
  return (el.scrollTop + el.clientHeight) >= (el.scrollHeight - 30);
}

function onLogScroll() {
  // 程序化滚动（自动滚到底部）触发的事件：消费一次即可，不误判为"用户滚走"
  if (pendingProgrammatic) { pendingProgrammatic = false; return; }
  state.autoScroll = isAtBottom();
}

function toggleAutoScroll() {
  state.autoScroll = !state.autoScroll;
  if (state.autoScroll) scrollLog();
}

function jumpToBottom() {
  state.autoScroll = true;
  scrollLog();
}

// ==================== REST 调用 ====================
async function api(url, body) {
  // 本应用的 api() 仅用于控制类动作（开关/发送/分析），统一用 POST
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  return res.json();
}

// ==================== 页面动作 ====================
function setMode(m) { state.mode = m; }

async function scanPorts() {
  const data = await fetch('/api/ports').then(r => r.json());
  state.ports = data.ports || [];
  if (state.ports.length && !state.port) state.port = state.ports[0].device;
  appendSystem(`已扫描到 ${state.ports.length} 个串口`);
}

function buildOpenBody() {
  return {
    port: state.port || 'SIM',
    baud: state.baud,
    databits: state.databits,
    parity: state.parity,
    stopbits: state.stopbits,
    mode: state.mode,
    pattern: state.pattern,
  };
}

async function openNow() {
  const res = await api('/api/open', buildOpenBody());
  if (res.ok) {
    state.connected = true;
    appendSystem(`${state.mode==='sim' ? '演示模式 · ' + demoLabel(state.pattern) : '串口'} 已连接 : ${state.port} @ ${state.baud}bps`);
    return true;
  }
  appendSystem('连接失败: ' + res.error);
  return false;
}

async function toggleConnect() {
  if (state.connected) {
    await api('/api/close');
    state.connected = false;
    appendSystem('串口已关闭');
    return;
  }
  await openNow();
}

// 演示模式下切换图案时，若已连接则用新图案重开，实现即时切换
async function reopenDemo() {
  if (!(state.connected && state.mode === 'sim')) return;
  const res = await api('/api/open', buildOpenBody());
  if (res.ok) {
    appendSystem(`演示图案已切换 → ${demoLabel(state.pattern)}`);
  }
}

function demoLabel(key) {
  const p = state.demoPatterns.find(x => x.key === key);
  return p ? p.label : '演示';
}

async function sendData() {
  if (!state.connected) return;
  const text = state.sendText;
  if (!text) return;
  const res = await api('/api/send', { data: text, fmt: state.txFormat });
  if (res.ok) {
    appendTx(text);
  } else {
    appendSystem('发送失败: ' + res.error);
  }
}

async function manualAnalyze() {
  const res = await api('/api/analyze', { size: state.analyzeSize });
  if (res.ok) {
    state.score = res.summary;
    appendSystem(`分析完成: 评分 ${res.summary.score}/${100}`);
  } else {
    appendSystem(res.error || '分析失败');
  }
}

async function clearRx() {
  state.terminalLines = [];
  await api('/api/clear');
}

function exportData() {
  const data = state.terminalLines.map(l => `[${l.time}] ${l.tag}: ${l.html.replace(/<[^>]+>/g,'')}`).join('\n');
  const blob = new Blob([data], { type: 'text/plain;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'serial_data.txt';
  a.click();
  URL.revokeObjectURL(a.href);
}

function toggleRxFmt() {
  state.rxFormat = state.rxFormat === 'HEX' ? 'ASCII' : 'HEX';
  appendSystem(`接收格式切换为 ${state.rxFormat}`);
}
function toggleTxFmt() {
  state.txFormat = state.txFormat === 'HEX' ? 'ASCII' : 'HEX';
}
function onModeChanged(appMode) {
  pushAutoAnalyze();
}
function switchMode(m) {
  state.appMode = m;
  onModeChanged(m);
  if (m === 'analysis') {
    // 进入分析页时立即有一次快照
    manualAnalyzeSilent();
    nextTick(resizeActiveChart);
  }
}

function setChart(key) {
  state.activeChart = key;
  nextTick(resizeActiveChart);
}

function resizeActiveChart() {
  const el = document.getElementById('chart-' + state.activeChart);
  const c = charts[state.activeChart];
  if (el && c) c.resize();
}

async function manualAnalyzeSilent() {
  const res = await api('/api/analyze', { size: state.analyzeSize });
  if (res.ok) state.score = res.summary;
}

function onAutoSend() {
  clearInterval(autoSendTimer);
  if (state.autoSend) {
    autoSendTimer = setInterval(sendData, 1000);
  }
}

// ==================== ECharts 渲染 ====================
function initCharts() {
  const keys = ['time', 'hist', 'scatter', 'autocorr'];
  keys.forEach((k) => {
    const el = document.getElementById('chart-' + k);
    if (el) {
      try { charts[k] = echarts.init(el); } catch (e) { console.warn('chart init', k, e); }
    }
  });
  window.addEventListener('resize', resizeCharts);
}

function resizeCharts() {
  Object.values(charts).forEach(c => c && c.resize());
}

function baseOption() {
  return {
    backgroundColor: 'transparent',
    grid: { left: 44, right: 20, top: 24, bottom: 34 },
    textStyle: { color: '#b4b4bc', fontFamily: 'Consolas, Menlo, monospace', fontSize: 11 },
    tooltip: { trigger: 'axis', backgroundColor: '#181a24', borderColor: '#2a2b36', textStyle: { color: '#e9e9ec' } },
  };
}

function renderCharts(chartsData) {
  if (!charts.time) return;
  // 时域波形
  charts.time.setOption({
    ...baseOption(),
    xAxis: { type: 'category', data: chartsData.time.map((_, i) => i), axisLine: { lineStyle: { color: '#44455a' } }, axisLabel: { color: '#b4b4bc' } },
    yAxis: { type: 'value', min: 0, max: 1, splitLine: { lineStyle: { color: '#232430' } }, axisLabel: { color: '#b4b4bc' } },
    series: [{ type: 'line', data: chartsData.time, showSymbol: false, lineStyle: { color: '#8a9cff', width: 1.4 }, areaStyle: { color: 'rgba(138,156,255,0.10)' } }],
  });

  // 直方图
  charts.hist.setOption({
    ...baseOption(),
    tooltip: { trigger: 'item' },
    xAxis: { type: 'category', data: Array.from({length:256},(_,i)=>i), axisLabel: { show:false }, axisLine: { lineStyle: { color: '#44455a' } } },
    yAxis: { type: 'value', min: 0, max: 1, splitLine: { lineStyle: { color: '#232430' } }, axisLabel: { color: '#b4b4bc' } },
    series: [{ type: 'bar', data: chartsData.hist, barCategoryGap: '1px', itemStyle: { color: '#8a9cff' } }],
  });

  // 散点
  charts.scatter.setOption({
    ...baseOption(),
    tooltip: { trigger: 'item' },
    xAxis: { type: 'value', min:0, max:1, splitLine: { lineStyle: { color: '#232430' } }, axisLabel: { color: '#b4b4bc' } },
    yAxis: { type: 'value', min:0, max:1, splitLine: { lineStyle: { color: '#232430' } }, axisLabel: { color: '#b4b4bc' } },
    series: [{ type: 'scatter', symbolSize: 2, data: chartsData.scatter_x.map((x,i)=>[x, chartsData.scatter_y[i]]), itemStyle: { color: 'rgba(138,156,255,0.7)' } }],
  });

  // 自相关
  const ac = chartsData.autocorr || [];
  charts.autocorr.setOption({
    ...baseOption(),
    xAxis: { type: 'category', data: ac.map((_,i)=>i+1), axisLabel: { color: '#b4b4bc' }, axisLine: { lineStyle: { color: '#44455a' } } },
    yAxis: { type: 'value', min:-0.3, max:0.3, splitLine: { lineStyle: { color: '#232430' } }, axisLabel: { color: '#b4b4bc' } },
    series: [{ type: 'line', data: ac, showSymbol: true, symbolSize: 4, lineStyle: { color: '#2dd4bf', width: 1.5 }, itemStyle: { color: '#2dd4bf' } }],
  });
}

// ==================== 生命周期 ====================
const app = createApp({
  data() { return { state, bauds, parityMap, chartTabs, statItems }; },
  computed: {
    scoreColor, scoreBarBg,
  },
  methods: {
    fmtCount, fmtStat, setMode, scanPorts, toggleConnect, sendData,
    manualAnalyze, clearRx, exportData, toggleRxFmt, toggleTxFmt,
    switchMode, setChart, onAutoSend, onLogScroll, toggleAutoScroll, jumpToBottom,
    onPatternChange: reopenDemo,
  },
  mounted() {
    initCharts();
    scanPorts();
    connectWS();
    fetch('/api/patterns').then(r => r.json()).then(d => {
      state.demoPatterns = d.patterns || [];
      setTimeout(() => {
        appendSystem('欢迎使用串口助手 · 随机数分析 V2.0');
        appendSystem('默认使用「演示」模式，无需串口即可体验完整分析；可在左侧切换数据图案。');
      }, 200);
    });
  },
  beforeUnmount() {
    clearInterval(autoSendTimer);
    if (ws) ws.close();
  },
});

app.use ? app.use({}) : null;
app.mount('#app');
