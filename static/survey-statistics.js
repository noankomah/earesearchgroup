document.addEventListener('DOMContentLoaded', function () {
  const data = document.getElementById('survey-charts');
  if (!data || typeof Chart === 'undefined') return;
  const charts = JSON.parse(data.textContent);
  document.querySelectorAll('[data-survey-chart]').forEach(function (canvas) {
    const item = charts[Number(canvas.dataset.surveyChart)];
    new Chart(canvas, {type: 'bar', data: {labels: item.labels, datasets: [{label: 'Responses', data: item.values, backgroundColor: '#2d6a4f'}]}, options: {indexAxis: 'y', scales: {x: {beginAtZero: true, ticks: {precision: 0}}}}});
  });
});
