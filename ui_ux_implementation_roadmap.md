
# MAPA DROGOWA IMPLEMENTACJI UI/UX - DJANGO AGENTY

## FAZA 1: DESIGN SYSTEM I PODSTAWY (1-2 TYGODNIE)

### 1.1 Tailwind CSS Configuration
```javascript
// tailwind.config.js
module.exports = {
  content: ['./templates/**/*.html', './static/**/*.js'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe', 
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a'
        },
        gray: {
          50: '#f9fafb',
          100: '#f3f4f6',
          200: '#e5e7eb',
          300: '#d1d5db',
          400: '#9ca3af',
          500: '#6b7280',
          600: '#4b5563',
          700: '#374151',
          800: '#1f2937',
          900: '#111827'
        },
        success: {
          50: '#ecfdf5',
          500: '#10b981',
          600: '#059669'
        },
        warning: {
          50: '#fffbeb', 
          500: '#f59e0b',
          600: '#d97706'
        },
        error: {
          50: '#fef2f2',
          500: '#ef4444',
          600: '#dc2626'
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif']
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem'
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'pulse-gentle': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite'
      }
    }
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography')
  ]
}
```

### 1.2 Base Template Refactor
- Implementacja nowoczesnej struktury HTML5
- Mobile-first responsive navigation
- Sticky header z proper z-index management
- Toast notification system
- Loading states framework

### 1.3 Component Library
```html
<!-- Button Component -->
<button class="btn btn-primary">
  <span>Primary Action</span>
  <svg class="btn-icon">...</svg>
</button>

<!-- Card Component -->
<div class="card">
  <div class="card-header">
    <h3 class="card-title">Title</h3>
  </div>
  <div class="card-body">Content</div>
  <div class="card-footer">Actions</div>
</div>

<!-- Input Component -->
<div class="form-group">
  <label class="form-label">Label</label>
  <input class="form-input" type="text">
  <span class="form-error">Error message</span>
</div>
```

### 1.4 Utility Classes System
```css
/* Custom utilities */
.btn {
  @apply inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 transition-colors duration-200;
}

.btn-primary {
  @apply bg-primary-600 text-white hover:bg-primary-700 focus:ring-primary-500;
}

.card {
  @apply bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden;
}

.form-input {
  @apply block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500;
}
```

## FAZA 2: RESPONSYWNOŚĆ I LAYOUT (1-2 TYGODNIE)

### 2.1 Mobile-First Grid System
```html
<!-- Responsive Grid -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 md:gap-6">
  <div class="col-span-1 md:col-span-2 lg:col-span-1">Priority content</div>
  <div>Regular content</div>
</div>

<!-- Flexible Containers -->
<div class="container mx-auto px-4 sm:px-6 lg:px-8 max-w-7xl">
  Content with proper margins
</div>
```

### 2.2 Navigation Patterns
```html
<!-- Desktop/Mobile Hybrid Nav -->
<nav class="bg-white shadow-sm">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="flex justify-between h-16">
      <!-- Logo -->
      <div class="flex items-center">
        <img class="h-8 w-8" src="logo.svg" alt="Agenty">
        <span class="ml-2 text-xl font-semibold">Agenty</span>
      </div>

      <!-- Desktop Nav -->
      <div class="hidden md:flex space-x-8">
        <a href="/" class="nav-link">Dashboard</a>
        <a href="/chat/" class="nav-link">Chat</a>
        <a href="/inventory/" class="nav-link">Magazyn</a>
      </div>

      <!-- Mobile Menu Button -->
      <div class="md:hidden flex items-center">
        <button class="mobile-menu-btn">
          <svg class="h-6 w-6">...</svg>
        </button>
      </div>
    </div>
  </div>

  <!-- Mobile Menu -->
  <div class="md:hidden" id="mobile-menu">
    <div class="px-2 pt-2 pb-3 space-y-1">
      <a href="/" class="mobile-nav-link">Dashboard</a>
      <a href="/chat/" class="mobile-nav-link">Chat</a>
      <a href="/inventory/" class="mobile-nav-link">Magazyn</a>
    </div>
  </div>
</nav>
```

