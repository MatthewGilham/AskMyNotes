// Draws a chart from the model's small JSON description (see chartSpec.ts), in
// the app's colours. Hovering or focusing the chart (Tab, then the arrow keys)
// shows each value, and a table of the same data is there for screen readers.
// A description that doesn't check out shows its JSON with a muted note.
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatValue, parseChart, type ChartSpec } from "./chartSpec";
import styles from "./Chart.module.css";

// Every colour is a design token, so charts follow the colour theme. The series
// colours leave out red, amber and the web blue on purpose: the app keeps them
// for "Beyond your notes", errors and "From the web".
export const PALETTE = [1, 2, 3, 4, 5, 6].map(
  (series) => `var(--chart-${series})`,
);
const AXIS = "var(--color-faint)";
const GRID = "var(--color-hairline-strong)";
const TEXT = "var(--color-muted)";

export function Chart({ json }: { json: string }) {
  const result = parseChart(json);
  if (!result.ok) {
    return (
      <div className={styles.failed} data-no-quote>
        <pre>{json}</pre>
        <div className={styles.note}>
          Couldn't draw this chart: {result.reason}.
        </div>
      </div>
    );
  }
  return <DrawnChart spec={result.spec} />;
}

function DrawnChart({ spec }: { spec: ChartSpec }) {
  const show = (value: number) =>
    formatValue(value, spec.format, spec.currency);
  const tooltip = (
    <Tooltip
      formatter={(value) => show(Number(value))}
      contentStyle={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border-strong)",
        borderRadius: 8,
        color: "var(--color-text)",
      }}
      labelStyle={{ color: TEXT }}
      itemStyle={{ color: "var(--color-text)" }}
    />
  );
  const axes = (
    <>
      <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
      <XAxis
        dataKey="x"
        stroke={AXIS}
        tick={{ fill: TEXT, fontSize: 12 }}
        label={
          spec.xLabel
            ? {
                value: spec.xLabel,
                position: "insideBottom",
                offset: -4,
                fill: TEXT,
              }
            : undefined
        }
        height={spec.xLabel ? 48 : 30}
      />
      <YAxis
        stroke={AXIS}
        tick={{ fill: TEXT, fontSize: 12 }}
        tickFormatter={(value) => show(Number(value))}
        width={72}
        label={
          spec.yLabel
            ? {
                value: spec.yLabel,
                angle: -90,
                position: "insideLeft",
                fill: TEXT,
              }
            : undefined
        }
      />
      {tooltip}
      {spec.series.length > 1 && <Legend wrapperStyle={{ color: TEXT }} />}
    </>
  );

  return (
    <figure className={styles.chart} data-no-quote>
      <figcaption className={styles.title}>{spec.title}</figcaption>
      <div
        className={styles.plot}
        aria-label={`${spec.type} chart: ${spec.title}`}
      >
        <ResponsiveContainer width="100%" height={320}>
          {spec.type === "line" ? (
            <LineChart
              data={spec.data}
              margin={{ top: 8, right: 16, bottom: 12, left: 4 }}
            >
              {axes}
              {spec.series.map((name, index) => (
                <Line
                  key={name}
                  type="monotone"
                  dataKey={name}
                  stroke={PALETTE[index % PALETTE.length]}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          ) : spec.type === "bar" ? (
            <BarChart
              data={spec.data}
              margin={{ top: 8, right: 16, bottom: 12, left: 4 }}
            >
              {axes}
              {spec.series.map((name, index) => (
                <Bar
                  key={name}
                  dataKey={name}
                  fill={PALETTE[index % PALETTE.length]}
                  radius={[3, 3, 0, 0]}
                  isAnimationActive={false}
                />
              ))}
            </BarChart>
          ) : (
            <PieChart>
              <Pie
                data={spec.data}
                dataKey={spec.series[0]}
                nameKey="x"
                outerRadius={110}
                stroke="var(--color-base)"
                isAnimationActive={false}
                label={({ name }) => String(name)}
              >
                {spec.data.map((_, index) => (
                  <Cell key={index} fill={PALETTE[index % PALETTE.length]} />
                ))}
              </Pie>
              {tooltip}
            </PieChart>
          )}
        </ResponsiveContainer>
      </div>
      <table className={styles.dataTable}>
        <caption>{spec.title}</caption>
        <thead>
          <tr>
            <th>{spec.xLabel ?? "x"}</th>
            {spec.series.map((name) => (
              <th key={name}>{name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {spec.data.map((row, index) => (
            <tr key={index}>
              <td>{row.x}</td>
              {spec.series.map((name) => (
                <td key={name}>{show(Number(row[name]))}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
