// The program as its file, program.py, to read and change. The canvas and the file are one program: saving the file
// is read back into the canvas from the server's answer. Monaco when it has loaded (the Editor panel's, in the
// glyphh theme); a plain text box until then.
import { useEffect, useRef, useState } from 'react';
import { loadMonaco } from '../shell/work/monaco';

export function CodeView({ source, onChange }: { source: string; onChange: (source: string) => void }) {
  const host = useRef<HTMLDivElement>(null);
  const said = useRef(onChange);
  said.current = onChange;
  const first = useRef(source);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let dead = false;
    let dispose = () => undefined as void;
    loadMonaco()
      .then((monaco) => {
        if (dead || !host.current) return;
        const editor = monaco.editor.create(host.current, {
          value: first.current,
          language: 'python',
          theme: 'glyphh',
          automaticLayout: true,
          fontSize: 13,
          fontFamily: '"JetBrains Mono Variable", "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace',
          minimap: { enabled: false },
          padding: { top: 12 },
          smoothScrolling: true,
          scrollBeyondLastLine: false,
          wordWrap: 'on',
        });
        editor.onDidChangeModelContent(() => said.current(editor.getValue()));
        dispose = () => {
          editor.getModel()?.dispose();
          editor.dispose();
        };
        setReady(true);
      })
      .catch(() => undefined);
    return () => {
      dead = true;
      dispose();
    };
  }, []);

  return (
    <div className="pcode">
      <div className="pcode-bar">
        <span className="pfile">program.py</span>
        <small>The canvas is the list of steps in this file. Everything else is the program’s own code.</small>
      </div>
      <div ref={host} className="pcode-ed" hidden={!ready} />
      {!ready && <textarea className="pcode-text" aria-label="program.py" spellCheck={false} value={source} onChange={(e) => onChange(e.target.value)} />}
    </div>
  );
}
