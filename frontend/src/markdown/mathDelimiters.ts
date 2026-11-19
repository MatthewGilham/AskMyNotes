// Converts the model's maths delimiters into the ones remark-math reads.
//
// Finance answers are full of currency, so a lone "$" must never start an
// equation. The model is told to write maths as \( inline \) and
// \[ display \]. Here those become $$…$$, and single-dollar maths is switched
// off in the renderer, so "$5" always stays "$5".

const CODE_FENCE = /(```[\s\S]*?(?:```|$))/;

export function convertMathDelimiters(markdown: string): string {
  // Splitting on the fence pattern keeps code blocks at odd indexes, and
  // leaves them untouched: maths delimiters inside code are just code.
  return markdown
    .split(CODE_FENCE)
    .map((part, index) => (index % 2 === 1 ? part : convertOutsideCode(part)))
    .join("");
}

function convertOutsideCode(text: string): string {
  return text
    .replace(
      /\\\[([\s\S]+?)\\\]/g,
      (_, maths: string) => `\n$$\n${maths.trim()}\n$$\n`,
    )
    .replace(
      /\\\(([\s\S]+?)\\\)/g,
      (_, maths: string) => `$$${maths.trim()}$$`,
    );
}
