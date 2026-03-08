"""
Binary Search Tree (BST) Implementation

A complete Python implementation of a Binary Search Tree with all standard
operations including insertion, deletion, traversal, and utility methods.
"""

from __future__ import annotations
from collections import deque
from typing import Optional, List, Any, TypeVar, Generic

T = TypeVar('T')


class Node(Generic[T]):
    """
    A node in the Binary Search Tree.
    
    Attributes:
        value: The value stored in the node
        left: Reference to the left child node
        right: Reference to the right child node
    """
    
    def __init__(self, value: T) -> None:
        """
        Initialize a new node with the given value.
        
        Args:
            value: The value to store in this node
        """
        self.value: T = value
        self.left: Optional[Node[T]] = None
        self.right: Optional[Node[T]] = None
    
    def __repr__(self) -> str:
        """Return a string representation of the node."""
        return f"Node({self.value})"


class BST(Generic[T]):
    """
    Binary Search Tree implementation.
    
    A BST is a binary tree where for each node:
    - All values in the left subtree are less than the node's value
    - All values in the right subtree are greater than the node's value
    
    Type Parameters:
        T: The type of values stored in the tree (must be comparable)
    """
    
    def __init__(self) -> None:
        """Initialize an empty Binary Search Tree."""
        self._root: Optional[Node[T]] = None
        self._size: int = 0
    
    def is_empty(self) -> bool:
        """
        Check if the tree is empty.
        
        Returns:
            True if the tree has no nodes, False otherwise
        """
        return self._root is None
    
    def insert(self, value: T) -> None:
        """
        Insert a new value into the tree.
        
        If the value already exists, it will not be inserted (duplicates not allowed).
        
        Args:
            value: The value to insert
        """
        if self._root is None:
            self._root = Node(value)
            self._size += 1
        else:
            self._insert_recursive(self._root, value)
    
    def _insert_recursive(self, node: Node[T], value: T) -> bool:
        """
        Recursively insert a value into the subtree rooted at node.
        
        Args:
            node: The current node being examined
            value: The value to insert
            
        Returns:
            True if insertion was successful, False if value already exists
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
            # Value already exists; duplicates not allowed
            return False
    
    def delete(self, value: T) -> bool:
        """
        Remove a value from the tree.
        
        Handles all three cases:
        - Leaf node (no children)
        - One child
        - Two children (replaced with inorder successor)
        
        Args:
            value: The value to delete
            
        Returns:
            True if deletion was successful, False if value not found
        """
        self._root, deleted = self._delete_recursive(self._root, value)
        if deleted:
            self._size -= 1
        return deleted
    
    def _delete_recursive(self, node: Optional[Node[T]], value: T) -> tuple[Optional[Node[T]], bool]:
        """
        Recursively delete a value from the subtree rooted at node.
        
        Args:
            node: The current node being examined
            value: The value to delete
            
        Returns:
            Tuple of (new_node, success_flag) where new_node is the node to
            replace the current node (may be None)
        """
        if node is None:
            return None, False
        
        if value < node.value:
            node.left, deleted = self._delete_recursive(node.left, value)
            return node, deleted
        elif value > node.value:
            node.right, deleted = self._delete_recursive(node.right, value)
            return node, deleted
        else:
            # Found the node to delete
            # Case 1: Leaf node (no children)
            if node.left is None and node.right is None:
                return None, True
            
            # Case 2: One child
            if node.left is None:
                return node.right, True
            if node.right is None:
                return node.left, True
            
            # Case 3: Two children
            # Find the inorder successor (smallest in right subtree)
            successor = self._find_min(node.right)
            node.value = successor.value
            node.right, _ = self._delete_recursive(node.right, successor.value)
            return node, True
    
    def _find_min(self, node: Node[T]) -> Node[T]:
        """
        Find the node with minimum value in the subtree rooted at node.
        
        Args:
            node: The starting node
            
        Returns:
            The node with the minimum value
        """
        current = node
        while current.left is not None:
            current = current.left
        return current
    
    def search(self, value: T) -> bool:
        """
        Search for a value in the tree.
        
        Args:
            value: The value to search for
            
        Returns:
            True if the value exists in the tree, False otherwise
        """
        return self._search_recursive(self._root, value)
    
    def _search_recursive(self, node: Optional[Node[T]], value: T) -> bool:
        """
        Recursively search for a value in the subtree rooted at node.
        
        Args:
            node: The current node being examined
            value: The value to search for
            
        Returns:
            True if found, False otherwise
        """
        if node is None:
            return False
        
        if value < node.value:
            return self._search_recursive(node.left, value)
        elif value > node.value:
            return self._search_recursive(node.right, value)
        else:
            return True
    
    def get_min(self) -> Optional[T]:
        """
        Get the minimum value in the tree.
        
        Returns:
            The minimum value, or None if tree is empty
        """
        if self._root is None:
            return None
        
        current = self._root
        while current.left is not None:
            current = current.left
        return current.value
    
    def get_max(self) -> Optional[T]:
        """
        Get the maximum value in the tree.
        
        Returns:
            The maximum value, or None if tree is empty
        """
        if self._root is None:
            return None
        
        current = self._root
        while current.right is not None:
            current = current.right
        return current.value
    
    def get_height(self) -> int:
        """
        Get the height of the tree.
        
        Height is defined as the number of edges on the longest path
        from the root to a leaf. An empty tree has height -1, a single
        node tree has height 0.
        
        Returns:
            The height of the tree
        """
        return self._get_height_recursive(self._root)
    
    def _get_height_recursive(self, node: Optional[Node[T]]) -> int:
        """
        Recursively calculate the height of the subtree rooted at node.
        
        Args:
            node: The root of the subtree
            
        Returns:
            The height of the subtree
        """
        if node is None:
            return -1
        
        left_height = self._get_height_recursive(node.left)
        right_height = self._get_height_recursive(node.right)
        
        return max(left_height, right_height) + 1
    
    def inorder_traversal(self) -> List[T]:
        """
        Perform inorder traversal (Left-Root-Right).
        
        Returns values in sorted ascending order.
        
        Returns:
            List of values in inorder traversal order
        """
        result: List[T] = []
        self._inorder_recursive(self._root, result)
        return result
    
    def _inorder_recursive(self, node: Optional[Node[T]], result: List[T]) -> None:
        """
        Recursively perform inorder traversal.
        
        Args:
            node: Current node
            result: List to store traversal results
        """
        if node is not None:
            self._inorder_recursive(node.left, result)
            result.append(node.value)
            self._inorder_recursive(node.right, result)
    
    def preorder_traversal(self) -> List[T]:
        """
        Perform preorder traversal (Root-Left-Right).
        
        Returns:
            List of values in preorder traversal order
        """
        result: List[T] = []
        self._preorder_recursive(self._root, result)
        return result
    
    def _preorder_recursive(self, node: Optional[Node[T]], result: List[T]) -> None:
        """
        Recursively perform preorder traversal.
        
        Args:
            node: Current node
            result: List to store traversal results
        """
        if node is not None:
            result.append(node.value)
            self._preorder_recursive(node.left, result)
            self._preorder_recursive(node.right, result)
    
    def postorder_traversal(self) -> List[T]:
        """
        Perform postorder traversal (Left-Right-Root).
        
        Returns:
            List of values in postorder traversal order
        """
        result: List[T] = []
        self._postorder_recursive(self._root, result)
        return result
    
    def _postorder_recursive(self, node: Optional[Node[T]], result: List[T]) -> None:
        """
        Recursively perform postorder traversal.
        
        Args:
            node: Current node
            result: List to store traversal results
        """
        if node is not None:
            self._postorder_recursive(node.left, result)
            self._postorder_recursive(node.right, result)
            result.append(node.value)
    
    def level_order_traversal(self) -> List[T]:
        """
        Perform level order traversal (breadth-first search).
        
        Visits nodes level by level from top to bottom, left to right.
        
        Returns:
            List of values in level order
        """
        result: List[T] = []
        if self._root is None:
            return result
        
        queue: deque[Node[T]] = deque([self._root])
        
        while queue:
            node = queue.popleft()
            result.append(node.value)
            
            if node.left is not None:
                queue.append(node.left)
            if node.right is not None:
                queue.append(node.right)
        
        return result
    
    def __repr__(self) -> str:
        """
        Return a string representation of the BST.
        
        Returns:
            String showing tree size, root value, and traversals
        """
        if self.is_empty():
            return "BST(empty)"
        
        return (
            f"BST(size={self._size}, "
            f"root={self._root.value}, "
            f"height={self.get_height()}, "
            f"min={self.get_min()}, "
            f"max={self.get_max()})"
        )
    
    def size(self) -> int:
        """
        Get the number of nodes in the tree.
        
        Returns:
            The count of nodes in the tree
        """
        return self._size


# Example Usage
if __name__ == "__main__":
    print("=" * 60)
    print("Binary Search Tree Implementation - Example Usage")
    print("=" * 60)
    
    # Create a BST
    bst: BST[int] = BST()
    
    print("\n1. Initial State")
    print(f"   Is empty? {bst.is_empty()}")
    print(f"   Size: {bst.size()}")
    print(f"   Representation: {bst}")
    
    # Insert values
    print("\n2. Inserting values: 50, 30, 70, 20, 40, 60, 80")
    values = [50, 30, 70, 20, 40, 60, 80]
    for v in values:
        bst.insert(v)
    
    print(f"   Size after insertions: {bst.size()}")
    print(f"   Is empty? {bst.is_empty()}")
    print(f"   Representation: {bst}")
    
    # Search
    print("\n3. Searching")
    print(f"   Search for 40: {bst.search(40)}")
    print(f"   Search for 100: {bst.search(100)}")
    
    # Get min/max
    print("\n4. Min and Max Values")
    print(f"   Minimum value: {bst.get_min()}")
    print(f"   Maximum value: {bst.get_max()}")
    
    # Height
    print("\n5. Tree Height")
    print(f"   Height: {bst.get_height()}")
    
    # Traversals
    print("\n6. Tree Traversals")
    print(f"   Inorder (sorted):    {bst.inorder_traversal()}")
    print(f"   Preorder:            {bst.preorder_traversal()}")
    print(f"   Postorder:           {bst.postorder_traversal()}")
    print(f"   Level Order (BFS):   {bst.level_order_traversal()}")
    
    # Deletion - Leaf node
    print("\n7. Deleting leaf node (20)")
    deleted = bst.delete(20)
    print(f"   Deleted successfully: {deleted}")
    print(f"   Inorder after delete: {bst.inorder_traversal()}")
    
    # Deletion - Node with one child
    print("\n8. Deleting node with one child (30)")
    deleted = bst.delete(30)
    print(f"   Deleted successfully: {deleted}")
    print(f"   Inorder after delete: {bst.inorder_traversal()}")
    
    # Deletion - Node with two children
    print("\n9. Deleting node with two children (50)")
    deleted = bst.delete(50)
    print(f"   Deleted successfully: {deleted}")
    print(f"   Inorder after delete: {bst.inorder_traversal()}")
    
    # Final state
    print("\n10. Final State")
    print(f"    Size: {bst.size()}")
    print(f"    Height: {bst.get_height()}")
    print(f"    Min: {bst.get_min()}, Max: {bst.get_max()}")
    print(f"    Representation: {bst}")
    
    # Test with strings
    print("\n" + "=" * 60)
    print("Testing with Strings")
    print("=" * 60)
    
    string_bst: BST[str] = BST()
    words = ["cherry", "apple", "banana", "date", "fig"]
    print(f"\nInserting: {words}")
    for word in words:
        string_bst.insert(word)
    
    print(f"   Inorder (sorted): {string_bst.inorder_traversal()}")
    print(f"   Min: '{string_bst.get_min()}', Max: '{string_bst.get_max()}'")
    print(f"   Search for 'banana': {string_bst.search('banana')}")
    print(f"   Delete 'cherry': {string_bst.delete('cherry')}")
    print(f"   Inorder after delete: {string_bst.inorder_traversal()}")
    
    # Edge cases
    print("\n" + "=" * 60)
    print("Edge Cases")
    print("=" * 60)
    
    empty_bst: BST[int] = BST()
    print(f"\nEmpty tree operations:")
    print(f"   Is empty? {empty_bst.is_empty()}")
    print(f"   Get min: {empty_bst.get_min()}")
    print(f"   Get max: {empty_bst.get_max()}")
    print(f"   Get height: {empty_bst.get_height()}")
    print(f"   Delete from empty: {empty_bst.delete(100)}")
    
    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)

        
