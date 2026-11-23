// The program's canvas: each step a card, the arrows its `next`. Drag a kind of step from the palette onto it, draw an
// arrow from a step's foot to another's head to say where it goes next, move a card to place it, select one and press
// Delete (or Delete step on the right) to take it away. The right rail edits the selected step. What the canvas holds
// is reported up as the steps (`flow`); saving it is the page's.
import { createContext, memo, useCallback, useContext, useEffect, useMemo, useState, type DragEvent, type ReactNode } from 'react';
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge,
  type EdgeChangeset,
  type Node,
  type NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { Bot } from '@/api/bots';
import type { Program, ProgramRun, Step, StepKind } from '@/api/programs';
import { BotCat } from '../shell/bits';
import { botOf, useToolName } from './useStepBits';
import { connect, disconnect, edgesOf, forks, KINDS, newStep, removeStep, renameStep, toFlow, toNodes, updateStep, type StepData, type StepEdge } from './flow';
import { StepEditor } from './StepEditor';
import { KIND, stepTitle } from './words';

type FlowNode = Node<StepData, StepKind>;
/** A card's size, given so the canvas can draw it before it has measured it. */
const CARD = { width: 248, height: 112 };
const DRAG = 'application/x-glyphh-step';

/** What every card reads besides its step: the program's bots, its first step, and where the run being followed is. */
type Info = { bots: Bot[]; programBot: string | null; first: string | null; now: string | null; done: Set<string>; failed: string | null };
const CanvasInfo = createContext<Info>({ bots: [], programBot: null, first: null, now: null, done: new Set(), failed: null });

const StepCard = memo(function StepCard({ id, data, selected }: NodeProps<FlowNode>) {
  const info = useContext(CanvasInfo);
  const step = data.step;
  const kind = KIND[step.kind];
  const bot = botOf(step, info.programBot, info.bots);
  const tool = useToolName(step, bot?.slug ?? null);
  const now = info.now === id;
  const done = info.done.has(id) && !now;
  const failed = info.failed === id;
  const map = forks(step.kind) && step.next && typeof step.next === 'object' ? Object.keys(step.next) : [];
  const detail =
    step.kind === 'tool'
      ? tool
        ? tool.app
        : step.tool
          ? 'An action'
          : 'No action chosen yet'
      : step.kind === 'code'
        ? 'Runs on a rrotor'
        : step.kind === 'ask'
          ? (step.options ?? []).join(' · ') || 'Free answer'
          : step.kind === 'branch'
            ? map.join(' · ')
            : '';
  return (
    <div
      className={`stepnode k-${step.kind}${selected ? ' sel' : ''}${now ? ' now' : ''}${done ? ' done' : ''}${failed ? ' bad' : ''}`}
      role="group"
      aria-label={`${kind.tag}: ${stepTitle(step, tool)}`}
      data-step={id}
      aria-current={now ? 'step' : undefined}
    >
      <Handle type="target" position={Position.Top} className="sn-in" />
      <div className="sn-head">
        <span className="sn-mark" aria-hidden>
          {kind.mark}
        </span>
        <span className="sn-tag">{kind.tag}</span>
        <span className="spacer" />
        {info.first === id && <span className="sn-flag">Starts here</span>}
        {now && <span className="sn-flag hot">Now</span>}
        {done && (
          <span className="sn-flag" title="Done in this run">
            ✓ Done
          </span>
        )}
        {failed && <span className="sn-flag hot">Stopped</span>}
      </div>
      <b className="sn-title">{stepTitle(step, tool)}</b>
      <div className="sn-foot">
        <span className="sn-who" title={bot ? `${bot.name} does it` : 'The program’s bot does it'}>
          {bot ? <BotCat look={bot.look} mascot={bot.mascot} size={18} /> : <i className="sn-nocat" />}
          {bot?.name ?? 'Its bot'}
        </span>
        {detail && <span className="sn-detail">{detail}</span>}
      </div>
      <Handle type="source" position={Position.Bottom} className="sn-out" />
    </div>
  );
});

const nodeTypes = { tool: StepCard, bot: StepCard, ask: StepCard, branch: StepCard, code: StepCard };

const sized = (nodes: ReturnType<typeof toNodes>): FlowNode[] => nodes.map((n) => ({ ...n, initialWidth: CARD.width, initialHeight: CARD.height }));

type Props = {
  program: Program;
  bots: Bot[];
  /** The run being followed, to light its step. */
  run: ProgramRun | null;
  /** The steps as they stand on the canvas, after each change. */
  onChange: (steps: Step[]) => void;
  /** What the right rail shows while no step is selected: the program's own settings. */
  aside: ReactNode;
};

