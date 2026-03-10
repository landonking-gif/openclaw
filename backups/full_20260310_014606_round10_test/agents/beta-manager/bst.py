"""
Binary Search Tree (BST) Implementation

A production-ready, type-hinted implementation of a binary search tree
data structure with standard operations: insert, search, and traversal.

Author: Beta Manager (coding-1 fallback)
Date: 2025
"""

from typing import Optional, Generic, TypeVar, List, Iterator

T = TypeVar("T")


class Node(Generic[T]):
    """
    A node in the binary search tree.

    Attributes:
        value: The value stored in this node.
        left: Reference to the left child node (values < node value).
        right: Reference to the right child node (values > node value).
    """

    def __init__(self, value: T) -> None:
        """
        Initialize a new node with the given value.

        Args:
            value: The value to store in this node.
        """
        self.value: T = value
        self.left: Optional["Node[T]"] = None
        self.right: Optional["Node[T]"] = None

    def __repr__(self) -> str:
        """Return a string representation of the node."""
        return f"Node({self.value!r})"


class BinarySearchTree(Generic[T]):
    """
    A binary search tree (BST) data structure.

    A BST maintains the invariant that for any node N:
    - All values in the left subtree are less than N.value
    - All values in the right subtree are greater than N.value
    - No duplicate values are stored

    Type Parameters:
        T: The type of values stored in the tree. Must support comparison operators.

    Example:
        >>> bst = BinarySearchTree[int]()
        >>> bst.insert(5)
        >>> bst.insert(3)
        >>> bst.insert(7)
        >>> bst.search(3)
        True
        >>> bst.search(10)
        False
        >>> list(bst.inorder_traversal())
        [3, 5, 7]
    """

    def __init__(self) -> None:
        """Initialize an empty binary search tree."""
        self._root: Optional[Node[T]] = None
        self._size: int = 0

    @property
    def size(self) -> int:
        """Return the number of elements in the tree."""
        return self._size

    @property
    def is_empty(self) -> bool:
        """Return True if the tree is empty, False otherwise."""
        return self._root is None

    def insert(self, value: T) -> bool:
        """
        Insert a new value into the tree while maintaining BST properties.

        Duplicate values are ignored (not inserted).

        Args:
            value: The value to insert into the tree.

        Returns:
            True if the value was inserted, False if it already existed.

        Time Complexity: O(h) where h is the height of the tree
        Space Complexity: O(h) for recursion stack (or O(1) for iterative)

        Example:
            >>> bst = BinarySearchTree[int]()
            >>> bst.insert(5)
            True
            >>> bst.insert(5)  # Duplicate
            False
        """
        if self._root is None:
            self._root = Node(value)
            self._size += 1
            return True

        return self._insert_recursive(self._root, value)

    def _insert_recursive(self, node: Node[T], value: T) -> bool:
        """
        Recursively insert a value into the subtree rooted at node.

        Args:
            node: The root of the subtree to insert into.
            value: The value to insert.

        Returns:
            True if inserted, False if duplicate.
        """
        if value < node.value:
            if node.left is None:
                node.left = Node(value)
                self._size += 1
                return True
            return self._insert_recursive(node.left, value)
        elif value > node.value:
            if node.right is None:
                node.right = Node(value)
                self._size += 1
                return True
            return self._insert_recursive(node.right, value)
        else:
            # Duplicate value - already exists
            return False

    def search(self, value: T) -> bool:
        """
        Search for a value in the tree.

        Args:
            value: The value to search for.

        Returns:
            True if the value exists in the tree, False otherwise.

        Time Complexity: O(h) where h is the height of the tree
        Space Complexity: O(h) for recursion stack (or O(1) for iterative)

        Example:
            >>> bst = BinarySearchTree[int]()
            >>> bst.insert(5)
            >>> bst.insert(3)
            >>> bst.search(3)
            True
            >>> bst.search(10)
            False
        """
        return self._search_recursive(self._root, value)

    def _search_recursive(self, node: Optional[Node[T]], value: T) -> bool:
        """
        Recursively search for a value in the subtree rooted at node.

        Args:
            node: The root of the subtree to search.
            value: The value to search for.

        Returns:
            True if found, False otherwise.
        """
        if node is None:
            return False

        if value < node.value:
            return self._search_recursive(node.left, value)
        elif value > node.value:
            return self._search_recursive(node.right, value)
        else:
            return True

    def inorder_traversal(self) -> Iterator[T]:
        """
        Perform an in-order traversal of the tree (left → node → right).

        Yields values in sorted ascending order.

        Yields:
            Values from the tree in sorted order.

        Time Complexity: O(n) where n is the number of nodes
        Space Complexity: O(h) for the recursion stack

        Example:
            >>> bst = BinarySearchTree[int]()
            >>> bst.insert(5)
            >>> bst.insert(3)
            >>> bst.insert(7)
            >>> list(bst.inorder_traversal())
            [3, 5, 7]
        """
        yield from self._inorder_recursive(self._root)

    def _inorder_recursive(self, node: Optional[Node[T]]) -> Iterator[T]:
        """
        Recursively yield values from the subtree rooted at node in order.

        Args:
            node: The root of the subtree to traverse.

        Yields:
            Values in sorted order.
        """
        if node is not None:
            yield from self._inorder_recursive(node.left)
            yield node.value
            yield from self._inorder_recursive(node.right)

    def find_min(self) -> Optional[T]:
        """
        Find the minimum value in the tree.

        Returns:
            The minimum value, or None if the tree is empty.
        """
        if self._root is None:
            return None

        current = self._root
        while current.left is not None:
            current = current.left
        return current.value

    def find_max(self) -> Optional[T]:
        """
        Find the maximum value in the tree.

        Returns:
            The maximum value, or None if the tree is empty.
        """
        if self._root is None:
            return None

        current = self._root
        while current.right is not None:
            current = current.right
        return current.value

    def __contains__(self, value: T) -> bool:
        """
        Support the 'in' operator: value in bst.

        Args:
            value: The value to check for membership.

        Returns:
            True if the value is in the tree.
        """
        return self.search(value)

    def __len__(self) -> int:
        """Return the number of elements in the tree."""
        return self.size

    def __repr__(self) -> str:
        """Return a string representation of the BST."""
        values = list(self.inorder_traversal())