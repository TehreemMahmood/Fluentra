/* Support Logic for Dashboard Extras & Techniques */

function initTechniques() {
    const container = document.getElementById('view-techniques');
    container.innerHTML = `
        <div class="section-header">
            <h2>Speech Techniques Library</h2>
            <p>Master these evidence-based techniques to improve fluency and manage dysfluencies.</p>
        </div>
        
        <div style="display: grid; grid-template-columns: 2fr 1fr; gap: var(--spacing-xl);">
            <!-- Articles -->
            <div style="display: flex; flex-direction: column; gap: var(--spacing-lg);">
                <div class="card card-hover" style="display: flex; gap: var(--spacing-lg);">
                    <div style="flex: 1;">
                        <span class="badge badge-medium" style="margin-bottom: 10px;">Breathing</span>
                        <h3 style="margin-bottom: 10px;">Diaphragmatic Breathing</h3>
                        <p class="text-secondary" style="margin-bottom: var(--spacing-md);">Learn how to use your breath to support speech and reduce tension in the vocal folds.</p>
                        <a href="#" style="color: var(--primary-color); font-weight: 600;">Read Full Module →</a>
                    </div>
                    <div style="width: 150px; background: #E2E8F0; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center;">
                         <i data-lucide="wind" style="width: 48px; height: 48px; color: var(--text-light);"></i>
                    </div>
                </div>

                <div class="card card-hover" style="display: flex; gap: var(--spacing-lg);">
                    <div style="flex: 1;">
                        <span class="badge badge-easy" style="margin-bottom: 10px;">Articulation</span>
                        <h3 style="margin-bottom: 10px;">Light Articulatory Contacts</h3>
                        <p class="text-secondary" style="margin-bottom: var(--spacing-md);">A technique to reduce the physical pressure of consonants like 'P', 'B', and 'K'.</p>
                        <a href="#" style="color: var(--primary-color); font-weight: 600;">Read Full Module →</a>
                    </div>
                   <div style="width: 150px; background: #E2E8F0; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center;">
                         <i data-lucide="smile" style="width: 48px; height: 48px; color: var(--text-light);"></i>
                    </div>
                </div>

                 <div class="card card-hover" style="display: flex; gap: var(--spacing-lg);">
                    <div style="flex: 1;">
                        <span class="badge badge-hard" style="margin-bottom: 10px;">Strategy</span>
                        <h3 style="margin-bottom: 10px;">Cancellation Technique</h3>
                        <p class="text-secondary" style="margin-bottom: var(--spacing-md);">A stuttering modification strategy used after a dysfluent word occurred.</p>
                        <a href="#" style="color: var(--primary-color); font-weight: 600;">Read Full Module →</a>
                    </div>
                    <div style="width: 150px; background: #E2E8F0; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center;">
                         <i data-lucide="refresh-cw" style="width: 48px; height: 48px; color: var(--text-light);"></i>
                    </div>
                </div>
            </div>

            <!-- Sidebar: Tip of the day -->
            <div>
                <div class="card" style="background: rgba(79, 209, 197, 0.1); border: 1px solid var(--secondary-color);">
                    <h3 style="display: flex; align-items: center; gap: 10px;">
                        <i data-lucide="lightbulb" style="color: var(--secondary-color);"></i>
                        Tip of the Day
                    </h3>
                    <p class="text-secondary" style="margin-top: var(--spacing-md); font-size: 0.95rem; line-height: 1.6;">
                        "The goal of therapy isn't always zero stuttering, but rather communicating what you want, when you want, with ease."
                    </p>
                </div>

                <div class="card" style="margin-top: var(--spacing-lg);">
                    <h3>Your Clinician</h3>
                    <div style="display: flex; align-items: center; gap: var(--spacing-md); margin-top: var(--spacing-md);">
                        <div class="author-avatar" style="width: 40px; height: 40px; background: var(--border-color);"></div>
                        <div>
                            <span style="font-weight: 600; display: block;">Dr. Emily Chen</span>
                            <span style="font-size: 0.8rem; color: var(--text-light);">SLP-CCC</span>
                        </div>
                    </div>
                    <button class="btn btn-primary btn-sm" style="width: 100%; margin-top: var(--spacing-md);">Message Therapist</button>
                </div>
            </div>
        </div>
    `;
    lucide.createIcons();
}

window.initTechniques = initTechniques;
