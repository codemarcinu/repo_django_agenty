// Enhanced UI Components for Django Agenty
// Phase 3: UX Enhancements Implementation

class ToastManager {
  constructor() {
    this.container = this.createContainer();
    this.toasts = [];
  }

  createContainer() {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    return container;
  }

  show(message, type = 'info', duration = 5000) {
    const toast = document.createElement('div');
    const toastId = Date.now() + Math.random();
    const bgColor = {
      'success': 'toast-success',
      'error': 'toast-error',
      'warning': 'toast-warning',
      'info': 'toast-info'
    }[type] || 'toast-info';

    const icon = {
      'success': '✅',
      'error': '❌',
      'warning': '⚠️',
      'info': 'ℹ️'
    }[type] || 'ℹ️';

    toast.className = `toast ${bgColor} animate-slide-in-right`;
    toast.id = `toast-${toastId}`;
    toast.innerHTML = `
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <span class="text-lg">${icon}</span>
          <span class="font-medium">${message}</span>
        </div>
        <button onclick="UI.toast.hide('${toastId}')" class="ml-4 text-white/80 hover:text-white transition-colors duration-200">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
          </svg>
        </button>
      </div>
    `;

    this.container.appendChild(toast);
    this.toasts.push({ id: toastId, element: toast, timeout: null });

    // Auto-hide after duration
    if (duration > 0) {
      const timeout = setTimeout(() => {
        this.hide(toastId);
      }, duration);
      this.toasts.find(t => t.id === toastId).timeout = timeout;
    }

    return toastId;
  }

  hide(toastId) {
    const toastData = this.toasts.find(t => t.id === toastId);
    if (!toastData) return;

    const toast = toastData.element;

    // Clear timeout if exists
    if (toastData.timeout) {
      clearTimeout(toastData.timeout);
    }

    // Animate out
    toast.classList.remove('animate-slide-in-right');
    toast.classList.add('animate-slide-up');

    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
      this.toasts = this.toasts.filter(t => t.id !== toastId);
    }, 300);
  }

  clear() {
    this.toasts.forEach(toast => {
      if (toast.timeout) clearTimeout(toast.timeout);
      if (toast.element.parentNode) {
        toast.element.parentNode.removeChild(toast.element);
      }
    });
    this.toasts = [];
  }
}

// Loading States Manager
class LoadingManager {
  constructor() {
    this.activeLoadings = new Map();
  }

  show(element, text = 'Przetwarzanie...') {
    const id = element.id || `loading-${Date.now()}`;
    element.id = id;

    if (this.activeLoadings.has(id)) {
      return id;
    }

    const originalContent = element.innerHTML;
    const originalText = element.textContent;

    element.dataset.originalContent = originalContent;
    element.dataset.originalText = originalText;

    element.classList.add('btn-loading', 'cursor-not-allowed');
    element.innerHTML = `
      <svg class="animate-spin -ml-1 mr-3 h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      ${text}
    `;

    this.activeLoadings.set(id, { element, originalContent, originalText });

    return id;
  }

  hide(elementOrId) {
    let element, id;

    if (typeof elementOrId === 'string') {
      id = elementOrId;
      element = document.getElementById(id);
    } else {
      element = elementOrId;
      id = element.id;
    }

    if (!element || !this.activeLoadings.has(id)) {
      return false;
    }

    const loadingData = this.activeLoadings.get(id);

    element.classList.remove('btn-loading', 'cursor-not-allowed');
    element.innerHTML = loadingData.originalContent;

    this.activeLoadings.delete(id);

    return true;
  }

  hideAll() {
    this.activeLoadings.forEach((data, id) => {
      this.hide(id);
    });
  }
}

// Form Validation Manager
class FormValidator {
  constructor(form) {
    this.form = form;
    this.rules = new Map();
    this.errors = new Map();
  }

  addRule(fieldName, validator, message) {
    if (!this.rules.has(fieldName)) {
      this.rules.set(fieldName, []);
    }
    this.rules.get(fieldName).push({ validator, message });
  }

  validate() {
    this.clearErrors();
    let isValid = true;

    for (const [fieldName, rules] of this.rules) {
      const field = this.form.querySelector(`[name="${fieldName}"]`);
      if (!field) continue;

      for (const rule of rules) {
        if (!rule.validator(field.value, field)) {
          this.showError(field, rule.message);
          isValid = false;
          break;
        }
      }
    }

    return isValid;
  }

