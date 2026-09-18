import type { Folder } from "../api/types";

interface Props {
  folders: Folder[];
  selectedId: string | null;
  onSelect: (folder: Folder) => void;
}

interface TreeNode extends Folder {
  children: TreeNode[];
}

function buildTree(folders: Folder[]): TreeNode[] {
  const byId = new Map<string, TreeNode>(folders.map((f) => [f.id, { ...f, children: [] }]));
  const roots: TreeNode[] = [];
  for (const node of byId.values()) {
    if (node.parent_id && byId.has(node.parent_id)) {
      byId.get(node.parent_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  }
  return roots;
}

function Node({ node, selectedId, onSelect }: { node: TreeNode; selectedId: string | null; onSelect: (f: Folder) => void }) {
  return (
    <div>
      <div className={`node ${selectedId === node.id ? "selected" : ""}`} onClick={() => onSelect(node)}>
        📁 {node.name}
      </div>
      {node.children.length > 0 && (
        <div className="children">
          {node.children.map((child) => (
            <Node key={child.id} node={child} selectedId={selectedId} onSelect={onSelect} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function FolderTree({ folders, selectedId, onSelect }: Props) {
  const tree = buildTree(folders);
  return (
    <div className="folder-tree">
      {tree.map((node) => (
        <Node key={node.id} node={node} selectedId={selectedId} onSelect={onSelect} />
      ))}
      {folders.length === 0 && <div style={{ color: "var(--muted)" }}>No folders yet.</div>}
    </div>
  );
}
