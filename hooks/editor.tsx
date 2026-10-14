import type { ClientKeyEvent, ClientSurface } from 'claude-code'

type Props = { path: string; text: string }
type State = { lines: string[]; row: number; col: number; top: number; left: number }

/**
 * A plain text editor: click to place the cursor (the click also gives it the
 * keys; Esc hands them back), type, arrows, return, backspace, delete, tab,
 * page up/down, ctrl+s to save. Every change posts the whole text, so a post
 * the frame folds away loses nothing.
 */
export default function Editor(props: Props, surface: ClientSurface<State>) {
  const { Box, Text } = surface.elements
  const state: State = surface.state ?? { lines: props.text.split('\n'), row: 0, col: 0, top: 0, left: 0 }
  const lines = state.lines
  const gutter = String(lines.length).length + 1
  const height = Math.max(1, surface.rows)
  const width = Math.max(1, surface.columns - gutter)

  const commit = (next: State, kind: 'edit' | 'save' | 'move') => {
    // Keep the cursor in view.
    if (next.row < next.top) next.top = next.row
    if (next.row >= next.top + height) next.top = next.row - height + 1
    if (next.col < next.left) next.left = next.col
    if (next.col >= next.left + width) next.left = next.col - width + 1
    surface.setState(next)
    if (kind !== 'move') surface.post({ kind, path: props.path, text: next.lines.join('\n') })
  }

  surface.onPointer(e => {
    if (e.type !== 'down') return
    const row = Math.min(lines.length - 1, state.top + e.y)
    const col = Math.max(0, Math.min((lines[row] ?? '').length, state.left + e.x - gutter))
    commit({ ...state, row, col }, 'move')
  })

  surface.onKey((e: ClientKeyEvent) => {
    const ls = [...lines]
    let { row, col } = state
    const line = ls[row] ?? ''
    const at = (r: number) => ls[r] ?? ''
    if (e.ctrl && e.key === 's') return commit({ ...state }, 'save')
    switch (e.key) {
      case 'up': row = Math.max(0, row - 1); col = Math.min(col, at(row).length); return commit({ ...state, row, col }, 'move')
      case 'down': row = Math.min(ls.length - 1, row + 1); col = Math.min(col, at(row).length); return commit({ ...state, row, col }, 'move')
      case 'left':
        if (col > 0) col -= 1
        else if (row > 0) { row -= 1; col = at(row).length }
        return commit({ ...state, row, col }, 'move')
      case 'right':
        if (col < line.length) col += 1
        else if (row < ls.length - 1) { row += 1; col = 0 }
        return commit({ ...state, row, col }, 'move')
      case 'home': return commit({ ...state, col: 0 }, 'move')
      case 'end': return commit({ ...state, col: line.length }, 'move')
      case 'pageup': row = Math.max(0, row - height); return commit({ ...state, row, col: Math.min(col, at(row).length) }, 'move')
      case 'pagedown': row = Math.min(ls.length - 1, row + height); return commit({ ...state, row, col: Math.min(col, at(row).length) }, 'move')
      case 'return':
        ls.splice(row, 1, line.slice(0, col), line.slice(col))
        return commit({ ...state, lines: ls, row: row + 1, col: 0 }, 'edit')
      case 'backspace':
        if (col > 0) {
          ls[row] = line.slice(0, col - 1) + line.slice(col)
          return commit({ ...state, lines: ls, col: col - 1 }, 'edit')
        }
        if (row === 0) return
        col = at(row - 1).length
        ls.splice(row - 1, 2, at(row - 1) + line)
        return commit({ ...state, lines: ls, row: row - 1, col }, 'edit')
      case 'delete':
        if (col < line.length) ls[row] = line.slice(0, col) + line.slice(col + 1)
        else if (row < ls.length - 1) ls.splice(row, 2, line + at(row + 1))
        else return
        return commit({ ...state, lines: ls }, 'edit')
      case 'tab':
        ls[row] = line.slice(0, col) + '  ' + line.slice(col)
        return commit({ ...state, lines: ls, col: col + 2 }, 'edit')
    }
    if (e.key.length === 1 && !e.ctrl && !e.meta) {
      ls[row] = line.slice(0, col) + e.key + line.slice(col)
      return commit({ ...state, lines: ls, col: col + 1 }, 'edit')
    }
  })

  const shown = lines.slice(state.top, state.top + height)
  return (
    <Box flexDirection="column" width={surface.columns} height={height}>
      {shown.map((text, i) => {
        const r = state.top + i
        const visible = text.slice(state.left, state.left + width)
        const num = <Text dimColor>{String(r + 1).padStart(gutter - 1)} </Text>
        if (r !== state.row) return <Box key={`l${r}`}>{num}<Text>{visible || ' '}</Text></Box>
        const c = state.col - state.left
        return (
          <Box key={`l${r}`}>
            {num}
            <Text>{visible.slice(0, c)}</Text>
            <Text inverse>{visible[c] ?? ' '}</Text>
            <Text>{visible.slice(c + 1)}</Text>
          </Box>
        )
      })}
    </Box>
  )
}
