import type { ClientSurface } from 'claude-code'

type Props = { axis: 'col' | 'row'; index: number; length: number; total: number }
type State = { drag?: number; start: number }

/**
 * A grid divider: a one-cell bar the person drags. Posts the drag as a
 * running delta in cells from where it started, so a post the frame folds
 * away loses nothing.
 */
export default function Divider(props: Props, surface: ClientSurface<State>) {
  const { Box, Text } = surface.elements
  const isCol = props.axis === 'col'

  surface.onPointer(e => {
    const at = isCol ? e.x : e.y
    const state = surface.state ?? { start: 0 }
    if (e.type === 'down' && e.button === 'left') {
      surface.setState({ drag: Date.now(), start: at })
    } else if ((e.type === 'move' || e.type === 'up') && state.drag !== undefined && (e.button || e.type === 'up')) {
      surface.post({
        kind: 'drag',
        axis: props.axis,
        index: props.index,
        drag: state.drag,
        delta: at - state.start,
        total: props.total,
        isEnd: e.type === 'up',
      })
      if (e.type === 'up') surface.setState({ start: 0 })
    }
  })

  const isDragging = surface.state?.drag !== undefined
  if (isCol) {
    return (
      <Box flexDirection="column" width={1} height={props.length}>
        <Text color={isDragging ? 'magenta' : undefined} dimColor={!isDragging}>
          {Array.from({ length: props.length }, () => '│').join('\n')}
        </Text>
      </Box>
    )
  }
  return (
    <Box width={props.length} height={1}>
      <Text color={isDragging ? 'magenta' : undefined} dimColor={!isDragging}>
        {'─'.repeat(props.length)}
      </Text>
    </Box>
  )
}