  showError(field, message) {
    const fieldName = field.name;
    this.errors.set(fieldName, message);

    field.classList.add('error');

    let errorElement = field.parentNode.querySelector('.form-error');
    if (!errorElement) {
      errorElement = document.createElement('div');
      errorElement.className = 'form-error';
      field.parentNode.appendChild(errorElement);
    }
    errorElement.textContent = message;
  }

  clearErrors() {
    for (const [fieldName, message] of this.errors) {
      const field = this.form.querySelector(`[name="${fieldName}"]`);
      if (field) {
        field.classList.remove('error');
        const errorElement = field.parentNode.querySelector('.form-error');
        if (errorElement) {
          errorElement.remove();
        }
      }
    }
    this.errors.clear();
  }

  // Common validators
  static required(message = 'To pole jest wymagane') {
    return (value) => {
      return value.trim().length > 0;
    };
  }

  static email(message = 'Wprowadź prawidłowy adres email') {
    return (value) => {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      return emailRegex.test(value);
    };
  }

  static minLength(length, message = `Minimum ${length} znaków`) {
    return (value) => {
      return value.length >= length;
    };
  }

  static maxLength(length, message = `Maksimum ${length} znaków`) {
    return (value) => {
      return value.length <= length;
    };
  }

  static pattern(regex, message = 'Nieprawidłowy format') {
    return (value) => {
      return regex.test(value);
    };
  }
}

// File Upload with Drag & Drop
class FileUploader {
  constructor(dropArea, options = {}) {
    this.dropArea = dropArea;
    this.options = {
      maxFiles: 5,
      maxSize: 10 * 1024 * 1024, // 10MB
      acceptedTypes: ['image/jpeg', 'image/png', 'application/pdf'],
      onUpload: null,
      onError: null,
      ...options
    };

    this.files = [];
    this.setupEventListeners();
  }

  setupEventListeners() {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      this.dropArea.addEventListener(eventName, this.preventDefaults.bind(this), false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
      this.dropArea.addEventListener(eventName, this.highlight.bind(this), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
      this.dropArea.addEventListener(eventName, this.unhighlight.bind(this), false);
    });

    this.dropArea.addEventListener('drop', this.handleDrop.bind(this), false);

    // Click to upload
    this.dropArea.addEventListener('click', () => {
      const input = document.createElement('input');
      input.type = 'file';
      input.multiple = this.options.maxFiles > 1;
      input.accept = this.options.acceptedTypes.join(',');
      input.onchange = (e) => this.handleFiles(e.target.files);
      input.click();
    });
  }

  preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  highlight() {
    this.dropArea.classList.add('dragover');
  }

  unhighlight() {
    this.dropArea.classList.remove('dragover');
  }

  handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    this.handleFiles(files);
  }

  handleFiles(files) {
    [...files].forEach(file => {
      if (this.validateFile(file)) {
        this.files.push(file);
        this.options.onUpload && this.options.onUpload(file);
      }
    });
  }

  validateFile(file) {
    if (this.files.length >= this.options.maxFiles) {
      this.options.onError && this.options.onError(`Maksimum ${this.options.maxFiles} plików`);
      return false;
    }

    if (file.size > this.options.maxSize) {
      this.options.onError && this.options.onError(`Plik ${file.name} jest za duży (max ${this.options.maxSize / 1024 / 1024}MB)`);
      return false;
    }

    if (!this.options.acceptedTypes.includes(file.type)) {
      this.options.onError && this.options.onError(`Typ pliku ${file.type} nie jest obsługiwany`);
      return false;
    }

    return true;
  }

  clear() {
    this.files = [];
  }

  getFiles() {
    return this.files;
  }
}

// Progress Bar Component
class ProgressBar {
  constructor(container, options = {}) {
    this.container = container;
    this.options = {
      showPercentage: true,
      animationDuration: 300,
      ...options
    };

    this.progress = 0;
    this.createProgressBar();
  }

  createProgressBar() {
    this.container.innerHTML = `
      <div class="progress-bar">
        <div class="progress-fill" style="width: 0%"></div>
      </div>
      ${this.options.showPercentage ? '<div class="text-sm text-gray-600 mt-2 text-center progress-text">0%</div>' : ''}
    `;

    this.fillElement = this.container.querySelector('.progress-fill');
    this.textElement = this.container.querySelector('.progress-text');
  }

  setProgress(progress) {
    this.progress = Math.max(0, Math.min(100, progress));

    this.fillElement.style.transition = `width ${this.options.animationDuration}ms ease`;
    this.fillElement.style.width = `${this.progress}%`;

    if (this.textElement) {
      this.textElement.textContent = `${Math.round(this.progress)}%`;
    }
  }

