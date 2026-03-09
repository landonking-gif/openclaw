/**
 * CSS-in-JS styles for the DataTable component
 * 
 * Using a style object pattern that can be used with:
 * - Inline styles (style={styles.container})
 * - CSS-in-JS libraries (styled-components, emotion)
 * - Or converted to CSS modules
 */

export const styles = {
  // Container styles
  container: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '20px',
  },

  // Header styles
  title: {
    fontSize: '24px',
    fontWeight: '600',
    color: '#1a1a1a',
    marginBottom: '20px',
    borderBottom: '2px solid #e0e0e0',
    paddingBottom: '10px',
  },

  // Table wrapper for horizontal scrolling
  tableWrapper: {
    overflowX: 'auto' as const,
    borderRadius: '8px',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
  },

  // Main table styles
  table: {
    width: '100%',
    borderCollapse: 'collapse' as const,
    backgroundColor: '#ffffff',
    fontSize: '14px',
  },

  // Table header styles
  thead: {
    backgroundColor: '#f5f5f5',
  },

  th: {
    padding: '14px 16px',
    textAlign: 'left' as const,
    fontWeight: '600',
    color: '#333',
    textTransform: 'capitalize' as const,
    borderBottom: '2px solid #ddd',
    whiteSpace: 'nowrap' as const,
  },

  // Table body styles
  tbody: {
    backgroundColor: '#ffffff',
  },

  td: {
    padding: '12px 16px',
    borderBottom: '1px solid #e0e0e0',
    color: '#555',
  },

  // Row hover effect
  tr: {
    transition: 'background-color 0.15s ease',
  },

  trHover: {
    backgroundColor: '#f8f9fa',
  },

  // Loading state styles
  loadingContainer: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    padding: '60px 20px',
    minHeight: '200px',
  },

  spinner: {
    width: '40px',
    height: '40px',
    border: '4px solid #e0e0e0',
    borderTop: '4px solid #007bff',
    borderRadius: '50%',
    animation: 'spin 1s linear infinite',
  },

  loadingText: {
    marginTop: '16px',
    color: '#666',
    fontSize: '14px',
  },

  // Error state styles
  errorContainer: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    padding: '60px 20px',
    minHeight: '200px',
    backgroundColor: '#fff5f5',
    borderRadius: '8px',
    border: '1px solid #feb2b2',
  },

  errorIcon: {
    fontSize: '48px',
    marginBottom: '12px',
  },

  errorTitle: {
    fontSize: '18px',
    fontWeight: '600',
    color: '#c53030',
    marginBottom: '8px',
  },

  errorMessage: {
    fontSize: '14px',
    color: '#718096',
    textAlign: 'center' as const,
    maxWidth: '400px',
  },

  retryButton: {
    marginTop: '16px',
    padding: '10px 24px',
    backgroundColor: '#c53030',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    fontSize: '14px',
    fontWeight: '500',
    cursor: 'pointer',
    transition: 'background-color 0.15s ease',
  },

  // Empty state styles
  emptyContainer: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    padding: '60px 20px',
    minHeight: '200px',
    backgroundColor: '#f7fafc',
    borderRadius: '8px',
    border: '2px dashed #cbd5e0',
  },

  emptyIcon: {
    fontSize: '48px',
    marginBottom: '12px',
  },

  emptyTitle: {
    fontSize: '18px',
    fontWeight: '600',
    color: '#4a5568',
    marginBottom: '8px',
  },

  emptyMessage: {
    fontSize: '14px',
    color: '#718096',
    textAlign: 'center' as const,
  },

  // Row action buttons (for future extension)
  actionButton: {
    padding: '6px 12px',
    backgroundColor: '#007bff',
    color: '#fff',
    border: 'none',
    borderRadius: '4px',
    fontSize: '12px',
    cursor: 'pointer',
    marginRight: '8px',
  },
};

/**
 * Global keyframes for spinner animation
 * Add this to your global CSS or CSS-in-JS provider
 */
export const globalStyles = `
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
`;
