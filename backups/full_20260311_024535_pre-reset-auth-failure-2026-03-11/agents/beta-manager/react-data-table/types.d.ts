/**
 * Type Definitions for DataTable Component
 *
 * These types provide full TypeScript support for the DataTable component
 */

// =============================================================================
// CORE TYPES
// =============================================================================

/** Generic data item with flexible structure */
export type DataItem = Record<string, unknown>;

/** Generic data item with typed keys */
export type TypedDataItem<T = unknown> = {
  [K in keyof T]: T[K];
};

// =============================================================================
// COLUMN CONFIGURATION
// =============================================================================

/**
 * Column configuration for the DataTable
 * @template T - The type of data items in the table
 */
export interface ColumnConfig<T extends DataItem = DataItem> {
  /** The property key to display from the data item */
  key: keyof T;

  /** Optional custom header text (defaults to key name) */
  header?: string;

  /** Optional custom render function for cell content */
  render?: (value: T[keyof T], item: T) => React.ReactNode;
}

// =============================================================================
// COMPONENT PROPS
// =============================================================================

/**
 * Props for the DataTable component
 * @template T - The type of data items in the table
 * @see DataTable
 */
export interface DataTableProps<T extends DataItem = DataItem> {
  /**
   * The API URL to fetch data from
   * @example "https://jsonplaceholder.typicode.com/users"
   */
  apiUrl: string;

  /**
   * Column definitions for the table
   * @see ColumnConfig
   */
  columns: ColumnConfig<T>[];

  /**
   * Optional fetch options (headers, method, etc.)
   * @see https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch
   */
  fetchOptions?: RequestInit;

  /**
   * Optional callback to transform raw API response before display
   * Useful when API returns nested or differently structured data
   * @example (data) => data.results ?? []
   */
  transformData?: (data: unknown) => T[];

  /**
   * Custom message for empty state (no data returned)
   * @default "No data available"
   */
  emptyMessage?: string;
}

// =============================================================================
// FETCH STATE
// =============================================================================

/**
 * Internal state for managing the async fetch lifecycle
 * @template T - The type of data items
 */
export interface FetchState<T extends DataItem> {
  /** The fetched data array, or null if not yet loaded */
  data: T[] | null;

  /** True while data is being fetched */
  loading: boolean;

  /** Error message if fetch failed, null otherwise */
  error: string | null;
}

// =============================================================================
// COMPONENT EVENT HANDLERS
// =============================================================================

/** Type for data fetch function */
export type FetchDataFunction = () => Promise<void>;

/** Type for retry button handler */
export type RetryHandler = () => void;

// =============================================================================
// UTILITY TYPES
// =============================================================================

/** Type guard to check if value is a valid DataItem */
export function isDataItem(value: unknown): value is DataItem {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Extract keys from a DataItem type */
export type DataItemKeys<T extends DataItem> = keyof T;

/** Get value type for a specific key */
export type DataItemValue<T extends DataItem, K extends keyof T> = T[K];