  increment(amount = 1) {
    this.setProgress(this.progress + amount);
  }

  complete() {
    this.setProgress(100);
  }

  reset() {
    this.setProgress(0);
  }
}

// Initialize UI Components
document.addEventListener('DOMContentLoaded', () => {
  // Initialize global UI object
  window.UI = window.UI || {};

  // Initialize toast system
  if (!window.UI.toast) {
    window.UI.toast = new ToastManager();
  }

  // Initialize loading system
  if (!window.UI.loading) {
    window.UI.loading = new LoadingManager();
  }

  // Enhanced showToast function
  const originalShowToast = window.UI.showToast;
  window.UI.showToast = (message, type = 'info', duration = 5000) => {
    return window.UI.toast.show(message, type, duration);
  };

  // Enhanced showLoading function
  const originalShowLoading = window.UI.showLoading;
  window.UI.showLoading = (element, show = true, text = 'Przetwarzanie...') => {
    if (show) {
      return window.UI.loading.show(element, text);
    } else {
      return window.UI.loading.hide(element);
    }
  };

  // Auto-initialize components
  document.querySelectorAll('.file-upload-area').forEach(area => {
    new FileUploader(area, {
      onUpload: (file) => {
        console.log('File uploaded:', file.name);
        UI.toast.show(`Plik ${file.name} został dodany`, 'success');
      },
      onError: (error) => {
        console.error('Upload error:', error);
        UI.toast.show(error, 'error');
      }
    });
  });

  // Auto-initialize progress bars
  document.querySelectorAll('[data-progress]').forEach(container => {
    const progressBar = new ProgressBar(container);
    const initialProgress = parseInt(container.dataset.progress) || 0;
    progressBar.setProgress(initialProgress);
  });

  // Auto-initialize form validation
  document.querySelectorAll('[data-validate]').forEach(form => {
    const validator = new FormValidator(form);

    // Add common validation rules
    form.querySelectorAll('[data-required]').forEach(field => {
      validator.addRule(field.name, FormValidator.required(), field.dataset.required || 'To pole jest wymagane');
    });

    form.querySelectorAll('[data-email]').forEach(field => {
      validator.addRule(field.name, FormValidator.email(), field.dataset.email || 'Wprowadź prawidłowy adres email');
    });

    form.querySelectorAll('[data-minlength]').forEach(field => {
      const length = parseInt(field.dataset.minlength);
      validator.addRule(field.name, FormValidator.minLength(length), `Minimum ${length} znaków`);
    });

    // Validate on submit
    form.addEventListener('submit', (e) => {
      if (!validator.validate()) {
        e.preventDefault();
        UI.toast.show('Wypełnij wszystkie wymagane pola poprawnie', 'error');
      }
    });

    // Clear errors on input
    form.addEventListener('input', (e) => {
      if (validator.errors.has(e.target.name)) {
        validator.clearErrors();
      }
    });
  });

  console.log('UI Components initialized successfully');
});

// Dark Mode Manager
class DarkModeManager {
  constructor() {
    this.currentTheme = this.getSavedTheme() || this.getSystemTheme();
    this.init();
  }

  init() {
    this.applyTheme(this.currentTheme);

    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      if (!this.getSavedTheme()) {
        const newTheme = e.matches ? 'dark' : 'light';
        this.applyTheme(newTheme);
      }
    });
  }

  getSystemTheme() {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  getSavedTheme() {
    return localStorage.getItem('theme');
  }

  applyTheme(theme) {
    this.currentTheme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);

    // Update theme icon
    this.updateThemeIcon(theme);

    // Dispatch custom event
    window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme } }));
  }

  updateThemeIcon(theme) {
    const themeIcon = document.getElementById('theme-icon');
    if (themeIcon) {
      themeIcon.textContent = theme === 'dark' ? '☀️' : '🌙';
    }
  }

  toggle() {
    const newTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
    this.applyTheme(newTheme);
    return newTheme;
  }

  isDark() {
    return this.currentTheme === 'dark';
  }
}

// Initialize Dark Mode
document.addEventListener('DOMContentLoaded', () => {
  // Initialize dark mode
  if (!window.UI.darkMode) {
    window.UI.darkMode = new DarkModeManager();
  }

  // Add dark mode toggle function to global UI
  window.UI.toggleDarkMode = () => {
    const newTheme = window.UI.darkMode.toggle();
    UI.toast.show(`Przełączono na ${newTheme === 'dark' ? 'ciemny' : 'jasny'} motyw`, 'info');
    return newTheme;
  };

  console.log('Dark Mode initialized successfully');
});
