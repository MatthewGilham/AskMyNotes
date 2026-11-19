// Hide reserved assistant citation tokens, including a trailing stream prefix.
// Mirrors chats/citation_markers.py; both use the same regression examples.
const opening = "\ue200cite\ue202";

export function withoutCitationMarkers(text: string): string {
  text = text.replace(/\ue200cite\ue202[^\ue201]*(?:\ue201|$)/g, "");
  for (let length = opening.length - 1; length > 0; length--) {
    if (text.endsWith(opening.slice(0, length))) return text.slice(0, -length);
  }
  return text;
}
