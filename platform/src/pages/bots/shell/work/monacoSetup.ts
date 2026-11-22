// Monaco as the Glyphh Bot app sets it up (glyphh-bot src/renderer/src/monaco.ts, copied): its workers and the
// black-and-white `glyphh` theme. One change: the package is named by its own files (its whole editor, then its API),
// which is what the bare name resolves to, so every tool that reads this file finds it. It is loaded only when the
// Editor or the Diff first opens.
import 'monaco-editor/esm/vs/editor/editor.main.js'
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api'
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import cssWorker from 'monaco-editor/esm/vs/language/css/css.worker?worker'
import htmlWorker from 'monaco-editor/esm/vs/language/html/html.worker?worker'
import jsonWorker from 'monaco-editor/esm/vs/language/json/json.worker?worker'
import tsWorker from 'monaco-editor/esm/vs/language/typescript/ts.worker?worker'

self.MonacoEnvironment = {
  getWorker(_id: string, label: string): Worker {
    if (label === 'json') return new jsonWorker()
    if (label === 'css' || label === 'scss' || label === 'less') return new cssWorker()
    if (label === 'html' || label === 'handlebars' || label === 'razor') return new htmlWorker()
    if (label === 'typescript' || label === 'javascript') return new tsWorker()
    return new editorWorker()
  }
}

// glyphh.ai's black and white: weight and grey carry the syntax, not colour.
monaco.editor.defineTheme('glyphh', {
  base: 'vs-dark',
  inherit: true,
  rules: [
    { token: '', foreground: 'eaeaea' },
    { token: 'comment', foreground: '9a9a9a', fontStyle: 'italic' },
    { token: 'keyword', foreground: 'ffffff', fontStyle: 'bold' },
    { token: 'string', foreground: 'c8c8c8' },
    { token: 'number', foreground: 'ffffff' },
    { token: 'type', foreground: 'ffffff', fontStyle: 'underline' },
    { token: 'tag', foreground: 'ffffff', fontStyle: 'bold' },
    { token: 'attribute.name', foreground: 'c8c8c8' },
    { token: 'delimiter', foreground: 'a6a6a6' }
  ],
  colors: {
    'editor.background': '#000000',
    'editor.foreground': '#eaeaea',
    'editor.lineHighlightBackground': '#0d0d0d',
    'editor.lineHighlightBorder': '#141414',
    'editorLineNumber.foreground': '#999999',
    'editorBracketHighlight.foreground1': '#c8c8c8',
    'editorBracketHighlight.foreground2': '#c8c8c8',
    'editorBracketHighlight.foreground3': '#c8c8c8',
    'editorBracketHighlight.foreground4': '#c8c8c8',
    'editorBracketHighlight.foreground5': '#c8c8c8',
    'editorBracketHighlight.foreground6': '#c8c8c8',
    'editorBracketMatch.background': '#ffffff1a',
    'editorBracketMatch.border': '#5a5a5a',
    'editorLineNumber.activeForeground': '#c8c8c8',
    'editorCursor.foreground': '#ffffff',
    'editor.selectionBackground': '#ffffff33',
    'editor.inactiveSelectionBackground': '#ffffff1a',
    'editorIndentGuide.background1': '#242424',
    'editorWidget.background': '#0d0d0d',
    'editorWidget.border': '#5a5a5a',
    'focusBorder': '#c68cff',
    'scrollbarSlider.background': '#ffffff22',
    'scrollbarSlider.hoverBackground': '#ffffff44',
    'minimap.background': '#000000',
    // The platform's addition, for the Diff panel's Monaco diff: black and white as the app's own diff lines are
    // (an added line lit, a removed one dimmed), never red and green.
    'diffEditor.insertedLineBackground': '#ffffff1a',
    'diffEditor.insertedTextBackground': '#ffffff24',
    'diffEditor.removedLineBackground': '#ffffff08',
    'diffEditor.removedTextBackground': '#ffffff12',
    'diffEditorGutter.insertedLineBackground': '#ffffff1a',
    'diffEditorGutter.removedLineBackground': '#ffffff08',
    'diffEditor.diagonalFill': '#24242400',
    'diffEditor.unchangedRegionBackground': '#0d0d0d',
    'diffEditor.unchangedRegionForeground': '#999999'
  }
})

export { monaco }
