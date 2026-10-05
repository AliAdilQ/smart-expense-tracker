const chartData = document.getElementById('chart-data');
if (chartData && typeof Chart !== 'undefined') {
  const data = JSON.parse(chartData.textContent);
  Chart.defaults.font.family = "'DM Sans', sans-serif";
  Chart.defaults.font.size = 10;
  Chart.defaults.color = '#8b998e';
  Chart.defaults.animation = false;
  const colors = ['#73976a', '#b9cd9e', '#e6cb9e', '#94bcb1', '#c4a699', '#929fbd', '#d1b4cc', '#9cc5da', '#bcc6b3'];
  const options = {responsive: true, maintainAspectRatio: false, plugins: {legend: {position: 'bottom', labels: {usePointStyle: true, padding: 22, boxWidth: 7}}}, scales: {x: {grid: {display: false}, border: {display: false}}, y: {beginAtZero: true, grid: {color: '#f0f3ed'}, border: {display: false}, ticks: {callback: value => '$' + value.toLocaleString()}}}};
  function make(id, config) { const canvas = document.getElementById(id); if (canvas) new Chart(canvas, config); }
  make('cashflow', {type: 'bar', data: {labels: data.labels, datasets: [{label: 'Income', data: data.income, backgroundColor: '#73976a', borderRadius: 4, maxBarThickness: 19}, {label: 'Expenses', data: data.expenses, backgroundColor: '#d6e2c7', borderRadius: 4, maxBarThickness: 19}]}, options});
  make('categories', {type: 'doughnut', data: {labels: data.categories, datasets: [{data: data.values, backgroundColor: colors, borderWidth: 4, borderColor: '#fff', hoverOffset: 5}]}, options: {responsive: true, maintainAspectRatio: false, cutout: '75%', plugins: {legend: {position: 'bottom', labels: {usePointStyle: true, boxWidth: 7, padding: 14}}, tooltip: {callbacks: {label: context => `${context.label}: $${context.parsed.toFixed(2)}`}}}}});
  make('monthly', {type: 'line', data: {labels: data.labels, datasets: [{label: 'Expenses', data: data.expenses, borderColor: '#73976a', backgroundColor: '#73976a14', fill: true, tension: .35, pointRadius: 4}]}, options});
  if (data.registrations) make('registrations', {type: 'bar', data: {labels: data.labels, datasets: [{label: 'New users', data: data.registrations, backgroundColor: '#91a6c5', borderRadius: 5}]}, options: {...options, scales: {...options.scales, y: {beginAtZero: true, ticks: {precision: 0}}}}});
  make('category-frequency', {type: 'bar', data: {labels: data.categories, datasets: [{label: 'Transactions', data: data.category_counts, backgroundColor: colors, borderRadius: 5}]}, options: {...options, scales: {...options.scales, y: {beginAtZero: true, ticks: {precision: 0}}}}});
}
