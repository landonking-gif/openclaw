"""
Binary Search Tree (BST) - Core Implementation

A clean, production-ready implementation of a Binary Search Tree
with essential operations: insert, search, and inorder traversal.
"""

from typing import Optional, List


class Node:
    """
    A node in the Binary Search Tree.

    Each node stores a value and references to its left and right children.
    In a BST, left subtree values < node value < right subtree values.

    Attributes:
        value: The integer stored in this node.
        left: Reference to the left child (values less than node value).
        right: Reference to the right child (values greater than node value).
    """

    def __init__(self, value: int) -> None:
        """
        Initialize a new node with the given value.

        Args:
            value: The integer value to store in this node.
        """
        self.value: int = value
        self.left: Optional['Node'] = None
        self.right: Optional['Node'] = None

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        return f"Node({self.value})"


class BinarySearchTree:
    """
    A Binary Search Tree implementation.

    Maintains BST property: for any node, all left descendants have smaller
    values and all right descendants have larger values.

    Attributes:
        _root: The root node of the tree (None if empty).
    """

    def __init__(self) -> None:
        """Initialize an empty Binary Search Tree."""
        self._root: Optional[Node] = None

    def insert(self, value: int) -> None:
        """
        Insert a new value into the tree while maintaining BST properties.

        Duplicate values are not inserted (silently ignored).

        Args:
            value: The integer value to insert.

        Time Complexity: O(h) where h is tree height.
            - Balanced tree: O(log n)
            - Skewed tree: O(n)
        """
        self._root = self._insert_recursive(self._root, value)

    def _insert_recursive(self, node: Optional[Node], value: int) -> Node:
        """
        Recursively insert value into subtree rooted at node.

        Args:
            node: Current root of the subtree.
            value: Value to insert.

        Returns:
            The (possibly new) root of the subtree.
        """
        if node is None:
            return Node(value)

        if value < node.value:
            node.left = self._insert_recursive(node.left, value)
        elif value > node.value:
            node.right = self._insert_recursive(node.right, value)
        # If value == node.value, do nothing (duplicates not allowed)

        return node

    def search(self, value: int) -> bool:
        """
        Search for a value in the tree.

        Args:
            value: The integer value to search for.

        Returns:
            True if the value exists in the tree, False otherwise.

        Time Complexity: O(h) where h is tree height.
            - Balanced tree: O(log n)
            - Skewed tree: O(n)
        """
        return self._search_recursive(self._root, value)

    def _search_recursive(self, node: Optional[Node], value: int) -> bool:
        """
        Recursively search for value in subtree rooted at node.

        Args:
            node: Current node being examined.
            value: Value to search for.

        Returns:
            True if found, False otherwise.
        """
        if node is None:
            return False

        if value == node.value:
            return True
        elif value < node.value:
            return self._search_recursive(node.left, value)
        else:
            return self._search_recursive(node.right, value)

    def inorder_traversal(self) -> List[int]:
        """
        Return values in inorder traversal order (Left-Root-Right).

        In a BST, inorder traversal produces values in sorted ascending order.

        Returns:
            List of values in sorted order.

        Time Complexity: O(n) where n is number of nodes.
        Space Complexity: O(n) for result list + O(h) for recursion stack.
        """
        result: List[int] = []
        self._inorder_recursive(self._root, result)
        return result

    def _inorder_recursive(self, node: Optional[Node], result: List[int]) -> None:
        """
        Recursively collect inorder values.

        Args:
            node: Current node.
            result: List to collect values into.
        """
        if node is not None:
            self._inorder_recursive(node.left, result)
            result.append(node.value)
            self._inorder_recursive(node.right, result)

    def is_empty(self) -> bool:
        """
        Check if the tree is empty.

        Returns:
            True if tree has no nodes, False otherwise.
        """
        return self._root is None

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        if self.is_empty():
            return "BinarySearchTree(empty)"
        values = self.inorder_traversal()
        return f"BinarySearchTree({values})"


# Example usage and testing
if __name__ == "__main__":
    print("=" * 60)
    print("Binary Search Tree - Core Implementation")
    print("=" * 60)

    # Create BST and insert values
    bst = BinarySearchTree()
    values = [50, 30, 70, 20, 40, 60, 80]

    print(f"\n1. Inserting values: {values}")
    for v in values:
        bst.insert(v)
    print(f"   Tree representation: {bst}")

    # Test search
    print("\n2. Searching for values:")
    test_values = [40, 100, 50, 25]
    for val in test_values:
        result = bst.search(val)
        status = "✓ Found" if result else "✗ Not found"
        print(f"   search({val}): {status}")

    # Test inorder traversal
    print(f"\n3. Inorder traversal (sorted): {bst.inorder_traversal()}")

    # Test empty tree
    print("\n4. Testing empty tree:")
    empty_bst = BinarySearchTree()
    print(f"   is_empty(): {empty_bst.is_empty()}")
    print(f"   search(10): {empty_bst.search(10)}")
    print(f"   inorder_traversal(): {empty_bst.inorder_traversal()}")

    # Test single element
    print("\n5. Testing single element tree:")
    single_bst = BinarySearchTree()
    single_bst.insert(42)
    print(f"   After insert(42): {single_bst}")
    print(f"   search(42): {single_bst.search(42)}")
    print(f"   search(99): {single_bst.search(99)}")

    # Test duplicate handling
    print("\n6. Testing duplicate handling:")
    dup_bst = BinarySearchTree()
    dup_bst.insert(50)
    dup_bst.insert(50)  # Duplicate
    dup_bst.insert(50)  # Another duplicate
    print(f"   After inserting 50 three times: {dup_bst}")
    print(f"   Values count: {len(dup_bst.inorder_traversal())}")

    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)
