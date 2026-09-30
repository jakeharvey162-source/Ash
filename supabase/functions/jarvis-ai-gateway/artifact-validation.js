export function completeHTMLArtifact(value) {
  let html=String(value||'').replace(/<think>[\s\S]*?<\/think>/gi,'').trim();
  const fence=html.match(/^```(?:html)?\s*\n([\s\S]*?)\n```$/i);
  if(fence)html=fence[1].trim();
  if(html.length>120000||!/^<!doctype html>/i.test(html)||!/<html\b/i.test(html)||!/<head\b/i.test(html)||!/<body\b/i.test(html)||!/<\/body>/i.test(html)||!/<\/html>\s*$/i.test(html))throw new Error('incomplete_html_artifact');
  return html;
}
