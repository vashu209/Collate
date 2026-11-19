import { FlatRow, TreeNode } from "../types";

export interface TreeSourceItem {
  key: number;
  path: string;
  category?: string;
  confidence?: number;
  rationale?: string;
  status?: string;
  hasConflict?: boolean;
  conflictType?: string;
  conflictMessage?: string;
}

/**
 * Normalizes a path string to forward slashes without trailing slashes.
 */
export function normalizePath(p: string): string {
  const norm = p.replace(/\\/g, "/");
  return norm.endsWith("/") && norm.length > 1 ? norm.slice(0, -1) : norm;
}

/**
 * Builds a hierarchical tree from a flat list of items with paths.
 */
export function buildTreeFromItems(items: TreeSourceItem[]): TreeNode[] {
  interface MutableNode {
    id: string;
    name: string;
    path: string;
    isFolder: boolean;
    itemKey?: number;
    category?: string;
    confidence?: number;
    rationale?: string;
    status?: string;
    hasConflict?: boolean;
    conflictType?: string;
    conflictMessage?: string;
    children: Map<string, MutableNode>;
    itemKeysSet: Set<number>;
  }

  const rootMap = new Map<string, MutableNode>();

  for (const item of items) {
    const cleanPath = normalizePath(item.path);
    const parts = cleanPath.split("/").filter(Boolean);
    if (parts.length === 0) continue;

    let currentMap = rootMap;
    let accumulatedPath = "";

    // Iterate through directories
    for (let i = 0; i < parts.length - 1; i++) {
      const part = parts[i];
      accumulatedPath = accumulatedPath ? `${accumulatedPath}/${part}` : part;
      const folderId = `dir:${accumulatedPath}`;

      let folderNode = currentMap.get(part);
      if (!folderNode) {
        folderNode = {
          id: folderId,
          name: part,
          path: accumulatedPath,
          isFolder: true,
          children: new Map(),
          itemKeysSet: new Set(),
        };
        currentMap.set(part, folderNode);
      }
      folderNode.itemKeysSet.add(item.key);
      currentMap = folderNode.children;
    }

    // Leaf file node
    const fileName = parts[parts.length - 1];
    accumulatedPath = accumulatedPath ? `${accumulatedPath}/${fileName}` : fileName;
    const fileNodeId = `file:${item.key}:${accumulatedPath}`;

    currentMap.set(fileName, {
      id: fileNodeId,
      name: fileName,
      path: accumulatedPath,
      isFolder: false,
      itemKey: item.key,
      category: item.category,
      confidence: item.confidence,
      rationale: item.rationale,
      status: item.status,
      hasConflict: item.hasConflict,
      conflictType: item.conflictType,
      conflictMessage: item.conflictMessage,
      children: new Map(),
      itemKeysSet: new Set([item.key]),
    });
  }

  // Convert mutable tree to immutable TreeNode array
  function convert(map: Map<string, MutableNode>): TreeNode[] {
    const list: TreeNode[] = [];
    for (const [, node] of map.entries()) {
      const children = convert(node.children);
      // Sort: folders first, then files alphabetically
      children.sort((a, b) => {
        if (a.isFolder && !b.isFolder) return -1;
        if (!a.isFolder && b.isFolder) return 1;
        return a.name.localeCompare(b.name);
      });

      list.push({
        id: node.id,
        name: node.name,
        path: node.path,
        isFolder: node.isFolder,
        itemKey: node.itemKey,
        category: node.category,
        confidence: node.confidence,
        rationale: node.rationale,
        status: node.status,
        hasConflict: node.hasConflict,
        conflictType: node.conflictType,
        conflictMessage: node.conflictMessage,
        children,
        itemKeys: Array.from(node.itemKeysSet),
      });
    }
    list.sort((a, b) => {
      if (a.isFolder && !b.isFolder) return -1;
      if (!a.isFolder && b.isFolder) return 1;
      return a.name.localeCompare(b.name);
    });
    return list;
  }

  return convert(rootMap);
}

/**
 * Flattens the tree into a 1D array of visible rows based on expanded folder IDs.
 */
export function flattenTree(
  nodes: TreeNode[],
  expandedIds: Set<string>,
  depth: number = 0
): FlatRow[] {
  const rows: FlatRow[] = [];

  for (const node of nodes) {
    const hasChildren = node.children.length > 0;
    const isExpanded = node.isFolder ? expandedIds.has(node.id) : false;

    rows.push({
      node,
      depth,
      isExpanded,
      hasChildren,
    });

    if (node.isFolder && isExpanded && hasChildren) {
      const childRows = flattenTree(node.children, expandedIds, depth + 1);
      for (let i = 0; i < childRows.length; i++) {
        rows.push(childRows[i]);
      }
    }
  }

  return rows;
}

/**
 * Collect all folder IDs from the tree (useful for 'Expand All').
 */
export function getAllFolderIds(nodes: TreeNode[]): Set<string> {
  const ids = new Set<string>();
  function walk(items: TreeNode[]) {
    for (const item of items) {
      if (item.isFolder) {
        ids.add(item.id);
        walk(item.children);
      }
    }
  }
  walk(nodes);
  return ids;
}
