/**
 * DataTable Usage Example
 * 
 * Demonstrates various ways to use the DataTable component
 * with JSONPlaceholder API and custom configurations.
 */

import React from 'react';
import DataTable from './DataTable';
import { ColumnConfig, DataItem } from './types';
import './styles.css'; // Optional: import if using CSS file approach

// ============================================================================
// TypeScript Interface Examples
// ============================================================================

/**
 * Example 1: Users data from JSONPlaceholder
 */
interface User extends DataItem {
  id: number;
  name: string;
  username: string;
  email: string;
  phone: string;
  website: string;
  address: {
    street: string;
    suite: string;
    city: string;
    zipcode: string;
  };
  company: {
    name: string;
    catchPhrase: string;
  };
}

/**
 * Example 2: Posts data from JSONPlaceholder
 */
interface Post extends DataItem {
  userId: number;
  id: number;
  title: string;
  body: string;
}

/**
 * Example 3: Todos data from JSONPlaceholder
 */
interface Todo extends DataItem {
  userId: number;
  id: number;
  title: string;
  completed: boolean;
}

// ============================================================================
// Column Configuration Examples
// ============================================================================

/** Users table configuration with custom rendering */
const userColumns: ColumnConfig<User>[] = [
  {
    key: 'id',
    header: 'ID',
  },
  {
    key: 'name',
    header: 'Full Name',
  },
  {
    key: 'username',
    header: 'Username',
  },
  {
    key: 'email',
    header: 'Email',
    // Custom render: make email clickable
    render: (user) => (
      <a href={`mailto:${user.email}`} style={{ color: '#007bff', textDecoration: 'none' }}>
        {user.email}
      </a>
    ),
  },
  {
    key: 'company',
    header: 'Company',
    // Custom render: extract nested property
    render: (user) => user.company?.name || '-',
  },
  {
    key: 'city',
    header: 'City',
    // Custom render: extract from nested address
    render: (user) => user.address?.city || '-',
  },
];

/** Posts table configuration */
const postColumns: ColumnConfig<Post>[] = [
  {
    key: 'id',
    header: 'ID',
  },
  {
    key: 'title',
    header: 'Title',
    // Render truncated title
    render: (post) => (
      <span title={post.title}>
        {post.title.slice(0, 50)}{post.title.length > 50 ? '...' : ''}
      </span>
    ),
  },
  {
    key: 'body',
    header: 'Content',
    // Render truncated body with styling
    render: (post) => (
      <span style={{ color: '#666' }}>
        {post.body.slice(0, 80)}...
      </span>
    ),
  },
];

/** Todos table with status badge */
const todoColumns: ColumnConfig<Todo>[] = [
  {
    key: 'id',
    header: 'ID',
  },
  {
    key: 'title',
    header: 'Task',
  },
  {
    key: 'completed',
    header: 'Status',
    // Custom render: status badge
    render: (todo) => (
      <span
        style={{
          display: 'inline-block',
          padding: '4px 12px',
          borderRadius: '12px',
          fontSize: '12px',
          fontWeight: '500',
          backgroundColor: todo.completed ? '#c6f6d5' : '#feebc8',
          color: todo.completed ? '#22543d' : '#744210',
        }}
      >
        {todo.completed ? '✅ Complete' : '⏳ Pending'}
      </span>
    ),
  },
];

// ============================================================================
// Component Examples
// ============================================================================

/**
 * Example 1: Basic Users Table
 * Simplest usage with default styling
 */
export const UsersTableExample: React.FC = () => (
  <DataTable<User>
    apiUrl="https://jsonplaceholder.typicode.com/users"
    columns={userColumns}
    title="Team Members"
  />
);

/**
 * Example 2: Posts Table with Custom Messages
 * Demonstrates custom error and empty state messages
 */
export const PostsTableExample: React.FC = () => (
  <DataTable<Post>
    apiUrl="https://jsonplaceholder.typicode.com/posts"
    columns={postColumns}
    title="Recent Blog Posts"
    customEmptyMessage="No posts found. Check back later!"
    customErrorMessage="Unable to load posts. Please refresh the page."
  />
);

/**
 * Example 3: Todos Table with Auto-refresh
 * Demonstrates polling for real-time updates
 */
export const TodosWithPollingExample: React.FC = () => (
  <DataTable<Todo>
    apiUrl="https://jsonplaceholder.typicode.com/todos"
    columns={todoColumns}
    title="Task List (Auto-refreshes every 10s)"
    refreshInterval={10000} // 10 seconds
  />
);

/**
 * Example 4: Custom CSS Class
 * Demonstrates external styling approach
 */
export const CustomStyledTableExample: React.FC = () => (
  <DataTable<User>
    apiUrl="https://jsonplaceholder.typicode.com/users"
    columns={userColumns}
    title="Custom Styled Users"
    className="custom-dark-theme"
  />
);

/**
 * Example 5: Error Handling Demo
 * Uses invalid URL to demonstrate error state
 */
export const ErrorStateExample: React.FC = () => (
  <DataTable<User>
    apiUrl="https://invalid-url.example.com/users"
    columns={userColumns}
    title="This will show error"
    customErrorMessage="This demonstrates the error handling"
  />
);

/**
 * Example 6: Empty State Demo
 * Uses filter to force empty results
 */
export const EmptyStateExample: React.FC = () => {
  // In real usage, backend would return empty
  // Here we just use the component with custom message
  return (
    <DataTable<User>
      apiUrl="https://jsonplaceholder.typicode.com/users?id=99999"
      columns={userColumns}
      title="This will show empty state"
      customEmptyMessage="No users found matching your criteria"
    />
  );
};

// ============================================================================
// Main Demo Page (for testing)
// ============================================================================

/**
 * Demo component showing all examples
 */
const Example: React.FC = () => {
  const [activeExample, setActiveExample] = React.useState<string>('users');

  const examples = [
    { id: 'users', label: 'Users Table', component: UsersTableExample },
    { id: 'posts', label: 'Posts Table', component: PostsTableExample },
    { id: 'todos', label: 'Todos + Polling', component: TodosWithPollingExample },
    { id: 'custom', label: 'Custom Styling', component: CustomStyledTableExample },
    { id: 'error', label: 'Error State', component: ErrorStateExample },
    { id: 'empty', label: 'Empty State', component: EmptyStateExample },
  ];

  const ActiveComponent = examples.find(e => e.id === activeExample)?.component || UsersTableExample;

  return (
    <div style={{ padding: '20px', minHeight: '100vh', backgroundColor: '#f5f5f5' }}>
      <h1 style={{ textAlign: 'center', marginBottom: '20px' }}>DataTable Examples</h1>
      
      {/* Navigation */}
      <div style={{ 
        display: 'flex', 
        gap: '12px', 
        justifyContent: 'center', 
        marginBottom: '30px',
        flexWrap: 'wrap' as const
      }}>
        {examples.map(example => (
          <button
            key={example.id}
            onClick={() => setActiveExample(example.id)}
            style={{
              padding: '10px 20px',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              backgroundColor: activeExample === example.id ? '#007bff' : '#fff',
              color: activeExample === example.id ? '#fff' : '#333',
              fontWeight: '500',
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)