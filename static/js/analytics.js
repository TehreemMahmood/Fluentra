/* Progress & Analytics View */

function initProgress() {
    const container = document.getElementById('view-progress');
    container.innerHTML = `
        <div style="display: grid; grid-template-columns: 2fr 1fr; gap: var(--spacing-xl);">
            <div class="card">
                <h3>Fluency Trend (7 Days)</h3>
                <canvas id="trendChart" style="margin-top: var(--spacing-xl);"></canvas>
            </div>
            <div class="card">
                <h3>Dysfluency Distribution</h3>
                <canvas id="typeChart" style="margin-top: var(--spacing-xl);"></canvas>
            </div>
        </div>
        <div class="card" style="margin-top: var(--spacing-xl);">
            <h3>Milestones & Badges</h3>
            <div style="display: flex; gap: var(--spacing-xl); margin-top: var(--spacing-lg); justify-content: space-around;">
                <div style="text-align: center;">
                    <div style="width: 80px; height: 80px; background: #E6FFFA; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto var(--spacing-sm); border: 2px solid var(--secondary-color);">
                        <i data-lucide="award" style="color: var(--secondary-color); width: 40px; height: 40px;"></i>
                    </div>
                    <span class="font-bold">5-Day Streak</span>
                </div>
                 <div style="text-align: center;">
                    <div style="width: 80px; height: 80px; background: #E6FFFA; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto var(--spacing-sm); border: 2px solid var(--secondary-color);">
                        <i data-lucide="zap" style="color: var(--secondary-color); width: 40px; height: 40px;"></i>
                    </div>
                    <span class="font-bold">Fast Finisher</span>
                </div>
                 <div style="text-align: center; opacity: 0.4;">
                    <div style="width: 80px; height: 80px; background: #F7FAFC; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto var(--spacing-sm); border: 2px solid var(--border-color);">
                        <i data-lucide="lock" style="color: var(--text-light); width: 40px; height: 40px;"></i>
                    </div>
                    <span>Fluency Master</span>
                </div>
            </div>
        </div>
    `;

    lucide.createIcons();

    // Trend Chart
    const trendCtx = document.getElementById('trendChart').getContext('2d');
    new Chart(trendCtx, {
        type: 'line',
        data: {
            labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            datasets: [{
                label: 'Fluency Score %',
                data: [72, 75, 74, 80, 82, 85, 82],
                borderColor: '#2C5282',
                backgroundColor: 'rgba(44, 82, 130, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: false, min: 60, max: 100 } }
        }
    });

    // Distribution Chart
    const typeCtx = document.getElementById('typeChart').getContext('2d');
    new Chart(typeCtx, {
        type: 'doughnut',
        data: {
            labels: ['Blocks', 'Prolongations', 'Repetitions'],
            datasets: [{
                data: [20, 35, 45],
                backgroundColor: ['#4FD1C5', '#F6E05E', '#E53E3E']
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { position: 'bottom' } }
        }
    });
}

window.initProgress = initProgress;