### 2.3 Responsive Typography Scale
```css
.text-display-1 { @apply text-4xl md:text-5xl lg:text-6xl font-bold; }
.text-display-2 { @apply text-3xl md:text-4xl lg:text-5xl font-bold; }
.text-headline { @apply text-2xl md:text-3xl font-semibold; }
.text-title { @apply text-xl md:text-2xl font-semibold; }
.text-body { @apply text-base md:text-lg; }
.text-caption { @apply text-sm md:text-base text-gray-600; }
```

## FAZA 3: USER EXPERIENCE ENHANCEMENTS (2-3 TYGODNIE)

### 3.1 Loading States & Skeletons
```html
<!-- Skeleton Component -->
<div class="animate-pulse">
  <div class="h-4 bg-gray-200 rounded w-3/4 mb-4"></div>
  <div class="h-4 bg-gray-200 rounded w-1/2 mb-4"></div>
  <div class="h-4 bg-gray-200 rounded w-full"></div>
</div>

<!-- Loading Button -->
<button class="btn btn-primary" :disabled="loading">
  <svg v-if="loading" class="animate-spin -ml-1 mr-3 h-5 w-5 text-white">...</svg>
  <span>{{ loading ? 'Processing...' : 'Submit' }}</span>
</button>
```

### 3.2 Form Enhancements
```html
<!-- Enhanced Form with Validation -->
<form class="space-y-6" method="post">
  {% csrf_token %}

  <!-- File Upload with Drag & Drop -->
  <div class="file-upload-area" 
       x-data="fileUpload()"
       @dragover.prevent
       @drop.prevent="handleDrop($event)">
    <input type="file" class="hidden" x-ref="fileInput" @change="handleFileSelect">
    <div class="text-center p-6">
      <svg class="mx-auto h-12 w-12 text-gray-400">...</svg>
      <p class="mt-2 text-sm text-gray-600">
        <button type="button" @click="$refs.fileInput.click()" class="font-medium text-primary-600 hover:text-primary-500">
          Upload a file
        </button>
        or drag and drop
      </p>
      <p class="text-xs text-gray-500">PNG, JPG, PDF up to 10MB</p>
    </div>
  </div>

  <!-- Progress Bar -->
  <div x-show="uploading" class="w-full bg-gray-200 rounded-full h-2">
    <div class="bg-primary-600 h-2 rounded-full transition-all duration-300" 
         :style="`width: ${progress}%`"></div>
  </div>

  <button type="submit" class="btn btn-primary w-full">
    Upload Receipt
  </button>
</form>
```

### 3.3 Micro-interactions
```css
/* Button Hover Effects */
.btn {
  @apply transform transition-all duration-200 ease-in-out;
}

.btn:hover {
  @apply -translate-y-0.5 shadow-lg;
}

.btn:active {
  @apply translate-y-0 shadow-md;
}

/* Card Hover Effects */
.card-hover {
  @apply transition-all duration-300 ease-in-out;
}

.card-hover:hover {
  @apply shadow-xl -translate-y-1;
}

/* Focus States */
.focus-visible {
  @apply ring-2 ring-primary-500 ring-offset-2;
}
```

