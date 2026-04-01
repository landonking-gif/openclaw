/**
 * DataTable Component
 * 
 * A reusable React TypeScript component for fetching and displaying
 * API data in a styled table with loading, error, and empty states.
 * 
 * Features:
 * - Generic type support for type-safe data handling
 * - Custom column configuration with optional render functions
 * - Loading state with animated spinner
 * - Error handling with retry capability
 * - Empty state visualization
 * - Responsive design with horizontal scrolling
 */

import React, {
  useState,
  useEffect,
  useCallback,
  useRef,
  useMemo,
} from 'react';
import {
  DataItem,
  ColumnConfig,
  DataTableProps,
  FetchStatus,
  ApiResponse,
} from './types';
import { styles } from './styles';

/**
 * DataTable Component - Main reusable table component
 * 
 * @template T - The expected shape of data items (must extend DataItem)
 * @param props - Configuration props including API URL and column definitions
 */
function DataTable<T extends DataItem>({
  apiUrl,
  columns,
  title = 'Data Table',
  refreshInterval,
  customErrorMessage,
  customEmptyMessage,
  className,
}: DataTableProps<T>): React.ReactElement {
  // State management for data lifecycle
  const [data, setData] = useState<T[]>([]);
  const [status, setStatus] = useState<FetchStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [hoveredRow, setHoveredRow] = useState<number | null>(null);
  
  // Ref for interval cleanup
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const isMountedRef = useRef(true);

  /**
   * Core data fetching function
   * Handles the fetch lifecycle with proper error boundaries
   */
  const fetchData = useCallback(async () => {
    // Prevent duplicate fetches
    if (status === 'loading') return;
    
    setStatus('loading');
    setError(null);

    try {
      const response = await fetch(apiUrl, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          // Common CORS headers for APIs
          'Accept': 'application/json',
        },
      });

      // Handle HTTP errors (4xx, 5xx)
      if (!response.ok) {
        throw new Error(
          `HTTP ${response.status}: ${response.statusText || 'Request failed'}`
        );
      }

      const result: T[] = await response.json();

      // Check if component is still mounted before updating state
      if (!isMountedRef.current) return;

      // Validate response data
      if (!Array.isArray(result)) {
        throw new Error('Invalid response format: expected array');
      }

      setData(result);
      setStatus('success');
    } catch (err) {
      if (!isMountedRef.current) return;
      
      const errorMessage = err instanceof Error 
        ? err.message 
        : 'Unknown error occurred';
      
      setError(errorMessage);
      setStatus('error');
      setData([]);
    }
  }, [apiUrl, status]);

  /**
   * Initial data fetch on mount and URL change
   */
  useEffect(() => {
    fetchData();

    // Cleanup function to handle unmounting
    return () => {
      isMountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchData]);

  /**
   * Optional polling mechanism for auto-refresh
   * Only activates if refreshInterval prop is provided
   */
  useEffect(() => {
    if (refreshInterval && refreshInterval > 0) {
      intervalRef.current = setInterval(fetchData, refreshInterval);
      
      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
      };
    }
  }, [refreshInterval, fetchData]);

  /**
   * Memoized table rows to prevent unnecessary re-renders
   */
  const tableRows = useMemo(() => {
    return data.map((item, index) => (
      <tr
        key={item.id ?? index}
        style={{
          ...styles.tr,
          ...(hoveredRow === index ? styles.trHover : {}),
        }}
        onMouseEnter={() => setHoveredRow(index)}
        onMouseLeave={() => setHoveredRow(null)}
        data-row-index={index}
      >
        {columns.map((column) => (
          <td
            key={`${item.id}-${column.key}`}
            style={{
              ...styles.td,
              ...(column.className ? {} : {}), // className would be applied via CSS
            }}
          >
            {/* 
              Render custom content if provided, 
              otherwise use simple property access
              Uses optional chaining for safety
            */}
            {column.render
              ? column.render(item)
              : (item[column.key] as React.ReactNode) ?? '-'}
          </td>
        ))}
      </tr>
    ));
  }, [data, columns, hoveredRow]);

  /**
   * Memoized table headers
   */
  const tableHeaders = useMemo(() => {
    return columns.map((column) => (
      <th
        key={column.key}
        style={styles.th}
        className={column.className}
      >
        {column.header}
      </th>
    ));
  }, [columns]);

  /**
   * Loading State Component
   * Shows animated spinner while fetching data
   */
  const LoadingState = (): React.ReactElement => (
    <div style={styles.loadingContainer}>
      <div style={styles.spinner} />
      <p style={styles.loadingText}>Loading data...</p>
    </div>
  );

  /**
   * Error State Component
   * Displays error message with retry button
   */
  const ErrorState = (): React.ReactElement => (
    <div style={styles.errorContainer}>
      <span style={styles.errorIcon}>⚠️</span>
      <h3 style={styles.errorTitle}>Failed to load data</h3>
      <p style={styles.errorMessage}>
        {customErrorMessage || error || 'An unexpected error occurred while fetching data.'}
      </p>
      <button
        style={styles.retryButton}
        onClick={fetchData}
        onMouseEnter={(e) => {
          (e.target as HTMLButtonElement).style.backgroundColor = '#9b2c2c';
        }}
        onMouseLeave={(e) => {
          (e.target as HTMLButtonElement).style.backgroundColor = '#c53030';
        }}
      >
        Try Again
      </button>
    </div>
  );

  /**
   * Empty State Component
   * Shown when API returns empty array
   */
  const EmptyState = (): React.ReactElement => (
    <div style={styles.emptyContainer}>
      <span style={styles.emptyIcon}>📭</span>
      <h3 style={styles.emptyTitle}>No Data Available</h3>
      <p style={styles.emptyMessage}>
        {customEmptyMessage || 
          'The API returned no data. This could be normal or indicate a configuration issue.'}
      </p>
    </div>
  );

  /**
   * Table Content Component
   * Renders the actual data table
   */
  const TableContent = (): React.ReactElement => (
    <div style={styles.tableWrapper}>
      <table style={styles.table}>
        <thead style={styles.thead}>
          <tr>{tableHeaders}</tr>
        </thead>
        <tbody style={styles.tbody}>{tableRows}</tbody>
      </table>
    </div>
  );

  // Main render: conditionally show based on status
  const renderContent = (): React.ReactElement => {
    switch (status) {
      case 'loading':
        return <LoadingState />;
      case 'error':
        return <ErrorState />;
      case 'success':
        return data.length === 0 ? <EmptyState /> : <TableContent />;
      default:
        return <LoadingState />;
    }
  };

  return (
    <div style={styles.container} className={className}>
      <h2 style={styles.title}>{title}</h2>
      {renderContent()}
    </div>
  );
}

export default DataTable;
