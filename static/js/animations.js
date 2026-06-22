// Register ScrollTrigger
gsap.registerPlugin(ScrollTrigger);

// Utility function relative to viewport
const animateFrom = (elem, direction) => {
    direction = direction || 1;
    let x = 0,
        y = direction * 100;
    if (elem.classList.contains("gs_reveal_fromLeft")) {
        x = -100;
        y = 0;
    } else if (elem.classList.contains("gs_reveal_fromRight")) {
        x = 100;
        y = 0;
    }
    elem.style.transform = "translate(" + x + "px, " + y + "px)";
    elem.style.opacity = "0";
    gsap.fromTo(elem, { x: x, y: y, autoAlpha: 0 }, {
        duration: 1.25,
        x: 0,
        y: 0,
        autoAlpha: 1,
        ease: "expo",
        overwrite: "auto"
    });
};

const hide = (elem) => {
    gsap.set(elem, { autoAlpha: 0 });
};

document.addEventListener("DOMContentLoaded", function () {

    // Generic Fade In Up
    gsap.utils.toArray(".hero-content, .section-header, .page-header").forEach(function (elem) {
        gsap.fromTo(elem,
            { y: 50, opacity: 0 },
            {
                y: 0,
                opacity: 1,
                duration: 1,
                ease: "power2.out",
                scrollTrigger: {
                    trigger: elem,
                    start: "top 85%", // Animation starts when top of element hits 85% of viewport height
                }
            }
        );
    });

    // Staggered Animations for Cards/Grids
    const grids = document.querySelectorAll(".feature-grid, .testimonials, .pricing-grid, .contact-grid");
    grids.forEach(grid => {
        const children = grid.children;
        if (children.length > 0) {
            gsap.fromTo(children,
                { y: 50, opacity: 0 },
                {
                    y: 0,
                    opacity: 1,
                    duration: 0.8,
                    stagger: 0.2,
                    ease: "power2.out",
                    scrollTrigger: {
                        trigger: grid,
                        start: "top 80%",
                    }
                }
            );
        }
    });

    // Navbar Slide Down
    const navbar = document.querySelector(".navbar");
    if (navbar) {
        gsap.fromTo(navbar,
            { y: -100, opacity: 0 },
            {
                y: 0,
                opacity: 1,
                duration: 1,
                ease: "power2.out"
            }
        );
    }

    // Sidebar Logo Animation if present
    const sidebarLogo = document.querySelector(".sidebar-logo");
    if (sidebarLogo) {
        gsap.fromTo(sidebarLogo,
            { x: -50, opacity: 0 },
            {
                x: 0,
                opacity: 1,
                duration: 1,
                ease: "power2.out",
                delay: 0.2
            }
        );
    }

    // Hero Image Slide In
    const heroImage = document.querySelector(".hero-image");
    if (heroImage) {
        gsap.fromTo(heroImage,
            { x: 50, opacity: 0 },
            {
                x: 0,
                opacity: 1,
                duration: 1.2,
                ease: "power3.out",
                delay: 0.2 // Wait a bit for text to start
            }
        );
    }

    // Number Counter Animation
    const counters = document.querySelectorAll(".counter");
    counters.forEach(counter => {
        const target = +counter.getAttribute("data-target");

        ScrollTrigger.create({
            trigger: counter,
            start: "top 85%",
            once: true,
            onEnter: () => {
                const obj = { val: 0 };
                gsap.to(obj, {
                    val: target,
                    duration: 2,
                    ease: "power1.out",
                    onUpdate: () => {
                        // Format numbers: 10000 -> 10k, 1000000 -> 1M
                        let formatted;
                        const current = Math.ceil(obj.val);
                        if (current >= 1000000) {
                            formatted = (current / 1000000).toFixed(0) + "M";
                        } else if (current >= 1000) {
                            formatted = (current / 1000).toFixed(0) + "k";
                        } else {
                            formatted = current;
                        }

                        // If the target didn't have suffix logic in HTML separate, we'd add it here.
                        // But we separated them in HTML for easier alignment, so just raw number or simplified.
                        // Actually, let's just animate the number value itself if we want exact, 
                        // OR if we want "10k" style, we should animate to the raw number and format.

                        // Adjusted logic to match "10k+" style:
                        // The HTML has <span class="counter" data-target="10000">0</span><span>+</span>
                        // So we just output the number.
                        if (target >= 1000 && target < 1000000) {
                            counter.innerText = (Math.ceil(obj.val) / 1000).toFixed(0) + "k";
                        } else if (target >= 1000000) {
                            counter.innerText = (Math.ceil(obj.val) / 1000000).toFixed(0) + "M";
                        } else {
                            counter.innerText = Math.ceil(obj.val);
                        }
                    }
                });
            }
        });
    });

    // Auth Box Animation
    const authBox = document.querySelector(".auth-box");
    if (authBox) {
        gsap.fromTo(authBox,
            { scale: 0.9, opacity: 0 },
            {
                scale: 1,
                opacity: 1,
                duration: 0.8,
                ease: "back.out(1.7)"
            }
        );
    }

    // Mobile Menu Toggle
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const navLinks = document.querySelector('.nav-links');

    if (mobileMenuBtn && navLinks) {
        mobileMenuBtn.addEventListener('click', () => {
            navLinks.classList.toggle('active');
            // Toggle icon
            const icon = mobileMenuBtn.querySelector('i');
            if (navLinks.classList.contains('active')) {
                if (icon) icon.setAttribute('data-lucide', 'x');
            } else {
                if (icon) icon.setAttribute('data-lucide', 'menu');
            }
            if (window.lucide) lucide.createIcons();
        });
    }

    // Sidebar Toggle
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('active');
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 768 &&
                sidebar.classList.contains('active') &&
                !sidebar.contains(e.target) &&
                !sidebarToggle.contains(e.target)) {
                sidebar.classList.remove('active');
            }
        });
    }

});
