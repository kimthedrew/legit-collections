// Dark mode toggle improvements
document.addEventListener('DOMContentLoaded', () => {
    // Theme Toggle
    const themeToggle = document.createElement('button');
    themeToggle.id = 'theme-toggle';
    themeToggle.className = 'btn btn-light position-fixed bottom-0 end-0 m-3';
    themeToggle.setAttribute('aria-label', 'Toggle dark mode');
    themeToggle.innerHTML = '<i class="bi bi-moon-stars"></i>';
    document.body.appendChild(themeToggle);

    // Get current theme with fallback
    const getCurrentTheme = () => {
        const savedTheme = localStorage.getItem('theme');
        return savedTheme || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    };

    // Apply theme
    const applyTheme = (theme) => {
        document.documentElement.setAttribute('data-bs-theme', theme);
        themeToggle.innerHTML = theme === 'dark' ? 
            '<i class="bi bi-sun"></i>' : '<i class="bi bi-moon-stars"></i>';
        themeToggle.setAttribute('aria-pressed', theme === 'dark');
    };

    // Initialize
    let currentTheme = getCurrentTheme();
    applyTheme(currentTheme);

    // Toggle handler
    themeToggle.addEventListener('click', () => {
        currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
        applyTheme(currentTheme);
        localStorage.setItem('theme', currentTheme);
    });

    // Cart animation improvements
    document.querySelectorAll('.add-to-cart').forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            const card = button.closest('.product-card');
            
            // Add animation class
            card.classList.add('adding-to-cart');
            
            // Store original transform
            const originalTransform = card.style.transform;
            
            // Animate
            card.style.transform = 'scale(0.95)';
            
            setTimeout(() => {
                card.style.transform = originalTransform;
                window.location.href = button.href;
            }, 300);
        });
    });

    // Dynamic event delegation for delete/remove buttons
    document.body.addEventListener('click', (e) => {
        // Delete confirmation
        if (e.target.closest('.delete-btn')) {
            if (!confirm('Are you sure you want to delete this item?')) {
                e.preventDefault();
            }
        }
        
        // Remove from cart confirmation
        if (e.target.closest('.remove-from-cart')) {
            if (!confirm('Are you sure you want to remove this item from your cart?')) {
                e.preventDefault();
            }
        }
    });

    // Improved checkout form handling
    const checkoutForm = document.getElementById('checkout-form');
    if (checkoutForm) {
        checkoutForm.addEventListener('submit', (e) => {
            const submitBtn = e.target.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            const spinner = submitBtn.querySelector('.spinner-border');
            if (spinner) spinner.classList.remove('d-none');
            
            // Re-enable button if submission fails
            window.addEventListener('pageshow', () => {
                submitBtn.disabled = false;
                if (spinner) spinner.classList.add('d-none');
            });
        });
    }

    // Add smooth scroll to top
    const scrollToTop = document.createElement('button');
    scrollToTop.id = 'scroll-to-top';
    scrollToTop.className = 'btn btn-primary position-fixed bottom-0 end-0 m-3';
    scrollToTop.innerHTML = '<i class="bi bi-arrow-up"></i>';
    scrollToTop.setAttribute('aria-label', 'Scroll to top');
    document.body.appendChild(scrollToTop);

    scrollToTop.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });

    // Show/hide scroll to top button
    window.addEventListener('scroll', () => {
        scrollToTop.style.display = window.scrollY > 300 ? 'block' : 'none';
    });
});