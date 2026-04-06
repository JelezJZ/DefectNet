/**
 * Frontend Environment Configuration
 * 
 * Copy this file to env-config.js and modify for your environment
 * This file is loaded AFTER the default config in index.html,
 * so it will override those values.
 */

window.ENV_CONFIG = {
    // Backend API URL
    API_URL: 'http://localhost:8000',
    
    // Default detection confidence threshold (0.0-1.0)
    DEFAULT_CONFIDENCE: '0.25',
    
    // Default image size for model inference
    DEFAULT_IMAGE_SIZE: '1024',
    
    // Maximum number of files allowed in batch upload
    MAX_BATCH_SIZE: '20',
    
    // Maximum file upload size in MB
    MAX_FILE_SIZE_MB: '50',
    
    // Allowed image types (comma-separated MIME types)
    ALLOWED_IMAGE_TYPES: 'image/jpeg,image/png,image/webp',
    
    // JWT token expiration time in minutes
    TOKEN_EXPIRE_MINUTES: '1440',
    
    // Enable/disable health check on page load
    HEALTH_CHECK_ENABLED: 'true'
};
