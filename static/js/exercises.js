/* Tongue Twister Exercises View */

function initExercises() {
    const container = document.getElementById('view-exercises');
    container.innerHTML = `
        <div class="section-header">
            <h2>Tongue-Twister Challenges</h2>
            <p>Practice these to improve articulation and manage speech rate.</p>
        </div>
        <div class="feature-grid">
            ${tongueTwisters.map((t, idx) => `
                <div class="card card-hover" style="display: flex; flex-direction: column; justify-content: space-between;">
                    <div>
                        <span class="badge badge-${t.difficulty.toLowerCase()}" style="margin-bottom: var(--spacing-md);">${t.difficulty}</span>
                        <p style="font-size: 1.1rem; font-weight: 600; line-height: 1.5; margin-bottom: var(--spacing-lg);">"${t.text}"</p>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="color: var(--text-light); font-size: 0.9rem;"><i data-lucide="zap" style="width: 14px; display: inline-block;"></i> ${t.points} XP</span>
                        <button class="btn btn-primary btn-sm" onclick="alert('Starting exercise: ${t.difficulty}')">Practice</button>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
    lucide.createIcons();
}

window.initExercises = initExercises;