function Board({ program, bots, run, onChange, aside }: Props) {
  const flow = useReactFlow<FlowNode, Edge>();
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode>(sized(toNodes(program.flow)));
  const [edgePick, setEdgePick] = useState<string | null>(null);
  const steps = useMemo(() => toFlow(nodes), [nodes]);
  const selected = nodes.find((n) => n.selected)?.id ?? null;
  const step = selected ? steps.find((s) => s.id === selected) : undefined;

  useEffect(() => onChange(steps), [steps, onChange]);

  /** A change to the steps, made on the canvas's nodes: each keeps its place, size and selection (a renamed one too). */
  const edit = useCallback(
    (fn: (steps: Step[]) => Step[], renamed?: [string, string], pick?: string) =>
      setNodes((held) => {
        const byId = new Map(held.map((n) => [n.id, n]));
        return sized(toNodes(fn(toFlow(held)))).map((n) => {
          const old = byId.get(n.id) ?? (renamed && n.id === renamed[1] ? byId.get(renamed[0]) : undefined);
          const chosen = pick === undefined ? old?.selected : n.id === pick;
          return old ? { ...old, id: n.id, type: n.type, data: n.data, position: n.position, selected: chosen } : { ...n, selected: chosen };
        });
      }),
    [setNodes],
  );

  const edges = useMemo(() => {
    const done = new Set(Object.keys(run?.outputs ?? {}));
    return edgesOf(steps).map(
      (e: StepEdge): Edge => ({
        ...e,
        type: 'smoothstep',
        selected: e.id === edgePick,
        animated: Boolean(run && done.has(e.source) && (run.at === e.target || done.has(e.target))),
        markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: e.id === edgePick ? '#ffffff' : '#a6a6a6' },
        className: e.label ? 'fork' : undefined,
        labelBgPadding: [6, 3],
        labelBgBorderRadius: 999,
      }),
    );
  }, [steps, edgePick, run]);

  const onEdgesChange = useCallback(
    (changes: EdgeChangeset<Edge>) => {
      for (const c of changes) {
        if (c.type === 'select') setEdgePick((was) => (c.selected ? c.id : was === c.id ? null : was));
        if (c.type === 'remove') {
          const gone = edgesOf(toFlow(nodes)).find((e) => e.id === c.id);
          if (gone) edit((s) => disconnect(s, gone));
          setEdgePick(null);
        }
      }
    },
    [nodes, edit],
  );

  const add = (kind: StepKind, at?: [number, number]) => {
    const place: [number, number] = at ?? (() => {
      const last = nodes.at(-1);
      return last ? [last.position.x, last.position.y + 160] : [0, 0];
    })();
    // The new step is selected, so its fields open on the right.
    const made = newStep(kind, steps, place);
    edit((s) => [...s, made], undefined, made.id);
  };

  const drop = (e: DragEvent) => {
    e.preventDefault();
    const kind = e.dataTransfer.getData(DRAG) as StepKind;
    if (!KINDS.includes(kind)) return;
    const p = flow.screenToFlowPosition({ x: e.clientX, y: e.clientY });
    add(kind, [p.x - CARD.width / 2, p.y - 24]);
  };

  const info = useMemo<Info>(() => {
    const going = run && ['queued', 'running', 'dispatched', 'needs_input'].includes(run.status);
    return {
      bots,
      programBot: program.bot,
      first: steps[0]?.id ?? null,
      now: going ? run.at : null,
      done: new Set(Object.keys(run?.outputs ?? {})),
      failed: run?.status === 'failed' ? run.at : null,
    };
  }, [bots, program.bot, steps, run]);

  return (
    <CanvasInfo.Provider value={info}>
      <div className="pcanvas-row">
        <div className="pcanvas" onDragOver={(e) => (e.preventDefault(), (e.dataTransfer.dropEffect = 'move'))} onDrop={drop}>
          <div className="palette" role="toolbar" aria-label="Add a step">
            <div className="palette-label">Add a step</div>
            {KINDS.map((k) => (
              <button
                key={k}
                type="button"
                className={`palette-item k-${k}`}
                draggable
                title={`${KIND[k].hint} Drag it onto the canvas, or click to add it under the last step.`}
                onDragStart={(e) => {
                  e.dataTransfer.setData(DRAG, k);
                  e.dataTransfer.effectAllowed = 'move';
                }}
                onClick={() => add(k)}
              >
                <span className="sn-mark" aria-hidden>
                  {KIND[k].mark}
                </span>
                {KIND[k].label}
              </button>
            ))}
          </div>
          {nodes.length === 0 && (
            <div className="pcanvas-empty">
              <b>No steps yet</b>
              <span>Drag a step from the left onto the canvas. The first step runs first.</span>
            </div>
          )}
          <ReactFlow<FlowNode, Edge>
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={(c: Connection) => edit((s) => connect(s, c.source, c.target))}
            onNodesDelete={(gone) => edit((s) => gone.reduce((left, n) => removeStep(left, n.id), s))}
            deleteKeyCode={['Backspace', 'Delete']}
            forceColorMode="dark"
            fitView
            fitViewOptions={{ padding: 0.25, maxZoom: 1 }}
            minZoom={0.3}
            maxZoom={1.6}
            snapToGrid
            snapGrid={[8, 8]}
            proOptions={{ hideAttribution: true }}
            aria-label="Program canvas"
          >
            <Background variant={BackgroundVariant.Dots} gap={22} size={1.2} color="#2e2e2e" />
            <Controls showInteractive={false} position="bottom-left" />
            <MiniMap pannable zoomable nodeColor="#1c1c1c" nodeStrokeColor="#5a5a5a" maskColor="rgba(0,0,0,0.72)" bgColor="#0d0d0d" position="bottom-right" />
          </ReactFlow>
        </div>
        {step ? (
          <StepEditor
            key={step.id}
            step={step}
            steps={steps}
            program={program}
            bots={bots}
            onChange={(patch) => edit((s) => updateStep(s, step.id, patch))}
            onRename={(to) => edit((s) => renameStep(s, step.id, to), [step.id, to], to)}
            onDelete={() => edit((s) => removeStep(s, step.id))}
            onClose={() => setNodes((held) => held.map((n) => ({ ...n, selected: false })))}
          />
        ) : (
          aside
        )}
      </div>
    </CanvasInfo.Provider>
  );
}

export function Canvas(props: Props) {
  return (
    <ReactFlowProvider>
      <Board {...props} />
    </ReactFlowProvider>
  );
}
