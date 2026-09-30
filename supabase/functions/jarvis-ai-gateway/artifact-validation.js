export function completeHTMLArtifact(value) {
  let html=String(value||'').replace(/<think>[\s\S]*?<\/think>/gi,'').trim();
  const fence=html.match(/^```(?:html)?\s*\n([\s\S]*?)\n```$/i);
  if(fence)html=fence[1].trim();
  if(html.length>120000||!/^<!doctype html>/i.test(html)||!/<html\b/i.test(html)||!/<head\b/i.test(html)||!/<body\b/i.test(html)||!/<\/body>/i.test(html)||!/<\/html>\s*$/i.test(html))throw new Error('incomplete_html_artifact');
  return html;
}

export function sourceArtifact(value) {
  let source=String(value||'').replace(/<think>[\s\S]*?<\/think>/gi,'').trim();
  const fence=source.match(/^```[^\n]*\n([\s\S]*?)\n```$/);if(fence)source=fence[1].trim();
  if(!source||source.length>120000||/^(?:sorry\b|i (?:am|cannot|can't|will)\b|offline python core|cloud intelligence|live web research is temporarily unavailable)/i.test(source))throw new Error('invalid_source_artifact');
  return source;
}
