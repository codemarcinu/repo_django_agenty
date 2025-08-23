/**
 * Receipts module for Agenty frontend
 * Handles receipt upload and processing
 */

import Utils from './utils.js';
import API from './api.js';
import App from './app.js';

const ReceiptsModule = {
    // State
    currentReceiptId: null,
    uploadProgress: 0,
    receiptsList: [],
    
    // Initialize receipts interface
    init: function() {
        console.log('Initializing receipts module...');
        
        // Initialize event listeners
        this.initEventListeners();
        
        // Load receipts list
        this.loadReceiptsList();
    },
    
    // Initialize event listeners
    initEventListeners: function() {
        // Receipt upload area
        const uploadArea = document.getElementById('receipt-upload-area');
        const fileInput = document.getElementById('receipt-file-upload');
        const selectFileBtn = document.getElementById('select-receipt-btn');
        
        if (uploadArea && fileInput) {
            // File selection button
            if (selectFileBtn) {
                selectFileBtn.addEventListener('click', () => {
                    fileInput.click();
                });
            }
            
            // File input change
            fileInput.addEventListener('change', (event) => {
                if (event.target.files.length > 0) {
                    this.handleFileUpload(event.target.files[0]);
                }
            });
            
            // Drag and drop
            uploadArea.addEventListener('dragover', (event) => {
                event.preventDefault();
                uploadArea.querySelector('.upload-container').classList.add('drag-over');
            });
            
            uploadArea.addEventListener('dragleave', (event) => {
                event.preventDefault();
                uploadArea.querySelector('.upload-container').classList.remove('drag-over');
            });
            
            uploadArea.addEventListener('drop', (event) => {
                event.preventDefault();
                uploadArea.querySelector('.upload-container').classList.remove('drag-over');
                
                if (event.dataTransfer.files.length > 0) {
                    this.handleFileUpload(event.dataTransfer.files[0]);
                }
            });
        }
    },
    
    // Handle file upload
    handleFileUpload: function(file) {
        // Validate file
        if (!this.validateFile(file)) {
            return;
        }
        
        // Show processing status
        this.showProcessingStatus(file.name);
        
        // Reset progress
        this.updateProgress(0);
        
        // Upload receipt
        this.uploadReceipt(file);
    },
    
    // Validate file
    validateFile: function(file) {
        // Check file type
        const validTypes = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'];
        if (!validTypes.includes(file.type)) {
            Utils.showToast('Nieprawidłowy format pliku. Obsługiwane formaty: PDF, JPG, PNG, WebP.', 'error');
            return false;
        }
        
        // Check file size (max 10MB)
        if (file.size > 10 * 1024 * 1024) {
            Utils.showToast('Plik jest za duży. Maksymalny rozmiar: 10MB.', 'error');
            return false;
        }
        
        return true;
    },
    
    // Show processing status
    showProcessingStatus: function(fileName) {
        // Hide upload area
        const uploadArea = document.getElementById('receipt-upload-area');
        if (uploadArea) {
            uploadArea.style.display = 'none';
        }
        
        // Show processing status
        const processingStatus = document.getElementById('receipt-processing-status');
        if (processingStatus) {
            // Update status text
            const statusText = document.getElementById('receipt-status-text');
            if (statusText) {
                statusText.textContent = `Przesyłanie pliku: ${fileName}`;
            }
            
            // Reset progress bar
            const progressBar = document.getElementById('receipt-progress-bar');
            if (progressBar) {
                progressBar.style.width = '0%';
            }
            
            // Show status container
            processingStatus.style.display = 'block';
        }
    },
    
    // Update progress bar
    updateProgress: function(progress) {
        this.uploadProgress = progress;
        
        const progressBar = document.getElementById('receipt-progress-bar');
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
        }
        
        const statusText = document.getElementById('receipt-status-text');
        if (statusText && progress === 100) {
            statusText.textContent = 'Przetwarzanie paragonu...';
        }
    },
    
    // Upload receipt
    uploadReceipt: async function(file) {
        try {
            const response = await API.uploadReceipt(file, (progress) => {
                this.updateProgress(progress);
            });
            
            // Update current receipt ID
            this.currentReceiptId = response.receipt_id;
            
            // Update processing status
            const processingStatus = document.getElementById('receipt-processing-status');
            if (processingStatus) {
                processingStatus.dataset.receiptId = response.receipt_id;
            }
            
            // Start polling for status
            this.pollReceiptStatus(response.receipt_id);
            
            // Show success message
            Utils.showToast('Paragon został przesłany. Trwa przetwarzanie...', 'info');
        } catch (error) {
            console.error('Error uploading receipt:', error);
            
            // Show error message
            Utils.showToast('Błąd przesyłania paragonu: ' + error.message, 'error');
            
            // Hide processing status and show upload area
            this.resetUploadArea();
        }
    },
    
    // Poll receipt status
    pollReceiptStatus: function(receiptId) {
        const statusCheckInterval = setInterval(async () => {
            try {
                const response = await API.getReceiptStatus(receiptId);
                
                // Update status display
                this.updateReceiptStatus(receiptId, response.status, response.error_message);
                
                // If processing is complete or errored, stop polling
                if (response.status === 'completed' || response.status === 'error' || response.status === 'review_pending') {
                    clearInterval(statusCheckInterval);
                    
                    // If completed, reload receipts list
                    if (response.status === 'completed') {
                        setTimeout(() => {
                            this.loadReceiptsList();
                            this.resetUploadArea();
                        }, 2000);
                    } else if (response.status === 'error') {
                        // Show error and reset
                        Utils.showToast('Błąd przetwarzania paragonu: ' + response.error_message, 'error');
                        setTimeout(() => {
                            this.resetUploadArea();
                        }, 2000);
                    } else if (response.status === 'review_pending') {
                        // Show success and reset
                        Utils.showToast('Paragon wymaga weryfikacji.', 'info');
                        setTimeout(() => {
                            this.resetUploadArea();
                            // Redirect to review page if available
                            if (response.redirect_url) {
                                window.location.href = response.redirect_url;
                            }
                        }, 2000);
                    }
                }
            } catch (error) {
                console.error('Error checking receipt status:', error);
                
                // If error occurs during polling, show message but continue polling
                Utils.showToast('Błąd pobierania statusu paragonu.', 'error');
            }
        }, 3000); // Check every 3 seconds
    },
    
    // Update receipt status display
    updateReceiptStatus: function(receiptId, status, errorMessage) {
        const statusText = document.getElementById('receipt-status-text');
        if (!statusText) return;
        
        // Get status display text
        let statusDisplay = '';
        
        switch (status) {
            case 'pending':
                statusDisplay = 'Oczekiwanie na przetwarzanie...';
                break;
            case 'processing':
                statusDisplay = 'Przetwarzanie paragonu...';
                break;
            case 'ocr_in_progress':
                statusDisplay = 'Rozpoznawanie tekstu (OCR)...';
                break;
            case 'ocr_completed':
                statusDisplay = 'Tekst rozpoznany, analizowanie zawartości...';
                break;
            case 'parsing_in_progress':
                statusDisplay = 'Analizowanie struktury paragonu...';
                break;
            case 'parsing_completed':
                statusDisplay = 'Struktura rozpoznana, dopasowywanie produktów...';
                break;
            case 'matching_in_progress':
                statusDisplay = 'Dopasowywanie produktów...';
                break;
            case 'matching_completed':
                statusDisplay = 'Produkty rozpoznane, aktualizowanie spiżarni...';
                break;
            case 'finalizing_inventory':
                statusDisplay = 'Finalizowanie aktualizacji spiżarni...';
                break;
            case 'review_pending':
                statusDisplay = 'Paragon wymaga weryfikacji!';
                break;
            case 'completed':
                statusDisplay = 'Przetwarzanie zakończone pomyślnie!';
                break;
            case 'error':
                statusDisplay = 'Wystąpił błąd: ' + (errorMessage || 'Nieznany błąd');
                break;
            default:
                statusDisplay = status;
        }
        
        // Update status text
        statusText.textContent = statusDisplay;
        
        // Also update in receipts table if visible
        const statusCell = document.querySelector(`#receipt-${receiptId} .receipt-status`);
        if (statusCell) {
            // Remove all status classes
            statusCell.classList.remove('pending', 'processing', 'review', 'completed', 'error');
            
            // Add new status class
            statusCell.classList.add(this.getStatusClass(status));
            
            // Update text
            statusCell.textContent = this.getStatusDisplayName(status);
        }
    },
    
    // Reset upload area
    resetUploadArea: function() {
        // Hide processing status
        const processingStatus = document.getElementById('receipt-processing-status');
        if (processingStatus) {
            processingStatus.style.display = 'none';
        }
        
        // Show upload area
        const uploadArea = document.getElementById('receipt-upload-area');
        if (uploadArea) {
            uploadArea.style.display = 'block';
        }
        
        // Reset file input
        const fileInput = document.getElementById('receipt-file-upload');
        if (fileInput) {
            fileInput.value = '';
        }
        
        // Reset progress
        this.uploadProgress = 0;
    },
    
    // Load receipts list
    loadReceiptsList: async function() {
        const tableBody = document.getElementById('receipts-table-body');
        if (!tableBody) return;
        
        // Show loading state
        tableBody.innerHTML = '<tr><td colspan="5" class="loading-cell">Ładowanie paragonów...</td></tr>';
        
        try {
            const response = await API.getRecentReceipts(50); // Get up to 50 receipts
            this.renderReceiptsList(response);
        } catch (error) {
            console.error('Error loading receipts:', error);
            tableBody.innerHTML = '<tr><td colspan="5" class="loading-cell">Błąd ładowania paragonów.</td></tr>';
        }
    },
    
    // Render receipts list
    renderReceiptsList: function(receipts) {
        const tableBody = document.getElementById('receipts-table-body');
        if (!tableBody) return;
        
        // Store receipts
        this.receiptsList = receipts;
        
        // Clear table
        tableBody.innerHTML = '';
        
        if (receipts.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" class="loading-cell">Brak paragonów.</td></tr>';
            return;
        }
        
        // Add receipts to table
        receipts.forEach(receipt => {
            const row = document.createElement('tr');
            row.id = `receipt-${receipt.id}`;
            
            row.innerHTML = `
                <td>${Utils.formatDate(receipt.purchased_at, true)}</td>
                <td>${receipt.store_name || 'Nieznany sklep'}</td>
                <td>${Utils.formatCurrency(receipt.total, receipt.currency)}</td>
                <td><span class="receipt-status ${this.getStatusClass(receipt.status)}">${this.getStatusDisplayName(receipt.status)}</span></td>
                <td>
                    <div class="action-icons">
                        <span class="action-icon view-receipt" title="Zobacz szczegóły">
                            <i class="fas fa-eye"></i>
                        </span>
                        <span class="action-icon delete-receipt" title="Usuń paragon">
                            <i class="fas fa-trash"></i>
                        </span>
                    </div>
                </td>
            `;
            
            // Add event listeners for actions
            row.querySelector('.view-receipt').addEventListener('click', () => {
                this.viewReceiptDetails(receipt.id);
            });
            
            row.querySelector('.delete-receipt').addEventListener('click', () => {
                this.confirmDeleteReceipt(receipt.id);
            });
            
            tableBody.appendChild(row);
        });
    },
    
    // Get status class for styling
    getStatusClass: function(status) {
        switch (status) {
            case 'pending':
            case 'uploaded':
                return 'pending';
            
            case 'processing':
            case 'ocr_in_progress':
            case 'ocr_completed':
            case 'parsing_in_progress':
            case 'parsing_completed':
            case 'matching_in_progress':
            case 'matching_completed':
            case 'finalizing_inventory':
                return 'processing';
            
            case 'review_pending':
                return 'review';
            
            case 'completed':
                return 'completed';
            
            case 'error':
            case 'failed':
                return 'error';
            
            default:
                return '';
        }
    },
    
    // Get status display name
    getStatusDisplayName: function(status) {
        switch (status) {
            case 'pending':
            case 'uploaded':
                return 'Oczekuje';
            
            case 'processing':
            case 'ocr_in_progress':
            case 'parsing_in_progress':
            case 'matching_in_progress':
            case 'finalizing_inventory':
                return 'Przetwarzanie';
            
            case 'review_pending':
                return 'Do weryfikacji';
            
            case 'completed':
                return 'Zakończono';
            
            case 'error':
            case 'failed':
                return 'Błąd';
            
            default:
                return status;
        }
    },
    
    // View receipt details
    viewReceiptDetails: function(receiptId) {
        console.log('View receipt details:', receiptId);
        
        // Find receipt in list
        const receipt = this.receiptsList.find(r => r.id === receiptId);
        if (!receipt) {
            Utils.showToast('Nie znaleziono paragonu.', 'error');
            return;
        }
        
        // For demo purposes, show toast
        Utils.showToast(`Szczegóły paragonu z ${receipt.store_name} (${Utils.formatDate(receipt.purchased_at)})`, 'info');
        
        // In a real implementation, we would:
        // 1. Navigate to receipt details page, or
        // 2. Open a modal with receipt details
    },
    
    // Confirm delete receipt
    confirmDeleteReceipt: async function(receiptId) {
        console.log('Confirm delete receipt:', receiptId);
        
        if (confirm('Czy na pewno chcesz usunąć ten paragon?')) {
            try {
                await API.deleteReceipt(receiptId);
                
                // Update local list
                this.receiptsList = this.receiptsList.filter(r => r.id !== receiptId);
                this.renderReceiptsList(this.receiptsList);
                
                // Show success message
                Utils.showToast('Paragon został usunięty.', 'success');
            } catch (error) {
                console.error('Error deleting receipt:', error);
                Utils.showToast('Błąd usuwania paragonu.', 'error');
            }
        }
    },
    
    // Simulate processing steps for demo
    simulateProcessingSteps: function(receiptId) {
        const steps = [
            { status: 'ocr_in_progress', message: 'Rozpoznawanie tekstu (OCR)...', delay: 1500 },
            { status: 'ocr_completed', message: 'Tekst rozpoznany, analizowanie zawartości...', delay: 1000 },
            { status: 'parsing_in_progress', message: 'Analizowanie struktury paragonu...', delay: 1500 },
            { status: 'parsing_completed', message: 'Struktura rozpoznana, dopasowywanie produktów...', delay: 1000 },
            { status: 'matching_in_progress', message: 'Dopasowywanie produktów...', delay: 2000 },
            { status: 'matching_completed', message: 'Produkty rozpoznane, aktualizowanie spiżarni...', delay: 1500 },
            { status: 'completed', message: 'Przetwarzanie zakończone pomyślnie!', delay: 1000 }
        ];
        
        let stepIndex = 0;
        
        const processStep = () => {
            if (stepIndex >= steps.length) {
                // All steps completed
                setTimeout(() => {
                    // Reload receipts list
                    this.loadReceiptsList();
                    
                    // Reset upload area
                    this.resetUploadArea();
                    
                    // Show success message
                    Utils.showToast('Paragon został pomyślnie przetworzony!', 'success');
                }, 1000);
                return;
            }
            
            const step = steps[stepIndex];
            
            // Update status
            this.updateReceiptStatus(receiptId, step.status, null);
            
            // Move to next step after delay
            setTimeout(() => {
                stepIndex++;
                processStep();
            }, step.delay);
        };
        
        // Start processing steps
        processStep();
    }
};

// Initialize module when page is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Initialize only if receipts page is active
    if (window.location.hash === '#receipts') {
        ReceiptsModule.init();
    }
    
    // Listen for hash changes
    window.addEventListener('hashchange', () => {
        if (window.location.hash === '#receipts') {
            ReceiptsModule.init();
        }
    });
});

// Export for ES6 modules
export default ReceiptsModule;