### 3.4 Toast Notification System
```javascript
// toast.js
class ToastManager {
  constructor() {
    this.container = document.getElementById('toast-container');
  }

  show(message, type = 'info', duration = 5000) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type} animate-slide-up`;
    toast.innerHTML = `
      <div class="flex items-center justify-between">
        <div class="flex items-center">
          ${this.getIcon(type)}
          <span class="ml-3 text-sm font-medium">${message}</span>
        </div>
        <button onclick="this.parentElement.parentElement.remove()" 
                class="ml-4 text-gray-400 hover:text-gray-600">
          <svg class="w-4 h-4">...</svg>
        </button>
      </div>
    `;

    this.container.appendChild(toast);

    if (duration > 0) {
      setTimeout(() => {
        if (toast.parentElement) {
          toast.remove();
        }
      }, duration);
    }
  }

  getIcon(type) {
    const icons = {
      success: '<svg class="w-5 h-5 text-green-400">...</svg>',
      error: '<svg class="w-5 h-5 text-red-400">...</svg>',
      warning: '<svg class="w-5 h-5 text-yellow-400">...</svg>',
      info: '<svg class="w-5 h-5 text-blue-400">...</svg>'
    };
    return icons[type] || icons.info;
  }
}

// Initialize
const toast = new ToastManager();
```

## FAZA 4: ADVANCED FEATURES (2-4 TYGODNIE)

### 4.1 Dark Mode Implementation
```css
/* Dark mode color scheme */
:root {
  --color-bg-primary: #ffffff;
  --color-bg-secondary: #f9fafb;
  --color-text-primary: #111827;
  --color-text-secondary: #6b7280;
}

[data-theme="dark"] {
  --color-bg-primary: #1f2937;
  --color-bg-secondary: #111827;
  --color-text-primary: #f9fafb;
  --color-text-secondary: #9ca3af;
}

.bg-primary { background-color: var(--color-bg-primary); }
.text-primary { color: var(--color-text-primary); }
```

```javascript
// Dark mode toggle
function toggleDarkMode() {
  const theme = document.documentElement.getAttribute('data-theme');
  const newTheme = theme === 'dark' ? 'light' : 'dark';

  document.documentElement.setAttribute('data-theme', newTheme);
  localStorage.setItem('theme', newTheme);
}

// Initialize theme
const savedTheme = localStorage.getItem('theme') || 
  (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
document.documentElement.setAttribute('data-theme', savedTheme);
```

### 4.2 Progressive Web App Features
```json
// manifest.json
{
  "name": "Agenty - Inteligentny Asystent AI",
  "short_name": "Agenty",
  "description": "System zarządzania domem z AI",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#3b82f6",
  "icons": [
    {
      "src": "/static/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/static/icons/icon-512.png", 
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

### 4.3 Advanced Animations
```css
/* Staggered animations */
@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.stagger-children > * {
  animation: slideInUp 0.6s ease-out forwards;
}

.stagger-children > *:nth-child(1) { animation-delay: 0.1s; }
.stagger-children > *:nth-child(2) { animation-delay: 0.2s; }
.stagger-children > *:nth-child(3) { animation-delay: 0.3s; }

/* Loading spinner */
@keyframes spin {
  to { transform: rotate(360deg); }
}

.spinner {
  animation: spin 1s linear infinite;
}
```

### 4.4 Accessibility Improvements
```html
<!-- ARIA Labels and Roles -->
<nav role="navigation" aria-label="Main navigation">
  <ul role="menubar">
    <li role="none">
      <a role="menuitem" href="/" aria-current="page">Dashboard</a>
    </li>
  </ul>
</nav>

<!-- Skip Links -->
<a href="#main-content" class="skip-link">Skip to main content</a>

<!-- Focus Management -->
<div class="modal" role="dialog" aria-labelledby="modal-title" aria-modal="true">
  <h2 id="modal-title">Modal Title</h2>
  <button aria-label="Close modal">×</button>
</div>
```

## METRYKI SUKCESU

### Performance Metrics
- Lighthouse Score: > 95/100
- First Contentful Paint: < 1.5s  
- Cumulative Layout Shift: < 0.1
- Time to Interactive: < 3s

### UX Metrics
- Mobile Usability Score: 100/100
- Accessibility Score: > 95/100
- Cross-browser compatibility: 99%
- User Task Completion Rate: > 95%

### Quality Metrics
- Code maintainability: A grade
- CSS specificity conflicts: 0
- Template duplication: < 5%
- Component reusability: > 80%
