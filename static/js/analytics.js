/**
 * Analytics module for Agenty frontend
 * Handles analytics, charts and statistics
 */

import Utils from './utils.js';
import API from './api.js';
import App from './app.js';

const AnalyticsModule = {
    // State
    charts: {},
    timeRange: '30days',
    
    // Initialize analytics interface
    init: function() {
        console.log('Initializing analytics module...');
        
        // Initialize event listeners
        this.initEventListeners();
        
        // Load analytics data
        this.loadAnalyticsData();
    },
    
    // Initialize event listeners
    initEventListeners: function() {
        // Time range filter
        const timeRangeFilter = document.getElementById('time-range-filter');
        if (timeRangeFilter) {
            timeRangeFilter.addEventListener('change', () => {
                this.timeRange = timeRangeFilter.value;
                this.loadAnalyticsData();
            });
        }
    },
    
    // Load analytics data
    loadAnalyticsData: async function() {
        // Show loading indicators
        this.showLoadingState();
        
        try {
            const analyticsData = await API.getAnalyticsData(this.timeRange);
            const topProducts = await API.getTopProducts(10);
            const wasteData = await API.getWasteData();
            
            // Render charts and data
            if (analyticsData) {
                this.renderCharts(analyticsData);
            } else {
                console.error("No analytics data received.");
                this.showError("Nie udało się załadować danych analitycznych.");
            }
            
            if (topProducts) {
                this.renderTopProducts(topProducts);
            } else {
                console.warn("No top products data received.");
            }

            if (wasteData) {
                this.renderWasteData(wasteData);
            } else {
                console.warn("No waste data received.");
            }

        } catch (error) {
            console.error('Error loading analytics data:', error);
            this.showError('Błąd ładowania danych analitycznych.');
        }
    },
    
    // Show loading state
    showLoadingState: function() {
        // Chart containers
        ['spending-chart', 'category-chart', 'consumption-chart'].forEach(id => {
            const container = document.getElementById(id);
            if (container) {
                container.innerHTML = '<div class="loading-indicator"><div class="spinner"></div><span>Ładowanie wykresu...</span></div>';
            }
        });
        
        // Top products list
        const topProductsList = document.getElementById('top-products-list');
        if (topProductsList) {
            topProductsList.innerHTML = '<li class="loading-item">Ładowanie danych...</li>';
        }
        
        // Waste container
        const wasteContainer = document.getElementById('waste-container');
        if (wasteContainer) {
            wasteContainer.innerHTML = '<div class="loading-indicator"><div class="spinner"></div><span>Ładowanie danych...</span></div>';
        }
    },
    
    // Show error message
    showError: function(message) {
        // Chart containers
        ['spending-chart', 'category-chart', 'consumption-chart'].forEach(id => {
            const container = document.getElementById(id);
            if (container) {
                container.innerHTML = `<div class="error-state">${message}</div>`;
            }
        });
        
        // Top products list
        const topProductsList = document.getElementById('top-products-list');
        if (topProductsList) {
            topProductsList.innerHTML = `<li class="error-item">${message}</li>`;
        }
        
        // Waste container
        const wasteContainer = document.getElementById('waste-container');
        if (wasteContainer) {
            wasteContainer.innerHTML = `<div class="error-state">${message}</div>`;
        }
    },
    
    // Render charts
    renderCharts: function(data) {
        // Destroy previous charts if exist
        this.destroyCharts();
        
        // Render spending chart
        if (data && data.spending) {
            this.renderSpendingChart(data.spending);
        } else {
            const canvas = document.getElementById('spending-chart');
            if (canvas) {
                canvas.parentElement.innerHTML = '<p class="text-center text-gray-500">Brak danych o wydatkach.</p>';
            }
        }
        
        // Render category chart
        if (data && data.categories) {
            this.renderCategoryChart(data.categories);
        } else {
            const canvas = document.getElementById('category-chart');
            if (canvas) {
                canvas.parentElement.innerHTML = '<p class="text-center text-gray-500">Brak danych o kategoriach.</p>';
            }
        }
        
        // Render consumption chart
        if (data && data.consumption) {
            this.renderConsumptionChart(data.consumption);
        } else {
            const canvas = document.getElementById('consumption-chart');
            if (canvas) {
                canvas.parentElement.innerHTML = '<p class="text-center text-gray-500">Brak danych o zużyciu.</p>';
            }
        }
    },
    
    // Destroy existing charts
    destroyCharts: function() {
        Object.values(this.charts).forEach(chart => {
            if (chart) {
                chart.destroy();
            }
        });
        this.charts = {};
    },
    
    // Render spending chart (line chart)
    renderSpendingChart: function(spendingData) {
        const canvas = document.getElementById('spending-chart');
        if (!canvas) return;
        
        // Clear container and add canvas
        const container = canvas.parentElement;
        container.innerHTML = '';
        const newCanvas = document.createElement('canvas');
        newCanvas.id = 'spending-chart';
        container.appendChild(newCanvas);
        
        // Create chart
        const ctx = newCanvas.getContext('2d');
        this.charts.spending = new Chart(ctx, {
            type: 'line',
            data: {
                labels: spendingData.labels,
                datasets: [{
                    label: 'Wydatki (PLN)',
                    data: spendingData.values,
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return Utils.formatCurrency(context.raw);
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return value + ' zł';
                            }
                        }
                    }
                }
            }
        });
    },
    
    // Render category chart (pie chart)
    renderCategoryChart: function(categoryData) {
        const canvas = document.getElementById('category-chart');
        if (!canvas) return;
        
        // Clear container and add canvas
        const container = canvas.parentElement;
        container.innerHTML = '';
        const newCanvas = document.createElement('canvas');
        newCanvas.id = 'category-chart';
        container.appendChild(newCanvas);
        
        // Create chart
        const ctx = newCanvas.getContext('2d');
        this.charts.category = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: categoryData.labels,
                datasets: [{
                    data: categoryData.values,
                    backgroundColor: [
                        '#007bff',
                        '#28a745',
                        '#ffc107',
                        '#dc3545',
                        '#6c757d',
                        '#17a2b8',
                        '#f8f9fa',
                        '#343a40',
                        '#6610f2',
                        '#fd7e14'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            boxWidth: 15,
                            padding: 10
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const value = context.raw;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${context.label}: ${percentage}% (${Utils.formatCurrency(value)})`;
                            }
                        }
                    }
                }
            }
        });
    },
    
    // Render consumption chart (heatmap)
    renderConsumptionChart: function(consumptionData) {
        const canvas = document.getElementById('consumption-chart');
        if (!canvas) return;
        
        // Clear container and add canvas
        const container = canvas.parentElement;
        container.innerHTML = '';
        const newCanvas = document.createElement('canvas');
        newCanvas.id = 'consumption-chart';
        container.appendChild(newCanvas);
        
        // Create chart
        const ctx = newCanvas.getContext('2d');
        this.charts.consumption = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: consumptionData.labels,
                datasets: consumptionData.datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            boxWidth: 15,
                            padding: 10
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Ilość zużycia'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Data'
                        }
                    }
                }
            }
        });
    },
    
    // Render top products list
    renderTopProducts: function(topProducts) {
        const topProductsList = document.getElementById('top-products-list');
        if (!topProductsList) return;
        
        // Clear list
        topProductsList.innerHTML = '';
        
        if (topProducts.length === 0) {
            topProductsList.innerHTML = '<li class="empty-item">Brak danych o produktach.</li>';
            return;
        }
        
        // Add top products to list
        topProducts.forEach((product, index) => {
            const li = document.createElement('li');
            li.className = 'top-product-item';
            
            li.innerHTML = `
                <span class="product-rank">#${index + 1}</span>
                <div class="product-info">
                    <span class="product-name">${product.name}</span>
                    <span class="product-category">${product.category || ''}</span>
                </div>
                <span class="purchase-count">${product.count} zakupów</span>
            `;
            
            topProductsList.appendChild(li);
        });
    },
    
    // Render waste data
    renderWasteData: function(wasteData) {
        const wasteContainer = document.getElementById('waste-container');
        if (!wasteContainer) return;
        
        // Clear container
        wasteContainer.innerHTML = '';
        
        if (wasteData.length === 0) {
            wasteContainer.innerHTML = '<div class="empty-state">Brak danych o marnotrawstwie.</div>';
            return;
        }
        
        // Add waste items to container
        wasteData.forEach(item => {
            const wasteItem = document.createElement('div');
            wasteItem.className = 'waste-item';
            
            wasteItem.innerHTML = `
                <div class="waste-info">
                    <span class="waste-product">${item.product}</span>
                    <span class="waste-date">${Utils.formatDate(item.date)}</span>
                </div>
                <span class="waste-quantity">${item.quantity} ${item.unit}</span>
            `;
            
            wasteContainer.appendChild(wasteItem);
        });
    },
    
    
    // Generate date labels based on selected time range
    generateDateLabels: function() {
        const dates = [];
        const today = new Date();
        let days;
        
        switch (this.timeRange) {
            case '7days':
                days = 7;
                break;
            case '30days':
                days = 30;
                break;
            case '90days':
                days = 90;
                break;
            case 'year':
                days = 365;
                break;
            default:
                days = 30;
        }
        
        // Generate dates (simplified for demo - in real app, use actual date points)
        if (days <= 30) {
            // Daily for 7 or 30 days
            for (let i = days - 1; i >= 0; i--) {
                const date = new Date();
                date.setDate(today.getDate() - i);
                dates.push(date.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' }));
            }
        } else if (days <= 90) {
            // Weekly for 90 days
            for (let i = 0; i < 13; i++) {
                const date = new Date();
                date.setDate(today.getDate() - i * 7);
                dates.push(date.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' }));
            }
        } else {
            // Monthly for year
            for (let i = 0; i < 12; i++) {
                const date = new Date();
                date.setMonth(today.getMonth() - i);
                dates.push(date.toLocaleDateString('pl-PL', { month: 'long' }));
            }
            dates.reverse();
        }
        
        return dates;
    }
};

// Initialize module when page is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Initialize only if analytics page is active
    if (window.location.hash === '#analytics') {
        AnalyticsModule.init();
    }
    
    // Listen for hash changes
    window.addEventListener('hashchange', () => {
        if (window.location.hash === '#analytics') {
            AnalyticsModule.init();
        }
    });
});

// Export for ES6 modules
export default AnalyticsModule;
