import { type Edge, type Node } from '@xyflow/react';
import { applyFocusOpacity } from '../CypherGraph';

const EDGE_COLOR = '#aaaaaa';

function makeNode(id: string, style?: React.CSSProperties): Node {
  return {
    id,
    position: { x: 0, y: 0 },
    data: {},
    style,
  };
}

function makeEdge(
  id: string,
  source: string,
  target: string,
  label?: string,
): Edge {
  return {
    id,
    source,
    target,
    label,
    style: { stroke: EDGE_COLOR, strokeWidth: 1.5 },
    labelStyle: { fontSize: 10 },
    labelBgStyle: {},
    data: {},
  };
}

const NODES = [
  makeNode('a'),
  makeNode('b'),
  makeNode('c'),
  makeNode('d'),
];

// a → b, a → c, d (isolated)
const EDGES = [
  makeEdge('edge-0', 'a', 'b', 'REL_AB'),
  makeEdge('edge-1', 'a', 'c', 'REL_AC'),
  makeEdge('edge-2', 'c', 'd', 'REL_CD'),
];

describe('applyFocusOpacity', () => {
  describe('focusedId = null (clear focus)', () => {
    const result = applyFocusOpacity(NODES, EDGES, null, EDGE_COLOR);

    it('sets all nodes to full opacity', () => {
      for (const n of result.nodes) {
        expect(n.style?.opacity).toBe(1);
      }
    });

    it('sets all edges to full opacity', () => {
      for (const e of result.edges) {
        expect(e.style?.opacity).toBe(1);
      }
    });

    it('sets all edge labels and label backgrounds to full opacity', () => {
      for (const e of result.edges) {
        expect(e.labelStyle?.opacity).toBe(1);
        expect(e.labelBgStyle?.opacity).toBe(1);
      }
    });

    it('includes a transition on all nodes', () => {
      for (const n of result.nodes) {
        expect(n.style?.transition).toBe('opacity 0.2s');
      }
    });

    it('includes a transition on all edges', () => {
      for (const e of result.edges) {
        expect(e.style?.transition).toBe('opacity 0.2s');
      }
    });
  });

  describe('node focused ("a" — hub with two outgoing edges)', () => {
    const result = applyFocusOpacity(NODES, EDGES, 'a', EDGE_COLOR);

    it('keeps the focused node at full opacity', () => {
      const node = result.nodes.find(n => n.id === 'a')!;
      expect(node.style?.opacity).toBe(1);
    });

    it('keeps direct neighbors (b, c) at full opacity', () => {
      const b = result.nodes.find(n => n.id === 'b')!;
      const c = result.nodes.find(n => n.id === 'c')!;
      expect(b.style?.opacity).toBe(1);
      expect(c.style?.opacity).toBe(1);
    });

    it('dims nodes not connected to focused node (d)', () => {
      const d = result.nodes.find(n => n.id === 'd')!;
      expect(d.style?.opacity).toBe(0.15);
    });

    it('keeps edges directly connected to focused node at full opacity', () => {
      const e0 = result.edges.find(e => e.id === 'edge-0')!;
      const e1 = result.edges.find(e => e.id === 'edge-1')!;
      expect(e0.style?.opacity).toBe(1);
      expect(e1.style?.opacity).toBe(1);
    });

    it('dims edges not connected to focused node', () => {
      const e2 = result.edges.find(e => e.id === 'edge-2')!;
      expect(e2.style?.opacity).toBe(0.15);
    });

    it('dims label and label background of non-connected edges', () => {
      const e2 = result.edges.find(e => e.id === 'edge-2')!;
      expect(e2.labelStyle?.opacity).toBe(0.15);
      expect(e2.labelBgStyle?.opacity).toBe(0.15);
    });

    it('keeps label and label background of connected edges at full opacity', () => {
      const e0 = result.edges.find(e => e.id === 'edge-0')!;
      expect(e0.labelStyle?.opacity).toBe(1);
      expect(e0.labelBgStyle?.opacity).toBe(1);
    });
  });

  describe('node focused ("e" — truly isolated node with no edges)', () => {
    // Use a separate graph that includes an isolated node 'e'
    const nodesWithIsolated = [...NODES, makeNode('e')];
    const result = applyFocusOpacity(nodesWithIsolated, EDGES, 'e', EDGE_COLOR);

    it('keeps isolated focused node at full opacity', () => {
      const e = result.nodes.find(n => n.id === 'e')!;
      expect(e.style?.opacity).toBe(1);
    });

    it('dims all other nodes', () => {
      for (const n of result.nodes.filter(n => n.id !== 'e')) {
        expect(n.style?.opacity).toBe(0.15);
      }
    });

    it('dims all edges since none are connected to the isolated node', () => {
      for (const e of result.edges) {
        expect(e.style?.opacity).toBe(0.15);
      }
    });
  });

  describe('edge focused ("edge-2": c → d)', () => {
    const result = applyFocusOpacity(NODES, EDGES, 'edge-2', EDGE_COLOR);

    it('keeps the source node (c) at full opacity', () => {
      const c = result.nodes.find(n => n.id === 'c')!;
      expect(c.style?.opacity).toBe(1);
    });

    it('keeps the target node (d) at full opacity', () => {
      const d = result.nodes.find(n => n.id === 'd')!;
      expect(d.style?.opacity).toBe(1);
    });

    it('dims nodes not part of the focused edge', () => {
      const a = result.nodes.find(n => n.id === 'a')!;
      const b = result.nodes.find(n => n.id === 'b')!;
      expect(a.style?.opacity).toBe(0.15);
      expect(b.style?.opacity).toBe(0.15);
    });

    it('keeps the focused edge at full opacity', () => {
      const e2 = result.edges.find(e => e.id === 'edge-2')!;
      expect(e2.style?.opacity).toBe(1);
    });

    it('dims other edges', () => {
      const e0 = result.edges.find(e => e.id === 'edge-0')!;
      const e1 = result.edges.find(e => e.id === 'edge-1')!;
      expect(e0.style?.opacity).toBe(0.15);
      expect(e1.style?.opacity).toBe(0.15);
    });

    it('dims label and label background of non-focused edges', () => {
      const e0 = result.edges.find(e => e.id === 'edge-0')!;
      expect(e0.labelStyle?.opacity).toBe(0.15);
      expect(e0.labelBgStyle?.opacity).toBe(0.15);
    });

    it('keeps label and label background of focused edge at full opacity', () => {
      const e2 = result.edges.find(e => e.id === 'edge-2')!;
      expect(e2.labelStyle?.opacity).toBe(1);
      expect(e2.labelBgStyle?.opacity).toBe(1);
    });
  });

  describe('unknown focusedId (not a node or edge id)', () => {
    const result = applyFocusOpacity(NODES, EDGES, 'does-not-exist', EDGE_COLOR);

    it('returns the original node array unchanged', () => {
      expect(result.nodes).toBe(NODES);
    });

    it('returns the original edge array unchanged', () => {
      expect(result.edges).toBe(EDGES);
    });
  });

  describe('preserves existing style properties', () => {
    it('preserves stroke color on edges when clearing focus', () => {
      const result = applyFocusOpacity(NODES, EDGES, null, EDGE_COLOR);
      for (const e of result.edges) {
        expect(e.style?.stroke).toBe(EDGE_COLOR);
      }
    });

    it('preserves strokeWidth on edges when applying node focus', () => {
      const result = applyFocusOpacity(NODES, EDGES, 'a', EDGE_COLOR);
      for (const e of result.edges) {
        expect(e.style?.strokeWidth).toBe(1.5);
      }
    });

    it('preserves existing node style properties when dimming', () => {
      const nodesWithStyle = [makeNode('x', { background: 'red' }), makeNode('y')];
      const result = applyFocusOpacity(nodesWithStyle, [], 'y', EDGE_COLOR);
      const x = result.nodes.find(n => n.id === 'x')!;
      expect(x.style?.background).toBe('red');
      expect(x.style?.opacity).toBe(0.15);
    });
  });
});
