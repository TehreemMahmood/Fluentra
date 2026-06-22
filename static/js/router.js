document.addEventListener('DOMContentLoaded', () => {
    const navItems = document.querySelectorAll('.nav-item[data-view]');
    const views = document.querySelectorAll('.view');

    function showView(targetView) {
        // Switch Views
        views.forEach(view => {
            view.style.display = view.id === `view-${targetView}` ? 'block' : 'none';
        });

        // Initialize view-specific logic if needed
        if (targetView === 'speech-analysis') {
            if (typeof initSpeechAnalysis === 'function') {
                initSpeechAnalysis();
            }
        } else if (targetView === 'progress') {
            if (typeof initProgress === 'function') {
                initProgress();
            }
        } else if (targetView === 'exercises') {
            if (typeof initExercises === 'function') {
                initExercises();
            }
        } else if (targetView === 'techniques') {
            if (typeof initTechniques === 'function') {
                initTechniques();
            }
        }
    }

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const targetView = item.getAttribute('data-view');

            // Update UI
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            showView(targetView);
        });
    });

    // Show dashboard by default on page load
    showView('dashboard');
});

// View initialization functions are defined in their respective JS files (recording.js, analytics.js, etc.)

