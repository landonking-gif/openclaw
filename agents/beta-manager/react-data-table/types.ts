/**
 * Type definitions for the DataTable component
 * 
 * These interfaces enforce type safety across the data fetching
 * and rendering pipeline.
 */

/**
 * Generic data item interface
 * Allows flexibility while requiring an id field for React keys
 */
export interface DataItem {
  id: number | string;
  [key: string]: unknown;
}

/**
 * Configuration for table columns
 * Supports custom rendering and styling per column
 */
export interface ColumnConfig<T extends DataItem> {
  /** Unique identifier for the column */
  key: string;
  /** Header display text */
  header: string;
  /** Optional custom render function for cell content */
  render?: (item: T) => React.ReactNode;
  /** Optional CSS class for the column */
  className?: string;
  /** Whether column is sortable (future enhancement) */
  sortable?: boolean;
}

/**
 * Props for the DataTable component
 * Designed to be flexible and reusable across different data sources
 */
export interface DataTableProps<T extends DataItem> {
  /** API endpoint URL to fetch data from */
  apiUrl: string;
  /** Column configuration array */
  columns: ColumnConfig<T>[];
  /** Optional custom title for the table */
  title?: string;
  /** Optional polling interval in milliseconds for auto-refresh */
  refreshInterval?: number;
  /** Optional custom error message component */
  customErrorMessage?: string;
  /** Optional custom empty state message */
  customEmptyMessage?: string;
  /** Optional CSS class for the container */
  className?: string;
}

/**
 * Possible states for the data fetching process
 */
export type FetchStatus = 'idle' | 'loading' | 'success' | 'error';

/**
 * API response structure (assumes JSONPlaceholder-style API)
 * Can be extended for different API shapes
 */
export interface ApiResponse<T> {
  data: T[];
  total?: number;
  page?: number;
}
