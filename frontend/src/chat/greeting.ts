// The new chat greeting, which changes with the day: "Happy Tuesday, Matt".

/** The greeting as the two lines it is set on: "Happy Tuesday," and "Matt". */
export function greetingLines(
  name: string,
  today: Date = new Date(),
): [string, string] {
  const weekday = today.toLocaleDateString("en-GB", { weekday: "long" });
  return [`Happy ${weekday},`, name];
}
